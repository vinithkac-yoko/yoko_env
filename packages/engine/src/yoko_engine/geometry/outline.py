"""Piece outlines: joining the points of a piece's nodes, and cleaning the result.

Ported from `VPiecePath::PathPoints` (src/libs/vpatterndb/vpiecepath.cpp) and
`VAbstractPiece::CorrectEquidistantPoints`, `CheckLoops` (src/libs/vlayout/vabstractpiece.*), which
Seamly2D applies to a piece's main path (`VPiece::mainPathPoints`).

One routine is a stand-in rather than a copy: `VAbstractPiece::Crossing` asks Qt whether two
painter paths overlap (`QPainterPath::intersects`, which runs Qt's path clipper). `crossing` here
answers the same question for polygons by a simpler rule, checked against Qt on the 27 real calls
the test patterns make (all agree) and on random polygons (about 95 % agree; the rest are
self-crossing, zero-width shapes). It only matters when a path has a loop.
"""

from __future__ import annotations

from yoko_engine.fuzzy import fuzzy_is_null
from yoko_engine.geometry.circle_line import (
    ACCURACY_POINT_ON_LINE,
    is_point_on_line_segment,
    is_point_on_line_via_pdp,
)
from yoko_engine.geometry.cut import from_begin, to_end
from yoko_engine.geometry.qt import IntersectType, Line, Pt, points_equal


# -- polyline helpers (VAbstractCurve) -----------------------------------------------------------
def is_point_on_curve(points: list[Pt], p: Pt) -> bool:
    """VAbstractCurve::isPointOnCurve."""
    if not points:
        return False
    if len(points) < 2:
        return points_equal(points[0], p)
    return any(
        is_point_on_line_segment(p, points[i], points[i + 1]) for i in range(len(points) - 1)
    )


def segment_points(points: list[Pt], begin: Pt, end: Pt, reverse: bool) -> list[Pt]:
    """VAbstractCurve::GetSegmentPoints: the part of a curve's polyline between two points."""
    segment = list(reversed(points)) if reverse else list(points)
    start, finish = begin, end
    if points_equal(begin, end):
        start, finish = segment[0], segment[-1]
    segment, _ = from_begin(segment, start)
    segment, _ = to_end(segment, finish)
    return segment


# -- cleaning a closed path ---------------------------------------------------------------------
def remove_duplicates(points: list[Pt], remove_first_and_last: bool) -> list[Pt]:
    """VAbstractPiece::RemoveDublicates: drop points closer than the accuracy to the one before."""
    acc = ACCURACY_POINT_ON_LINE
    p = list(points)
    first_equals_last = len(p) > 1 and abs(p[0].x - p[-1].x) < acc and abs(p[0].y - p[-1].y) < acc
    if remove_first_and_last and first_equals_last:
        p.pop()
    i = 0
    while i < len(p) - 1:
        if abs(p[i].x - p[i + 1].x) < acc and abs(p[i].y - p[i + 1].y) < acc:
            if not remove_first_and_last and i == len(p) - 1:
                i += 1
                continue
            del p[i + 1]
            continue  # Seamly2D does --i then ++i: it looks at the same index again
        i += 1
    return p


def correct_equidistant_points(points: list[Pt], remove_first_and_last: bool = True) -> list[Pt]:
    """VAbstractPiece::CorrectEquidistantPoints: remove equal points. A point is also removed when
    it lies on the line between two neighbours that are the same point (a spike); a point that is
    merely collinear with different neighbours stays."""
    if len(points) < 4:
        return points
    buf1 = remove_duplicates(points, remove_first_and_last)
    if len(buf1) < 3:
        return buf1
    prev = -1
    buf2: list[Pt] = []
    last = len(buf1) - 1
    for i, i_point in enumerate(buf1):
        if prev == -1:
            prev = last if i == 0 else i - 1
        nxt = 0 if i == last else i + 1
        prev_point = buf1[prev]
        next_point = buf1[nxt]
        on_line = is_point_on_line_via_pdp(i_point, prev_point, next_point) and points_equal(
            prev_point, next_point
        )
        end_case = i in (0, last) and (
            points_equal(i_point, prev_point) or points_equal(i_point, next_point)
        )
        if not on_line or end_case:
            buf2.append(i_point)
            prev = -1
    return remove_duplicates(buf2, False)


def sub_path(path: list[Pt], start: int, end: int) -> list[Pt]:
    """VAbstractPiece::SubPath: the points from `start` to `end`, wrapping round the end."""
    if not path or not 0 <= start < len(path) or not 0 <= end < len(path) or start == end:
        return path
    out: list[Pt] = []
    i = start - 1
    while True:
        i += 1
        if i >= len(path):
            i = 0
        out.append(path[i])
        if i == end:
            return out


def sum_trapezoids(points: list[Pt]) -> float:
    """VAbstractPiece::sumTrapezoids: twice the signed area of a polygon."""
    n = len(points)
    total = 0.0
    if n > 2:
        for i in range(n):
            if i == 0:
                total += points[i].x * (points[n - 1].y - points[i + 1].y)
            elif i == n - 1:
                total += points[i].x * (points[i - 1].y - points[0].y)
            else:
                total += points[i].x * (points[i - 1].y - points[i + 1].y)
    return total


def _bounds(points: list[Pt]) -> tuple[float, float, float, float]:
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _inside(p: Pt, polygon: list[Pt]) -> bool:
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        a, b = polygon[i], polygon[j]
        if (a.y > p.y) != (b.y > p.y) and p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x:
            inside = not inside
        j = i
    return inside


def _area(points: list[Pt]) -> float:
    return abs(sum_trapezoids(points)) / 2.0 if len(points) > 2 else 0.0


def crossing(sub1: list[Pt], sub2: list[Pt]) -> bool:
    """VAbstractPiece::Crossing: do the two closed polygons overlap? (See the module note.)

    Checked against Qt: a polygon with no area (a sliver or a single point) overlaps nothing;
    otherwise they overlap when an edge of one meets an edge of the other (touching counts) or one
    has a vertex strictly inside the other."""
    if not sub1 or not sub2:
        return False
    x1, y1, x2, y2 = _bounds(sub1)
    u1, v1, u2, v2 = _bounds(sub2)
    if not (x1 < u2 and u1 < x2 and y1 < v2 and v1 < y2):
        return False
    if _area(sub1) < 1e-6 or _area(sub2) < 1e-6:
        return False
    closed1 = [*sub1, sub1[0]]
    closed2 = [*sub2, sub2[0]]
    for i in range(len(closed1) - 1):
        a = Line(closed1[i], closed1[i + 1])
        for j in range(len(closed2) - 1):
            kind, _ = a.intersects(Line(closed2[j], closed2[j + 1]))
            if kind is IntersectType.BOUNDED:
                return True
    return _inside(sub1[0], sub2) or _inside(sub2[0], sub1)


def _parallel_cross_point(line1: Line, line2: Line) -> Pt | None:
    """VAbstractPiece::ParallelCrossPoint."""
    if points_equal(line1.p2, line2.p2) or points_equal(line1.p2, line2.p1):
        return line1.p2
    if points_equal(line1.p1, line2.p1) or points_equal(line1.p1, line2.p2):
        return line1.p1
    return None


def _check_intersection(
    points: list[Pt], i: int, i_next: int, j: int, j_next: int, cross: Pt
) -> bool:
    """VAbstractPiece::CheckIntersection: is a crossing a real loop (as opposed to a touch)?"""
    sub1 = [*sub_path(points, i_next, j), cross]
    sub1 = check_loops(correct_equidistant_points(sub1, False))
    sub1_sum = sum_trapezoids(sub1)
    sub2 = [*sub_path(points, j_next, i), cross]
    sub2 = check_loops(correct_equidistant_points(sub2, False))
    sub2_sum = sum_trapezoids(sub2)
    if sub1_sum < 0 and sub2_sum < 0:
        return crossing(sub1, sub2)
    return not crossing(sub1, sub2)


_NO, _BOUNDED, _PARALLEL = 0, 1, 2


def check_loops(points: list[Pt]) -> list[Pt]:
    """VAbstractPiece::CheckLoops: find and cut out loops (the path crossing itself)."""
    count = len(points)
    if count < 4:
        return points
    path_closed = points_equal(points[0], points[-1])
    out: list[Pt] = []
    i = 0
    j = j_next = 0
    cross = Pt(0.0, 0.0)
    while i < count:
        if i > count - 3:
            out.append(points[i])
            i += 1
            continue
        status = _NO
        line1 = Line(points[i], points[i + 1])
        j = count - 1
        while j >= i + 2:
            j_next = 0 if j == count - 1 else j + 1
            line2 = Line(points[j], points[j_next])
            if fuzzy_is_null(line2.length()):
                j -= 1
                continue
            unique = [i, i + 1, j]
            last = 0 if (path_closed and j_next == count - 1) else j_next
            if last not in unique:
                unique.append(last)
            kind, found = line1.intersects(line2)
            if found is not None:
                cross = found
            if kind is IntersectType.NO_INTERSECTION:
                if (
                    is_point_on_line_via_pdp(points[j], points[i], points[i + 1])
                    and len(unique) == 4
                ):
                    tmp1 = line1.set_angle(line1.angle() + 90)
                    k1, _ = tmp1.intersects(line2)
                    tmp2 = line2.set_angle(line2.angle() + 90)
                    k2, _ = line1.intersects(tmp2)
                    if k1 is IntersectType.BOUNDED or k2 is IntersectType.BOUNDED:
                        c_point = _parallel_cross_point(line1, line2)
                        if c_point is None or _check_intersection(
                            points, i, i + 1, j, j_next, c_point
                        ):
                            status = _PARALLEL
                            break
            elif kind is IntersectType.BOUNDED and len(unique) == 4:
                touches_end = (
                    points_equal(line1.p1, cross)
                    or points_equal(line1.p2, cross)
                    or points_equal(line2.p1, cross)
                    or points_equal(line2.p2, cross)
                )
                if not touches_end or _check_intersection(points, i, i + 1, j, j_next, cross):
                    status = _BOUNDED
                    break
            status = _NO
            j -= 1
        if status == _PARALLEL:
            out.append(points[i])
            out.append(points[j_next])
            i = j_next if j_next > j else j
        elif status == _BOUNDED:
            out.append(points[i])
            out.append(cross)
            i = j
        else:
            out.append(points[i])
        i += 1
    return out
