"""`PatternSession`: the only way a pattern changes.

Every change is a typed action. `apply` builds the changed pattern, re-evaluates incrementally,
validates, and keeps the change only if it introduces no new error: otherwise nothing happens
(all or nothing). Sessions are cheap to `fork`, can `undo`, and have a stable `state_hash`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace

from yoko_engine.evaluator import Evaluation, Evaluator, Issue
from yoko_engine.model import DraftBlock, MeasurementSet, Obj, Pattern, RawNode, Variable
from yoko_engine.units import px_to_mm
from yoko_engine.validation import errors, validate

# attributes that hold the id of another object
REF_ATTRS = frozenset(
    {
        "basePoint", "firstPoint", "secondPoint", "thirdPoint", "center", "p1Line", "p2Line",
        "curve", "point1", "point2", "point3", "point4", "baseLineP1", "baseLineP2",
        "dartP1", "dartP2", "dartP3",
    }
)  # fmt: skip
IMMUTABLE_ATTRS = frozenset({"id", "type"})


# -- actions ---------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ActionMeta:
    """Who did this and why; stored as provenance for every object the action creates or edits."""

    step: str | None = None  # plan step id
    op: str | None = None  # recipe op id
    author: str = "model"  # model | human | teacher | import
    episode: str | None = None
    on_plan: bool | None = None  # privileged: never shown to the policy


@dataclass(frozen=True, slots=True)
class AddObject:
    obj: Obj  # id 0 means "assign the next free id"
    after: int | None = None  # insert after this object; None appends to the last block


@dataclass(frozen=True, slots=True)
class SetAttrs:
    id: int
    attrs: tuple[tuple[str, str], ...]  # attribute -> new value (formulas, references, labels)


@dataclass(frozen=True, slots=True)
class DeleteObject:
    id: int


@dataclass(frozen=True, slots=True)
class SetVariable:
    """Add a variable, or change an existing one's formula."""

    name: str
    formula: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class DeleteVariable:
    name: str


Action = AddObject | SetAttrs | DeleteObject | SetVariable | DeleteVariable


# -- results ---------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ActionError:
    code: str
    message: str
    field: str | None = None
    hint: str | None = None
    object_id: int | None = None


@dataclass(frozen=True, slots=True)
class Moved:
    """What an action moved: a change to one formula can move hundreds of points."""

    count: int
    top: tuple[tuple[str, float], ...]  # (label, mm moved), the largest few


@dataclass(frozen=True, slots=True)
class Result:
    ok: bool
    created: tuple[int, ...] = ()
    changed: tuple[int, ...] = ()
    deleted: tuple[int, ...] = ()
    warnings: tuple[Issue, ...] = ()
    error: ActionError | None = None
    moved: Moved = Moved(0, ())
    reevaluated: int = 0


@dataclass(frozen=True, slots=True)
class FieldChange:
    field: str
    old: str | None
    new: str | None


@dataclass(frozen=True, slots=True)
class Provenance:
    """One entry in an object's history."""

    kind: str  # created | edited
    meta: ActionMeta
    changes: tuple[FieldChange, ...] = ()


@dataclass(frozen=True, slots=True)
class PatternDiff:
    added: tuple[int, ...] = ()
    removed: tuple[int, ...] = ()
    edited: tuple[tuple[int, tuple[FieldChange, ...]], ...] = ()
    variables_added: tuple[str, ...] = ()
    variables_removed: tuple[str, ...] = ()
    variables_edited: tuple[tuple[str, str, str], ...] = ()

    @property
    def empty(self) -> bool:
        return not (
            self.added
            or self.removed
            or self.edited
            or self.variables_added
            or self.variables_removed
            or self.variables_edited
        )


def diff_patterns(a: Pattern, b: Pattern) -> PatternDiff:
    """What changed from pattern `a` to pattern `b`: objects added, removed and edited (old to
    new), and variables. This is the basis of derivation diffs."""
    old = {o.id: o for o in a.objects()}
    new = {o.id: o for o in b.objects()}
    edited: list[tuple[int, tuple[FieldChange, ...]]] = []
    for oid, nobj in new.items():
        oobj = old.get(oid)
        if oobj is None or oobj == nobj:
            continue
        edited.append((oid, _attr_changes(oobj, nobj)))
    va = {v.name: v for v in a.variables}
    vb = {v.name: v for v in b.variables}
    return PatternDiff(
        added=tuple(i for i in new if i not in old),
        removed=tuple(i for i in old if i not in new),
        edited=tuple(edited),
        variables_added=tuple(n for n in vb if n not in va),
        variables_removed=tuple(n for n in va if n not in vb),
        variables_edited=tuple(
            (n, va[n].formula, vb[n].formula) for n in vb if n in va and va[n] != vb[n]
        ),
    )


def _attr_changes(old: Obj, new: Obj) -> tuple[FieldChange, ...]:
    o = dict(old.attrs)
    n = dict(new.attrs)
    out = [FieldChange(k, o.get(k), n.get(k)) for k in {*o, *n} if o.get(k) != n.get(k)]
    if old.children != new.children:
        out.append(FieldChange("children", None, None))
    return tuple(sorted(out, key=lambda c: c.field))


# -- hashing ---------------------------------------------------------------------------------------
def _raw(n: RawNode) -> list[object]:
    return [n.tag, [list(a) for a in n.attrs], n.text, [_raw(c) for c in n.children]]


def _object_state(o: Obj) -> list[object]:
    return [o.id, o.tag, o.kind, [list(a) for a in o.attrs], [_raw(c) for c in o.children]]


def _variable_state(v: Variable) -> list[object]:
    return [v.name, v.formula, v.description, [list(e) for e in v.extra]]


def pattern_state(pattern: Pattern) -> dict[str, object]:
    return {
        "unit": pattern.unit,
        "version": pattern.version,
        "measurements": pattern.measurements_file,
        "variables": [_variable_state(v) for v in pattern.variables],
        "blocks": [
            [b.name, [_object_state(o) for o in b.objects], [_raw(s) for s in b.sections]]
            for b in pattern.blocks
        ],
        "header": [_raw(h) for h in pattern.header],
    }


def state_hash(pattern: Pattern, measurements: Mapping[str, float]) -> str:
    """Stable hash of a pattern and the measurement values it is evaluated with."""
    payload = {"pattern": pattern_state(pattern), "values": sorted(measurements.items())}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Snapshot:
    pattern: Pattern
    measurements: tuple[tuple[str, float], ...]
    hash: str


class _State:
    __slots__ = ("error_keys", "evaluator", "issues", "pattern", "provenance")

    def __init__(
        self,
        pattern: Pattern,
        evaluator: Evaluator,
        provenance: dict[int, tuple[Provenance, ...]] | None = None,
        issues: list[Issue] | None = None,
    ) -> None:
        self.pattern = pattern
        self.evaluator = evaluator
        self.provenance: dict[int, tuple[Provenance, ...]] = provenance if provenance else {}
        # validation of this state, computed once when the state is created
        self.issues: list[Issue] = issues if issues is not None else validate(pattern, evaluator.ev)
        self.error_keys = {_key(i) for i in errors(self.issues)}


class PatternSession:
    """A pattern under edit."""

    def __init__(
        self,
        pattern: Pattern,
        measurements: MeasurementSet | Mapping[str, float],
        *,
        size: float | None = None,
        height: float | None = None,
        read_only: bool = False,
    ) -> None:
        self.read_only = read_only
        if isinstance(measurements, MeasurementSet):
            self._values: dict[str, float] = measurements.values(size, height)
        else:
            self._values = dict(measurements)
        evaluator = Evaluator()
        evaluator.run(pattern, self._values)
        self._state = _State(pattern, evaluator)
        self._undo: list[_State] = []
        self._hash: tuple[int, str] | None = None
        self.parent_hash: str | None = None  # hash of the pattern this one was derived from

    # -- reading ----------------------------------------------------------------------------
    @property
    def pattern(self) -> Pattern:
        return self._state.pattern

    @property
    def evaluation(self) -> Evaluation:
        return self._state.evaluator.ev

    def issues(self) -> list[Issue]:
        return list(self._state.issues)

    def provenance(self, object_id: int) -> tuple[Provenance, ...]:
        return self._state.provenance.get(object_id, ())

    def dependencies(self, object_id: int) -> frozenset[int]:
        """The objects `object_id` was built from."""
        return self.evaluation.deps.get(object_id, frozenset())

    def dependents(self, object_id: int) -> frozenset[int]:
        """The objects built (directly) from `object_id`."""
        return frozenset(i for i, deps in self.evaluation.deps.items() if object_id in deps)

    def state_hash(self) -> str:
        key = id(self.pattern)
        if self._hash is None or self._hash[0] != key:
            self._hash = (key, state_hash(self.pattern, self._values))
        return self._hash[1]

    def sidecar(self) -> dict[str, object]:
        """The `<style>.yoko.json` sidecar (docs/adr/0005-provenance.md): provenance for every
        object created or edited, and the hash of the pattern this one was derived from. The
        privileged `on_plan` flag is included for training and scoring; policies never see it."""
        objects: dict[str, object] = {}
        for oid in sorted(self._state.provenance):
            objects[str(oid)] = [
                {
                    "kind": p.kind,
                    "step": p.meta.step,
                    "op": p.meta.op,
                    "author": p.meta.author,
                    "episode": p.meta.episode,
                    "on_plan": p.meta.on_plan,
                    "changes": [{"field": c.field, "old": c.old, "new": c.new} for c in p.changes],
                }
                for p in self._state.provenance[oid]
            ]
        return {
            "version": 1,
            "parent_hash": self.parent_hash,
            "state_hash": self.state_hash(),
            "objects": objects,
        }

    def snapshot(self) -> Snapshot:
        return Snapshot(self.pattern, tuple(sorted(self._values.items())), self.state_hash())

    def diff(self, other: PatternSession) -> PatternDiff:
        """What changed from `other` to this session."""
        return diff_patterns(other.pattern, self.pattern)

    # -- forking and undo -------------------------------------------------------------------
    def fork(self) -> PatternSession:
        child = PatternSession.__new__(PatternSession)
        child.read_only = self.read_only
        child._values = dict(self._values)
        child._state = _State(
            self._state.pattern,
            self._state.evaluator.copy(),
            dict(self._state.provenance),
            self._state.issues,
        )
        child._undo = []
        child._hash = self._hash
        child.parent_hash = self.parent_hash
        return child

    def undo(self) -> Result:
        if not self._undo:
            return Result(False, error=ActionError("nothing_to_undo", "there is nothing to undo"))
        before = self._state
        self._state = self._undo.pop()
        return Result(
            True,
            changed=tuple(sorted(self._touched(before.pattern, self._state.pattern))),
            moved=self._moved(before.evaluator.ev, self.evaluation),
        )

    @staticmethod
    def _touched(a: Pattern, b: Pattern) -> set[int]:
        d = diff_patterns(a, b)
        return {*d.added, *d.removed, *(i for i, _ in d.edited)}

    # -- applying ---------------------------------------------------------------------------
    def apply(self, action: Action, meta: ActionMeta | None = None) -> Result:
        meta = meta or ActionMeta()
        if self.read_only:
            return _fail(
                "read_only",
                "this pattern is locked",
                hint="derive a style from it (fork it into the styles area) and edit that",
            )
        try:
            new_pattern, edited, created, deleted = self._build(action)
        except _Rejected as err:
            return Result(False, error=err.error)

        evaluator = self._state.evaluator.copy()
        before_issues = self._state.error_keys
        evaluator.update(new_pattern, self._values, edited)
        after = validate(new_pattern, evaluator.ev)
        new_errors = [i for i in errors(after) if _key(i) not in before_issues]
        if new_errors:
            first = new_errors[0]
            more = f" (and {len(new_errors) - 1} more)" if len(new_errors) > 1 else ""
            return _fail(
                first.code,
                first.message + more,
                field=first.field,
                hint=first.hint,
                object_id=first.object_id,
            )

        old = self._state
        provenance = dict(old.provenance)
        diff = diff_patterns(old.pattern, new_pattern)
        for oid in created:
            provenance[oid] = (Provenance("created", meta),)
        for oid, changes in diff.edited:
            if oid not in created:
                provenance[oid] = (*provenance.get(oid, ()), Provenance("edited", meta, changes))
        for oid in deleted:
            provenance.pop(oid, None)
        self._undo.append(old)
        self._state = _State(new_pattern, evaluator, provenance, after)
        warnings = tuple(i for i in after if i.severity != "error")
        return Result(
            True,
            created=tuple(created),
            changed=tuple(sorted({i for i, _ in diff.edited} - set(created))),
            deleted=tuple(deleted),
            warnings=warnings,
            moved=self._moved(old.evaluator.ev, evaluator.ev),
            reevaluated=evaluator.last_reevaluated,
        )

    # -- building the changed pattern -------------------------------------------------------
    def _build(self, action: Action) -> tuple[Pattern, set[int], list[int], list[int]]:
        pattern = self.pattern
        if isinstance(action, AddObject):
            return self._add(pattern, action)
        if isinstance(action, SetAttrs):
            return self._set_attrs(pattern, action)
        if isinstance(action, DeleteObject):
            return self._delete(pattern, action)
        if isinstance(action, SetVariable):
            return self._set_variable(pattern, action), set(), [], []
        return self._delete_variable(pattern, action), set(), [], []

    def _add(
        self, pattern: Pattern, a: AddObject
    ) -> tuple[Pattern, set[int], list[int], list[int]]:
        existing = {o.id for o in pattern.objects()}
        obj = a.obj
        if obj.id == 0:
            obj = replace(obj, id=max(existing, default=0) + 1)
        elif obj.id in existing:
            raise _Rejected(
                "duplicate_id", f"object id {obj.id} is already in use", object_id=obj.id
            )
        _check_forward_refs(pattern, obj, position=None, after=a.after)
        blocks = list(pattern.blocks) or [DraftBlock("Draft block 1", ())]
        index = len(blocks) - 1
        insert_at = len(blocks[index].objects)
        if a.after is not None:
            found = False
            for bi, b in enumerate(blocks):
                for oi, existing_obj in enumerate(b.objects):
                    if existing_obj.id == a.after:
                        index, insert_at, found = bi, oi + 1, True
            if not found:
                raise _Rejected("unknown_object", f"no object {a.after} to insert after")
        block = blocks[index]
        objs = (*block.objects[:insert_at], obj, *block.objects[insert_at:])
        blocks[index] = replace(block, objects=objs)
        return replace(pattern, blocks=tuple(blocks)), {obj.id}, [obj.id], []

    def _set_attrs(
        self, pattern: Pattern, a: SetAttrs
    ) -> tuple[Pattern, set[int], list[int], list[int]]:
        for key, _ in a.attrs:
            if key in IMMUTABLE_ATTRS:
                raise _Rejected(
                    "immutable_field", f"'{key}' cannot be changed", field=key, object_id=a.id
                )
        found: Obj | None = None
        blocks: list[DraftBlock] = []
        for b in pattern.blocks:
            objs: list[Obj] = []
            for o in b.objects:
                if o.id == a.id:
                    found = o
                    for key, value in a.attrs:
                        o = o.with_attr(key, value)
                    _check_forward_refs(pattern, o, position=a.id, after=None)
                objs.append(o)
            blocks.append(replace(b, objects=tuple(objs)))
        if found is None:
            raise _Rejected("unknown_object", f"there is no object {a.id}", object_id=a.id)
        return replace(pattern, blocks=tuple(blocks)), {a.id}, [], []

    def _delete(
        self, pattern: Pattern, a: DeleteObject
    ) -> tuple[Pattern, set[int], list[int], list[int]]:
        if a.id not in {o.id for o in pattern.objects()}:
            raise _Rejected("unknown_object", f"there is no object {a.id}", object_id=a.id)
        users = sorted(self.dependents(a.id))
        owned = self._state.evaluator.records.get(a.id)
        if owned is not None:
            names = owned.symbols
            for oid, rec in self._state.evaluator.records.items():
                if oid != a.id and not rec.uses_names.isdisjoint(names) and oid not in users:
                    users.append(oid)
        if users:
            raise _Rejected(
                "has_dependents",
                f"object {a.id} is used by {', '.join(str(u) for u in users[:8])}",
                object_id=a.id,
                hint="edit or delete the objects that use it first, or change them to use "
                "something else",
            )
        blocks = [
            replace(b, objects=tuple(o for o in b.objects if o.id != a.id)) for b in pattern.blocks
        ]
        return replace(pattern, blocks=tuple(blocks)), set(), [], [a.id]

    def _set_variable(self, pattern: Pattern, a: SetVariable) -> Pattern:
        variables = list(pattern.variables)
        for i, v in enumerate(variables):
            if v.name == a.name:
                variables[i] = replace(
                    v, formula=a.formula, description=a.description or v.description
                )
                return replace(pattern, variables=tuple(variables))
        variables.append(Variable(a.name, a.formula, a.description))
        return replace(pattern, variables=tuple(variables))

    def _delete_variable(self, pattern: Pattern, a: DeleteVariable) -> Pattern:
        if a.name not in {v.name for v in pattern.variables}:
            raise _Rejected("unknown_variable", f"there is no variable {a.name!r}")
        users = sorted(
            oid for oid, rec in self._state.evaluator.records.items() if a.name in rec.uses_names
        )
        if users:
            raise _Rejected(
                "has_dependents",
                f"variable {a.name!r} is used by {', '.join(str(u) for u in users[:8])}",
                hint="change the formulas that use it first",
            )
        return replace(pattern, variables=tuple(v for v in pattern.variables if v.name != a.name))

    # -- what moved -------------------------------------------------------------------------
    @staticmethod
    def _moved(old: Evaluation, new: Evaluation) -> Moved:
        moved: list[tuple[str, float]] = []
        for pid, g in new.points.items():
            before = old.points.get(pid)
            if before is not None and before.p != g.p:
                dist = px_to_mm(max(abs(g.p.x - before.p.x), abs(g.p.y - before.p.y)))
                moved.append((g.label, dist))
        moved.sort(key=lambda m: -m[1])
        return Moved(len(moved), tuple((label, round(d, 6)) for label, d in moved[:3]))


class _Rejected(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str | None = None,
        hint: str | None = None,
        object_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error = ActionError(code, message, field, hint, object_id)


def _fail(
    code: str,
    message: str,
    *,
    field: str | None = None,
    hint: str | None = None,
    object_id: int | None = None,
) -> Result:
    return Result(False, error=ActionError(code, message, field, hint, object_id))


def _key(i: Issue) -> tuple[str, int | None, str | None]:
    return (i.code, i.object_id, i.field)


def _check_forward_refs(
    pattern: Pattern, obj: Obj, *, position: int | None, after: int | None
) -> None:
    """Reject a reference to an object that comes later: an object may not depend on its own
    dependents."""
    order = {o.id: i for i, o in enumerate(pattern.objects())}
    if position is not None:
        here = order.get(position, len(order))
    elif after is not None:
        here = order.get(after, len(order) - 1) + 0.5
    else:
        here = len(order)
    for key, value in obj.attrs:
        if key in REF_ATTRS and value.isdigit():
            ref = order.get(int(value))
            if ref is not None and ref >= here and int(value) != obj.id:
                raise _Rejected(
                    "forward_reference",
                    f"'{key}' refers to object {value}, which comes after this one",
                    field=key,
                    hint="an object can only be built from objects defined before it",
                    object_id=obj.id or None,
                )
