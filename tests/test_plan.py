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
