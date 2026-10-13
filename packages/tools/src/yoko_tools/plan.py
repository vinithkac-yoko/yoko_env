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
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import jsonschema
from yoko_engine.formula import is_valid_name
from yoko_engine.session import SetVariable

from yoko_tools.runtime import fmt_number

SCHEMA_PATH = Path(__file__).resolve().parents[4] / "config/plan/schema.json"
LENGTH_UNITS = {"cm": 10.0, "mm": 1.0, "inch": 25.4}  # millimetres in one unit
OTHER_UNITS = ("deg", "count", "ratio")


@dataclass(frozen=True, slots=True)
class RecipeParam:
    """What a recipe says about one parameter (Addendum 1 section 8)."""

    unit: str
    minimum: float | None = None
    maximum: float | None = None
    default: float | None = None
    required: bool = True


@dataclass(frozen=True, slots=True)
class RecipeSpec:
    name: str
    params: Mapping[str, RecipeParam] = field(default_factory=lambda: dict[str, RecipeParam]())


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
) -> list[PlanIssue]:
    """Everything wrong with a plan, in plan order. An empty list means it can be approved."""
    issues: list[PlanIssue] = []
    validator = jsonschema.Draft202012Validator(load_schema())
    found: list[Any] = list(validator.iter_errors(dict(plan)))  # pyright: ignore[reportUnknownMemberType]
    for err in sorted(found, key=lambda e: list(e.absolute_path)):
        issues.append(PlanIssue("schema", err.message, _path(err.absolute_path)))
    if issues:
        return issues  # the rest assumes a well-formed plan
    steps = cast("list[Mapping[str, Any]]", plan["steps"])
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
        if recipes is not None:
            issues.extend(_recipe_issues(step, params, recipes, where))
    return issues


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
    if from_unit == to_unit or from_unit not in LENGTH_UNITS:
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
