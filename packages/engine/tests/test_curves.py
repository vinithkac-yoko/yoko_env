"""Curve and arc geometry (Seamly2D's flattening-based lengths, smooth path joins, arcs)."""

from __future__ import annotations

import math

import pytest
from yoko_engine.geometry import Pt
from yoko_engine.geometry.curves import (
    Arc,
    Bezier,
    BezierPath,
    count_sub_splines,
    normalize_angle,
    path_length,
)


def test_collinear_bezier_flattens_to_its_end_points() -> None:
    b = Bezier(Pt(0, 0), Pt(10, 0), Pt(20, 0), Pt(30, 0))
    assert b.points() == [Pt(0, 0), Pt(30, 0)]
    assert b.length() == 30.0


def test_degenerate_bezier_with_equal_ends() -> None:
    b = Bezier(Pt(5, 5), Pt(5, 5), Pt(5, 5), Pt(5, 5))
    assert b.length() == 0.0


def test_quarter_circle_bezier_length_is_close_to_the_arc_length() -> None:
    k = 0.5522847498
    b = Bezier(Pt(100, 0), Pt(100, 100 * k), Pt(100 * k, 100), Pt(0, 100))
    assert b.length() == pytest.approx(math.pi / 2 * 100, abs=0.1)
    assert len(b.points()) > 3  # it really was subdivided
    # the flattened polyline starts and ends exactly on the end points
    assert b.points()[0] == b.p1
    assert b.points()[-1] == b.p4


def _sampled_length(b: Bezier, n: int = 20000) -> float:
    def at(t: float) -> Pt:
        u = 1 - t
        x = u**3 * b.p1.x + 3 * u * u * t * b.c1.x + 3 * u * t * t * b.c2.x + t**3 * b.p4.x
        y = u**3 * b.p1.y + 3 * u * u * t * b.c1.y + 3 * u * t * t * b.c2.y + t**3 * b.p4.y
        return Pt(x, y)

    return path_length([at(i / n) for i in range(n + 1)])


def test_flattened_length_is_close_to_the_true_length() -> None:
    k = 0.5522847498
    for b in (
        Bezier(Pt(100, 0), Pt(100, 100 * k), Pt(100 * k, 100), Pt(0, 100)),
        Bezier(Pt(0, 0), Pt(50, -80), Pt(120, 90), Pt(200, 10)),
        Bezier(Pt(0, 0), Pt(300, 0), Pt(-100, 50), Pt(200, 50)),
    ):
        true = _sampled_length(b)
        flat = b.length()
        # Seamly2D's polyline contains the control-point midpoint (x23, y23), which is not on the
        # curve, so the flattened length can be slightly above or below the true length.
        assert abs(flat - true) < 0.05


def test_angles_and_handle_lengths() -> None:
    b = Bezier(Pt(0, 0), Pt(0, -10), Pt(20, -30), Pt(20, 0))
    assert b.start_angle() == pytest.approx(90.0)  # up on screen
    assert b.end_angle() == pytest.approx(math.degrees(math.atan2(30, 0)) % 360)  # p4 -> c2 is up
    assert b.c1_length() == 10.0
    assert b.c2_length() == 30.0


def test_path_segment_counts() -> None:
    assert [count_sub_splines(n) for n in (0, 1, 3, 4, 5, 7, 10)] == [0, 0, 0, 1, 1, 2, 3]


def test_path_segments_join_smoothly() -> None:
    path = BezierPath(
        (Pt(0, 0), Pt(10, 0), Pt(20, 10), Pt(30, 10), Pt(40, 15), Pt(50, 20), Pt(60, 20))
    )
    assert path.count() == 2
    first = path.segment(1)
    assert first.c1.x == pytest.approx(10.0)  # the first segment is untouched
    assert first.c1.y == pytest.approx(0.0)
    second = path.segment(2)
    # The second segment's first handle is re-aimed along the previous handle's continuation
    # (previous handle p3->c2 points left, so the continuation points right), keeping its length.
    assert second.p1 == Pt(30, 10)
    assert second.c1.y == pytest.approx(10.0)
    assert second.c1.x == pytest.approx(30 + math.hypot(10, 5))
    assert second.c2.x == pytest.approx(50.0)
    assert second.c2.y == pytest.approx(20.0)


def test_path_length_points_and_angles() -> None:
    path = BezierPath((Pt(0, 0), Pt(10, 0), Pt(20, 0), Pt(30, 0), Pt(40, 0), Pt(50, 0), Pt(60, 0)))
    assert path.length() == pytest.approx(60.0)
    pts = path.points()
    assert pts[0] == Pt(0, 0)
    assert pts[-1] == Pt(60, 0)
    assert len(pts) == len(set(pts))  # the shared joint is not duplicated
    assert path.start_angle() == 0.0
    assert path.end_angle() == pytest.approx(180.0)
    assert path.c1_length() == 10.0
    assert path.c2_length() == 10.0


def test_short_path_is_rejected_or_zero() -> None:
    short = BezierPath((Pt(0, 0), Pt(1, 1)))
    assert short.count() == 0
    assert short.length() == 0.0
    assert short.start_angle() == 0.0
    assert short.end_angle() == 0.0
    assert short.c1_length() == 0.0
    assert short.c2_length() == 0.0
    with pytest.raises(ValueError, match="not enough points"):
        short.segment(1)
    full = BezierPath((Pt(0, 0), Pt(1, 0), Pt(2, 0), Pt(3, 0)))
    with pytest.raises(ValueError, match="does not exist"):
        full.segment(2)


def test_arc() -> None:
    quarter = Arc(Pt(0, 0), 10.0, 0.0, 90.0)
    assert quarter.angle_arc() == pytest.approx(90.0)
    assert quarter.length() == pytest.approx(10 * math.pi / 2)
    assert quarter.p1().x == pytest.approx(10.0)
    assert quarter.p2().y == pytest.approx(-10.0)  # up on screen
    assert quarter.start_angle() == 0.0
    assert quarter.end_angle() == 90.0
    assert Arc(Pt(0, 0), 5.0, 30.0, 30.0).angle_arc() == 360.0  # equal angles: a full circle
    assert Arc(Pt(0, 0), 5.0, 0.0, 360.0).angle_arc() == 360.0
    assert Arc(Pt(0, 0), 5.0, 270.0, 90.0).angle_arc() == pytest.approx(180.0)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (90, 90), (360, 360), (720, 360), (370, 10), (-10, 350), (-360, 360), (180, 180)],
)
def test_normalize_angle(value: float, expected: float) -> None:
    assert normalize_angle(value, 0.0, 360.0) == pytest.approx(expected)
