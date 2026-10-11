"""Point tools (src/libs/vtools/tools/drawTools/toolpoint) and the plain line."""

from __future__ import annotations

import math

from yoko_engine.evalcore import Ctx, Issue, ObjectError
from yoko_engine.fuzzy import fuzzy_compare_possible_nulls
from yoko_engine.geometry import Line, Pt
from yoko_engine.geometry.circle_line import (
    closest_point,
    find_circle_line_point,
    line_intersect_circle,
)
from yoko_engine.geometry.cut import q_round
from yoko_engine.geometry.qt import IntersectType
from yoko_engine.model import Obj
from yoko_engine.units import from_pixel, to_pixel

CURRENT_LENGTH = "CurrentLength"


# -- point kinds (src/libs/vtools/tools/drawTools/toolpoint) -------------------------------------
def single(c: Ctx, o: Obj) -> None:
    # VPattern::ParseToolBasePoint: x and y default to 10.0 and are in the pattern unit.
    x = to_pixel(c.number(o, "x", "10.0"), c.unit)
    y = to_pixel(c.number(o, "y", "10.0"), c.unit)
    c.add_point(o, Pt(x, y))


def end_line(c: Ctx, o: Obj) -> None:
    base = c.point(o, "basePoint")
    line = Line(base.p, Pt(base.p.x + 100, base.p.y))
    line = line.set_angle(c.check(o, "angle", "0.0"))  # the angle is set first
    line = line.set_length(to_pixel(c.check(o, "length", "100.0"), c.unit))
    c.add_point(o, line.p2)
    c.add_line(o.id, base, c.ev.points[o.id])


def along_line(c: Ctx, o: Obj) -> None:
    first = c.point(o, "firstPoint")
    second = c.point(o, "secondPoint")
    line = Line(first.p, second.p)
    # The special variable CurrentLength exists only while this tool evaluates its formula.
    c.set_symbol(CURRENT_LENGTH, from_pixel(line.length(), c.unit), o.id)
    try:
        length = to_pixel(c.check(o, "length", "100.0"), c.unit)
    finally:
        c.ev.symbols.pop(CURRENT_LENGTH, None)
        c.ev.owners.pop(CURRENT_LENGTH, None)
        c.rec.symbols.discard(CURRENT_LENGTH)
    c.add_point(o, line.set_length(length).p2)
    new = c.ev.points[o.id]
    c.add_line(o.id, first, new)
    c.add_line(o.id, new, second)


def normal(c: Ctx, o: Obj) -> None:
    first = c.point(o, "firstPoint")
    second = c.point(o, "secondPoint")
    length = to_pixel(c.check(o, "length", "100.0"), c.unit)
    angle = c.number(o, "angle", "0.0")  # plain number, not a formula
    normal = Line(first.p, second.p).normal_vector()
    normal = normal.set_angle(normal.angle() + angle)
    c.add_point(o, normal.set_length(length).p2)
    c.add_line(o.id, first, c.ev.points[o.id])


def _bisector_angle(first: Pt, second: Pt, third: Pt) -> float:
    line1 = Line(second, first)
    line2 = Line(second, third)
    angle = line1.angle_to(line2)
    if angle > 180:
        angle = 360 - angle
        return line1.angle() - angle / 2
    return line1.angle() + angle / 2


def bisector(c: Ctx, o: Obj) -> None:
    first = c.point(o, "firstPoint")
    second = c.point(o, "secondPoint")
    third = c.point(o, "thirdPoint")
    length = to_pixel(c.check(o, "length", "100.0"), c.unit)
    line = Line(second.p, first.p)
    line = line.set_angle(_bisector_angle(first.p, second.p, third.p))
    c.add_point(o, line.set_length(length).p2)
    c.add_line(o.id, second, c.ev.points[o.id])


def intersect_xy(c: Ctx, o: Obj) -> None:
    first = c.point(o, "firstPoint")
    second = c.point(o, "secondPoint")
    c.add_point(o, Pt(first.p.x, second.p.y))
    new = c.ev.points[o.id]
    c.add_line(o.id, first, new)
    c.add_line(o.id, second, new)


def _line_intersect_axis_point(axis: Line, line: Line) -> Pt | None:
    kind, point = axis.intersects(line)
    if kind in (IntersectType.UNBOUNDED, IntersectType.BOUNDED) and point is not None:
        a1, a2 = axis.angle(), line.angle()
        if fuzzy_compare_possible_nulls(a1, a2) or fuzzy_compare_possible_nulls(abs(a1 - a2), 180):
            return None
        return point
    return None


def line_intersect_axis(c: Ctx, o: Obj) -> None:
    base = c.point(o, "basePoint")
    axis = Line(base.p, Pt(base.p.x + 100, base.p.y))
    axis = axis.set_angle(c.check(o, "angle", "0.0"))
    first = c.point(o, "p1Line")
    second = c.point(o, "p2Line")
    found = _line_intersect_axis_point(axis, Line(first.p, second.p))
    if found is None:
        # Seamly2D warns and uses the origin as a placeholder until the pattern is corrected.
        c.rec.issues.append(
            Issue(
                "no_intersection",
                "the line and the axis do not intersect (parallel or degenerate)",
                o.id,
                None,
                "change the axis angle or the line's points",
            )
        )
        found = Pt(0.0, 0.0)
    c.add_point(o, found)
    new = c.ev.points[o.id]
    c.add_line(o.id, base, new)
    c.add_line(o.id, first, new)
    c.add_line(o.id, new, second)


def line(c: Ctx, o: Obj) -> None:
    c.add_line(o.id, c.point(o, "firstPoint"), c.point(o, "secondPoint"))


def point_of_contact(c: Ctx, o: Obj) -> None:
    center = c.point(o, "center")
    first = c.point(o, "firstPoint")
    second = c.point(o, "secondPoint")
    radius = to_pixel(c.check(o, "radius", "0"), c.unit)
    found = find_circle_line_point(radius, center.p, first.p, second.p)
    if found is None:
        c.rec.issues.append(
            Issue(
                "no_intersection",
                "the circle and the line do not meet",
                o.id,
                "radius",
                "make the radius larger or move the line",
            )
        )
        found = Pt(0.0, 0.0)
    c.add_point(o, found)
    new = c.ev.points[o.id]
    c.add_line(o.id, first, new)
    c.add_line(o.id, second, new)
    c.add_line(o.id, center, new)


def true_darts(c: Ctx, o: Obj) -> None:
    base1 = c.point(o, "baseLineP1")
    base2 = c.point(o, "baseLineP2")
    dart1 = c.point(o, "dartP1")
    dart2 = c.point(o, "dartP2")
    dart3 = c.point(o, "dartP3")
    d2d1 = Line(dart2.p, dart1.p)
    d2d3 = Line(dart2.p, dart3.p)
    degrees = d2d3.angle_to(d2d1)
    d2bl = Line(dart2.p, base2.p)
    d2bl = d2bl.set_angle(d2bl.angle() + degrees)
    kind, found = Line(base1.p, d2bl.p2).intersects(d2d1)
    if kind is IntersectType.NO_INTERSECTION or found is None:
        p1 = Pt(0.0, 0.0)
        p2 = Pt(0.0, 0.0)
    else:
        p1 = found
        d2p1 = Line(dart2.p, p1)
        p2 = d2p1.set_angle(d2p1.angle() - degrees).p2
    id1 = int(o.get("point1", "-1") or -1)
    id2 = int(o.get("point2", "-1") or -1)
    c.add_point(o, p1, key=id1, label=o.get("name1", "A"))
    c.add_point(o, p2, key=id2, label=o.get("name2", "A"))


def line_intersect(c: Ctx, o: Obj) -> None:
    """`VToolLineIntersect`: where two lines (each through two points) cross. Seamly2D creates no
    point when they are parallel, so later objects that use it cannot be built either."""
    p1l1 = c.point(o, "p1Line1")
    p2l1 = c.point(o, "p2Line1")
    p1l2 = c.point(o, "p1Line2")
    p2l2 = c.point(o, "p2Line2")
    kind, found = Line(p1l1.p, p2l1.p).intersects(Line(p1l2.p, p2l2.p))
    if kind not in (IntersectType.UNBOUNDED, IntersectType.BOUNDED) or found is None:
        c.rec.issues.append(
            Issue(
                "no_intersection",
                "the two lines do not cross (they are parallel)",
                o.id,
                None,
                "change one of the lines' points",
            )
        )
        return
    c.add_point(o, found)
    new = c.ev.points[o.id]
    c.add_line(o.id, p1l1, new)
    c.add_line(o.id, new, p2l1)
    c.add_line(o.id, p1l2, new)
    c.add_line(o.id, new, p2l2)


def height(c: Ctx, o: Obj) -> None:
    """`VToolHeight`: the foot of the perpendicular from a point onto a line."""
    base = c.point(o, "basePoint")
    first = c.point(o, "p1Line")
    second = c.point(o, "p2Line")
    c.add_point(o, closest_point(Line(first.p, second.p), base.p))
    new = c.ev.points[o.id]
    c.add_line(o.id, base, new)
    c.add_line(o.id, first, new)
    c.add_line(o.id, second, new)


def _shoulder_point(p1_line: Pt, p2_line: Pt, p_shoulder: Pt, length: float) -> Pt:
    """`VToolShoulderPoint::FindPoint`: on the line p1-p2 (extended), the point at distance
    `length` from `p_shoulder`, beyond p2 and in the same direction. p2 if there is none."""
    found = p2_line
    if length <= 0:
        return found
    line = Line(p1_line, p2_line)
    base_length = line.length()
    base_angle = q_round(line.angle())
    line = line.set_length(length * 2)
    count, p1, p2 = line_intersect_circle(p_shoulder, length, line)
    if count in (1, 2):
        line1 = Line(p1_line, p1)
        line2 = Line(p1_line, p2)
        if line1.length() > base_length and base_angle == q_round(line1.angle()):
            found = p1
        elif count == 2 and line2.length() > base_length and base_angle == q_round(line2.angle()):
            found = p2
    return found


def shoulder(c: Ctx, o: Obj) -> None:
    """`VToolShoulderPoint`: a point on the line through p1 and p2, `length` away from a third
    point (the neck point, in a bodice)."""
    first = c.point(o, "p1Line")
    second = c.point(o, "p2Line")
    p_shoulder = c.point(o, "pShoulder")
    length = to_pixel(c.check(o, "length", "100.0"), c.unit)
    c.add_point(o, _shoulder_point(first.p, second.p, p_shoulder.p, length))
    new = c.ev.points[o.id]
    c.add_line(o.id, first, new)
    c.add_line(o.id, second, new)


_TRIANGLE_LIMIT = 1_000_000  # Seamly2D's loop has none; a degenerate triangle would never end


def _triangle_point(axis1: Pt, axis2: Pt, first: Pt, second: Pt) -> Pt | None:
    """`VToolTriangle::FindPoint`: the point on the axis from which the segment first-second is seen
    at a right angle (integer-pixel steps, as Seamly2D does). (0, 0) when the axis and the segment
    are parallel."""
    axis = Line(axis1, axis2)
    hypotenuse = Line(first, second)
    kind, start = axis.intersects(hypotenuse)
    if kind not in (IntersectType.UNBOUNDED, IntersectType.BOUNDED) or start is None:
        return Pt(0.0, 0.0)
    if fuzzy_compare_possible_nulls(axis.angle(), hypotenuse.angle()) or (
        fuzzy_compare_possible_nulls(abs(axis.angle() - hypotenuse.angle()), 180)
    ):
        return Pt(0.0, 0.0)
    step = 1.0
    # QLineF line; line.setP1(start): the other end stays at the origin until the angle is set
    line = Line(start, Pt(0.0, 0.0)).set_angle(axis.angle()).set_length(step)
    target = math.floor(hypotenuse.length())
    for _ in range(_TRIANGLE_LIMIT):
        line = line.set_length(line.length() + step)
        a = math.floor(Line(line.p2, first).length())
        b = math.floor(Line(line.p2, second).length())
        if target * target <= a * a + b * b:
            return line.p2
    return None


def triangle(c: Ctx, o: Obj) -> None:
    """`VToolTriangle`: the point on an axis that sees a segment at a right angle."""
    axis1 = c.point(o, "axisP1")
    axis2 = c.point(o, "axisP2")
    first = c.point(o, "firstPoint")
    second = c.point(o, "secondPoint")
    found = _triangle_point(axis1.p, axis2.p, first.p, second.p)
    if found is None:
        raise ObjectError(
            Issue("no_solution", "no triangle point was found on the axis", o.id, "axisP1")
        )
    c.add_point(o, found)
