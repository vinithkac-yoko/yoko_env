"""Geometry conventions of Qt's QLineF, which Seamly2D uses for every point calculation."""

from __future__ import annotations

import math

import pytest
from yoko_engine.geometry import Line, Pt, fuzzy_compare, fuzzy_is_null, points_equal
from yoko_engine.geometry.qt import IntersectType


def L(x1: float, y1: float, x2: float, y2: float) -> Line:
    return Line(Pt(x1, y1), Pt(x2, y2))


def close(p: Pt, x: float, y: float) -> None:
    assert p.x == pytest.approx(x, abs=1e-9)
    assert p.y == pytest.approx(y, abs=1e-9)


def test_angle_convention_y_down_counter_clockwise_on_screen() -> None:
    assert L(0, 0, 10, 0).angle() == 0.0
    assert L(0, 0, 0, -10).angle() == pytest.approx(90.0)  # up on screen
    assert L(0, 0, -10, 0).angle() == pytest.approx(180.0)
    assert L(0, 0, 0, 10).angle() == pytest.approx(270.0)  # down on screen
    assert L(0, 0, 10, 10).angle() == pytest.approx(315.0)


def test_angle_near_360_collapses_to_zero() -> None:
    assert L(0, 0, 10, 1e-14).angle() == 0.0


def test_set_angle_keeps_length() -> None:
    line = L(1, 1, 11, 1).set_angle(90)
    close(line.p2, 1.0, -9.0)
    assert line.length() == pytest.approx(10.0)
    close(L(0, 0, 100, 0).set_angle(270).p2, 0.0, 100.0)  # the engine's "5 cm below" case


def test_set_length_scales_about_p1_and_ignores_null_lines() -> None:
    close(L(2, 3, 5, 7).set_length(10).p2, 2 + 6.0, 3 + 8.0)
    null = L(4, 4, 4, 4)
    assert null.set_length(10) is null


def test_normal_vector_is_rotated_counter_clockwise_on_screen() -> None:
    n = L(0, 0, 10, 0).normal_vector()
    close(n.p2, 0.0, -10.0)
    assert n.angle() == pytest.approx(90.0)
    close(L(0, 0, 0, -10).normal_vector().p2, -10.0, 0.0)


def test_angle_to() -> None:
    a = L(0, 0, 10, 0)
    assert a.angle_to(L(0, 0, 0, -10)) == pytest.approx(90.0)
    assert a.angle_to(L(0, 0, 0, 10)) == pytest.approx(270.0)
    assert a.angle_to(a) == 0.0
    assert a.angle_to(L(1, 1, 1, 1)) == 0.0


def test_intersects_bounded_and_unbounded() -> None:
    kind, p = L(0, 0, 10, 10).intersects(L(0, 10, 10, 0))
    assert kind is IntersectType.BOUNDED
    assert p is not None
    close(p, 5.0, 5.0)
    kind, p = L(0, 0, 1, 1).intersects(L(0, 10, 10, 0))
    assert kind is IntersectType.UNBOUNDED
    assert p is not None
    close(p, 5.0, 5.0)
    assert L(0, 0, 10, 0).intersects(L(0, 1, 10, 1)) == (IntersectType.NO_INTERSECTION, None)


def test_fuzzy_helpers_follow_qt() -> None:
    assert fuzzy_is_null(1e-13)
    assert not fuzzy_is_null(1e-11)
    assert fuzzy_compare(1.0, 1.0 + 1e-13)
    assert not fuzzy_compare(1.0, 1.0 + 1e-9)
    assert points_equal(Pt(0.0, 5.0), Pt(1e-13, 5.0))
    assert not points_equal(Pt(0.0, 5.0), Pt(1e-9, 5.0))
    assert L(0, 0, 1e-14, 0).is_null()


def test_unit_vector_of_a_null_line_is_nan() -> None:
    v = L(0, 0, 0, 0).unit_vector()
    assert math.isnan(v.p2.x)
