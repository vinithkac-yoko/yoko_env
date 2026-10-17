"""Plans: ordered steps whose amounts are typed parameters that become pattern variables.

The planner decides every amount from the design intent; the drafter never invents a number. Each
parameter of each step becomes a variable `#s<step>_<parameter>` in the derived pattern (an
`increment` in format 0.6.8, a `variable` from 0.6.9), described by the step's summary, so a pattern
maker can change an amount in Seamly2D's variable table and the whole style updates.

Plan validation (before a person approves a plan) checks the structure against
`config/plan/schema.json`, the numbering of the steps, the units, and, when the recipes are known,
that every parameter a recipe needs is present, in its unit and within its range.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import jsonschema
from yoko_engine.binding import missing_measurements, size_grid
from yoko_engine.formula import is_valid_name
from yoko_engine.model import MeasurementSet, Pattern
from yoko_engine.session import PatternSession, SetVariable

from yoko_tools.numbers import fmt_number

SCHEMA_PATH = Path(__file__).resolve().parents[4] / "config/plan/schema.json"
LENGTH_UNITS = {"cm": 10.0, "mm": 1.0, "inch": 25.4}  # millimetres in one unit
OTHER_UNITS = ("deg", "count", "ratio")
SCALING_VARIABLES = ("#CM",)  # scales fixed numbers by body height; amounts use measurements


@dataclass(frozen=True, slots=True)
class RecipeParam:
    """What a recipe says about one parameter (Addendum 1 section 8)."""

    unit: str
    minimum: float | None = None
    maximum: float | None = None
    default: float | None = None
    required: bool = True


@dataclass(frozen=True, slots=True)
class RecipeRole:
    """A place a recipe needs the plan to name: a landmark, or a section of a piece."""

    description: str = ""
    kind: str = "point"  # point | curve | section | any
    required: bool = True  # False: a rule the pattern makers define supplies it by default


@dataclass(frozen=True, slots=True)
class RecipeOption:
    """A choice the recipe branches on, from a list the recipe defines."""

    choices: tuple[str, ...]
    default: str | None = None


@dataclass(frozen=True, slots=True)
class RecipeSpec:
    name: str
    params: Mapping[str, RecipeParam] = field(default_factory=lambda: dict[str, RecipeParam]())
    roles: Mapping[str, RecipeRole] = field(default_factory=lambda: dict[str, RecipeRole]())
    options: Mapping[str, RecipeOption] = field(default_factory=lambda: dict[str, RecipeOption]())
    creates: tuple[str, ...] = ()  # landmark names the recipe makes, for the steps after it


@dataclass(frozen=True, slots=True)
class PlanIssue:
    code: str
    message: str
    path: str  # where in the plan, for example steps[2].params.hem_flare
    severity: str = "error"


def load_schema() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(SCHEMA_PATH.read_text()))


def variable_name(step: int, param: str) -> str:
    return f"#s{step}_{param}"


def validate_plan(
    plan: Mapping[str, Any],
    pattern_unit: str = "cm",
    recipes: Mapping[str, RecipeSpec] | None = None,
    landmarks: Collection[str] | None = None,
    scaling_variables: Collection[str] = SCALING_VARIABLES,
) -> list[PlanIssue]:
    """Everything wrong with a plan, in plan order. An empty list means it can be approved.

    With `landmarks` (the names the pattern has), every landmark a step refers to must exist, in the
    pattern or made by an earlier step."""
    issues: list[PlanIssue] = []
    validator = jsonschema.Draft202012Validator(load_schema())
    found: list[Any] = list(validator.iter_errors(dict(plan)))  # pyright: ignore[reportUnknownMemberType]
    for err in sorted(found, key=lambda e: list(e.absolute_path)):
        issues.append(PlanIssue("schema", err.message, _path(err.absolute_path)))
    if issues:
        return issues  # the rest assumes a well-formed plan
    steps = cast("list[Mapping[str, Any]]", plan["steps"])
    known: set[str] | None = None if landmarks is None else set(landmarks)
    for i, step in enumerate(steps):
        where = f"steps[{i}]"
        if step["step"] != i + 1:
            issues.append(
                PlanIssue(
                    "step_number",
                    f"steps are numbered 1, 2, 3 ...; this one is {step['step']}",
                    f"{where}.step",
                )
            )
        params = cast("Mapping[str, Mapping[str, Any]]", step["params"])
        for name, amount in params.items():
            path = f"{where}.params.{name}"
            if not is_valid_name(variable_name(i + 1, name)):
                issues.append(
                    PlanIssue("bad_name", f"{name!r} cannot be part of a variable name", path)
                )
            issues.extend(_unit_issues(amount, pattern_unit, path))
            issues.extend(_scaling_issues(amount, scaling_variables, path))
        if recipes is not None:
            issues.extend(_recipe_issues(step, params, recipes, where))
            issues.extend(_role_issues(step, recipes, where, known))
        if known is not None and recipes is not None:
            recipe = recipes.get(cast(str, step["transformation"]))
            if recipe is not None:
                known.update(recipe.creates)
    return issues


_SECTION = re.compile(
    r"^(?P<piece>.+?)\.section\((?P<a>[^,()]+),\s*(?P<b>[^,()]+)\)(?P<mods>(?:\s*[+-]\s*[^+\-\s]+)*)$"
)
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?")


def section_parts(text: str) -> tuple[str, str, str, tuple[tuple[str, str], ...]] | None:
    """`piece.section(a, b) + x - y` -> (piece, a, b, (("+", "x"), ("-", "y"))); None if `text` is
    not a section."""
    m = _SECTION.match(text.strip())
    if m is None:
        return None
    mods = tuple(
        (sign, name) for sign, name in re.findall(r"([+-])\s*([^+\-\s]+)", m.group("mods") or "")
    )
    return m.group("piece").strip(), m.group("a").strip(), m.group("b").strip(), mods


def _scaling_issues(
    amount: Mapping[str, Any], scaling: Collection[str], path: str
) -> list[PlanIssue]:
    value = amount["value"]
    if not isinstance(value, str):
        return []
    names = set(re.findall(r"#[A-Za-z0-9_]+", value))
    bad = sorted(names & set(scaling))
    if not bad:
        return []
    return [
        PlanIssue(
            "scaling_variable",
            f"{', '.join(bad)} scales a fixed number by body height; write the amount as a "
            "formula over measurements (for example hip_circ/20) so that it adapts to each size",
            path,
        )
    ]


def _role_issues(
    step: Mapping[str, Any],
    recipes: Mapping[str, RecipeSpec],
    where: str,
    known: set[str] | None,
) -> list[PlanIssue]:
    """The step's `refs` against the recipe's roles, and its `options` against its choices."""
    recipe = recipes.get(cast(str, step["transformation"]))
    if recipe is None:
        return []  # reported already
    out: list[PlanIssue] = []
    refs = cast("Mapping[str, str]", step.get("refs", {}))
    options = cast("Mapping[str, str]", step.get("options", {}))
    for role, spec in recipe.roles.items():
        if spec.required and role not in refs:
            out.append(
                PlanIssue(
                    "missing_ref",
                    f"{recipe.name} needs {role}: {spec.description or 'a landmark'}",
                    f"{where}.refs",
                )
            )
    for role, target in refs.items():
        path = f"{where}.refs.{role}"
        spec = recipe.roles.get(role)
        if spec is None:
            out.append(PlanIssue("unknown_ref", f"{recipe.name} has no role {role}", path))
            continue
        section = section_parts(target)
        if section is not None:
            if spec.kind not in ("section", "any"):
                out.append(
                    PlanIssue("wrong_ref_kind", f"{role} is a {spec.kind}, not a section", path)
                )
            names = [section[1], section[2], *(n for _, n in section[3])]
        else:
            if spec.kind == "section":
                out.append(
                    PlanIssue("wrong_ref_kind", f"{role} is a section: piece.section(a, b)", path)
                )
            names = [target]
        for name in names:
            if not _NAME.fullmatch(name):
                out.append(PlanIssue("bad_landmark", f"{name!r} is not a landmark name", path))
            elif known is not None and name not in known:
                out.append(
                    PlanIssue("unknown_landmark", f"the pattern has no landmark {name}", path)
                )
    for name, spec_o in recipe.options.items():
        if name not in options and spec_o.default is None:
            out.append(
                PlanIssue(
                    "missing_option", f"{recipe.name} needs the option {name}", f"{where}.options"
                )
            )
    for name, choice in options.items():
        path = f"{where}.options.{name}"
        opt = recipe.options.get(name)
        if opt is None:
            out.append(PlanIssue("unknown_option", f"{recipe.name} has no option {name}", path))
        elif choice not in opt.choices:
            out.append(
                PlanIssue(
                    "bad_option",
                    f"{name} is {choice!r}; the choices are {', '.join(opt.choices)}",
                    path,
                )
            )
    return out


def _path(parts: Any) -> str:
    out = ""
    for p in parts:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out or "plan"


def _unit_issues(amount: Mapping[str, Any], pattern_unit: str, path: str) -> list[PlanIssue]:
    unit = cast(str, amount["unit"])
    value = amount["value"]
    if isinstance(value, str) and unit in LENGTH_UNITS and unit != pattern_unit:
        return [
            PlanIssue(
                "unit_mismatch",
                f"a formula is written in the pattern's unit ({pattern_unit}), not {unit}",
                path,
            )
        ]
    return []


def _recipe_issues(
    step: Mapping[str, Any],
    params: Mapping[str, Mapping[str, Any]],
    recipes: Mapping[str, RecipeSpec],
    where: str,
) -> list[PlanIssue]:
    recipe = recipes.get(cast(str, step["transformation"]))
    if recipe is None:
        return [
            PlanIssue(
                "unknown_recipe",
                f"there is no recipe {step['transformation']!r}",
                f"{where}.transformation",
            )
        ]
    out: list[PlanIssue] = []
    for name, spec in recipe.params.items():
        if spec.required and name not in params and spec.default is None:
            out.append(PlanIssue("missing_param", f"{recipe.name} needs {name}", f"{where}.params"))
    for name, amount in params.items():
        path = f"{where}.params.{name}"
        spec = recipe.params.get(name)
        if spec is None:
            out.append(PlanIssue("unknown_param", f"{recipe.name} has no parameter {name}", path))
            continue
        if amount["unit"] != spec.unit and not (
            amount["unit"] in LENGTH_UNITS and spec.unit in LENGTH_UNITS
        ):
            out.append(
                PlanIssue("wrong_unit", f"{name} is in {spec.unit}, not {amount['unit']}", path)
            )
            continue
        value = amount["value"]
        if isinstance(value, str):
            out.append(
                PlanIssue(
                    "range_unchecked",
                    f"{name} is a formula; its range cannot be checked",
                    path,
                    "warning",
                )
            )
            continue
        number = _in_unit(float(value), cast(str, amount["unit"]), spec.unit)
        if spec.minimum is not None and number < spec.minimum:
            out.append(
                PlanIssue(
                    "too_small",
                    f"{name} is {fmt_number(number)} {spec.unit}; the least is "
                    f"{fmt_number(spec.minimum)}",
                    path,
                )
            )
        if spec.maximum is not None and number > spec.maximum:
            out.append(
                PlanIssue(
                    "too_large",
                    f"{name} is {fmt_number(number)} {spec.unit}; the most is "
                    f"{fmt_number(spec.maximum)}",
                    path,
                )
            )
    return out


def _in_unit(value: float, from_unit: str, to_unit: str) -> float:
    if from_unit == to_unit or from_unit not in LENGTH_UNITS or to_unit not in LENGTH_UNITS:
        return value
    return value * LENGTH_UNITS[from_unit] / LENGTH_UNITS[to_unit]


def plan_variables(plan: Mapping[str, Any], pattern_unit: str = "cm") -> list[SetVariable]:
    """The `SetVariable` actions that put every amount of a valid plan into the pattern, in step
    order. A number in a length unit is converted to the pattern's unit; a formula is kept."""
    actions: list[SetVariable] = []
    for step in cast("list[Mapping[str, Any]]", plan["steps"]):
        params = cast("Mapping[str, Mapping[str, Any]]", step["params"])
        for name, amount in params.items():
            value = amount["value"]
            if isinstance(value, str):
                formula = value
            else:
                formula = fmt_number(
                    _in_unit(float(value), cast(str, amount["unit"]), pattern_unit)
                )
            actions.append(
                SetVariable(
                    variable_name(cast(int, step["step"]), name),
                    formula,
                    cast(str, step["summary"]),
                )
            )
    return actions


def errors(issues: list[PlanIssue]) -> list[PlanIssue]:
    """The issues that stop a plan from being approved (warnings do not)."""
    return [i for i in issues if i.severity == "error"]


def validate_plan_at_sizes(
    plan: Mapping[str, Any],
    pattern: Pattern,
    table: MeasurementSet,
    recipes: Mapping[str, RecipeSpec] | None = None,
    *,
    person: MeasurementSet | None = None,
    sizes: Sequence[float] | None = None,
    heights: Sequence[float] | None = None,
) -> list[PlanIssue]:
    """Does every amount work at every size of the table, and for a person's own file?

    The plan's amounts are put into the pattern as variables for each size (and each height the
    pattern switches on), exactly as they will be when the plan runs. An amount that cannot be
    computed at some size, or leaves the recipe's range at some size, is an issue that says where.
    Amounts are formulas over measurements, so what holds at one size is not enough."""
    unit = pattern.unit
    actions = plan_variables(plan, unit)
    owners = _owners(plan)
    points = size_grid(pattern, table, sizes=sizes, heights=heights)
    if person is not None:
        points += size_grid(pattern, person)
    failures: dict[tuple[str, str], tuple[str, list[str]]] = {}

    def note(path: str, code: str, message: str, where: str) -> None:
        failures.setdefault((path, code), (message, []))[1].append(where)

    for point in points:
        missing = missing_measurements(pattern, point.values)
        if missing:
            note(
                "plan",
                "missing_measurement",
                f"the measurements lack {', '.join(missing)}",
                point.label,
            )
            continue
        session = PatternSession(pattern, point.values)
        for action in actions:
            path = owners[action.name]
            result = session.apply(action)
            if not result.ok:
                err = result.error
                note(
                    path, "formula_error", err.message if err else "cannot be computed", point.label
                )
                continue
            if recipes is None:
                continue
            value = session.evaluation.symbols.get(action.name)
            spec = _param_spec(plan, recipes, path)
            if value is None or spec is None:
                continue
            number = _in_unit(value, unit, spec.unit)
            if spec.minimum is not None and number < spec.minimum - 1e-9:
                note(
                    path,
                    "too_small",
                    f"is {fmt_number(number)} {spec.unit}; the least is {fmt_number(spec.minimum)}",
                    point.label,
                )
            if spec.maximum is not None and number > spec.maximum + 1e-9:
                note(
                    path,
                    "too_large",
                    f"is {fmt_number(number)} {spec.unit}; the most is {fmt_number(spec.maximum)}",
                    point.label,
                )
    issues: list[PlanIssue] = []
    for (path, code), (message, where) in failures.items():
        shown = ", ".join(where[:4]) + (f" and {len(where) - 4} more" if len(where) > 4 else "")
        issues.append(PlanIssue(code, f"{message} (at {shown})", path))
    return issues


def _owners(plan: Mapping[str, Any]) -> dict[str, str]:
    """Variable name -> where in the plan its amount is."""
    out: dict[str, str] = {}
    for i, step in enumerate(cast("list[Mapping[str, Any]]", plan["steps"])):
        for name in cast("Mapping[str, Any]", step["params"]):
            out[variable_name(cast(int, step["step"]), name)] = f"steps[{i}].params.{name}"
    return out


def _param_spec(
    plan: Mapping[str, Any], recipes: Mapping[str, RecipeSpec], path: str
) -> RecipeParam | None:
    index = int(path.split("[")[1].split("]")[0])
    step = cast("list[Mapping[str, Any]]", plan["steps"])[index]
    recipe = recipes.get(cast(str, step["transformation"]))
    return recipe.params.get(path.rsplit(".", 1)[1]) if recipe else None
