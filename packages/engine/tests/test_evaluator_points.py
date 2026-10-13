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


def test_options_that_change_handles_are_refused_on_a_bezier_path() -> None:
    p = pattern(
        *(single(i, chr(64 + i), 4.0 * i, float(i % 2)) for i in range(1, 8)),
        obj(
            9,
            "cubicBezierPath",
            tag="spline",
            children=tuple(RawNode("pathPoint", (("pSpline", str(i)),)) for i in range(1, 8)),
            autoSmooth="true",
        ),
    )
    assert [i.code for i in evaluate(p, {}).issues] == ["not_implemented"]


# ---- circles, arcs, tangents, curve crossings, arc with length ----------------------


def two_points() -> list[Obj]:
    return [single(1, "A", 1, 1), single(2, "B", 11, 1)]


def circles(cross: str, r1: str = "6", r2: str = "6") -> Obj:
    return obj(
        3,
        "pointOfIntersectionCircles",
        name="X",
        c1Center="1",
        c1Radius=r1,
        c2Center="2",
        c2Radius=r2,
        crossPoint=cross,
    )


def test_circle_intersection_picks_the_first_or_second_point() -> None:
    root = math.sqrt(11)
    first = evaluate(pattern(*two_points(), circles("1")), {})
    assert first.issues == []
    close(first.point_mm("X"), 60.0, 10.0 + 10 * root, 1e-6)
    second = evaluate(pattern(*two_points(), circles("2")), {})
    close(second.point_mm("X"), 60.0, 10.0 - 10 * root, 1e-6)


def test_circles_that_do_not_meet_use_the_origin_and_report() -> None:
    ev = evaluate(pattern(*two_points(), circles("1", "1", "1")), {})
    assert [i.code for i in ev.issues] == ["no_intersection"]
    close(ev.point_mm("X"), 0.0, 0.0)


def test_circle_tangent_point() -> None:
    ev = evaluate(
        pattern(
            *two_points(),
            obj(
                3,
                "pointFromCircleAndTangent",
                name="T",
                cCenter="1",
                cRadius="3",
                tangent="2",
                crossPoint="1",
            ),
        ),
        {},
    )
    assert ev.issues == []
    sin = math.sqrt(1 - 0.09)  # cos(phi) = radius / distance = 3 / 10
    close(ev.point_mm("T"), 10 + 30 * 0.3, 10 - 30 * sin, 1e-6)


def test_a_tangent_from_inside_the_circle_does_not_exist() -> None:
    ev = evaluate(
        pattern(
            *two_points(),
            obj(
                3,
                "pointFromCircleAndTangent",
                name="T",
                cCenter="1",
                cRadius="30",
                tangent="2",
                crossPoint="1",
            ),
        ),
        {},
    )
    assert [i.code for i in ev.issues] == ["no_intersection"]


def arc(id_: int, center: int, radius: str, a1: str, a2: str) -> Obj:
    return obj(id_, "simple", tag="arc", center=str(center), radius=radius, angle1=a1, angle2=a2)


def test_arc_intersection_only_counts_points_both_arcs_reach() -> None:
    root = math.sqrt(11)
    full = evaluate(
        pattern(
            *two_points(),
            arc(3, 1, "6", "0", "360"),
            arc(4, 2, "6", "0", "360"),
            obj(
                5, "pointOfIntersectionArcs", name="X", firstArc="3", secondArc="4", crossPoint="2"
            ),
        ),
        {},
    )
    assert full.issues == []
    close(full.point_mm("X"), 60.0, 10.0 - 10 * root, 1e-6)
    # the first arc is only the half above its centre (angles 0 to 180 run through "up"): only
    # the upper crossing is on it, so it is chosen whatever crossPoint says
    upper = evaluate(
        pattern(
            *two_points(),
            arc(3, 1, "6", "0", "180"),
            arc(4, 2, "6", "0", "360"),
            obj(
                5, "pointOfIntersectionArcs", name="X", firstArc="3", secondArc="4", crossPoint="1"
            ),
        ),
        {},
    )
    close(upper.point_mm("X"), 60.0, 10.0 - 10 * root, 1e-6)


def test_arc_tangent_point() -> None:
    ev = evaluate(
        pattern(
            *two_points(),
            arc(3, 1, "3", "0", "360"),
            obj(4, "pointFromArcAndTangent", name="T", arc="3", tangent="2", crossPoint="1"),
        ),
        {},
    )
    assert ev.issues == []
    sin = math.sqrt(1 - 0.09)
    close(ev.point_mm("T"), 10 + 30 * 0.3, 10 - 30 * sin, 1e-6)


def test_intersection_of_two_curves() -> None:
    def straight(id_: int, p1: int, p4: int, a1: str, a2: str) -> Obj:
        return obj(
            id_,
            "simpleInteractive",
            tag="spline",
            point1=str(p1),
            point4=str(p4),
            angle1=a1,
            angle2=a2,
            length1="4.7140452",
            length2="4.7140452",
        )

    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            single(2, "B", 11, 11),
            single(3, "C", 1, 11),
            single(4, "D", 11, 1),
            straight(5, 1, 2, "315", "135"),
            straight(6, 3, 4, "45", "225"),
            obj(7, "pointOfIntersectionCurves", name="X", curve1="5", curve2="6"),
        ),
        {},
    )
    assert ev.issues == []
    close(ev.point_mm("X"), 60.0, 60.0, 0.01)


def test_arc_with_length_finds_its_end_angle() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            obj(
                2,
                "arcWithLength",
                tag="arc",
                center="1",
                radius="10",
                angle1="0",
                length=str(5 * math.pi),
            ),
        ),
        {},
    )
    assert ev.issues == []
    assert ev.symbols["Arc_A_2"] == pytest.approx(5 * math.pi)
    assert ev.symbols["Angle2Arc_A_2"] == pytest.approx(90.0)
    assert ev.symbols["RadiusArc_A_2"] == pytest.approx(10.0)


def test_arc_with_length_cannot_be_longer_than_the_circle() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            obj(2, "arcWithLength", tag="arc", center="1", radius="10", angle1="0", length="1000"),
        ),
        {},
    )
    assert ev.symbols["Arc_A_2"] == pytest.approx(20 * math.pi)


def test_arc_with_negative_length_is_flipped() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            obj(2, "arcWithLength", tag="arc", center="1", radius="10", angle1="90", length="-5"),
        ),
        {},
    )
    assert ev.issues == []
    assert ev.symbols["Arc_A_2"] == pytest.approx(-5.0)
    # clockwise from 90 degrees by 5 / 10 radians (28.65 degrees)
    assert ev.symbols["Angle2Arc_A_2"] == pytest.approx(90 - math.degrees(0.5))


# ---- operations: rotate, move, mirror ------------------------------------------------------------


def operation(id_: int, kind: str, sources: list[int], dests: list[int], **attrs: str) -> Obj:
    src = RawNode(
        "source", (), "", tuple(RawNode("item", (("idObject", str(i)),)) for i in sources)
    )
    dst = RawNode(
        "destination", (), "", tuple(RawNode("item", (("idObject", str(i)),)) for i in dests)
    )
    return obj(id_, kind, tag="operation", children=(src, dst), **attrs)


def test_rotation_turns_a_point_and_names_the_copy() -> None:
    ev = evaluate(
        pattern(
            *two_points(),
            operation(10, "rotation", [2], [20], center="1", angle="90", suffix="_r"),
        ),
        {},
    )
    assert ev.issues == []
    assert ev.points[20].label == "B_r"
    close((ev.points[20].x_mm, ev.points[20].y_mm), 10.0, -90.0, 1e-6)


def test_rotation_copies_curves_with_their_variables() -> None:
    ev = evaluate(
        pattern(
            *two_points(),
            obj(
                3,
                "simpleInteractive",
                tag="spline",
                point1="1",
                point4="2",
                angle1="0",
                angle2="180",
                length1="3",
                length2="3",
            ),
            operation(10, "rotation", [3], [30], center="1", angle="90", suffix="_r"),
        ),
        {},
    )
    assert ev.issues == []
    assert ev.symbols["Spl_A_B_r"] == pytest.approx(ev.symbols["Spl_A_B"], abs=1e-6)
    assert ev.symbols["Angle1Spl_A_B_r"] == pytest.approx(90.0, abs=1e-6)
    assert 30 in ev.curves


def test_moving_shifts_by_a_length_at_an_angle() -> None:
    ev = evaluate(
        pattern(
            *two_points(),
            operation(
                10,
                "moving",
                [2],
                [20],
                center="0",
                angle="90",
                length="5",
                rotationAngle="0",
                suffix="_m",
            ),
        ),
        {},
    )
    assert ev.issues == []
    close((ev.points[20].x_mm, ev.points[20].y_mm), 110.0, -40.0, 1e-6)


def test_moving_then_rotating_about_the_centre_of_the_moved_objects() -> None:
    """With no pivot point, the objects turn about the centre of their bounding box, moved with
    them (`findRotationOrigin`)."""
    ev = evaluate(
        pattern(
            *two_points(),
            operation(
                10,
                "moving",
                [1, 2],
                [20, 21],
                center="0",
                angle="0",
                length="0",
                rotationAngle="180",
                suffix="_m",
            ),
        ),
        {},
    )
    # the pair turns 180 degrees about its middle (6, 1): A -> B's place and B -> A's place
    close((ev.points[20].x_mm, ev.points[20].y_mm), 110.0, 10.0, 1e-6)
    close((ev.points[21].x_mm, ev.points[21].y_mm), 10.0, 10.0, 1e-6)


def test_mirror_by_a_vertical_axis() -> None:
    ev = evaluate(
        pattern(
            *two_points(),
            operation(10, "flippingByAxis", [2], [20], center="1", axisType="1", suffix="_m"),
        ),
        {},
    )
    assert ev.issues == []
    close((ev.points[20].x_mm, ev.points[20].y_mm), -90.0, 10.0, 1e-6)
    horizontal = evaluate(
        pattern(
            single(1, "A", 1, 1),
            single(2, "B", 1, 5),
            operation(10, "flippingByAxis", [2], [20], center="1", axisType="2", suffix="_m"),
        ),
        {},
    )
    close((horizontal.points[20].x_mm, horizontal.points[20].y_mm), 10.0, -30.0, 1e-6)


def test_a_mirrored_arc_runs_the_other_way_and_has_a_negative_length() -> None:
    ev = evaluate(
        pattern(
            single(1, "A", 1, 1),
            arc(2, 1, "10", "0", "90"),
            operation(10, "flippingByAxis", [2], [20], center="1", axisType="1", suffix="_m"),
        ),
        {},
    )
    assert ev.issues == []
    assert ev.symbols["Arc_A_2"] == pytest.approx(5 * math.pi)
    assert ev.symbols["Arc_A_20"] == pytest.approx(-5 * math.pi)
    assert ev.curves[20].geom.flipped is True  # type: ignore[union-attr]
    # the mirror of the mirror is the original again
    twice = evaluate(
        pattern(
            single(1, "A", 1, 1),
            arc(2, 1, "10", "0", "90"),
            operation(10, "flippingByAxis", [2], [20], center="1", axisType="1", suffix="_m"),
            operation(11, "flippingByAxis", [20], [21], center="1", axisType="1", suffix="_n"),
        ),
        {},
    )
    assert twice.symbols["Arc_A_21"] == pytest.approx(5 * math.pi)


def test_a_source_that_does_not_exist_is_reported() -> None:
    ev = evaluate(
        pattern(*two_points(), operation(10, "rotation", [99], [20], center="1", angle="1")), {}
    )
    assert ev.issues[0].code == "missing_reference"
