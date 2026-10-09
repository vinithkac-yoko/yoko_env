"""Circle and line helpers from `VGObject` (src/libs/vgeometry/vgobject.cpp), in pixel scale."""

from __future__ import annotations

import math

from yoko_engine.fuzzy import fuzzy_compare_possible_nulls, fuzzy_is_null
from yoko_engine.geometry.qt import IntersectType, Line, Pt

# accuracyPointOnLine = (0.1555 mm / 25.4) * 96 (src/libs/vmisc/def.h)
ACCURACY_POINT_ON_LINE = (0.1555 / 25.4) * 96.0


def line_coefficients(line: Line) -> tuple[float, float, float]:
    """Coefficients of ax + by + c = 0 for the line through p1 and p2."""
    p1 = line.p1
    a = line.p2.y - p1.y
    b = p1.x - line.p2.x
    c = -a * p1.x - b * p1.y
    return a, b, c


def closest_point(line: Line, point: Pt) -> Pt:
    """Projection of `point` onto the (infinite) line (VGObject::ClosestPoint)."""
    a, b, _ = line_coefficients(line)
    x = point.x + a
    y = b + point.y
    kind, found = line.intersects(Line(point, Pt(x, y)))
    if kind in (IntersectType.UNBOUNDED, IntersectType.BOUNDED) and found is not None:
        return found
    return point


def _add_vector(p: Pt, p1: Pt, p2: Pt, k: float) -> Pt:
    return Pt(p.x + (p2.x - p1.x) * k, p.y + (p2.y - p1.y) * k)


def line_intersect_circle(center: Pt, radius: float, line: Line) -> tuple[int, Pt, Pt]:
    """VGObject::LineIntersectCircle. Returns (count, p1, p2) with count 0, 1 or 2."""
    zero = Pt(0.0, 0.0)
    if fuzzy_is_null(line.length()):
        return 0, zero, zero
    a, b, _ = line_coefficients(line)
    p = closest_point(line, center)
    d = Line(center, p).length()
    if fuzzy_compare_possible_nulls(d, radius):
        flag = 1
    elif radius > d:
        flag = 2
    else:
        return 0, zero, zero
    k = math.sqrt(abs(radius * radius - d * d))
    t = Line(Pt(0, 0), Pt(b, -a)).length()
    p1 = _add_vector(p, Pt(0, 0), Pt(-b, a), k / t)
    p2 = _add_vector(p, Pt(0, 0), Pt(b, -a), k / t)
    return flag, p1, p2


def _perp_dot_product(p1: Pt, p2: Pt, t: Pt) -> float:
    return (p1.x - t.x) * (p2.y - t.y) - (p1.y - t.y) * (p2.x - t.x)


def _epsilon(p1: Pt, p2: Pt) -> float:
    line = Line(p1, p2)
    line = line.set_angle(line.angle() + 90)
    line = line.set_length(ACCURACY_POINT_ON_LINE)
    return abs(_perp_dot_product(p1, p2, line.p2))


def is_point_on_line_via_pdp(t: Pt, p1: Pt, p2: Pt) -> bool:
    p = abs(_perp_dot_product(p1, p2, t))
    e = _epsilon(p1, p2)
    return p < e or fuzzy_compare_possible_nulls(p, e)


def is_point_on_line_segment(t: Pt, p1: Pt, p2: Pt) -> bool:
    """VGObject::IsPointOnLineSegment."""
    acc = ACCURACY_POINT_ON_LINE
    in_x = (p1.x <= t.x <= p2.x) or (p2.x <= t.x <= p1.x)
    if not in_x and not abs(p1.x - t.x) <= acc and not abs(p2.x - t.x) <= acc:
        return False
    in_y = (p1.y <= t.y <= p2.y) or (p2.y <= t.y <= p1.y)
    if not in_y and not abs(p1.y - t.y) <= acc and not abs(p2.y - t.y) <= acc:
        return False
    return is_point_on_line_via_pdp(t, p1, p2)


def find_circle_line_point(radius: float, center: Pt, first: Pt, second: Pt) -> Pt | None:
    """IntersectArcLineTool::FindPoint: the circle/line intersection Seamly2D picks, or None."""
    count, p1, p2 = line_intersect_circle(center, radius, Line(first, second))
    if count == 0:
        return None
    if count == 1:
        return p1
    flag1 = is_point_on_line_segment(p1, first, second)
    flag2 = is_point_on_line_segment(p2, first, second)
    if flag1 == flag2:
        # No way to choose by position: take the one closest to the segment's first point.
        if Line(first, p1).length() <= Line(first, p2).length():
            return p1
        return p2
    return p1 if flag1 else p2
