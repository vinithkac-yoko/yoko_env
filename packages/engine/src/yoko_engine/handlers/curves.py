"""Curve tools: arcs and cubic Beziers (src/libs/vtools/tools/drawTools/toolcurve)."""

from __future__ import annotations

from yoko_engine.evalcore import Ctx, CurveGeom, Issue, ObjectError, PointGeom
from yoko_engine.geometry.curves import Arc, Bezier, BezierPath, normalize_angle
from yoko_engine.model import Obj
from yoko_engine.units import from_pixel, to_pixel


def arc(c: Ctx, o: Obj) -> None:
    center = c.point(o, "center")
    radius = to_pixel(c.check(o, "radius", "10"), c.unit)
    f1 = normalize_angle(c.check(o, "angle1", "180"), 0.0, 360.0)
    f2 = normalize_angle(c.check(o, "angle2", "270"), 0.0, 360.0)
    arc = Arc(center.p, radius, f1, f2)
    name = f"Arc_{center.label}_{o.id}"
    c.add_curve(o.id, CurveGeom(o.id, name, arc, (center.label,)))
    c.add_curve_variables(o.id, name, arc.length(), arc.start_angle(), arc.end_angle())
    c.set_symbol(f"Radius{name}", from_pixel(radius, c.unit), o.id)


def cubic_bezier(c: Ctx, o: Obj) -> None:
    pts = [c.point(o, f"point{i}") for i in (1, 2, 3, 4)]
    bez = Bezier(pts[0].p, pts[1].p, pts[2].p, pts[3].p)
    name = f"Spl_{pts[0].label}_{pts[3].label}"
    c.add_curve(o.id, CurveGeom(o.id, name, bez, tuple(p.label for p in pts)))
    c.add_curve_variables(o.id, name, bez.length(), bez.start_angle(), bez.end_angle())
    c.add_control_lengths(o.id, name, bez.c1_length(), bez.c2_length())


def cubic_bezier_path(c: Ctx, o: Obj) -> None:
    points: list[PointGeom] = []
    for child in o.children:
        if child.tag != "pathPoint":
            continue
        raw = child.get("pSpline")
        if raw is None or not raw.isdigit():
            raise ObjectError(Issue("bad_reference", "pathPoint without pSpline", o.id))
        points.append(c.point_by_id(o, int(raw), "pSpline"))
    path = BezierPath(tuple(p.p for p in points))
    if path.count() < 1:
        raise ObjectError(
            Issue("too_few_points", "a Bezier path needs at least 4 points", o.id, "pathPoint")
        )
    name = f"SplPath_{points[0].label}_{points[-1].label}"
    c.add_curve(o.id, CurveGeom(o.id, name, path, tuple(p.label for p in points)))
    c.add_curve_variables(o.id, name, path.length(), path.start_angle(), path.end_angle())
    c.add_control_lengths(o.id, name, path.c1_length(), path.c2_length())
    for i, seg in enumerate(path.segments(), start=1):
        seg_name = f"{name}_Seg_{i}"
        c.add_curve_variables(o.id, seg_name, seg.length(), seg.start_angle(), seg.end_angle())
        c.add_control_lengths(o.id, seg_name, seg.c1_length(), seg.c2_length())
