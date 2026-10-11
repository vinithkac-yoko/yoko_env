"""Evaluator: lineIntersect, height, shoulder, triangle and the three cut tools. Small patterns with
hand-computed answers; Seamly2D's own results for the same tools are compared in
tests/test_external_seamly2d.py."""

from __future__ import annotations

import math

import pytest
from yoko_engine.evaluator import evaluate
from yoko_engine.model import DraftBlock, Obj, Pattern, RawNode


def obj(
    id_: int, kind: str, tag: str = "point", *, children: tuple[RawNode, ...] = (), **attrs: str
) -> Obj:
    return Obj(id_, tag, kind, tuple(attrs.items()), children)


def pattern(*objs: Obj) -> Pattern:
    return Pattern("cm", "0.6.8", "m.smms", (), (DraftBlock("b", tuple(objs)),))


def single(id_: int, name: str, x: float, y: float) -> Obj:
    return obj(id_, "single", name=name, x=str(x), y=str(y))


def close(pt: tuple[float, float], x: float, y: float, tol: float = 1e-6) -> None:
    assert pt[0] == pytest.approx(x, abs=tol)
    assert pt[1] == pytest.approx(y, abs=tol)


def test_line_intersect_finds_the_crossing_and_registers_four_lines() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            single(2, "B", 11, 1),
            single(3, "C", 1, 11),
            single(4, "D", 11, 11),
            obj(5, "lineIntersect", name="X", p1Line1="1", p2Line1="4", p1Line2="2", p2Line2="3"),
        ),
        {},
    )
    assert ev.issues == []
    close(ev.point_mm("X"), 60.0, 60.0)
    for name in ("Line_A_X", "Line_X_D", "Line_B_X", "Line_X_C"):
        assert ev.symbols[name] == pytest.approx(math.hypot(5, 5))


def test_parallel_lines_give_no_point_and_the_objects_after_it_fail() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            single(2, "B", 11, 1),
            single(3, "C", 1, 5),
            single(4, "D", 11, 5),
            obj(5, "lineIntersect", name="X", p1Line1="1", p2Line1="2", p1Line2="3", p2Line2="4"),
            obj(6, "endLine", name="Y", basePoint="5", length="1", angle="0"),
        ),
        {},
    )
    codes = [i.code for i in ev.issues]
    assert codes == ["no_intersection", "missing_reference"]
    assert not any(g.label == "X" for g in ev.points.values())


def test_height_is_the_foot_of_the_perpendicular() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            single(2, "B", 11, 1),
            single(3, "C", 4, 5),
            obj(4, "height", name="H", basePoint="3", p1Line="1", p2Line="2"),
        ),
        {},
    )
    assert ev.issues == []
    close(ev.point_mm("H"), 40.0, 10.0)
    assert ev.symbols["Line_C_H"] == pytest.approx(4.0)
    assert "Line_A_H" in ev.symbols and "Line_B_H" in ev.symbols


def test_shoulder_point_is_on_the_line_the_given_distance_from_the_third_point() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            single(2, "B", 11, 1),
            single(3, "C", 15, 5),
            obj(4, "shoulder", name="S", p1Line="1", p2Line="2", pShoulder="3", length="5"),
        ),
        {},
    )
    assert ev.issues == []
    # the circle of radius 5 around C meets the line at x = 12 and x = 18; the one beyond B in
    # the direction of A to B is chosen, and it is the first in Seamly2D's order (x = 18)
    close(ev.point_mm("S"), 180.0, 10.0)
    assert ev.symbols["Line_A_S"] == pytest.approx(17.0)


def test_shoulder_point_falls_back_to_the_second_point() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            single(2, "B", 11, 1),
            single(3, "C", 15, 5),
            obj(4, "shoulder", name="S", p1Line="1", p2Line="2", pShoulder="3", length="1"),
        ),
        {},
    )
    close(ev.point_mm("S"), 110.0, 10.0)  # the circle does not reach the line: p2 is used


def test_triangle_point_lies_on_the_axis_beyond_where_the_segment_crosses_it() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 5),
            single(2, "B", 31, 5),
            single(3, "F", 11, 1),
            single(4, "G", 21, 9),
            obj(5, "triangle", name="T", axisP1="1", axisP2="2", firstPoint="3", secondPoint="4"),
        ),
        {},
    )
    assert ev.issues == []
    x_mm, y_mm = ev.point_mm("T")
    assert y_mm == pytest.approx(50.0, abs=1e-6)  # on the axis y = 5 cm
    # the segment crosses the axis at x = 16 cm; the search walks from there along the axis in
    # whole-pixel steps until the right-angle condition holds
    assert x_mm > 160.0


def test_triangle_with_a_parallel_axis_gives_the_origin() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            single(2, "B", 11, 1),
            single(3, "C", 1, 5),
            single(4, "D", 11, 5),
            obj(5, "triangle", name="T", axisP1="1", axisP2="2", firstPoint="3", secondPoint="4"),
        ),
        {},
    )
    close(ev.point_mm("T"), 0.0, 0.0)


def straight_spline() -> list[Obj]:
    return [
        single(1, "A", 1, 1),
        single(2, "B", 31, 1),
        obj(
            3,
            "simpleInteractive",
            tag="spline",
            point1="1",
            point4="2",
            angle1="0",
            angle2="180",
            length1="10",
            length2="10",
        ),
    ]


def test_cut_spline_forward_and_backward() -> None:
    fwd = evaluate(
        pattern(*straight_spline(), obj(4, "cutSpline", name="X", length="10", spline="3")), {}
    )
    assert fwd.issues == []
    # the cut position is found by bisection to within 0.1 % of the length
    assert fwd.point_mm("X")[0] == pytest.approx(110.0, abs=0.5)
    assert fwd.symbols["Spl_A_X"] + fwd.symbols["Spl_X_B"] == pytest.approx(30.0, abs=0.1)
    back = evaluate(
        pattern(
            *straight_spline(),
            obj(4, "cutSpline", name="X", length="10", spline="3", direction="backward"),
        ),
        {},
    )
    assert back.point_mm("X")[0] == pytest.approx(210.0, abs=0.5)


def test_cut_spline_rounds_the_length_to_four_decimals() -> None:
    a = evaluate(
        pattern(*straight_spline(), obj(4, "cutSpline", name="X", length="10.00004", spline="3")),
        {},
    )
    b = evaluate(
        pattern(*straight_spline(), obj(4, "cutSpline", name="X", length="10", spline="3")), {}
    )
    assert a.point_mm("X") == b.point_mm("X")


def test_cut_spline_needs_a_single_spline() -> None:
    ev = evaluate(
        pattern(
            *straight_spline(),
            obj(
                4,
                "cutArc",
                name="X",
                length="1",
                arc="3",
            ),
        ),
        {},
    )
    assert ev.issues[0].code == "bad_curve"


def test_cut_spline_path_splits_a_path() -> None:
    pts = [single(1, "A", 1, 1), single(2, "B", 11, 1), single(3, "C", 21, 1)]
    kids = tuple(
        RawNode(
            "pathPoint",
            (
                ("pSpline", str(i)),
                ("angle1", "180"),
                ("angle2", "0"),
                ("length1", "0" if i == 1 else "3"),
                ("length2", "0" if i == 3 else "3"),
            ),
        )
        for i in (1, 2, 3)
    )
    path = obj(4, "pathInteractive", tag="spline", children=kids)
    ev = evaluate(
        pattern(*pts, path, obj(5, "cutSplinePath", name="X", length="5", splinePath="4")), {}
    )
    assert ev.issues == []
    assert ev.point_mm("X")[0] == pytest.approx(60.0, abs=0.5)
    assert ev.symbols["SplPath_A_X"] + ev.symbols["SplPath_X_C"] == pytest.approx(20.0, abs=0.1)


def test_cut_arc_gives_the_point_and_two_arcs_with_the_next_ids() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            obj(2, "simple", tag="arc", center="1", radius="10", angle1="0", angle2="90"),
            obj(3, "cutArc", name="X", length="5", arc="2"),
        ),
        {},
    )
    assert ev.issues == []
    theta = 5 / 10  # arc length / radius
    close(ev.point_mm("X"), 10 + 100 * math.cos(theta), 10 - 100 * math.sin(theta), 1e-6)
    assert 4 in ev.curves and 5 in ev.curves  # ids after the point's
    assert ev.symbols["Arc_A_4"] == pytest.approx(5.0)
    assert ev.symbols["Arc_A_5"] == pytest.approx(5 * math.pi - 5, abs=1e-6)
    back = evaluate(
        pattern(
            single(1, "A", 1, 1),
            obj(2, "simple", tag="arc", center="1", radius="10", angle1="0", angle2="90"),
            obj(3, "cutArc", name="X", length="5", arc="2", direction="backward"),
        ),
        {},
    )
    assert back.symbols["Arc_A_4"] == pytest.approx(5 * math.pi - 5, abs=1e-6)


def test_options_that_change_handles_are_refused_on_every_cubic() -> None:
    p = pattern(
        single(1, "A", 1, 1),
        single(2, "B", 5, 1),
        single(3, "C", 9, 1),
        single(4, "D", 15, 1),
        obj(
            5,
            "cubicBezier",
            tag="spline",
            point1="1",
            point2="2",
            point3="3",
            point4="4",
            autoSmooth="true",
            lengthMode="3",
            length="17",
        ),
    )
    assert [i.code for i in evaluate(p, {}).issues] == ["not_implemented"]
