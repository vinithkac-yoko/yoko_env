"""Shared by the teacher and environment tests: one example recipe and a toy skirt.

`LengthenOrShorten` exists only to exercise the framework. It is not drafting practice: how the
pattern makers lengthen a skirt is theirs to say (docs/manipulations/lengthen_or_shorten.md, every
rule there is a question). The framework itself is recipe-agnostic, and so are the tests.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from yoko_engine.formula import parse
from yoko_engine.landmarks import Landmarks
from yoko_engine.model import Measurement, MeasurementSet
from yoko_engine.session import ActionMeta, PatternSession
from yoko_io.seamly import blank_pattern
from yoko_tools.plan import RecipeOption, RecipeParam, RecipeRole, RecipeSpec, plan_variables
from yoko_tools.recipes import (
    Completion,
    Op,
    Recipe,
    RecipeGraph,
    RecipeRegistry,
    StepContext,
)
from yoko_tools.runtime import Toolbox
from yoko_tools.spec import all_tools
from yoko_tools.teacher import Call, Teacher, teacher_sizes

ROOT = Path(__file__).resolve().parents[1]
SPECS = all_tools(ROOT / "config/tools")
TABLE = MeasurementSet("cm", 38.0, 164.0, (Measurement("waist", 70.0, 2.0),))


class LengthenOrShorten(Recipe):
    """Example: move the two hem points down (or up) by an amount, then mark the hem."""

    spec = RecipeSpec(
        "lengthen_or_shorten",
        params={"amount": RecipeParam("cm", -10.0, 30.0, 0.0)},
        roles={
            "hem_left": RecipeRole("the hem point at the left", "point"),
            "hem_right": RecipeRole("the hem point at the right", "point"),
        },
        options={"mark": RecipeOption(("yes", "no"), "yes")},
        creates=("skirt.hem_notch",),
    )

    def expand(self, ctx: StepContext) -> RecipeGraph:
        ops: list[Op] = []
        for role in ("hem_left", "hem_right"):
            target = ctx.need(role)
            ops.append(
                Op(
                    role,
                    "edit",
                    "edit_point_at_distance_angle",
                    {
                        "target": target,
                        "length": f"{ctx.original(target, 'length')} + {ctx.var('amount')}",
                    },
                )
            )
        if ctx.option("mark") == "yes":
            ops.append(
                Op(
                    "notch",
                    "add",
                    "point_at_distance_angle",
                    {"base_point": ctx.need("hem_right"), "length": "2", "angle": "270"},
                    needs=("hem_right",),
                    landmark="skirt.hem_notch",
                )
            )
        return RecipeGraph(tuple(ops))

    def measure(self, ctx: StepContext) -> Mapping[str, float]:
        target = ctx.need("hem_left")
        obj = ctx.box.maker(ctx.box.resolve(target, "object", "t").id)
        assert obj is not None
        values = {**ctx.box.session.measurements, **ctx.box.session.evaluation.symbols}
        now = parse(obj.get("length") or "0").evaluate(values)
        was = parse(ctx.original(target, "length")).evaluate(values)
        return {"amount": now - was}

    def check(self, ctx: StepContext) -> Completion:
        got = self.measure(ctx)["amount"]
        want = ctx.value("amount")
        assert want is not None
        if abs(got - want) < 1e-9:
            return Completion(True)
        return Completion(False, f"the hem moved {got:g} cm, the plan says {want:g}")


RECIPES = RecipeRegistry([LengthenOrShorten()])


def plan(*amounts: float, mark: str = "yes") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "design_summary": "a longer skirt",
        "starting_pattern": {"id": "toy-skirt"},
        "steps": [
            {
                "step": i + 1,
                "transformation": "lengthen_or_shorten",
                "summary": f"lengthen the skirt by {a} cm",
                "params": {"amount": {"value": a, "unit": "cm"}},
                "refs": {"hem_left": "skirt.hem_left", "hem_right": "skirt.hem_right"},
                "options": {"mark": mark},
            }
            for i, a in enumerate(amounts)
        ],
    }


def toy_box(the_plan: Mapping[str, Any] | None = None) -> Toolbox:
    """A skirt in four points, drawn through the tools, with its plan applied as variables."""
    session = PatternSession(blank_pattern("cm"), TABLE)
    landmarks = Landmarks.from_mapping(
        {
            "version": 1,
            "landmarks": {
                "skirt.hem_left": {"label": "H1"},
                "skirt.hem_right": {"label": "H2"},
            },
        }
    )
    box = Toolbox(session, SPECS, landmarks=landmarks)
    for name, args in [
        ("point_origin", {"label": "A", "x": 10, "y": 10}),
        (
            "point_at_distance_angle",
            {"label": "B", "base_point": "A", "length": "waist/4", "angle": "0"},
        ),
        (
            "point_at_distance_angle",
            {"label": "H1", "base_point": "A", "length": "20", "angle": "270"},
        ),
        (
            "point_at_distance_angle",
            {"label": "H2", "base_point": "B", "length": "20", "angle": "270"},
        ),
    ]:
        assert box.call(name, args)["ok"], name
    if the_plan is not None:
        for action in plan_variables(the_plan):
            assert session.apply(action, ActionMeta(author="plan")).ok
    return box


# an action taken while step 1 is active, before anyone has matched it to an op
STEP1 = ActionMeta(step="s1", author="model")


def teacher_for(box: Toolbox, **kw: Any) -> Teacher:
    return Teacher(
        RECIPES, others=teacher_sizes(box.session.pattern, TABLE, box.session.measurements), **kw
    )


def do(
    box: Toolbox, call: Call, *, on_plan: bool = True, author: str = "teacher"
) -> dict[str, Any]:
    meta = ActionMeta(
        step=f"s{call.step}" if call.step else None, op=call.op, author=author, on_plan=on_plan
    )
    result = box.call(call.tool, call.args, meta)
    assert result["ok"], (call, result)
    return result


def length_of(box: Toolbox, label: str) -> float:
    return box.session.evaluation.point_mm(label)[1]


def toy_task(the_plan: Mapping[str, Any] | None = None, **kw: Any) -> Any:
    """The toy skirt as a task (the plan's variables are put in by the environment)."""
    from yoko_env import Task

    box = toy_box()
    return Task(box.session.pattern, TABLE, the_plan, box.landmarks, **kw)


class HemOnly(Recipe):
    """Example on the real skirt: edit the formula of one hem point."""

    spec = RecipeSpec(
        "lengthen_or_shorten",
        params={"amount": RecipeParam("cm", -10.0, 30.0, 0.0)},
        roles={"hem": RecipeRole("the hem point", "point")},
    )

    def expand(self, ctx: StepContext) -> RecipeGraph:
        t = ctx.need("hem")
        length = f"{ctx.original(t, 'length')} + {ctx.var('amount')}"
        return RecipeGraph(
            (Op("hem", "edit", "edit_point_at_distance_angle", {"target": t, "length": length}),)
        )
