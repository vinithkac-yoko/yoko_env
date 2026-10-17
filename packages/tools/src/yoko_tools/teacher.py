"""The teacher: for any state, the set of next actions that follow the plan (docs/adr/0007).

    expert(box, plan, recipes) -> list[Call] | None

reads only the state (the pattern, its landmarks), the plan and the provenance, so it can label any
state, including the ones after a mistake. It works in this order:

1. If off-plan actions left something behind, the acceptable set is the way back: undo (when the
   last action was the off-plan one), delete a leftover nothing depends on, or edit a wrong
   object's formula back (or to what the recipe requires).
2. Otherwise the active step is the first plan step that is not complete. Its acceptable set is
   every op of its recipe graph whose inputs exist and that is not done yet, in any order, plus the
   composite call for the whole step when composites are on.
3. When every step is complete, `done`.
4. When no recipe covers the active step: None, "no label".

An op is **done** when an on-plan object (provenance) stands for it, or when some object
reproduces its geometry exactly at the base size and at the other sizes. Equivalent constructions
therefore count. A step is complete when all its ops are done and its recipe's completion check
holds; once a later step has begun, the check is not asked again (later steps move things).

The function knows no recipe in particular: a recipe is a `Recipe` (yoko_tools.recipes).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from yoko_engine.evalcore import Evaluation
from yoko_engine.model import MeasurementSet, Obj, Pattern
from yoko_engine.pieces_edit import pieces_of, pieces_using
from yoko_engine.session import ActionMeta, PatternSession, Provenance
from yoko_engine.units import px_to_mm

from yoko_tools.plan import variable_name
from yoko_tools.recipes import (
    Completion,
    Op,
    Recipe,
    RecipeError,
    RecipeRegistry,
    StepContext,
    op_args,
)
from yoko_tools.runtime import Toolbox, ToolError

DONE_TOOL = "done"
APPLY_STEP = "apply_step"
TOLERANCE_MM = 0.001  # "exactly": node coordinates within 0.001 mm (Addendum 1 section 13)


@dataclass(frozen=True, slots=True)
class Call:
    """An action: a tool call, with the plan step and recipe op it carries out when known."""

    tool: str
    args: Mapping[str, Any] = field(default_factory=lambda: dict[str, Any]())
    step: int | None = None
    op: str | None = None

    def as_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"tool": self.tool, "args": dict(self.args)}
        if self.step is not None:
            out["step"] = self.step
        if self.op is not None:
            out["op"] = self.op
        return out

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> Call:
        return Call(
            cast(str, data["tool"]),
            dict(cast("Mapping[str, Any]", data.get("args") or {})),
            cast("int | None", data.get("step")),
            cast("str | None", data.get("op")),
        )


DONE = Call(DONE_TOOL)


# -- the analysis ----------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class OpStatus:
    op: Op
    status: Literal["done", "ready", "blocked"]
    by: Literal["provenance", "geometry"] | None = None  # how a done op was found done
    object_id: int | None = None  # the object that stands for a done op
    call: Call | None = None  # a ready op: the call, ready to make
    reason: str = ""  # a blocked op: why


@dataclass(frozen=True, slots=True)
class StepStatus:
    number: int
    transformation: str
    summary: str
    state: Literal["done", "active", "pending"]
    covered: bool = True
    ops: tuple[OpStatus, ...] = ()
    check: Completion | None = None
    targets: Mapping[str, float] = field(default_factory=lambda: dict[str, float]())
    measured: Mapping[str, float] = field(default_factory=lambda: dict[str, float]())
    error: str = ""  # the step could not be expanded: what is missing


@dataclass(frozen=True, slots=True)
class Leftover:
    """Something an off-plan action left in the pattern."""

    object_id: int
    name: str
    kind: Literal["created", "edited"]
    restore: Mapping[str, str] = field(default_factory=lambda: dict[str, str]())  # attr -> old


@dataclass(frozen=True, slots=True)
class Analysis:
    steps: tuple[StepStatus, ...]
    active: int | None  # step number; None when every step is complete
    leftovers: tuple[Leftover, ...] = ()
    last_off_plan: bool = False  # the latest action recorded in provenance was off-plan
    problem: str = ""  # the state cannot be labelled at all (for example the plan is not applied)

    @property
    def complete(self) -> bool:
        return self.active is None and not self.leftovers and not self.problem

    def step(self, number: int) -> StepStatus:
        return self.steps[number - 1]


# -- geometry signatures ---------------------------------------------------------------------------
def signature(ev: Evaluation, oid: int) -> tuple[float, ...] | None:
    """Where an object is, in millimetres: a point's coordinates, a curve's outline."""
    g = ev.points.get(oid)
    if g is not None:
        return (g.x_mm, g.y_mm)
    c = ev.curves.get(oid)
    if c is not None:
        return tuple(px_to_mm(v) for p in c.geom.points() for v in (p.x, p.y))
    return None


def same_place(a: tuple[float, ...] | None, b: tuple[float, ...] | None) -> bool:
    if a is None or b is None or len(a) != len(b):
        return False
    return all(abs(x - y) <= TOLERANCE_MM for x, y in zip(a, b, strict=True))


class _Sizes:
    """The pattern evaluated at the other sizes, kept while the pattern stays the same."""

    def __init__(self, others: Sequence[Mapping[str, float]]) -> None:
        self.others = tuple(others)
        self._cache: dict[tuple[int, int], tuple[Pattern, PatternSession]] = {}

    def at(self, pattern: Pattern, i: int) -> PatternSession:
        key = (id(pattern), i)
        hit = self._cache.get(key)
        if hit is not None:
            return hit[1]
        if len(self._cache) > 24:
            self._cache.clear()
        session = PatternSession(pattern, self.others[i])
        self._cache[key] = (pattern, session)
        return session


def teacher_sizes(
    pattern: Pattern, table: MeasurementSet | None, base: Mapping[str, float]
) -> tuple[dict[str, float], ...]:
    """The other sizes an equivalence is checked at: two more points of the table, far apart (the
    base size is the session's own). A person's own file has only itself."""
    from yoko_engine.binding import size_grid

    if table is None or table.kind == "individual":
        return ()
    out: list[dict[str, float]] = []
    grid = size_grid(pattern, table)
    picks = [grid[len(grid) // 2], grid[-1]] if len(grid) >= 3 else grid[1:]
    for point in picks:
        values = dict(point.values)
        if values != dict(base) and values not in out:
            out.append(values)
    return tuple(out[:2])


# -- provenance -----------------------------------------------------------------------------------
def _bindings(box: Toolbox) -> dict[tuple[str, str], int]:
    """(step id, op id) -> the object an on-plan action made or edited for that op."""
    found: dict[tuple[str, str], int] = {}
    live = {o.id for o in box.session.pattern.objects()} | set(_piece_ids(box.session.pattern))
    for oid in sorted(live):
        for entry in box.session.provenance(oid):
            m = entry.meta
            if m.step is not None and m.op is not None and m.on_plan is not False:
                found.setdefault((m.step, m.op), oid)
    return found


def _piece_ids(pattern: Pattern) -> list[int]:
    return [int(p.get("id") or 0) for _, p, _ in pieces_of(pattern)]


def _started_steps(box: Toolbox, bindings: Mapping[tuple[str, str], int]) -> set[int]:
    return {int(step[1:]) for step, _ in bindings if step.startswith("s") and step[1:].isdigit()}


def _last_order(box: Toolbox) -> tuple[int, bool]:
    """The order of the latest action recorded in provenance, and whether it was off-plan."""
    best: Provenance | None = None
    pattern = box.session.pattern
    for oid in [o.id for o in pattern.objects()] + _piece_ids(pattern):
        for entry in box.session.provenance(oid):
            if best is None or entry.order > best.order:
                best = entry
    if best is None:
        return 0, False
    return best.order, best.meta.on_plan is False


def _leftovers(box: Toolbox, adopted: set[int]) -> tuple[Leftover, ...]:
    """What off-plan actions left: objects they made, and fields they changed that no later
    on-plan action changed again. `adopted` objects stand for an op, so they are not leftovers."""
    out: list[Leftover] = []
    pattern = box.session.pattern
    names = {o.id: o for o in pattern.objects()}
    pieces = {int(p.get("id") or 0): p.get("name") or "" for _, p, _ in pieces_of(pattern)}
    for oid in sorted({*names, *pieces}):
        if oid in adopted:
            continue
        history = box.session.provenance(oid)
        if not history:
            continue
        label = _name_of(box, oid, names, pieces)
        if history[0].kind == "created" and history[0].meta.on_plan is False:
            out.append(Leftover(oid, label, "created"))
            continue
        obj = names.get(oid)
        if obj is None:
            continue
        restore: dict[str, str] = {}
        fields = {c.field for e in history for c in e.changes}
        for fld in sorted(fields):
            touching = [e for e in history if any(c.field == fld for c in e.changes)]
            run: list[Provenance] = []
            for e in reversed(touching):
                if e.meta.on_plan is not False:
                    break
                run.append(e)
            if not run:
                continue
            first = run[-1]
            old = next(c.old for c in first.changes if c.field == fld)
            if old is not None and obj.get(fld) != old:
                restore[fld] = old
        if restore:
            out.append(Leftover(oid, label, "edited", restore))
    return tuple(out)


def _name_of(box: Toolbox, oid: int, objs: Mapping[int, Obj], pieces: Mapping[int, str]) -> str:
    if oid in pieces:
        return pieces[oid]
    try:
        return box.resolve(f"#{oid}", "object", "target").name
    except ToolError:
        return f"#{oid}" if oid in objs else str(oid)


# -- the teacher ----------------------------------------------------------------------------------
class Teacher:
    """A teacher for one recipe registry. Cheap to make; keep one per run."""

    def __init__(
        self,
        recipes: RecipeRegistry,
        *,
        others: Sequence[Mapping[str, float]] = (),
        composites: bool = True,
    ) -> None:
        self.recipes = recipes
        self.sizes = _Sizes(others)
        self.composites = composites

    # -- analysis ----------------------------------------------------------------------------
    def analyse(self, box: Toolbox, plan: Mapping[str, Any]) -> Analysis:
        steps_in = cast("list[Mapping[str, Any]]", plan["steps"])
        missing = [
            variable_name(cast(int, s["step"]), p)
            for s in steps_in
            for p in cast("Mapping[str, Any]", s["params"])
            if variable_name(cast(int, s["step"]), p) not in box.session.evaluation.symbols
        ]
        if missing:
            return Analysis(
                (),
                None,
                problem=f"the plan's variables are not in the pattern ({', '.join(missing[:3])})",
            )
        bindings = _bindings(box)
        started = _started_steps(box, bindings)
        statuses: list[StepStatus] = []
        adopted: set[int] = set(bindings.values())
        active: int | None = None
        for index, raw in enumerate(steps_in):
            number = index + 1
            name = cast(str, raw["transformation"])
            summary = cast(str, raw["summary"])
            if active is not None:
                statuses.append(StepStatus(number, name, summary, "pending"))
                continue
            recipe = self.recipes.get(name)
            if recipe is None:
                statuses.append(StepStatus(number, name, summary, "active", covered=False))
                active = number
                continue
            status = self._step(box, raw, number, recipe, bindings, started, adopted)
            statuses.append(status)
            if status.state == "active":
                active = number
        leftovers = _leftovers(box, adopted)
        _, last_off = _last_order(box)
        return Analysis(tuple(statuses), active, leftovers, last_off)

    def _step(
        self,
        box: Toolbox,
        raw: Mapping[str, Any],
        number: int,
        recipe: Recipe,
        bindings: Mapping[tuple[str, str], int],
        started: set[int],
        adopted: set[int],
    ) -> StepStatus:
        name = cast(str, raw["transformation"])
        summary = cast(str, raw["summary"])
        ctx = StepContext(box, number, raw, recipe.spec)
        try:
            graph = recipe.expand(ctx)
        except (RecipeError, ToolError) as err:
            return StepStatus(number, name, summary, "active", error=str(err))
        names: dict[str, str] = {}
        ops: list[OpStatus] = []
        for op in graph:
            status = self._op(box, ctx, op, bindings, names)
            ops.append(status)
            if status.status == "done" and status.object_id is not None:
                adopted.add(status.object_id)
                target = box.resolve(f"#{status.object_id}", "object", "target")
                names[op.id] = target.name
                ctx.bound[op.id] = target
                if op.landmark is not None:
                    self._register(box, op.landmark, status.object_id)
        all_done = all(o.status == "done" for o in ops)
        check = recipe.check(ctx) if all_done else None
        moved_past = any(j > number for j in started)
        complete = all_done and (cast(Completion, check).done or moved_past)
        measured: dict[str, float] = {}
        targets: dict[str, float] = {}
        if not complete:
            measured = dict(recipe.measure(ctx))
            for p in recipe.spec.params:
                v = ctx.value(p)
                if v is not None:
                    targets[p] = v
        return StepStatus(
            number,
            name,
            summary,
            "done" if complete else "active",
            ops=tuple(ops),
            check=check,
            targets=targets,
            measured=measured,
        )

    @staticmethod
    def _register(box: Toolbox, landmark: str, oid: int) -> None:
        if (
            box.landmarks is not None
            and box.landmarks.resolve(box.session.evaluation)[0].get(landmark) == oid
        ):
            return
        box.add_landmark(landmark, oid)

    def _op(
        self,
        box: Toolbox,
        ctx: StepContext,
        op: Op,
        bindings: Mapping[tuple[str, str], int],
        names: Mapping[str, str],
    ) -> OpStatus:
        by_provenance = bindings.get((ctx.step_id, op.id))
        if by_provenance is not None:
            return OpStatus(op, "done", "provenance", by_provenance)
        waiting = [n for n in op.needed() if n not in names]
        if waiting:
            return OpStatus(op, "blocked", reason=f"waits for {', '.join(waiting)}")
        call = self._call(box, ctx, op, names)
        twin, result = self._try(box, call)
        if not result["ok"]:
            err = result["error"]
            return OpStatus(op, "blocked", reason=f"{err['code']}: {err['message']}")
        found = self._reproduced(box, op, call, twin, result)
        if found is not None:
            return OpStatus(op, "done", "geometry", found)
        return OpStatus(op, "ready", call=call)

    @staticmethod
    def _call(box: Toolbox, ctx: StepContext, op: Op, names: Mapping[str, str]) -> Call:
        return Call(op.tool, op_args(op, ctx, box.specs, names), ctx.number, op.id)

    @staticmethod
    def _try(box: Toolbox, call: Call) -> tuple[Toolbox, dict[str, Any]]:
        twin = box.fork()
        return twin, twin.call(call.tool, call.args, ActionMeta(author="teacher"))

    def _reproduced(
        self, box: Toolbox, op: Op, call: Call, twin: Toolbox, result: Mapping[str, Any]
    ) -> int | None:
        """The object that already reproduces what the op would make, if any: same place at the
        base size and at the other sizes. Nothing is made for an op that is already satisfied."""
        ev = box.session.evaluation
        if op.kind == "edit":
            try:
                target = box.resolve(cast(str, call.args["target"]), "object", "target").id
            except (ToolError, KeyError):
                return None
            if not same_place(signature(ev, target), signature(twin.session.evaluation, target)):
                return None
            return target if self._holds_elsewhere(box, twin, {target: target}) else None
        made = [cast(int, c["id"]) for c in cast("list[Mapping[str, Any]]", result["created"])]
        pairs: dict[int, int] = {}
        for new_id in made:
            want = signature(twin.session.evaluation, new_id)
            if want is None:
                continue
            match = next(
                (oid for oid in (*ev.points, *ev.curves) if same_place(signature(ev, oid), want)),
                None,
            )
            if match is None:
                return None
            pairs[match] = new_id
        if not pairs:
            return None
        return next(iter(pairs)) if self._holds_elsewhere(box, twin, pairs) else None

    def _holds_elsewhere(self, box: Toolbox, twin: Toolbox, pairs: Mapping[int, int]) -> bool:
        """`pairs` maps an object here to the object the op would make: the same place at every
        other size too?"""
        for i in range(len(self.sizes.others)):
            here = self.sizes.at(box.session.pattern, i).evaluation
            there = self.sizes.at(twin.session.pattern, i).evaluation
            for mine, theirs in pairs.items():
                if not same_place(signature(here, mine), signature(there, theirs)):
                    return False
        return True

    # -- the acceptable set -------------------------------------------------------------------
    def expert(self, box: Toolbox, plan: Mapping[str, Any]) -> list[Call] | None:
        return self.acceptable(box, plan, self.analyse(box, plan))

    def acceptable(
        self, box: Toolbox, plan: Mapping[str, Any], analysis: Analysis
    ) -> list[Call] | None:
        if analysis.problem:
            return None
        if analysis.leftovers:
            return self._recovery(box, analysis)
        if analysis.active is None:
            return [DONE]
        step = analysis.step(analysis.active)
        if not step.covered:
            return None
        out = [o.call for o in step.ops if o.status == "ready" and o.call is not None]
        if self.composites and any(o.status != "done" for o in step.ops) and not step.error:
            out.append(Call(APPLY_STEP, {"step": step.number}, step.number))
        return out

    def _recovery(self, box: Toolbox, analysis: Analysis) -> list[Call]:
        out: list[Call] = []
        if analysis.last_off_plan and box.session.can_undo:
            out.append(Call("undo"))
        dependents = box.session.dependents
        for left in analysis.leftovers:
            if left.kind == "created":
                call = self._delete_call(box, left)
                if (
                    call is not None
                    and not dependents(left.object_id)
                    and not pieces_using(box.session.pattern, left.object_id)
                ):
                    out.append(call)
            else:
                call = self._restore_call(box, left)
                if call is not None:
                    out.append(call)
        active = analysis.active
        if active is not None:
            edited = {left.object_id for left in analysis.leftovers if left.kind == "edited"}
            for status in analysis.step(active).ops:
                if status.op.kind != "edit" or status.call is None:
                    continue
                try:
                    target = box.resolve(cast(str, status.call.args["target"]), "object", "t").id
                except (ToolError, KeyError):
                    continue
                if target in edited:
                    out.append(status.call)
        # a delete of an object nothing uses is certain to work; the other calls are tried first
        return [c for c in out if c.tool.startswith("delete_") or self._works(box, c)]

    @staticmethod
    def _works(box: Toolbox, call: Call) -> bool:
        if call.tool == "undo":
            return True
        return bool(box.fork().call(call.tool, call.args, ActionMeta(author="teacher"))["ok"])

    @staticmethod
    def _delete_call(box: Toolbox, left: Leftover) -> Call | None:
        pattern = box.session.pattern
        if any(int(p.get("id") or 0) == left.object_id for _, p, _ in pieces_of(pattern)):
            return Call("delete_piece", {"piece": f"#{left.object_id}"})
        obj = next((o for o in pattern.objects() if o.id == left.object_id), None)
        tool = box.tool_for(obj) if obj is not None else None
        if tool is None or f"delete_{tool}" not in box.specs:
            return None
        return Call(f"delete_{tool}", {"target": f"#{left.object_id}"})

    @staticmethod
    def _restore_call(box: Toolbox, left: Leftover) -> Call | None:
        obj = next((o for o in box.session.pattern.objects() if o.id == left.object_id), None)
        tool = box.tool_for(obj) if obj is not None else None
        spec = box.specs.get(f"edit_{tool}") if tool else None
        if spec is None or spec.engine is None:
            return None
        args: dict[str, Any] = {"target": f"#{left.object_id}"}
        for attr, rule in cast("Mapping[str, Any]", spec.engine.get("set", {})).items():
            if attr in left.restore and isinstance(rule, str) and rule.startswith("{"):
                param = rule[1:-1]
                if param in spec.parameters and "{" not in param:
                    args[param] = left.restore[attr]
        return Call(spec.name, args) if len(args) > 1 else None

    # -- labelling an action ------------------------------------------------------------------
    def label(
        self,
        box: Toolbox,
        plan: Mapping[str, Any],
        call: Call,
        analysis: Analysis | None = None,
    ) -> Label:
        """Compare an action with the teacher's set for this state (before it is applied)."""
        analysis = analysis or self.analyse(box, plan)
        accepted = self.acceptable(box, plan, analysis)
        if accepted is None:
            return Label(None, None, None)
        key = box.canonical(call.tool, call.args)
        for a in accepted:
            if box.canonical(a.tool, a.args) == key:
                return Label(True, a.step, a.op)
        if analysis.active is None or analysis.leftovers:
            return Label(False, None, None)
        return self._equivalent(box, call, analysis)

    def _equivalent(self, box: Toolbox, call: Call, analysis: Analysis) -> Label:
        """An action that is not one of the ops as written can still make what an op makes: an
        object in the same place at every size (for an edit: the edited object ends up there)."""
        assert analysis.active is not None
        step = analysis.step(analysis.active)
        actual, result = self._try(box, call)
        if not result["ok"]:
            return Label(False, None, None)
        made = [cast(int, c["id"]) for c in cast("list[Mapping[str, Any]]", result["created"])]
        for status in step.ops:
            if status.status != "ready" or status.call is None:
                continue
            want, res = self._try(box, status.call)
            if not res["ok"]:
                continue
            if status.op.kind == "edit":
                try:
                    target = box.resolve(cast(str, status.call.args["target"]), "object", "t").id
                except (ToolError, KeyError):
                    continue
                pairs = [(target, target)]
            else:
                pairs = self._pair_up(actual, made, want, res)
            if pairs and self._same_result(actual, want, pairs):
                return Label(True, step.number, status.op.id)
        return Label(False, None, None)

    @staticmethod
    def _pair_up(
        actual: Toolbox, actual_made: Sequence[int], want: Toolbox, res: Mapping[str, Any]
    ) -> list[tuple[int, int]]:
        """Each object the op makes with the object the action made in the same place; empty if
        any of them has no partner."""
        evx, evw = actual.session.evaluation, want.session.evaluation
        pairs: list[tuple[int, int]] = []
        for w in (cast(int, c["id"]) for c in cast("list[Mapping[str, Any]]", res["created"])):
            sig = signature(evw, w)
            match = next((a for a in actual_made if same_place(signature(evx, a), sig)), None)
            if match is None:
                return []
            pairs.append((match, w))
        return pairs

    def _same_result(
        self, actual: Toolbox, want: Toolbox, pairs: Sequence[tuple[int, int]]
    ) -> bool:
        """(object in `actual`, object in `want`) pairs: in the same place at the base size and at
        every other size?"""
        evx, evw = actual.session.evaluation, want.session.evaluation
        if not all(same_place(signature(evx, a), signature(evw, w)) for a, w in pairs):
            return False
        for i in range(len(self.sizes.others)):
            here = self.sizes.at(actual.session.pattern, i).evaluation
            there = self.sizes.at(want.session.pattern, i).evaluation
            if not all(same_place(signature(here, a), signature(there, w)) for a, w in pairs):
                return False
        return True


@dataclass(frozen=True, slots=True)
class Label:
    """The teacher's verdict on an action: `on_plan` is None when the teacher has no label."""

    on_plan: bool | None
    step: int | None
    op: str | None


def expert(
    box: Toolbox,
    plan: Mapping[str, Any],
    recipes: RecipeRegistry,
    others: Sequence[Mapping[str, float]] = (),
) -> list[Call] | None:
    """The acceptable next actions, canonical first; None when no recipe covers the step."""
    return Teacher(recipes, others=others).expert(box, plan)


__all__ = [
    "APPLY_STEP",
    "DONE",
    "DONE_TOOL",
    "Analysis",
    "Call",
    "Label",
    "Leftover",
    "OpStatus",
    "StepStatus",
    "Teacher",
    "expert",
    "signature",
    "teacher_sizes",
]
