"""Recipes: the framework a manipulation is written in (docs/adr/0007, Addendum 1 section 8).

This module knows nothing about any one manipulation. A recipe supplies

- a `RecipeSpec` (name, parameters with unit and range, roles it needs named, options it branches
  on, landmarks it creates), the thing plan validation reads;
- `expand(ctx)`: the operation graph for one plan step, a `RecipeGraph` of `Op`s with stable ids;
- `check(ctx)`: the completion check (a half-applied recipe does not count as done);
- `measure(ctx)`: how to measure each parameter on the pattern now, for the status card.

An op is a canonical tool call written with landmark names and the step's variables. It either
**adds** an object or **edits** an existing one (pattern makers mostly make a style by editing the
formulas of the copied block's own points). An op's arguments may name what an earlier op made with
`@<op id>`; the teacher fills in the real label, whichever object stands for that op.

Edits are applied again whenever the teacher expands a step, and the pattern has changed by then. So
an edit that builds on an object's old formula reads it with `ctx.original(target, attr)`, the value
the step found before it edited anything (read back from provenance), never the current one.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, cast

from yoko_tools.numbers import fmt_number
from yoko_tools.plan import LENGTH_UNITS, RecipeSpec, variable_name

if TYPE_CHECKING:
    from yoko_tools.runtime import Target, Toolbox

TOKEN = re.compile(r"@([a-z][a-z0-9_]*)")
OP_ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class RecipeError(ValueError):
    """A recipe that is not well formed, or a plan step it cannot be expanded for."""


@dataclass(frozen=True, slots=True)
class Op:
    """One operation of a recipe: a tool call with a stable id."""

    id: str
    kind: Literal["add", "edit"]
    tool: str
    args: Mapping[str, Any]
    needs: tuple[str, ...] = ()  # ops that must be done first, besides the ones `args` names
    landmark: str | None = None  # the landmark the object this op makes is given

    def tokens(self) -> tuple[str, ...]:
        """The ops whose results `args` names (`@id`)."""
        found: list[str] = []

        def visit(text: str) -> None:
            found.extend(TOKEN.findall(text))

        _walk(self.args, visit)
        return tuple(dict.fromkeys(found))

    def needed(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.needs, *self.tokens())))


def _walk(node: Any, visit: Callable[[str], None]) -> None:
    if isinstance(node, str):
        visit(node)
    elif isinstance(node, Mapping):
        for v in cast("Mapping[str, Any]", node).values():
            _walk(v, visit)
    elif isinstance(node, list | tuple):
        for v in cast("Sequence[Any]", node):
            _walk(v, visit)


def fill(node: Any, names: Mapping[str, str]) -> Any:
    """`node` with every `@op` replaced by the label of the object that stands for the op."""
    if isinstance(node, str):
        return TOKEN.sub(lambda m: names[m.group(1)], node)
    if isinstance(node, Mapping):
        return {k: fill(v, names) for k, v in cast("Mapping[str, Any]", node).items()}
    if isinstance(node, list | tuple):
        return [fill(v, names) for v in cast("Sequence[Any]", node)]
    return node


@dataclass(frozen=True, slots=True)
class RecipeGraph:
    """The ops of one step, in an order that respects their dependencies."""

    ops: tuple[Op, ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for op in self.ops:
            if not OP_ID.match(op.id):
                raise RecipeError(f"op id {op.id!r}: lower case letters, digits and _ only")
            if op.id in seen:
                raise RecipeError(f"two ops are called {op.id!r}")
            for need in op.needed():
                if need not in seen:
                    raise RecipeError(
                        f"op {op.id!r} needs {need!r}, which is not an earlier op of the graph"
                    )
            seen.add(op.id)

    def __iter__(self) -> Iterator[Op]:
        return iter(self.ops)

    def __len__(self) -> int:
        return len(self.ops)

    def get(self, op_id: str) -> Op | None:
        return next((o for o in self.ops if o.id == op_id), None)


@dataclass(frozen=True, slots=True)
class Completion:
    done: bool
    detail: str = ""  # when not done: what is still wrong, in plain words


class Recipe(ABC):
    """A manipulation. Subclasses set `spec` and implement `expand`."""

    spec: RecipeSpec
    version: int = 1

    @property
    def name(self) -> str:
        return self.spec.name

    @abstractmethod
    def expand(self, ctx: StepContext) -> RecipeGraph:
        """The ops that carry out this plan step on the pattern the step started from."""

    def check(self, ctx: StepContext) -> Completion:
        """Whether the step's result holds now, beyond every op being done. By default it does."""
        return Completion(True)

    def measure(self, ctx: StepContext) -> Mapping[str, float]:
        """Each parameter as the pattern has it now, in the parameter's own unit."""
        return {}


class RecipeRegistry:
    """The recipes a run knows, by name."""

    def __init__(self, recipes: Iterable[Recipe] = ()) -> None:
        self._by_name: dict[str, Recipe] = {}
        for r in recipes:
            self.add(r)

    def add(self, recipe: Recipe) -> None:
        if recipe.name in self._by_name:
            raise RecipeError(f"two recipes are called {recipe.name!r}")
        self._by_name[recipe.name] = recipe

    def get(self, name: str) -> Recipe | None:
        return self._by_name.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(self._by_name)

    def specs(self) -> dict[str, RecipeSpec]:
        """What plan validation reads."""
        return {n: r.spec for n, r in self._by_name.items()}


@dataclass(slots=True)
class StepContext:
    """Everything a recipe may read about one plan step and the pattern it works on."""

    box: Toolbox
    number: int  # 1-based, as in the plan
    plan_step: Mapping[str, Any]
    spec: RecipeSpec
    # op id -> the object that stands for it; filled in by the teacher's analysis
    bound: dict[str, Target] = field(default_factory=lambda: dict[str, Any]())

    @property
    def step_id(self) -> str:
        """The id provenance records for the step (the prefix of its variables)."""
        return f"s{self.number}"

    def var(self, param: str) -> str:
        """The pattern variable that holds a parameter's amount: `#s3_amount`."""
        return variable_name(self.number, param)

    def value(self, param: str) -> float | None:
        """The amount now, in the parameter's own unit; its default if the plan left it out; None
        if neither exists."""
        spec = self.spec.params.get(param)
        symbols = self.box.session.evaluation.symbols
        if self.var(param) in symbols:
            number = symbols[self.var(param)]
            unit = self.box.session.pattern.unit
            if spec is not None and unit in LENGTH_UNITS and spec.unit in LENGTH_UNITS:
                return number * LENGTH_UNITS[unit] / LENGTH_UNITS[spec.unit]
            return number
        return spec.default if spec is not None else None

    def option(self, name: str) -> str:
        """The choice the plan made, or the recipe's default for it."""
        chosen = cast("Mapping[str, str]", self.plan_step.get("options") or {}).get(name)
        if chosen is not None:
            return chosen
        opt = self.spec.options.get(name)
        if opt is None or opt.default is None:
            raise RecipeError(f"step {self.number}: option {name!r} has no value and no default")
        return opt.default

    def ref(self, role: str) -> str | None:
        """What the plan names for a role (a landmark, or `piece.section(a, b)`); None when the
        plan leaves out a role the recipe has a default rule for."""
        return cast("Mapping[str, str]", self.plan_step.get("refs") or {}).get(role)

    def need(self, role: str) -> str:
        found = self.ref(role)
        if found is None:
            raise RecipeError(f"step {self.number}: the plan does not say where ({role!r})")
        return found

    def label(self, op_id: str) -> str:
        """The name an add op gives its point: unique to the step and the op, so a retry or another
        step cannot collide with it."""
        return f"s{self.number}_{op_id}"

    def original(self, target: str, attr: str) -> str:
        """An attribute of an object as it was before this step edited it."""
        found = self.box.resolve(target, "object", "target")
        obj = self.box.maker(found.id)
        if obj is None:
            raise RecipeError(f"step {self.number}: {target!r} was not drawn with a tool")
        for entry in self.box.session.provenance(obj.id):
            if entry.kind != "edited" or entry.meta.step != self.step_id:
                continue
            for change in entry.changes:
                if change.field == attr and change.old is not None:
                    return change.old
        value = obj.get(attr)
        if value is None:
            raise RecipeError(f"step {self.number}: {target!r} has no {attr!r}")
        return value

    def number_text(self, value: float) -> str:
        return fmt_number(value)


def op_args(
    op: Op, ctx: StepContext, specs: Mapping[str, Any], names: Mapping[str, str]
) -> dict[str, Any]:
    """The arguments an op's call is made with: `@op` filled in with real labels, and the label of
    the point an add op makes (unique to the step and the op) when the recipe leaves it out."""
    args = dict(cast("Mapping[str, Any]", fill(op.args, names)))
    spec = specs.get(op.tool)
    if op.kind == "add" and spec is not None and "label" in spec.parameters and "label" not in args:
        args["label"] = ctx.label(op.id)
    return args


def graph_problems(recipe: Recipe, ctx: StepContext, specs: Mapping[str, Any]) -> list[str]:
    """What is wrong with a recipe's graph for one step: an unknown tool, arguments the tool does
    not accept, a landmark it creates that its spec does not list. For recipe tests."""
    from yoko_tools.spec import SpecError

    problems: list[str] = []
    graph = recipe.expand(ctx)
    placeholders = {op.id: f"P{i}" for i, op in enumerate(graph)}
    for op in graph:
        spec = specs.get(op.tool)
        if spec is None:
            problems.append(f"op {op.id}: there is no tool {op.tool!r}")
            continue
        try:
            spec.validate(op_args(op, ctx, specs, placeholders))
        except SpecError as err:
            problems.append(f"op {op.id}: {err}")
        if op.landmark is not None and op.landmark not in recipe.spec.creates:
            problems.append(f"op {op.id}: landmark {op.landmark} is not in the recipe's `creates`")
    made = {op.landmark for op in graph if op.landmark}
    for name in recipe.spec.creates:
        if name not in made:
            problems.append(f"the recipe says it creates {name}, but no op does")
    return problems
