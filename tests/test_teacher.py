"""The recipe framework and the teacher, with one example recipe that lives in this file.

`LengthenOrShorten` is here only to exercise the framework. It is not drafting practice: how the
pattern makers lengthen a skirt is theirs to say (docs/manipulations/lengthen_or_shorten.md, every
rule there is a question). The framework itself is recipe-agnostic, and so are these tests.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from yoko_engine.formula import parse
from yoko_engine.landmarks import Landmarks
from yoko_engine.model import Measurement, MeasurementSet
from yoko_engine.session import ActionMeta, PatternSession
from yoko_io.seamly import blank_pattern
from yoko_tools.plan import (
    RecipeOption,
    RecipeParam,
    RecipeRole,
    RecipeSpec,
    plan_variables,
    validate_plan,
)
from yoko_tools.recipes import (
    Completion,
    Op,
    Recipe,
    RecipeError,
    RecipeGraph,
    RecipeRegistry,
    StepContext,
    fill,
    graph_problems,
)
from yoko_tools.runtime import Toolbox
from yoko_tools.spec import all_tools
from yoko_tools.teacher import DONE, Call, Teacher, teacher_sizes

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


# -- the framework ---------------------------------------------------------------------------------
def test_a_graph_refuses_an_op_that_needs_something_later() -> None:
    first = Op("a", "add", "point_origin", {"label": "A", "x": 1, "y": 1})
    later = Op(
        "b", "add", "point_at_distance_angle", {"base_point": "@c", "length": "1", "angle": "0"}
    )
    with pytest.raises(RecipeError, match="needs 'c'"):
        RecipeGraph((first, later))
    with pytest.raises(RecipeError, match="two ops"):
        RecipeGraph((first, first))
    ok = RecipeGraph((first, Op("c", "add", "point_origin", {"label": "C"}, needs=("a",))))
    assert [o.id for o in ok] == ["a", "c"]
    assert Op("d", "add", "x", {"p": ["@a", {"q": "@b+@a"}]}).tokens() == ("a", "b")
    assert fill({"p": ["@a", {"q": "@b+1"}]}, {"a": "A1", "b": "B2"}) == {
        "p": ["A1", {"q": "B2+1"}]
    }


def test_the_example_recipe_is_a_well_formed_graph() -> None:
    box = toy_box(plan(5))
    ctx = StepContext(box, 1, plan(5)["steps"][0], LengthenOrShorten.spec)
    assert graph_problems(LengthenOrShorten(), ctx, SPECS) == []
    assert ctx.value("amount") == pytest.approx(5)
    assert ctx.option("mark") == "yes" and ctx.var("amount") == "#s1_amount"
    with pytest.raises(RecipeError, match="does not say where"):
        ctx.need("nowhere")


def test_a_registry_gives_plan_validation_its_specs() -> None:
    issues = validate_plan(
        plan(5), "cm", RECIPES.specs(), landmarks={"skirt.hem_left", "skirt.hem_right"}
    )
    assert issues == []
    assert [i.code for i in validate_plan(plan(99), "cm", RECIPES.specs())] == ["too_large"]


# -- the teacher on a clean state ------------------------------------------------------------------
def test_the_acceptable_set_is_every_ready_op_and_the_composite() -> None:
    the_plan = plan(5)
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    accepted = teacher.expert(box, the_plan)
    assert accepted is not None
    assert [(c.tool, c.op) for c in accepted] == [
        ("edit_point_at_distance_angle", "hem_left"),
        ("edit_point_at_distance_angle", "hem_right"),
        ("apply_step", None),
    ]  # the notch waits for the hem_right edit
    assert accepted[0].args == {"target": "skirt.hem_left", "length": "20 + #s1_amount"}
    assert accepted[2].args == {"step": 1}
    without = Teacher(RECIPES, composites=False).expert(box, the_plan)
    assert without is not None and len(without) == 2


def test_following_the_teacher_reaches_done_and_does_what_the_plan_says() -> None:
    the_plan = plan(5)
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    before = length_of(box, "H1")
    seen: list[str | None] = []
    for _ in range(10):
        accepted = teacher.expert(box, the_plan)
        assert accepted
        pick = next(c for c in accepted if c.tool != "apply_step")
        if pick == DONE:
            break
        seen.append(pick.op)
        do(box, pick)
    assert seen == ["hem_left", "hem_right", "notch"]
    assert length_of(box, "H1") - before == pytest.approx(50)  # 5 cm, in millimetres
    assert length_of(box, "H2") - before == pytest.approx(50)
    ids, _ = box.landmarks.resolve(box.session.evaluation) if box.landmarks else ({}, [])
    assert "skirt.hem_notch" in ids
    analysis = teacher.analyse(box, the_plan)
    assert analysis.complete and analysis.step(1).state == "done"
    assert all(o.by == "provenance" for o in analysis.step(1).ops)


def test_ops_may_be_done_in_any_order() -> None:
    the_plan = plan(5)
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    accepted = teacher.expert(box, the_plan)
    assert accepted
    do(box, accepted[1])  # hem_right first
    after = teacher.expert(box, the_plan)
    assert after
    assert [c.op for c in after if c.tool != "apply_step"] == ["hem_left", "notch"]


def test_an_edit_that_builds_on_the_old_formula_is_not_applied_twice() -> None:
    the_plan = plan(5)
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    accepted = teacher.expert(box, the_plan)
    assert accepted
    do(box, accepted[0])
    again = teacher.expert(box, the_plan)
    assert again
    # hem_left is done; hem_right's call is unchanged; nothing says "20 + #s1_amount + #s1_amount"
    assert all("#s1_amount + #s1_amount" not in str(c.args) for c in again)
    status = teacher.analyse(box, the_plan).step(1)
    assert status.ops[0].status == "done" and status.ops[0].by == "provenance"
    assert status.measured["amount"] == pytest.approx(5) and status.targets[
        "amount"
    ] == pytest.approx(5)


def test_the_option_changes_the_graph() -> None:
    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    accepted = teacher_for(box).expert(box, the_plan)
    assert accepted
    assert [c.op for c in accepted if c.tool != "apply_step"] == ["hem_left", "hem_right"]


def test_a_second_step_starts_when_the_first_is_complete_and_the_first_is_not_asked_again() -> None:
    the_plan = plan(5, 3, mark="no")
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    for _ in range(2):
        accepted = teacher.expert(box, the_plan)
        assert accepted
        do(box, accepted[0])
    analysis = teacher.analyse(box, the_plan)
    assert analysis.active == 2 and analysis.step(1).state == "done"
    accepted = teacher.acceptable(box, the_plan, analysis)
    assert accepted and accepted[0].args["length"] == "20 + #s1_amount + #s2_amount"
    do(box, accepted[0])
    # step 1's own check (hem moved 5) is now false: the hem moved 8. A later step has begun, so
    # step 1 stays complete.
    analysis = teacher.analyse(box, the_plan)
    assert analysis.step(1).state == "done" and analysis.active == 2
    left = teacher.expert(box, the_plan)
    assert left and [c.op for c in left if c.tool != "apply_step"] == ["hem_right"]


def test_the_check_must_hold_before_a_step_is_complete() -> None:
    class Strict(LengthenOrShorten):
        spec = RecipeSpec(
            "lengthen_or_shorten", LengthenOrShorten.spec.params, LengthenOrShorten.spec.roles
        )

        def check(self, ctx: StepContext) -> Completion:
            return Completion(False, "never satisfied")

        def expand(self, ctx: StepContext) -> RecipeGraph:
            graph = super().expand(ctx)
            return RecipeGraph(tuple(o for o in graph if o.id != "notch"))

    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    teacher = Teacher(RecipeRegistry([Strict()]))
    for _ in range(2):
        accepted = teacher.expert(box, the_plan)
        assert accepted
        do(box, accepted[0])
    analysis = teacher.analyse(box, the_plan)
    step = analysis.step(1)
    assert all(o.status == "done" for o in step.ops)
    assert step.state == "active" and step.check == Completion(False, "never satisfied")
    assert teacher.expert(box, the_plan) == []  # nothing left to do, and still not complete


# -- no label --------------------------------------------------------------------------------------
def test_a_step_no_recipe_covers_has_no_label() -> None:
    the_plan = plan(5)
    the_plan["steps"][0]["transformation"] = "pleats"
    box = toy_box(the_plan)
    teacher = Teacher(RECIPES)
    assert teacher.expert(box, the_plan) is None
    analysis = teacher.analyse(box, the_plan)
    assert analysis.active == 1 and not analysis.step(1).covered


def test_a_state_without_the_plans_variables_cannot_be_labelled() -> None:
    box = toy_box()  # the plan was never applied
    teacher = Teacher(RECIPES)
    analysis = teacher.analyse(box, plan(5))
    assert "variables are not in the pattern" in analysis.problem
    assert teacher.expert(box, plan(5)) is None


# -- equivalent constructions ---------------------------------------------------------------------
def test_an_op_is_done_when_another_construction_makes_the_same_geometry_at_every_size() -> None:
    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    # "25" is 20 + 5, and the length does not depend on the size: the same at every size
    assert box.call("edit_point_at_distance_angle", {"target": "H1", "length": "25"}, STEP1)["ok"]
    status = teacher.analyse(box, the_plan).step(1)
    assert status.ops[0].status == "done" and status.ops[0].by == "geometry"
    assert status.ops[1].status == "ready"


def test_a_match_at_the_base_size_alone_does_not_count() -> None:
    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    assert len(teacher.sizes.others) == 2
    # 25 at the base size (waist 70), but it grows with the waist: not the same at other sizes
    edit = {"target": "H1", "length": "waist/70*25"}
    assert box.call("edit_point_at_distance_angle", edit, STEP1)["ok"]
    status = teacher.analyse(box, the_plan).step(1)
    assert status.ops[0].status == "ready"
    individual = Teacher(RECIPES)  # no other sizes known: the base size decides
    assert individual.analyse(box, the_plan).step(1).ops[0].status == "done"


def test_an_action_is_labelled_by_comparing_it_with_the_acceptable_set() -> None:
    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    accepted = teacher.expert(box, the_plan)
    assert accepted
    exact = teacher.label(box, the_plan, accepted[0])
    assert (exact.on_plan, exact.step, exact.op) == (True, 1, "hem_left")
    # the same edit with a different but equal formula: the equivalent construction counts
    same = Call("edit_point_at_distance_angle", {"target": "H1", "length": "25"})
    assert teacher.label(box, the_plan, same).on_plan is True
    assert teacher.label(box, the_plan, same).op == "hem_left"
    wrong = Call("edit_point_at_distance_angle", {"target": "H1", "length": "26"})
    assert teacher.label(box, the_plan, wrong).on_plan is False
    other = Call(
        "point_at_distance_angle", {"label": "X", "base_point": "A", "length": "3", "angle": "0"}
    )
    assert teacher.label(box, the_plan, other).on_plan is False


def test_an_added_point_in_the_right_place_counts_whatever_its_name() -> None:
    the_plan = plan(5)
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    for c in (teacher.expert(box, the_plan) or [])[:2]:
        do(box, c)
    notch = Call(
        "point_at_distance_angle",
        {"label": "Z9", "base_point": "H2", "length": "2", "angle": "270"},
    )
    label = teacher.label(box, the_plan, notch)
    assert (label.on_plan, label.op) == (True, "notch")
    # a point 2 cm below H2 at the base size only
    sneaky = Call(
        "point_at_distance_angle",
        {"label": "Z8", "base_point": "H2", "length": "waist/35", "angle": "270"},
    )
    assert teacher.label(box, the_plan, sneaky).on_plan is False


# -- recovery --------------------------------------------------------------------------------------
def test_something_off_plan_made_is_taken_back_by_undo_or_by_deleting_it() -> None:
    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    do(
        box,
        Call(
            "point_at_distance_angle",
            {"label": "X", "base_point": "A", "length": "3", "angle": "0"},
            1,
        ),
        on_plan=False,
        author="model",
    )
    accepted = teacher.expert(box, the_plan)
    assert accepted
    assert [c.tool for c in accepted] == ["undo", "delete_point_at_distance_angle"]
    # recovery is checked against the set: deleting is on plan, so is undo, a new op is not
    assert teacher.label(box, the_plan, accepted[1]).on_plan is True
    ops = Call(
        "edit_point_at_distance_angle", {"target": "H1", "length": "20 + #s1_amount"}, 1, "hem_left"
    )
    assert teacher.label(box, the_plan, ops).on_plan is False  # first clean up
    do(box, accepted[1])
    after = teacher.expert(box, the_plan)
    assert after and after[0].op == "hem_left"
    assert not teacher.analyse(box, the_plan).leftovers


def test_a_leftover_other_things_were_built_on_is_taken_back_leaf_first() -> None:
    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    for label, base in (("X", "A"), ("Y", "X")):
        do(
            box,
            Call(
                "point_at_distance_angle",
                {"label": label, "base_point": base, "length": "3", "angle": "0"},
            ),
            on_plan=False,
            author="model",
        )
    accepted = teacher.expert(box, the_plan)
    assert accepted
    deletes = [c for c in accepted if c.tool.startswith("delete_")]
    assert len(deletes) == 1  # only Y: X has a dependent
    do(box, deletes[0])
    again = teacher.expert(box, the_plan)
    assert again and any(c.tool.startswith("delete_") for c in again)  # now X


def test_a_wrong_edit_is_put_back_or_replaced_by_what_the_recipe_requires() -> None:
    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    do(
        box,
        Call("edit_point_at_distance_angle", {"target": "H1", "length": "31"}, 1),
        on_plan=False,
        author="model",
    )
    analysis = teacher.analyse(box, the_plan)
    assert [(left.name, left.kind, dict(left.restore)) for left in analysis.leftovers] == [
        ("H1", "edited", {"length": "20"})
    ]
    accepted = teacher.acceptable(box, the_plan, analysis)
    assert accepted
    assert [c.tool for c in accepted] == [
        "undo",
        "edit_point_at_distance_angle",  # back to 20
        "edit_point_at_distance_angle",  # or straight to what the recipe requires
    ]
    assert accepted[1].args["length"] == "20"
    assert accepted[2].args["length"] == "20 + #s1_amount" and accepted[2].op == "hem_left"
    do(box, accepted[2])  # straight to the target: the recipe's edit
    assert not teacher.analyse(box, the_plan).leftovers
    assert length_of(box, "H1") == pytest.approx(length_of(toy_box(the_plan), "H1") + 50)


def test_an_off_plan_edit_that_is_reverted_leaves_nothing_behind() -> None:
    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    for length in ("31", "20"):
        do(
            box,
            Call("edit_point_at_distance_angle", {"target": "H1", "length": length}, 1),
            on_plan=False,
            author="model",
        )
    assert not teacher.analyse(box, the_plan).leftovers


# -- done ------------------------------------------------------------------------------------------
def test_done_is_acceptable_only_when_every_step_is_complete_and_nothing_is_left() -> None:
    the_plan = plan(5, mark="no")
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    assert DONE not in (teacher.expert(box, the_plan) or [])
    for _ in range(2):
        accepted = teacher.expert(box, the_plan)
        assert accepted
        do(box, accepted[0])
    assert teacher.expert(box, the_plan) == [DONE]
    do(
        box,
        Call(
            "point_at_distance_angle",
            {"label": "X", "base_point": "A", "length": "3", "angle": "0"},
        ),
        on_plan=False,
        author="model",
    )
    assert DONE not in (teacher.expert(box, the_plan) or [])


def test_labelling_does_not_change_the_pattern() -> None:
    the_plan = plan(5)
    box = toy_box(the_plan)
    teacher = teacher_for(box)
    before = box.session.state_hash()
    accepted = teacher.expert(box, the_plan)
    assert accepted
    teacher.label(box, the_plan, accepted[0])
    teacher.label(box, the_plan, Call("point_origin", {"label": "Q", "x": 1, "y": 1}))
    assert box.session.state_hash() == before


def test_the_canonical_form_of_a_call_ignores_labels_and_spacing() -> None:
    box = toy_box()
    a = box.canonical(
        "point_at_distance_angle",
        {"label": "P", "base_point": "H1", "length": "2 + 1", "angle": "270"},
    )
    b = box.canonical(
        "point_at_distance_angle",
        {
            "label": "Q",
            "base_point": "#"
            + str(
                box.session.evaluation.points
                and next(i for i, g in box.session.evaluation.points.items() if g.label == "H1")
            ),
            "length": "2+1",
            "angle": "270",
        },
    )
    assert a == b
    c = box.canonical(
        "point_at_distance_angle",
        {"label": "P", "base_point": "H1", "length": "2+2", "angle": "270"},
    )
    assert a != c


# -- the basic set ---------------------------------------------------------------------------------
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


def basic_skirt() -> tuple[Toolbox, dict[str, Any], Teacher]:
    from yoko_io.library import DirectoryLibrary

    library = DirectoryLibrary(ROOT / "library", ROOT / "fixtures")
    _, pattern, table = library.load("aldrich-womens-6th-basic")
    the_plan = plan(5)
    the_plan["steps"][0]["refs"] = {"hem": "skirt_back.hem_left"}
    session = PatternSession(pattern, table)
    landmarks = Landmarks.from_mapping(
        {"version": 1, "landmarks": {"skirt_back.hem_left": {"label": "A3"}}}
    )
    box = Toolbox(session, SPECS, landmarks=landmarks)
    for action in plan_variables(the_plan):
        assert session.apply(action, ActionMeta(author="plan")).ok
    others = teacher_sizes(pattern, table, session.measurements)
    return box, the_plan, Teacher(RecipeRegistry([HemOnly()]), others=others)


def test_the_teacher_works_on_the_real_basic_set_at_the_table_sizes() -> None:
    box, the_plan, teacher = basic_skirt()
    assert len(teacher.sizes.others) == 2
    accepted = teacher.expert(box, the_plan)
    assert accepted and accepted[0].args["length"] == "height_waist_side_to_knee + #s1_amount"
    do(box, accepted[0])
    assert teacher.expert(box, the_plan) == [DONE]
    # the same edit written another way is the same thing at every size of the table
    other, _, _ = basic_skirt()
    edit = {"target": "A3", "length": "height_waist_side_to_knee + 5"}
    assert other.call("edit_point_at_distance_angle", edit, STEP1)["ok"]
    assert teacher.analyse(other, the_plan).step(1).ops[0].by == "geometry"
    # but not a fixed length that matches only the base size
    third, _, _ = basic_skirt()
    base_length = third.session.measurements["height_waist_side_to_knee"]
    edit = {"target": "A3", "length": f"{base_length + 5}"}
    assert third.call("edit_point_at_distance_angle", edit, STEP1)["ok"]
    assert teacher.analyse(third, the_plan).step(1).ops[0].status == "ready"
