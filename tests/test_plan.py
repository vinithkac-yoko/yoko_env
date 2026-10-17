"""Plans: the schema, validation before approval, and amounts that become variables."""

from __future__ import annotations

import copy
from typing import Any

from yoko_engine.session import PatternSession
from yoko_io.seamly import blank_pattern
from yoko_tools.plan import (
    RecipeParam,
    RecipeSpec,
    errors,
    plan_variables,
    validate_plan,
    variable_name,
)

PLAN: dict[str, Any] = {
    "schema_version": 1,
    "design_summary": "An A-line skirt with a 6 cm flare",
    "starting_pattern": {"id": "aldrich-womens-6th-basic", "pieces": ["A - Skirt Front"]},
    "steps": [
        {
            "step": 1,
            "transformation": "lengthen_at_line",
            "summary": "lengthen the skirt by 5 cm",
            "pieces": ["A - Skirt Front"],
            "params": {"amount": {"value": 50, "unit": "mm"}},
            "retrue": ["the side seams still match"],
            "check": "the hem is 5 cm lower",
        },
        {
            "step": 2,
            "transformation": "slash_and_spread",
            "summary": "add flare at the hem",
            "params": {
                "hem_flare": {"value": 6, "unit": "cm"},
                "slashes": {"value": 3, "unit": "count"},
                "waist_share": {"value": "#s1_amount/2", "unit": "cm"},
            },
        },
    ],
}
RECIPES = {
    "lengthen_at_line": RecipeSpec(
        "lengthen_at_line", {"amount": RecipeParam("cm", minimum=-30, maximum=60)}
    ),
    "slash_and_spread": RecipeSpec(
        "slash_and_spread",
        {
            "hem_flare": RecipeParam("cm", minimum=0, maximum=40),
            "slashes": RecipeParam("count", minimum=1, maximum=50),
            "waist_share": RecipeParam("cm", required=False),
        },
    ),
}


def codes(plan: dict[str, Any], recipes: Any = None, unit: str = "cm") -> list[str]:
    return [i.code for i in errors(validate_plan(plan, unit, recipes))]


def test_a_good_plan_has_no_issues() -> None:
    issues = validate_plan(PLAN, "cm", RECIPES)
    assert errors(issues) == []
    assert [i.code for i in issues] == ["range_unchecked"]  # waist_share is a formula
    assert validate_plan(PLAN) == []  # without recipes only the shape is checked


def test_the_shape_is_checked_with_the_place_of_the_mistake() -> None:
    bad = copy.deepcopy(PLAN)
    del bad["steps"][1]["summary"]
    bad["steps"][0]["params"]["amount"]["unit"] = "yards"
    issues = validate_plan(bad)
    assert {i.path for i in issues} == {"steps[1]", "steps[0].params.amount.unit"}
    assert all(i.code == "schema" for i in issues)
    # schema_version, design_summary and starting_pattern are missing, and no step
    assert codes({"steps": []}) == ["schema"] * 4


def test_steps_are_numbered_in_order() -> None:
    bad = copy.deepcopy(PLAN)
    bad["steps"][1]["step"] = 4
    assert codes(bad) == ["step_number"]


def test_a_formula_must_be_written_in_the_patterns_unit() -> None:
    bad = copy.deepcopy(PLAN)
    bad["steps"][1]["params"]["waist_share"]["unit"] = "mm"
    assert codes(bad) == ["unit_mismatch"]
    assert codes(bad, unit="mm") == []


def test_recipes_check_presence_units_and_ranges() -> None:
    bad = copy.deepcopy(PLAN)
    del bad["steps"][1]["params"]["slashes"]
    bad["steps"][0]["params"]["amount"] = {"value": 900, "unit": "mm"}  # 90 cm > 60 cm
    bad["steps"][1]["params"]["hem_flare"]["unit"] = "deg"
    bad["steps"][1]["params"]["colour"] = {"value": 1, "unit": "count"}
    assert sorted(codes(bad, RECIPES)) == [
        "missing_param",
        "too_large",
        "unknown_param",
        "wrong_unit",
    ]
    unknown = copy.deepcopy(PLAN)
    unknown["steps"][0]["transformation"] = "teleport"
    assert codes(unknown, RECIPES) == ["unknown_recipe"]


def test_a_formula_amount_is_a_warning_because_its_range_cannot_be_known() -> None:
    plan = copy.deepcopy(PLAN)
    plan["steps"][0]["params"]["amount"] = {"value": "waist/10", "unit": "cm"}
    issues = validate_plan(plan, "cm", RECIPES)
    assert errors(issues) == []
    assert [i.severity for i in issues] == ["warning", "warning"]


def test_amounts_become_named_variables_in_the_patterns_unit() -> None:
    actions = plan_variables(PLAN, "cm")
    assert [(a.name, a.formula) for a in actions] == [
        ("#s1_amount", "5"),  # 50 mm in cm
        ("#s2_hem_flare", "6"),
        ("#s2_slashes", "3"),
        ("#s2_waist_share", "#s1_amount/2"),
    ]
    assert actions[0].description == "lengthen the skirt by 5 cm"
    assert variable_name(3, "hem") == "#s3_hem"
    assert plan_variables(PLAN, "mm")[0].formula == "50"


def test_the_variables_land_in_the_pattern_and_evaluate() -> None:
    session = PatternSession(blank_pattern("cm"), {})
    for action in plan_variables(PLAN, "cm"):
        assert session.apply(action).ok, action
    symbols = session.evaluation.symbols
    assert symbols["#s1_amount"] == 5 and symbols["#s2_waist_share"] == 2.5


# ---- refs, options, sizes ---------------------------------------------------------------------

from pathlib import Path  # noqa: E402

from yoko_engine.binding import individual_table  # noqa: E402
from yoko_io.seamly import read_measurements, read_pattern  # noqa: E402
from yoko_tools.plan import (  # noqa: E402
    RecipeOption,
    RecipeRole,
    section_parts,
    validate_plan_at_sizes,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BASE = read_pattern(FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d")
TABLE = read_measurements(FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms")

SPREAD = RecipeSpec(
    "slash_and_spread",
    params={
        "spread": RecipeParam("cm", minimum=0, maximum=40),
        "slashes": RecipeParam("count", minimum=1, maximum=50),
    },
    roles={
        "edge": RecipeRole("the edge that gets wider", "section"),
        "pivot": RecipeRole("where the slashes hinge", "point", required=False),
    },
    options={"mode": RecipeOption(("parallel", "hinged"))},
    creates=("skirt_front.spread_corner",),
)


def spread_plan(**step: Any) -> dict[str, Any]:
    base = {
        "step": 1,
        "transformation": "slash_and_spread",
        "summary": "flare the hem",
        "params": {"spread": {"value": 6, "unit": "cm"}, "slashes": {"value": 3, "unit": "count"}},
        "refs": {"edge": "skirt_front.section(skirt_front.hem_CF, skirt_front.hem_side)"},
        "options": {"mode": "hinged"},
    }
    return {
        "schema_version": 1,
        "design_summary": "x",
        "starting_pattern": {"id": "aldrich-womens-6th-basic"},
        "steps": [{**base, **step}],
    }


LANDMARKS = {"skirt_front.hem_CF", "skirt_front.hem_side", "skirt_front.waist_CF"}
RECIPES2 = {"slash_and_spread": SPREAD}


def test_a_step_says_where_and_which_option() -> None:
    assert codes(spread_plan(), RECIPES2) == []
    assert validate_plan(spread_plan(), "cm", RECIPES2, LANDMARKS) == []


def test_refs_are_checked_against_the_recipes_roles_and_the_patterns_landmarks() -> None:
    bad = spread_plan(refs={"pivot": "skirt_front.waist_CF"})
    assert codes(bad, RECIPES2) == ["missing_ref"]  # the edge is required, the pivot is not
    wrong_role = spread_plan(refs={"edge": "skirt_front.section(a.b, c.d)", "corner": "a.b"})
    assert "unknown_ref" in codes(wrong_role, RECIPES2)
    kind = spread_plan(refs={"edge": "skirt_front.hem_CF"})
    assert codes(kind, RECIPES2) == ["wrong_ref_kind"]
    typo = spread_plan(refs={"edge": "skirt_front.section(skirt_front.hem_CF, skirt_front.hemm)"})
    issues = validate_plan(typo, "cm", RECIPES2, LANDMARKS)
    assert [i.code for i in issues] == ["unknown_landmark"] and "hemm" in issues[0].message
    odd = spread_plan(refs={"edge": "skirt_front.section(skirt_front.hem_CF, a b)"})
    assert codes(odd, RECIPES2) == ["bad_landmark"]


def test_a_section_can_add_and_remove_single_objects() -> None:
    parts = section_parts(
        "C - Bodice Front.section(bodice_front.SNP, bodice_front.underarm) + X1 - bodice_front.BP"
    )
    assert parts == (
        "C - Bodice Front",
        "bodice_front.SNP",
        "bodice_front.underarm",
        (("+", "X1"), ("-", "bodice_front.BP")),
    )
    assert section_parts("bodice_front.SNP") is None


def test_landmarks_made_by_a_step_can_be_used_by_the_next() -> None:
    plan = spread_plan()
    second = copy.deepcopy(plan["steps"][0])
    second["step"] = 2
    second["refs"] = {"edge": "skirt_front.section(skirt_front.hem_CF, skirt_front.spread_corner)"}
    plan["steps"].append(second)
    assert validate_plan(plan, "cm", RECIPES2, LANDMARKS) == []
    plan["steps"].reverse()
    plan["steps"][0]["step"], plan["steps"][1]["step"] = 1, 2
    assert [i.code for i in validate_plan(plan, "cm", RECIPES2, LANDMARKS)] == ["unknown_landmark"]


def test_options_come_from_the_recipes_list() -> None:
    assert codes(spread_plan(options={"mode": "diagonal"}), RECIPES2) == ["bad_option"]
    assert codes(spread_plan(options={}), RECIPES2) == ["missing_option"]
    assert codes(spread_plan(options={"mode": "hinged", "colour": "red"}), RECIPES2) == [
        "unknown_option"
    ]
    with_default = {
        "slash_and_spread": RecipeSpec(
            "slash_and_spread",
            SPREAD.params,
            SPREAD.roles,
            {"mode": RecipeOption(("parallel", "hinged"), "hinged")},
        )
    }
    assert codes(spread_plan(options={}), with_default) == []


def test_an_amount_may_not_use_the_height_scaling_variable() -> None:
    plan = spread_plan(
        params={
            "spread": {"value": "2*#CM", "unit": "cm"},
            "slashes": {"value": 3, "unit": "count"},
        }
    )
    assert codes(plan) == ["scaling_variable"]
    assert (
        codes(
            spread_plan(
                params={
                    "spread": {"value": "hip_circ/20", "unit": "cm"},
                    "slashes": {"value": 3, "unit": "count"},
                }
            )
        )
        == []
    )


def test_amounts_hold_at_every_size_of_the_table() -> None:
    plan = spread_plan(
        params={
            "spread": {"value": "hip_circ/20", "unit": "cm"},
            "slashes": {"value": 3, "unit": "count"},
        }
    )
    assert validate_plan_at_sizes(plan, BASE, TABLE, RECIPES2) == []
    tight = {
        "slash_and_spread": RecipeSpec(
            "slash_and_spread",
            {**SPREAD.params, "spread": RecipeParam("cm", minimum=0, maximum=4.5)},
            SPREAD.roles,
            SPREAD.options,
        )
    }
    issues = validate_plan_at_sizes(plan, BASE, TABLE, tight)
    assert [i.code for i in issues] == ["too_large"]
    # hip_circ/20 is 4.2 cm at size 34 and 5.0 at 42: it fails from the size where it passes 4.5
    assert "size 38" in issues[0].message or "size 40" in issues[0].message
    assert "size 34" not in issues[0].message


def test_an_amount_that_cannot_be_computed_at_a_size_says_so() -> None:
    plan = spread_plan(
        params={
            "spread": {"value": "no_such_measurement/2", "unit": "cm"},
            "slashes": {"value": 3, "unit": "count"},
        }
    )
    issues = validate_plan_at_sizes(plan, BASE, TABLE, RECIPES2)
    assert [i.code for i in issues] == ["formula_error"]
    assert issues[0].path == "steps[0].params.spread"


def test_the_plan_is_also_checked_for_a_persons_own_file() -> None:
    plan = spread_plan(
        params={
            "spread": {"value": "hip_circ/20", "unit": "cm"},
            "slashes": {"value": 3, "unit": "count"},
        }
    )
    values = dict(TABLE.values(38, 164))
    assert (
        validate_plan_at_sizes(plan, BASE, TABLE, RECIPES2, person=individual_table(values)) == []
    )
    values["hip_circ"] = (
        140.0  # 7 cm, more than the range allows? no: the range is 40; use a tighter one
    )
    tight = {
        "slash_and_spread": RecipeSpec(
            "slash_and_spread",
            {**SPREAD.params, "spread": RecipeParam("cm", maximum=6)},
            SPREAD.roles,
            SPREAD.options,
        )
    }
    issues = validate_plan_at_sizes(plan, BASE, TABLE, tight, person=individual_table(values))
    assert [i.code for i in issues] == ["too_large"] and "your measurements" in issues[0].message
    del values["hip_circ"]
    missing = validate_plan_at_sizes(plan, BASE, TABLE, RECIPES2, person=individual_table(values))
    assert [i.code for i in missing] == ["missing_measurement"]
