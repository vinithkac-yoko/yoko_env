"""Points found where circles, arcs, curves and tangents meet (the `pointOf...` tools).

When Seamly2D cannot find the point it shows a warning and uses the origin as a placeholder until
the pattern is corrected; here that is an issue and the same placeholder.
"""

from __future__ import annotations

from yoko_engine.evalcore import Ctx, Issue, ObjectError
from yoko_engine.geometry import Line, Pt, points_equal
from yoko_engine.geometry.circle_line import contact_points, intersection_circles
from yoko_engine.geometry.curves import Arc
from yoko_engine.model import Obj
from yoko_engine.units import to_pixel

ORIGIN = Pt(0.0, 0.0)


def _placeholder(c: Ctx, o: Obj, found: Pt | None, what: str, hint: str) -> Pt:
    """Seamly2D treats "no result" and "the origin" alike (`point == QPointF()`)."""
    if found is None or points_equal(found, ORIGIN):
        c.rec.issues.append(
            Issue("no_intersection", f"cannot find the point: {what}", o.id, None, hint)
        )
        return ORIGIN
    return found


def _cross(o: Obj, default: str = "1") -> bool:
    """`crossPoint`: 1 is the first of the two points, 2 the second."""
    return (o.get("crossPoint", default) or default) != "2"


def _pick(count: int, p1: Pt, p2: Pt, first: bool) -> Pt | None:
    if count == 2:
        return p1 if first else p2
    if count == 1:
        return p1
    return None


def circles(c: Ctx, o: Obj) -> None:
    """`IntersectCirclesTool`: two circles, each from a centre point and a radius formula."""
    r1 = to_pixel(c.check(o, "c1Radius", "0"), c.unit)
    r2 = to_pixel(c.check(o, "c2Radius", "0"), c.unit)
    c1 = c.point(o, "c1Center")
    c2 = c.point(o, "c2Center")
    count, p1, p2 = intersection_circles(c1.p, r1, c2.p, r2)
    found = _pick(count, p1, p2, _cross(o))
    point = _placeholder(c, o, found, "the circles do not meet", "change a radius or a centre")
    c.add_point(o, point)


def circle_tangent(c: Ctx, o: Obj) -> None:
    """`IntersectCircleTangentTool`: where a tangent from a point touches a circle."""
    radius = to_pixel(c.check(o, "cRadius", "0"), c.unit)
    center = c.point(o, "cCenter")
    tangent = c.point(o, "tangent")
    count, p1, p2 = contact_points(tangent.p, center.p, radius)
    found = _pick(count, p1, p2, _cross(o))
    point = _placeholder(
        c,
        o,
        found,
        "no tangent from the point touches the circle",
        "change the radius or the point",
    )
    c.add_point(o, point)


def _arc(c: Ctx, o: Obj, attr: str) -> tuple[Arc, str]:
    curve = c.curve(o, attr)
    if not isinstance(curve.geom, Arc):
        raise ObjectError(Issue("bad_curve", f"'{attr}' is not an arc", o.id, attr))
    return curve.geom, curve.name


def _on_arc(arc: Arc, center: Pt, p: Pt) -> bool:
    """The ray from the centre through `p`, 10 px longer than the radius, crosses the arc."""
    ray = Line(center, p)
    ray = ray.set_length(ray.length() + 10)
    return _crosses(arc.points(), ray)


def _crosses(points: list[Pt], line: Line) -> bool:
    return bool(_curve_intersect_line(points, line))


def _curve_intersect_line(points: list[Pt], line: Line) -> list[Pt]:
    """`VAbstractCurve::CurveIntersectLine`: where `line` crosses the polyline (segments only)."""
    from yoko_engine.geometry.qt import IntersectType

    found: list[Pt] = []
    for i in range(len(points) - 1):
        kind, cross = line.intersects(Line(points[i], points[i + 1]))
        if kind is IntersectType.BOUNDED and cross is not None:
            found.append(cross)
    return found


def arcs(c: Ctx, o: Obj) -> None:
    """`VToolPointOfIntersectionArcs`: a point common to two arcs (their full circles meet there
    and both arcs reach it)."""
    arc1, _ = _arc(c, o, "firstArc")
    arc2, _ = _arc(c, o, "secondArc")
    count, p1, p2 = intersection_circles(arc1.center, arc1.radius, arc2.center, arc2.radius)
    found: Pt | None = None
    if count == 2:
        ok1 = _on_arc(arc1, arc1.center, p1) and _on_arc(arc2, arc2.center, p1)
        ok2 = _on_arc(arc1, arc1.center, p2) and _on_arc(arc2, arc2.center, p2)
        if ok1 and ok2:
            found = p1 if _cross(o) else p2
        elif ok1:
            found = p1
        elif ok2:
            found = p2
    elif count == 1 and _on_arc(arc1, arc1.center, p1) and _on_arc(arc2, arc2.center, p1):
        found = p1
    point = _placeholder(c, o, found, "the arcs do not meet", "change an arc or its radius")
    c.add_point(o, point)


def arc_tangent(c: Ctx, o: Obj) -> None:
    """`VToolPointFromArcAndTangent`: where a tangent from a point touches an arc."""
    arc, _ = _arc(c, o, "arc")
    tangent = c.point(o, "tangent")
    count, p1, p2 = contact_points(tangent.p, arc.center, arc.radius)

    def on_arc(p: Pt) -> bool:
        ray = Line(arc.center, p).set_length(arc.radius + 10)
        return _crosses(arc.points(), ray)

    found: Pt | None = None
    if count == 2:
        ok1, ok2 = on_arc(p1), on_arc(p2)
        if ok1 and ok2:
            found = p1 if _cross(o) else p2
        elif ok1:
            found = p1
        elif ok2:
            found = p2
    elif count == 1 and on_arc(p1):
        found = p1
    point = _placeholder(
        c, o, found, "no tangent from the point touches the arc", "change the arc or the point"
    )
    c.add_point(o, point)


def curves(c: Ctx, o: Obj) -> None:
    """`VToolPointOfIntersectionCurves`: where two curves cross. With several crossings the highest
    (or lowest) wins, then the leftmost (or rightmost)."""
    first = c.curve(o, "curve1").geom.points()
    second = c.curve(o, "curve2").geom.points()
    highest = (o.get("vCrossPoint", "1") or "1") != "2"
    leftmost = (o.get("hCrossPoint", "1") or "1") != "2"
    found = _curves_point(first, second, highest, leftmost)
    point = _placeholder(c, o, found, "the curves do not cross", "move one of the curves")
    c.add_point(o, point)


def _curves_point(first: list[Pt], second: list[Pt], highest: bool, leftmost: bool) -> Pt | None:
    if not first or not second:
        return None
    crossings: list[Pt] = []
    for i in range(len(first) - 1):
        crossings.extend(_curve_intersect_line(second, Line(first[i], first[i + 1])))
    if not crossings:
        return None
    if len(crossings) == 1:
        return crossings[0]
    # y grows downward on screen: "highest" is the smallest y
    best = crossings[0].y
    chosen = [crossings[0]]
    for p in crossings[1:]:
        if highest:
            if p.y > best:
                continue
            if p.y < best:
                best, chosen = p.y, [p]
            else:
                chosen.append(p)
        else:
            if p.y > best:
                best, chosen = p.y, [p]
            elif p.y < best:
                continue
            else:
                chosen.append(p)
    if len(chosen) == 1:
        return chosen[0]
    result = chosen[0]
    x_best = chosen[0].x
    for p in chosen[1:]:
        if (leftmost and p.x < x_best) or (not leftmost and p.x > x_best):
            x_best, result = p.x, p
    return result
