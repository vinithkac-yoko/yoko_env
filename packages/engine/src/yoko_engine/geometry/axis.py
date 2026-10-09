"""Rays and curve/axis intersection, from `VGObject::BuildRay` and `VToolCurveIntersectAxis`.

Seamly2D finds where a curve meets an axis by clipping a very long line to a huge scene rectangle
(`QRectF(0, 0, INT_MAX, INT_MAX)` shifted to be centred on the origin) and intersecting it with the
curve's flattened polyline. The huge coordinates matter for the last bits, so they are reproduced.
"""

from __future__ import annotations

import math
from itertools import pairwise

from yoko_engine.geometry.qt import IntersectType, Line, Pt

_INT_MAX = 2147483647
# rectangle = QRectF(0, 0, INT_MAX, INT_MAX).translated(-INT_MAX / 2.0, -INT_MAX / 2.0)
_LEFT = -_INT_MAX / 2.0
_TOP = -_INT_MAX / 2.0
_WIDTH = float(_INT_MAX)
_HEIGHT = float(_INT_MAX)


def _rect_contains(p: Pt) -> bool:
    """QRectF::contains for the scene rectangle."""
    left, right = _LEFT, _LEFT + _WIDTH
    top, bottom = _TOP, _TOP + _HEIGHT
    return not (p.x < left or p.x > right or p.y < top or p.y > bottom)


def build_line(p1: Pt, length: float, angle: float) -> Line:
    """VGObject::BuildLine: start from QLineF() (a line to the origin), set p1, then angle, then
    length."""
    line = Line(p1, Pt(0.0, 0.0))
    line = line.set_angle(angle)
    return line.set_length(length)


def _line_intersect_rect(line: Line) -> Pt:
    x1, y1 = _LEFT, _TOP
    x2, y2 = _LEFT + _WIDTH, _TOP + _HEIGHT
    edges = (
        Line(Pt(x1, y1), Pt(x1, y2)),
        Line(Pt(x1, y1), Pt(x2, y1)),
        Line(Pt(x1, y2), Pt(x2, y2)),
        Line(Pt(x2, y1), Pt(x2, y2)),
    )
    for edge in edges:
        kind, point = line.intersects(edge)
        if kind is IntersectType.BOUNDED and point is not None:
            return point
    return Pt(0.0, 0.0)


def build_ray(p: Pt, angle: float) -> Pt:
    """The point where a ray from `p` at `angle` leaves the scene rectangle."""
    if not _rect_contains(p):
        raise ValueError("a point lies outside the scene rectangle")
    diagonal = math.sqrt(math.pow(_HEIGHT, 2) + math.pow(_WIDTH, 2))
    return _line_intersect_rect(build_line(p, diagonal, angle))


def curve_intersect_line(points: list[Pt], line: Line) -> list[Pt]:
    """VAbstractCurve::CurveIntersectLine: crossings of `line` with each polyline segment."""
    found: list[Pt] = []
    for a, b in pairwise(points):
        kind, point = line.intersects(Line(a, b))
        if kind is IntersectType.BOUNDED and point is not None:
            found.append(point)
    return found


def curve_axis_point(axis_point: Pt, angle: float, curve_points: list[Pt]) -> Pt | None:
    """VToolCurveIntersectAxis::FindPoint: where the axis through `axis_point` meets the curve.

    Tries the ray at `angle`, then the opposite ray; among several crossings the nearest to
    `axis_point` wins (a later crossing wins a tie, as Seamly2D's QMap insert does).
    """
    axis = Line(axis_point, build_ray(axis_point, angle))
    points = curve_intersect_line(curve_points, axis)
    if not points:
        axis2 = Line(axis_point, build_ray(axis_point, angle + 180))
        points = curve_intersect_line(curve_points, axis2)
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    lengths: dict[float, int] = {}
    for i, p in enumerate(points):
        lengths[Line(p, axis_point).length()] = i
    return points[lengths[min(lengths)]]
