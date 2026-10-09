"""Curves and arcs, ported from Seamly2D (src/libs/vgeometry).

Seamly2D has no closed-form curve length. It flattens a cubic Bezier with an adaptive subdivision
(`VAbstractCubicBezier::PointBezier_r`, from Anti-Grain Geometry) and sums the segment lengths
(`QPainterPath::length`). That flattened length is what formulas see as `Spl_A_B`, `SplPath_A_B`,
and so on, so we reproduce the algorithm exactly rather than integrate the curve.

Values are in Seamly2D's pixel scale (see `yoko_engine.units`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

from yoko_engine.fuzzy import fuzzy_compare_possible_nulls
from yoko_engine.geometry.qt import Line, Pt

_COLLINEARITY_EPSILON = 1e-30
_RECURSION_LIMIT = 32
# m_approximation_scale is 1.0 in Seamly2D, so the distance tolerance is 0.5 px, squared.
_DISTANCE_TOLERANCE_SQUARE = 0.5 * 0.5
# m_angle_tolerance and m_cusp_limit are 0.0 in Seamly2D, which makes every "angle condition"
# branch of the original AGG routine unreachable; they are omitted here.


def _sq_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    return dx * dx + dy * dy


def _subdivide(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    x3: float,
    y3: float,
    x4: float,
    y4: float,
    level: int,
    out: list[Pt],
) -> None:
    """PointBezier_r: append the interior points of the flattened curve to `out`."""
    if level > _RECURSION_LIMIT:
        return

    x12 = (x1 + x2) / 2
    y12 = (y1 + y2) / 2
    x23 = (x2 + x3) / 2
    y23 = (y2 + y3) / 2
    x34 = (x3 + x4) / 2
    y34 = (y3 + y4) / 2
    x123 = (x12 + x23) / 2
    y123 = (y12 + y23) / 2
    x234 = (x23 + x34) / 2
    y234 = (y23 + y34) / 2
    x1234 = (x123 + x234) / 2
    y1234 = (y123 + y234) / 2

    dx = x4 - x1
    dy = y4 - y1
    d2 = abs((x2 - x4) * dy - (y2 - y4) * dx)
    d3 = abs((x3 - x4) * dy - (y3 - y4) * dx)

    case = (int(d2 > _COLLINEARITY_EPSILON) << 1) + int(d3 > _COLLINEARITY_EPSILON)
    if case == 0:
        # All collinear, or p1 == p4.
        k = dx * dx + dy * dy
        if k < 0.000000001:
            d2 = _sq_distance(x1, y1, x2, y2)
            d3 = _sq_distance(x4, y4, x3, y3)
        else:
            k = 1 / k
            d2 = k * ((x2 - x1) * dx + (y2 - y1) * dy)
            d3 = k * ((x3 - x1) * dx + (y3 - y1) * dy)
            if 0 < d2 < 1 and 0 < d3 < 1:
                return  # simple collinear case 1---2---3---4: just the two end points
            if d2 <= 0:
                d2 = _sq_distance(x2, y2, x1, y1)
            elif d2 >= 1:
                d2 = _sq_distance(x2, y2, x4, y4)
            else:
                d2 = _sq_distance(x2, y2, x1 + d2 * dx, y1 + d2 * dy)
            if d3 <= 0:
                d3 = _sq_distance(x3, y3, x1, y1)
            elif d3 >= 1:
                d3 = _sq_distance(x3, y3, x4, y4)
            else:
                d3 = _sq_distance(x3, y3, x1 + d3 * dx, y1 + d3 * dy)
        if d2 > d3:
            if d2 < _DISTANCE_TOLERANCE_SQUARE:
                out.append(Pt(x2, y2))
                return
        elif d3 < _DISTANCE_TOLERANCE_SQUARE:
            out.append(Pt(x3, y3))
            return
    elif case == 1:
        # p1, p2, p4 collinear; p3 is significant.
        if d3 * d3 <= _DISTANCE_TOLERANCE_SQUARE * (dx * dx + dy * dy):
            out.append(Pt(x23, y23))
            return
    elif case == 2:
        # p1, p3, p4 collinear; p2 is significant.
        if d2 * d2 <= _DISTANCE_TOLERANCE_SQUARE * (dx * dx + dy * dy):
            out.append(Pt(x23, y23))
            return
    else:
        # Regular case.
        if (d2 + d3) * (d2 + d3) <= _DISTANCE_TOLERANCE_SQUARE * (dx * dx + dy * dy):
            out.append(Pt(x23, y23))
            return

    _subdivide(x1, y1, x12, y12, x123, y123, x1234, y1234, level + 1, out)
    _subdivide(x1234, y1234, x234, y234, x34, y34, x4, y4, level + 1, out)


def flatten_bezier(p1: Pt, p2: Pt, p3: Pt, p4: Pt) -> list[Pt]:
    """GetCubicBezierPoints: the polyline Seamly2D uses for a cubic Bezier."""
    points = [p1]
    _subdivide(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y, p4.x, p4.y, 0, points)
    points.append(p4)
    return points


def path_length(points: list[Pt]) -> float:
    """VAbstractCurve::PathLength (QPainterPath::length of a polyline)."""
    if len(points) < 2:
        return 0.0
    total = 0.0
    for a, b in pairwise(points):
        total += Line(a, b).length()
    return total


@dataclass(frozen=True, slots=True)
class Bezier:
    """A cubic Bezier through `p1` and `p4` with control points `c1` and `c2`
    (Seamly2D `VCubicBezier`, whose control points are ordinary pattern points)."""

    p1: Pt
    c1: Pt
    c2: Pt
    p4: Pt

    def points(self) -> list[Pt]:
        return flatten_bezier(self.p1, self.c1, self.c2, self.p4)

    def length(self) -> float:
        return path_length(self.points())

    def start_angle(self) -> float:
        return Line(self.p1, self.c1).angle()

    def end_angle(self) -> float:
        return Line(self.p4, self.c2).angle()

    def c1_length(self) -> float:
        return Line(self.p1, self.c1).length()

    def c2_length(self) -> float:
        return Line(self.p4, self.c2).length()


def count_sub_splines(size: int) -> int:
    """VCubicBezierPath::CountSubSpl(size)."""
    if size <= 0:
        return 0
    return math.floor(abs((size - 4) / 3.0 + 1))


@dataclass(frozen=True, slots=True)
class BezierPath:
    """A chain of cubic Beziers: points are p0 c1 c2 p3 c4 c5 p6 ... (`VCubicBezierPath`)."""

    pts: tuple[Pt, ...]

    def count(self) -> int:
        return count_sub_splines(len(self.pts))

    def segment(self, index: int) -> Bezier:
        """Segment `index` (1-based). Like Seamly2D, the first control point of every segment after
        the first is re-aimed to continue the previous segment's last handle (a smooth join),
        keeping its own length."""
        if len(self.pts) < 4:
            raise ValueError("not enough points to create the spline")
        if index < 1 or index > self.count():
            raise ValueError("this spline does not exist")
        base = (index - 1) * 3
        p2 = self.pts[base + 1]
        if base + 1 > 1:
            b = self.pts[base]
            foot1 = Line(b, self.pts[base - 1])
            foot2 = Line(b, p2)
            p2 = foot2.set_angle(foot1.angle() + 180).p2
        return Bezier(self.pts[base], p2, self.pts[base + 2], self.pts[base + 3])

    def segments(self) -> list[Bezier]:
        return [self.segment(i) for i in range(1, self.count() + 1)]

    def length(self) -> float:
        total = 0.0
        for seg in self.segments():
            total += seg.length()
        return total

    def points(self) -> list[Pt]:
        out: list[Pt] = []
        for seg in self.segments():
            if out:
                out.pop()
            out.extend(seg.points())
        return out

    def start_angle(self) -> float:
        return self.segment(1).start_angle() if self.count() > 0 else 0.0

    def end_angle(self) -> float:
        n = self.count()
        return self.segment(n).end_angle() if n > 0 else 0.0

    def c1_length(self) -> float:
        return self.segment(1).c1_length() if self.count() > 0 else 0.0

    def c2_length(self) -> float:
        n = self.count()
        return self.segment(n).c2_length() if n > 0 else 0.0


def normalize_angle(value: float, start: float, end: float) -> float:
    """`normalize` in src/libs/vmisc/def.cpp: wrap `value` into (start, end], with exact multiples
    of `end` returning `end`."""
    if abs(value) != start and math.fmod(abs(value), end) < 1e-9:
        return end
    rng = end - start
    offset = value - start
    return (offset - (math.floor(offset / rng) * rng)) + start


@dataclass(frozen=True, slots=True)
class Arc:
    """A circular arc from angle `f1` to `f2` (degrees, counter-clockwise on screen)."""

    center: Pt
    radius: float
    f1: float
    f2: float

    def angle_arc(self) -> float:
        """VAbstractArc::AngleArc."""
        diff = abs(self.f1 - self.f2)
        if fuzzy_compare_possible_nulls(diff, 0) or fuzzy_compare_possible_nulls(diff, 360):
            return 360.0
        l1 = Line(Pt(0, 0), Pt(100, 0)).set_angle(self.f1)
        l2 = Line(Pt(0, 0), Pt(100, 0)).set_angle(self.f2)
        return l1.angle_to(l2)

    def length(self) -> float:
        return self.radius * math.radians(self.angle_arc())

    def start_angle(self) -> float:
        return self.f1

    def end_angle(self) -> float:
        return self.f2

    def p1(self) -> Pt:
        line = Line(self.center, Pt(self.center.x + self.radius, self.center.y))
        return line.set_angle(self.f1).p2

    def p2(self) -> Pt:
        line = Line(self.center, Pt(self.center.x + self.radius, self.center.y))
        return line.set_angle(self.f2).p2


__all__ = [
    "Arc",
    "Bezier",
    "BezierPath",
    "count_sub_splines",
    "flatten_bezier",
    "normalize_angle",
    "path_length",
]
