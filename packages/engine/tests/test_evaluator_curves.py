"""Evaluator: arcs, curves, circle contact, darts, mirror. Small hand-computed patterns; the real
basic set is checked against Seamly2D itself in tests/test_oracle_basic_set.py."""

from __future__ import annotations

import math

import pytest
from yoko_engine.evaluator import evaluate
from yoko_engine.model import DraftBlock, Obj, Pattern, RawNode, Variable


def obj(
    id_: int, kind: str, tag: str = "point", *, children: tuple[RawNode, ...] = (), **attrs: str
) -> Obj:
    return Obj(id_, tag, kind, tuple(attrs.items()), children)


def pattern(*objs: Obj, unit: str = "cm") -> Pattern:
    return Pattern(unit, "0.6.8", "m.smms", (), (DraftBlock("b", tuple(objs)),))


def origin(id_: int = 1, name: str = "A") -> Obj:
    return obj(id_, "single", name=name, x="0", y="0")


def end(id_: int, name: str, base: int, length: str, angle: str) -> Obj:
    return obj(id_, "endLine", name=name, basePoint=str(base), length=length, angle=angle)


def close(pt: tuple[float, float], x: float, y: float, tol: float = 1e-6) -> None:
    assert pt[0] == pytest.approx(x, abs=tol)
    assert pt[1] == pytest.approx(y, abs=tol)


def test_point_of_contact_picks_the_intersection_nearest_the_first_point() -> None:
    ev = evaluate(
        pattern(
            origin(),
            end(2, "B", 1, "10", "0"),
            end(3, "C", 1, "10", "90"),
            obj(
                4,
                "pointOfContact",
                name="Q",
                center="1",
                firstPoint="2",
                secondPoint="3",
                radius="8",
            ),
        ),
        {},
    )
    assert ev.issues == []
    close(ev.point_mm("Q"), 76.457513, -23.542487, 1e-4)


def test_point_of_contact_without_an_intersection_reports_and_uses_the_origin() -> None:
    ev = evaluate(
        pattern(
            origin(),
            end(2, "B", 1, "10", "0"),
            end(3, "C", 1, "10", "90"),
            obj(
                4,
                "pointOfContact",
                name="Q",
                center="1",
                firstPoint="2",
                secondPoint="3",
                radius="2",
            ),
        ),
        {},
    )
    assert [i.code for i in ev.issues] == ["no_intersection"]
    close(ev.point_mm("Q"), 0.0, 0.0)


def test_point_of_contact_tangent_circle_has_one_solution() -> None:
    ev = evaluate(
        pattern(
            origin(),
            end(2, "B", 1, "10", "0"),
            end(3, "C", 1, "10", "90"),
            obj(
                4,
                "pointOfContact",
                name="Q",
                center="1",
                firstPoint="2",
                secondPoint="3",
                radius="10/sqrt(2)",
            ),
        ),
        {},
    )
    assert ev.issues == []
    close(ev.point_mm("Q"), 50.0, -50.0, 1e-4)


def test_arc_registers_length_angles_and_radius() -> None:
    ev = evaluate(
        pattern(
            origin(), obj(2, "simple", tag="arc", center="1", radius="10", angle1="0", angle2="90")
        ),
        {},
    )
    name = "Arc_A_2"
    assert ev.symbols[name] == pytest.approx(10 * math.pi / 2)
    assert ev.symbols[f"Angle1{name}"] == 0.0
    assert ev.symbols[f"Angle2{name}"] == 90.0
    assert ev.symbols[f"Radius{name}"] == pytest.approx(10.0)
    assert ev.curves[2].name == name


def test_arc_angles_are_normalised_into_0_360() -> None:
    ev = evaluate(
        pattern(
            origin(),
            obj(2, "simple", tag="arc", center="1", radius="1", angle1="-90", angle2="450"),
        ),
        {},
    )
    assert ev.symbols["Angle1Arc_A_2"] == 270.0
    assert ev.symbols["Angle2Arc_A_2"] == 90.0


def test_cubic_bezier_variables() -> None:
    ev = evaluate(
        pattern(
            origin(),
            end(2, "B", 1, "10", "0"),
            end(3, "C", 1, "20", "0"),
            end(4, "D", 1, "30", "0"),
            obj(5, "cubicBezier", tag="spline", point1="1", point2="2", point3="3", point4="4"),
        ),
        {},
    )
    assert ev.symbols["Spl_A_D"] == pytest.approx(30.0)
    assert ev.symbols["Angle1Spl_A_D"] == 0.0
    assert ev.symbols["Angle2Spl_A_D"] == pytest.approx(180.0)
    assert ev.symbols["C1LengthSpl_A_D"] == pytest.approx(10.0)
    assert ev.symbols["C2LengthSpl_A_D"] == pytest.approx(10.0)


def _path_object(id_: int, point_ids: list[int]) -> Obj:
    kids = tuple(RawNode("pathPoint", (("pSpline", str(i)),)) for i in point_ids)
    return obj(id_, "cubicBezierPath", tag="spline", children=kids)


def test_cubic_bezier_path_variables_include_each_segment() -> None:
    pts = [origin()] + [end(i, f"P{i}", 1, str(10 * (i - 1)), "0") for i in range(2, 8)]
    ev = evaluate(pattern(*pts, _path_object(8, [1, 2, 3, 4, 5, 6, 7])), {})
    assert ev.issues == []
    assert ev.symbols["SplPath_A_P7"] == pytest.approx(60.0)
    assert ev.symbols["SplPath_A_P7_Seg_1"] == pytest.approx(30.0)
    assert ev.symbols["SplPath_A_P7_Seg_2"] == pytest.approx(30.0)
    assert ev.symbols["C1LengthSplPath_A_P7_Seg_2"] == pytest.approx(10.0)


def test_cubic_bezier_path_needs_four_points() -> None:
    ev = evaluate(
        pattern(origin(), end(2, "B", 1, "1", "0"), _path_object(3, [1, 2])),
        {},
    )
    assert ev.issues[0].code == "too_few_points"


def test_curve_intersect_axis_finds_the_crossing_and_registers_the_cut_pieces() -> None:
    ev = evaluate(
        pattern(
            origin(),
            end(2, "B", 1, "10", "0"),
            end(3, "C", 1, "20", "0"),
            end(4, "D", 1, "30", "0"),
            obj(5, "cubicBezier", tag="spline", point1="1", point2="2", point3="3", point4="4"),
            end(6, "E", 3, "10", "90"),  # 10 cm above C
            obj(7, "curveIntersectAxis", name="X", basePoint="6", curve="5", angle="270"),
        ),
        {},
    )
    assert ev.issues == []
    close(ev.point_mm("X"), 200.0, 0.0, 1e-3)  # straight down from E onto the curve
    # the curve is split at X: the pieces are registered under names built from the labels
    assert ev.symbols["Spl_A_X"] == pytest.approx(20.0, abs=0.05)
    assert ev.symbols["Spl_X_D"] == pytest.approx(10.0, abs=0.05)
    assert ev.symbols["Spl_A_X"] + ev.symbols["Spl_X_D"] == pytest.approx(30.0, abs=0.05)


def test_curve_intersect_axis_with_no_crossing_reports_an_issue() -> None:
    ev = evaluate(
        pattern(
            origin(),
            end(2, "B", 1, "10", "0"),
            end(3, "C", 1, "20", "0"),
            end(4, "D", 1, "30", "0"),
            obj(5, "cubicBezier", tag="spline", point1="1", point2="2", point3="3", point4="4"),
            end(6, "E", 1, "10", "90"),
            obj(7, "curveIntersectAxis", name="X", basePoint="6", curve="5", angle="0"),
        ),
        {},
    )
    assert [i.code for i in ev.issues] == ["no_intersection"]


def test_curve_intersect_axis_on_an_arc_registers_arc_pieces() -> None:
    # (The base point must not sit exactly on the scene origin: Seamly2D builds the ray from a line
    # to (0, 0), which is null there and finds nothing.)
    ev = evaluate(
        pattern(
            obj(1, "single", name="A", x="1", y="1"),
            obj(2, "simple", tag="arc", center="1", radius="10", angle1="0", angle2="90"),
            end(3, "E", 1, "20", "45"),
            obj(4, "curveIntersectAxis", name="X", basePoint="1", curve="2", angle="45"),
        ),
        {},
    )
    assert ev.issues == []
    # the axis at 45 degrees meets the quarter circle at its middle (7.07 cm right and up)
    close(ev.point_mm("X"), 10 + 70.7107, 10 - 70.7107, 0.5)
    pieces = [k for k in ev.symbols if k.startswith("Arc_A_") and k != "Arc_A_2"]
    assert any(k.startswith("Arc_A_5") for k in pieces)  # ids are the new point's id + 1 and + 2


def test_true_darts_emits_two_points_with_their_own_ids_and_labels() -> None:
    ev = evaluate(
        pattern(
            origin(),  # A: dart apex
            end(2, "B", 1, "10", "200"),  # dart leg 1
            end(3, "C", 1, "10", "250"),  # dart leg 2
            end(4, "D", 1, "10", "180"),  # base line point 1
            end(5, "E", 1, "10", "0"),  # base line point 2
            obj(
                6,
                "trueDarts",
                name1="P",
                name2="Q",
                point1="7",
                point2="8",
                baseLineP1="4",
                baseLineP2="5",
                dartP1="2",
                dartP2="1",
                dartP3="3",
            ),
        ),
        {},
    )
    assert ev.issues == []
    assert ev.points[7].label == "P"
    assert ev.points[8].label == "Q"
    assert 7 in ev.deps or 6 in ev.deps


def test_flip_by_line_mirrors_points_and_appends_the_suffix() -> None:
    items_src = (
        RawNode("source", (), "", (RawNode("item", (("idObject", "3"),)),)),
        RawNode("destination", (), "", (RawNode("item", (("idObject", "100"),)),)),
    )
    ev = evaluate(
        pattern(
            origin(),
            end(2, "V", 1, "10", "90"),  # (0, -100 mm): a vertical axis through A
            end(3, "P", 1, "5", "0"),  # (50, 0)
            obj(
                4,
                "flippingByLine",
                tag="operation",
                children=items_src,
                p1Line="1",
                p2Line="2",
                suffix="_a1",
            ),
        ),
        {},
    )
    assert ev.issues == []
    assert ev.points[100].label == "P_a1"
    close(ev.point_mm("P_a1"), -50.0, 0.0, 1e-9)


def test_flip_by_line_with_mismatched_lists_is_an_error() -> None:
    bad = (
        RawNode("source", (), "", (RawNode("item", (("idObject", "3"),)),)),
        RawNode("destination", (), "", ()),
    )
    ev = evaluate(
        pattern(
            origin(),
            end(2, "V", 1, "10", "90"),
            end(3, "P", 1, "5", "0"),
            obj(
                4,
                "flippingByLine",
                tag="operation",
                children=bad,
                p1Line="1",
                p2Line="2",
                suffix="_a",
            ),
        ),
        {},
    )
    assert ev.issues[0].code == "bad_operation"


# ---- splines: simple, simpleInteractive, path, pathInteractive ----------------------------------


def spline(id_: int, p1: int, p4: int, **attrs: str) -> Obj:
    base = (("point1", str(p1)), ("point4", str(p4)))
    return Obj(id_, "spline", "simpleInteractive", (*base, *attrs.items()))


def line_ab() -> list[Obj]:
    return [origin(), end(2, "B", 1, "30", "0")]


def test_interactive_spline_from_angles_and_lengths() -> None:
    ev = evaluate(
        pattern(
            *line_ab(),
            spline(3, 1, 2, angle1="0", angle2="180", length1="10", length2="10"),
        ),
        {},
    )
    assert ev.issues == []
    assert ev.symbols["Spl_A_B"] == pytest.approx(30.0)
    assert ev.symbols["Angle1Spl_A_B"] == 0.0
    assert ev.symbols["Angle2Spl_A_B"] == 180.0
    assert ev.symbols["C1LengthSpl_A_B"] == pytest.approx(10.0)


def test_interactive_spline_formulas_can_use_variables_and_geometry() -> None:
    p = pattern(
        *line_ab(),
        spline(3, 1, 2, angle1="0", angle2="180", length1="Line_A_B/3", length2="#h"),
    )
    p = Pattern(p.unit, p.version, p.measurements_file, (Variable("#h", "4"),), p.blocks)
    ev = evaluate(p, {})
    assert ev.issues == []
    assert ev.symbols["C1LengthSpl_A_B"] == pytest.approx(10.0)
    assert ev.symbols["C2LengthSpl_A_B"] == pytest.approx(4.0)


def test_a_curve_drawn_twice_gets_a_numbered_name() -> None:
    ev = evaluate(
        pattern(
            *line_ab(),
            spline(3, 1, 2, angle1="0", angle2="180", length1="1", length2="1", duplicate="1"),
        ),
        {},
    )
    assert "Spl_A_B_1" in ev.symbols and "Spl_A_B" not in ev.symbols


def test_auto_smooth_gives_a_symmetric_curve_equal_handles() -> None:
    """A curve leaving A at 45 degrees and arriving at B at 135 degrees is symmetric, so Hobby's
    handles have the same length (the stored ones, 1 cm, are ignored)."""
    ev = evaluate(
        pattern(
            *line_ab(),
            spline(3, 1, 2, angle1="45", angle2="135", length1="1", length2="1", autoSmooth="true"),
        ),
        {},
    )
    assert not ev.issues
    assert ev.symbols["C1LengthSpl_A_B"] == pytest.approx(ev.symbols["C2LengthSpl_A_B"], rel=1e-9)
    assert ev.symbols["C1LengthSpl_A_B"] > 1.0


def test_a_target_length_sets_the_curve_length_within_a_twentieth_of_a_millimetre() -> None:
    ev = evaluate(
        pattern(
            *line_ab(),
            spline(
                3,
                1,
                2,
                angle1="45",
                angle2="135",
                length1="2",
                length2="2",
                lengthMode="3",
                length="40",
            ),
        ),
        {},
    )
    assert not ev.issues
    assert ev.symbols["Spl_A_B"] == pytest.approx(40.0, abs=0.005)


def test_old_simple_spline_uses_the_quarter_circle_handle() -> None:
    """With kAsm1 = kAsm2 = kCurve = 1 each handle is 4/3 tan(22.5 deg) times the radius of the
    circle through the two points, 30 / sqrt(2): 11.7157 cm."""
    ev = evaluate(
        pattern(
            *line_ab(),
            obj(
                3,
                "simple",
                tag="spline",
                point1="1",
                point4="2",
                angle1="0",
                angle2="180",
                kAsm1="1",
                kAsm2="1",
                kCurve="1",
            ),
        ),
        {},
    )
    assert ev.issues == []
    handle = 30 / math.sqrt(2) * 4 / 3 * math.tan(math.pi / 8)
    assert ev.symbols["C1LengthSpl_A_B"] == pytest.approx(handle)
    assert ev.symbols["C2LengthSpl_A_B"] == pytest.approx(handle)


def _spline_path(id_: int, kind: str, points: list[dict[str, str]]) -> Obj:
    kids = tuple(RawNode("pathPoint", tuple(p.items())) for p in points)
    return obj(id_, kind, tag="spline", children=kids)


def three_points() -> list[Obj]:
    return [origin(), end(2, "B", 1, "10", "0"), end(3, "C", 1, "20", "0")]


def test_interactive_spline_path_variables_and_segments() -> None:
    path = _spline_path(
        4,
        "pathInteractive",
        [
            {"pSpline": "1", "angle1": "180", "angle2": "0", "length1": "0", "length2": "3"},
            {"pSpline": "2", "angle1": "180", "angle2": "0", "length1": "3", "length2": "3"},
            {"pSpline": "3", "angle1": "180", "angle2": "0", "length1": "3", "length2": "0"},
        ],
    )
    ev = evaluate(pattern(*three_points(), path), {})
    assert ev.issues == []
    assert ev.symbols["SplPath_A_C"] == pytest.approx(20.0)
    assert ev.symbols["SplPath_A_C_Seg_1"] == pytest.approx(10.0)
    assert ev.symbols["Angle1SplPath_A_C"] == 0.0  # the first point's angle2
    assert ev.symbols["Angle2SplPath_A_C"] == 180.0  # the last point's angle1
    assert ev.symbols["C1LengthSplPath_A_C"] == pytest.approx(3.0)


def test_spline_path_corrects_the_angle_that_is_a_plain_number() -> None:
    """Handle angles of a point must be opposite. When they are not, the one that is a plain number
    gives way to the one that is a formula (`VSplinePointData`)."""

    def middle(a1: str, a2: str) -> list[dict[str, str]]:
        return [
            {"pSpline": "1", "angle1": "180", "angle2": "0", "length1": "0", "length2": "3"},
            {"pSpline": "2", "angle1": a1, "angle2": a2, "length1": "3", "length2": "3"},
            {"pSpline": "3", "angle1": "180", "angle2": "0", "length1": "3", "length2": "0"},
        ]

    # angle1 is a plain number, angle2 a formula: angle1 becomes angle2 + 180 = 180
    plain_first = evaluate(
        pattern(*three_points(), _spline_path(4, "pathInteractive", middle("90", "0+0"))), {}
    )
    assert plain_first.symbols["Angle2SplPath_A_C_Seg_1"] == 180.0
    assert plain_first.symbols["Angle1SplPath_A_C_Seg_2"] == 0.0
    # angle1 is a formula, angle2 a plain number: angle2 becomes angle1 + 180 = 270
    formula_first = evaluate(
        pattern(*three_points(), _spline_path(4, "pathInteractive", middle("0+90", "0"))), {}
    )
    assert formula_first.symbols["Angle1SplPath_A_C_Seg_2"] == 270.0
    assert formula_first.symbols["Angle2SplPath_A_C_Seg_1"] == 90.0
    # both plain numbers: angle2 is recomputed from angle1
    both_plain = evaluate(
        pattern(*three_points(), _spline_path(4, "pathInteractive", middle("90", "5"))), {}
    )
    assert both_plain.symbols["Angle1SplPath_A_C_Seg_2"] == 270.0


def test_old_spline_path_from_coefficients() -> None:
    path = _spline_path(
        4,
        "path",
        [
            {"pSpline": "1", "kAsm1": "1", "angle": "0", "kAsm2": "1"},
            {"pSpline": "2", "kAsm1": "1", "angle": "0", "kAsm2": "1"},
            {"pSpline": "3", "kAsm1": "1", "angle": "0", "kAsm2": "1"},
        ],
    )
    path = Obj(path.id, path.tag, path.kind, (*path.attrs, ("kCurve", "1")), path.children)
    ev = evaluate(pattern(*three_points(), path), {})
    assert ev.issues == []
    assert ev.symbols["SplPath_A_C"] == pytest.approx(20.0)


def test_an_empty_spline_path_is_an_unnamed_curve_of_length_zero() -> None:
    """Seamly2D accepts it (some real patterns contain one) and registers the unnamed variables."""
    ev = evaluate(pattern(*three_points(), _spline_path(4, "pathInteractive", [])), {})
    assert ev.issues == []
    assert ev.symbols[""] == 0.0
    assert ev.symbols["Angle1"] == 0.0 and ev.symbols["C2Length"] == 0.0


def test_a_spline_can_be_cut_by_an_axis() -> None:
    """curveIntersectAxis splits the spline it crosses and registers both pieces."""
    ev = evaluate(
        pattern(
            obj(1, "single", name="A", x="1", y="1"),
            end(2, "B", 1, "30", "0"),
            end(3, "C", 1, "15", "0"),
            spline(4, 1, 2, angle1="0", angle2="180", length1="10", length2="10"),
            obj(5, "curveIntersectAxis", name="X", basePoint="3", curve="4", angle="90"),
        ),
        {},
    )
    assert ev.issues == []
    assert ev.symbols["Spl_A_X"] + ev.symbols["Spl_X_B"] == pytest.approx(30.0, abs=0.2)
