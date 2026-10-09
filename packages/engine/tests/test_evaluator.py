"""Evaluator tests on small hand-computed patterns (coordinates: x right, y DOWN, mm)."""

from __future__ import annotations

import pytest
from yoko_engine.evaluator import evaluate
from yoko_engine.model import DraftBlock, Obj, Pattern, Variable


def obj(id_: int, kind: str, tag: str = "point", **attrs: str) -> Obj:
    return Obj(id_, tag, kind, tuple(attrs.items()))


def pattern(*objs: Obj, variables: tuple[Variable, ...] = (), unit: str = "cm") -> Pattern:
    return Pattern(unit, "0.6.8", "m.smms", variables, (DraftBlock("block", tuple(objs)),))


def origin(id_: int = 1, name: str = "A", x: str = "0", y: str = "0") -> Obj:
    return obj(id_, "single", name=name, x=x, y=y)


def at(ev_point: tuple[float, float], x: float, y: float) -> None:
    assert ev_point[0] == pytest.approx(x, abs=1e-6)
    assert ev_point[1] == pytest.approx(y, abs=1e-6)


def test_origin_is_converted_from_the_pattern_unit() -> None:
    ev = evaluate(pattern(origin(x="2", y="3")), {})
    at(ev.point_mm("A"), 20.0, 30.0)
    assert not ev.issues
    cm = evaluate(pattern(origin(x="2", y="3"), unit="mm"), {})
    at(cm.point_mm("A"), 2.0, 3.0)
    inch = evaluate(pattern(origin(x="1", y="0"), unit="inch"), {})
    at(inch.point_mm("A"), 25.4, 0.0)


def test_origin_defaults_to_10_when_absent() -> None:
    ev = evaluate(pattern(obj(1, "single", name="A")), {})
    at(ev.point_mm("A"), 100.0, 100.0)


def test_end_line_angle_zero_is_right_and_270_is_down() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
            obj(3, "endLine", name="C", basePoint="1", length="5", angle="270"),
            obj(4, "endLine", name="D", basePoint="1", length="10", angle="90"),
        ),
        {},
    )
    at(ev.point_mm("B"), 100.0, 0.0)
    at(ev.point_mm("C"), 0.0, 50.0)  # 5 cm below
    at(ev.point_mm("D"), 0.0, -100.0)  # 10 cm above
    assert not ev.issues


def test_formulas_see_measurements_and_variables() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="#half*bust/2", angle="0"),
            variables=(Variable("#half", "0.5"),),
        ),
        {"bust": 80.0},
    )
    at(ev.point_mm("B"), 200.0, 0.0)  # 0.5 * 80 / 2 = 20 cm


def test_line_variables_are_registered_and_usable() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
            obj(3, "endLine", name="C", basePoint="2", length="Line_A_B/2", angle="0"),
        ),
        {},
    )
    assert ev.symbols["Line_A_B"] == pytest.approx(10.0)
    at(ev.point_mm("C"), 150.0, 0.0)
    assert ev.deps[3] == frozenset({2})  # base point 2; Line_A_B is owned by object 2


def test_angle_variable_is_truncated_to_5_decimals() -> None:
    # A line at 30 degrees: the exact angle has noise; Seamly2D floors it to 5 decimals.
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="33.333333"),
        ),
        {},
    )
    assert ev.symbols["AngleLine_A_B"] == pytest.approx(33.33333, abs=1e-12)


def test_along_line_and_current_length() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
            obj(
                3, "alongLine", name="M", firstPoint="1", secondPoint="2", length="CurrentLength/4"
            ),
            obj(4, "alongLine", name="N", firstPoint="2", secondPoint="1", length="1"),
        ),
        {},
    )
    at(ev.point_mm("M"), 25.0, 0.0)
    at(ev.point_mm("N"), 90.0, 0.0)  # 1 cm from B towards A
    assert "CurrentLength" not in ev.symbols  # it only exists while the tool evaluates
    assert "Line_A_M" in ev.symbols
    assert "Line_M_B" in ev.symbols


def test_along_line_on_a_null_line_returns_the_first_point() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="0", angle="0"),
            obj(3, "alongLine", name="M", firstPoint="1", secondPoint="2", length="5"),
        ),
        {},
    )
    at(ev.point_mm("M"), 0.0, 0.0)  # QLineF::setLength ignores a null line


def test_normal_points_left_hand_of_the_line() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
            obj(3, "normal", name="N", firstPoint="1", secondPoint="2", length="5", angle="0"),
            obj(4, "normal", name="P", firstPoint="1", secondPoint="2", length="5", angle="90"),
        ),
        {},
    )
    at(ev.point_mm("N"), 0.0, -50.0)  # 90 degrees counter-clockwise on screen: up
    at(ev.point_mm("P"), -50.0, 0.0)  # extra angle 90: points left


def test_bisector_halves_the_angle() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
            obj(3, "endLine", name="C", basePoint="1", length="10", angle="90"),
            obj(
                4,
                "bisector",
                name="D",
                firstPoint="2",
                secondPoint="1",
                thirdPoint="3",
                length="10",
            ),
        ),
        {},
    )
    at(ev.point_mm("D"), 70.710678, -70.710678)


def test_bisector_reflex_branch() -> None:
    # first = up, third = right: the counter-clockwise angle from first to third is 270 (> 180),
    # so the code takes the other branch and still bisects the 90 degree gap.
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="90"),
            obj(3, "endLine", name="C", basePoint="1", length="10", angle="0"),
            obj(
                4,
                "bisector",
                name="D",
                firstPoint="2",
                secondPoint="1",
                thirdPoint="3",
                length="10",
            ),
        ),
        {},
    )
    at(ev.point_mm("D"), 70.710678, -70.710678)


def test_intersect_xy_takes_x_of_first_and_y_of_second() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
            obj(3, "endLine", name="C", basePoint="1", length="10", angle="90"),
            obj(4, "intersectXY", name="X", firstPoint="2", secondPoint="3"),
        ),
        {},
    )
    at(ev.point_mm("X"), 100.0, -100.0)


def test_line_intersect_axis() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
            obj(3, "endLine", name="C", basePoint="1", length="10", angle="90"),
            obj(
                4, "lineIntersectAxis", name="I", basePoint="1", p1Line="2", p2Line="3", angle="45"
            ),
        ),
        {},
    )
    at(ev.point_mm("I"), 50.0, -50.0)
    assert not ev.issues


def test_line_intersect_axis_parallel_reports_an_issue() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
            obj(3, "endLine", name="C", basePoint="2", length="10", angle="0"),
            obj(4, "lineIntersectAxis", name="I", basePoint="1", p1Line="2", p2Line="3", angle="0"),
        ),
        {},
    )
    assert [i.code for i in ev.issues] == ["no_intersection"]
    at(ev.point_mm("I"), 0.0, 0.0)  # Seamly2D's placeholder


def test_line_object_registers_variables() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="3", angle="0"),
            obj(3, "line", tag="line", firstPoint="1", secondPoint="2"),
        ),
        {},
    )
    assert ev.symbols["Line_A_B"] == pytest.approx(3.0)


# -- error handling: bad objects are reported and evaluation carries on ---------------------------
def test_missing_reference_is_reported_and_does_not_stop_evaluation() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="99", length="10", angle="0"),
            obj(3, "endLine", name="C", basePoint="1", length="10", angle="0"),
        ),
        {},
    )
    assert [(i.code, i.object_id, i.field) for i in ev.issues] == [
        ("missing_reference", 2, "basePoint")
    ]
    at(ev.point_mm("C"), 100.0, 0.0)


def test_forward_reference_is_a_missing_reference() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="3", length="10", angle="0"),
            obj(3, "endLine", name="C", basePoint="1", length="10", angle="0"),
        ),
        {},
    )
    assert ev.issues[0].code == "missing_reference"


def test_formula_errors_carry_a_code_and_hint() -> None:
    ev = evaluate(
        pattern(origin(), obj(2, "endLine", name="B", basePoint="1", length="ghost", angle="0")), {}
    )
    (issue,) = ev.issues
    assert issue.code == "formula_undefined_name"
    assert issue.field == "length"
    assert issue.hint


def test_non_finite_formula_value_becomes_zero_like_seamly2d() -> None:
    ev = evaluate(
        pattern(origin(), obj(2, "endLine", name="B", basePoint="1", length="1/0", angle="0")), {}
    )
    assert [i.code for i in ev.issues] == ["invalid_formula_value"]
    at(ev.point_mm("B"), 0.0, 0.0)


def test_bad_variable_formula_is_reported() -> None:
    ev = evaluate(pattern(origin(), variables=(Variable("#bad", "1+"),)), {})
    assert ev.symbols["#bad"] == 0.0
    assert ev.issues[0].code == "formula_unexpected_eof"


def test_unsupported_kind_is_flagged() -> None:
    ev = evaluate(pattern(origin(), obj(2, "pointOfContact", name="Q")), {})
    assert ev.issues[0].code == "pending_kind"
    ev = evaluate(pattern(origin(), obj(2, "madeUp", name="Q")), {})
    assert ev.issues[0].code == "unknown_kind"


def test_bad_attributes() -> None:
    ev = evaluate(pattern(origin(), obj(2, "endLine", name="B", length="1", angle="0")), {})
    assert ev.issues[0].code == "missing_attribute"
    ev = evaluate(pattern(origin(), obj(2, "endLine", name="B", basePoint="x", length="1")), {})
    assert ev.issues[0].code == "bad_reference"
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "endLine", name="B", basePoint="1", length="1", angle="0"),
            obj(3, "normal", name="N", firstPoint="1", secondPoint="2", length="1", angle="north"),
        ),
        {},
    )
    assert ev.issues[0].code == "bad_number"
