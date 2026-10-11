"""Curve tools: arcs, cubic Beziers and splines (src/libs/vtools/tools/drawTools/toolcurve)."""

from __future__ import annotations

import math

from yoko_engine.evalcore import Ctx, CurveGeom, Issue, ObjectError, PointGeom
from yoko_engine.formula import is_single
from yoko_engine.fuzzy import fuzzy_compare_possible_nulls
from yoko_engine.geometry import Line, Pt
from yoko_engine.geometry.curves import (
    Arc,
    Bezier,
    BezierPath,
    Spline,
    SplinePath,
    SplinePoint,
    normalize_angle,
)
from yoko_engine.model import Obj
from yoko_engine.units import from_pixel, to_pixel


def _duplicate_suffix(o: Obj) -> str:
    """`VAbstractCurve::GetDuplicate`: a curve drawn twice between the same points gets `_N`."""
    try:
        n = int(o.get("duplicate", "0") or 0)
    except ValueError:
        n = 0
    return f"_{n}" if n > 0 else ""


def register_spline(
    c: Ctx,
    o: Obj,
    geom: Bezier | Spline,
    name: str,
    labels: tuple[str, ...],
    *,
    curve_id: int | None = None,
) -> None:
    """VContainer::AddSpline: length, angles and the two handle lengths. `curve_id` is the id the
    curve takes when it is not the object itself (the copy an operation makes)."""
    cid = o.id if curve_id is None else curve_id
    c.add_curve(cid, CurveGeom(cid, name, geom, labels))
    c.add_curve_variables(o.id, name, geom.length(), geom.start_angle(), geom.end_angle())
    c.add_control_lengths(o.id, name, geom.c1_length(), geom.c2_length())


def register_path(
    c: Ctx,
    o: Obj,
    path: BezierPath | SplinePath,
    name: str,
    labels: tuple[str, ...],
    *,
    curve_id: int | None = None,
) -> None:
    """VContainer::AddCurveWithSegments: the path, then each segment under `<name>_Seg_<n>`."""
    cid = o.id if curve_id is None else curve_id
    c.add_curve(cid, CurveGeom(cid, name, path, labels))
    c.add_curve_variables(o.id, name, path.length(), path.start_angle(), path.end_angle())
    c.add_control_lengths(o.id, name, path.c1_length(), path.c2_length())
    for i, seg in enumerate(path.segments(), start=1):
        seg_name = f"{name}_Seg_{i}"
        c.add_curve_variables(o.id, seg_name, seg.length(), seg.start_angle(), seg.end_angle())
        c.add_control_lengths(o.id, seg_name, seg.c1_length(), seg.c2_length())


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


def arc_with_length(c: Ctx, o: Obj) -> None:
    """`VToolArcWithLength`: an arc from a start angle and an arc length (`VArc::FindF2`). A
    negative length gives a flipped arc: it runs clockwise from the start angle and its length is
    negative."""
    radius = to_pixel(c.check(o, "radius", "10"), c.unit)
    length = to_pixel(c.check(o, "length", "10"), c.unit)
    f1 = c.check(o, "angle1", "180")
    center = c.point(o, "center")
    flipped = length < 0
    length = min(length, math.tau * radius)  # `length >= MaxLength` only limits the positive side
    arc_angle = abs(math.degrees(length / radius))
    if flipped:
        arc_angle = -arc_angle
    f2 = Line(Pt(0.0, 0.0), Pt(100.0, 0.0)).set_angle(f1 + arc_angle).angle()
    arc_geom = Arc(center.p, radius, f1, f2, flipped)
    name = f"Arc_{center.label}_{o.id}{_duplicate_suffix(o)}"
    c.add_curve(o.id, CurveGeom(o.id, name, arc_geom, (center.label,)))
    c.add_curve_variables(
        o.id, name, arc_geom.length(), arc_geom.start_angle(), arc_geom.end_angle()
    )
    c.set_symbol(f"Radius{name}", from_pixel(radius, c.unit), o.id)


def cubic_bezier(c: Ctx, o: Obj) -> None:
    _reject_length_options(o)
    pts = [c.point(o, f"point{i}") for i in (1, 2, 3, 4)]
    bez = Bezier(pts[0].p, pts[1].p, pts[2].p, pts[3].p)
    name = f"Spl_{pts[0].label}_{pts[3].label}{_duplicate_suffix(o)}"
    register_spline(c, o, bez, name, tuple(p.label for p in pts))


def _path_points(c: Ctx, o: Obj) -> list[PointGeom]:
    points: list[PointGeom] = []
    for child in o.children:
        if child.tag != "pathPoint":
            continue
        raw = child.get("pSpline")
        if raw is None or not raw.isdigit():
            raise ObjectError(Issue("bad_reference", "pathPoint without pSpline", o.id))
        points.append(c.point_by_id(o, int(raw), "pSpline"))
    return points


def cubic_bezier_path(c: Ctx, o: Obj) -> None:
    _reject_length_options(o)
    points = _path_points(c, o)
    path = BezierPath(tuple(p.p for p in points))
    if path.count() < 1:
        raise ObjectError(
            Issue("too_few_points", "a Bezier path needs at least 4 points", o.id, "pathPoint")
        )
    name = f"SplPath_{points[0].label}_{points[-1].label}{_duplicate_suffix(o)}"
    register_path(c, o, path, name, tuple(p.label for p in points))


def _reject_length_options(o: Obj) -> None:
    """0.7.4 added `autoSmooth` (Hobby handles) and `lengthMode` with a target `length`. They change
    the handle lengths through solvers that are not ported yet."""
    try:
        mode = int(o.get("lengthMode", "0") or 0)
    except ValueError:
        mode = 0
    if o.get("autoSmooth") == "true" or (mode > 0 and (o.get("length") or "")):
        raise ObjectError(
            Issue(
                "not_implemented",
                "autoSmooth and lengthMode (format 0.7.4) are not evaluated yet",
                o.id,
                "autoSmooth",
                "set the handle lengths directly",
            )
        )


def spline_interactive(c: Ctx, o: Obj) -> None:
    """`VToolSpline` (type `simpleInteractive`): end points, handle angles and handle lengths."""
    p1 = c.point(o, "point1")
    p4 = c.point(o, "point4")
    angle1 = c.check(o, "angle1", "0")
    angle2 = c.check(o, "angle2", "0")
    length1 = to_pixel(c.check(o, "length1", "0"), c.unit)
    length2 = to_pixel(c.check(o, "length2", "0"), c.unit)
    _reject_length_options(o)
    spl = Spline(p1.p, p4.p, angle1, angle2, length1, length2)
    name = f"Spl_{p1.label}_{p4.label}{_duplicate_suffix(o)}"
    register_spline(c, o, spl, name, (p1.label, p4.label))


def _handle_scale(p1: Pt, p4: Pt, k_curve: float) -> float:
    """`VSplineData::GetL`: the handle length that makes a quarter circle through the two points."""
    radius = Line(p1, p4).length() / math.sqrt(2.0)
    return k_curve * radius * 4 / 3 * math.tan(90 * (math.pi / 4) / 180.0)


def _handle_length(origin: Pt, scale: float, angle: float) -> float:
    return Line(origin, Pt(origin.x + scale, origin.y)).set_angle(angle).length()


def spline_simple(c: Ctx, o: Obj) -> None:
    """`VToolSpline` old format (type `simple`): handle angles and length coefficients kAsm1, kAsm2
    and kCurve, no formulas (`VPattern::ParseOldToolSpline`, `VSplineData`)."""
    p1 = c.point(o, "point1")
    p4 = c.point(o, "point4")
    angle1 = c.number(o, "angle1", "270.0")
    angle2 = c.number(o, "angle2", "90.0")
    k_asm1 = c.number(o, "kAsm1", "1.0")
    k_asm2 = c.number(o, "kAsm2", "1.0")
    k_curve = c.number(o, "kCurve", "1.0")
    scale = _handle_scale(p1.p, p4.p, k_curve)
    spl = Spline(
        p1.p,
        p4.p,
        angle1,
        angle2,
        _handle_length(p1.p, scale * k_asm1, angle1),
        _handle_length(p4.p, scale * k_asm2, angle2),
    )
    name = f"Spl_{p1.label}_{p4.label}{_duplicate_suffix(o)}"
    register_spline(c, o, spl, name, (p1.label, p4.label))


def _spline_point(
    p: PointGeom, a1: float, a1_text: str, a2: float, a2_text: str, l1: float, l2: float
) -> SplinePoint:
    """`VSplinePointData`: when the two handle angles are not opposite, one of them is corrected.
    angle2 is recomputed from angle1, unless angle1 is a plain number and angle2 is not: then
    angle1 is recomputed from angle2. (So a formula wins over a plain number.)"""
    if not fuzzy_compare_possible_nulls(abs(a1 - a2), 180):
        line = Line(Pt(0.0, 0.0), Pt(100.0, 0.0))
        if not is_single(a1_text) or is_single(a2_text):
            a2 = line.set_angle(a1 + 180).angle()
        else:
            a1 = line.set_angle(a2 + 180).angle()
    return SplinePoint(p.p, p.label, a1, a2, l1, l2)


def spline_path_interactive(c: Ctx, o: Obj) -> None:
    """`VToolSplinePath` (type `pathInteractive`): per point, handle angles and lengths as
    formulas."""
    path = SplinePath(())
    labels: list[str] = []
    for child in o.children:
        if child.tag != "pathPoint":
            continue
        a1_text = child.get("angle1", "0") or "0"
        a2_text = child.get("angle2", "0") or "0"
        a1 = c.check(o, "angle1", "0", child)
        a2 = c.check(o, "angle2", "0", child)
        l1 = to_pixel(c.check(o, "length1", "0", child), c.unit)
        l2 = to_pixel(c.check(o, "length2", "0", child), c.unit)
        raw = child.get("pSpline")
        if raw is None or not raw.isdigit():
            raise ObjectError(Issue("bad_reference", "pathPoint without pSpline", o.id))
        p = c.point_by_id(o, int(raw), "pSpline")
        path = path.append(_spline_point(p, a1, a1_text, a2, a2_text, l1, l2))
        labels.append(p.label)
    # An empty path is legal in Seamly2D (it holds an unnamed curve of length 0).
    _register_spline_path(c, o, path, tuple(labels))


def _register_spline_path(c: Ctx, o: Obj, path: SplinePath, labels: tuple[str, ...]) -> None:
    """`VAbstractCubicBezierPath::CreateName` and `VContainer::AddCurveWithSegments`."""
    name = path.name + (_duplicate_suffix(o) if path.count() >= 1 else "")
    register_path(c, o, path, name, labels)


def spline_path_simple(c: Ctx, o: Obj) -> None:
    """`VToolSplinePath` old format (type `path`): per point an angle and length coefficients
    (`VPattern::ParseOldToolSplinePath`, `VSplinePath(QVector<VFSplinePoint>, kCurve)`)."""
    k_curve = c.number(o, "kCurve", "1.0")
    fpoints: list[tuple[PointGeom, float, float, float, float]] = []
    for child in o.children:
        if child.tag != "pathPoint":
            continue
        k_asm1 = float(child.get("kAsm1", "1.0") or 1.0)
        angle = float(child.get("angle", "0") or 0.0)
        k_asm2 = float(child.get("kAsm2", "1.0") or 1.0)
        raw = child.get("pSpline")
        if raw is None or not raw.isdigit():
            raise ObjectError(Issue("bad_reference", "pathPoint without pSpline", o.id))
        p = c.point_by_id(o, int(raw), "pSpline")
        line = Line(Pt(0, 0), Pt(100, 0)).set_angle(angle + 180)
        fpoints.append((p, k_asm1, line.angle(), k_asm2, angle))
    if len(fpoints) < 3:
        raise ObjectError(
            Issue("too_few_points", "a spline path needs 3 points", o.id, "pathPoint")
        )
    points = [SplinePoint(p.p, p.label) for p, *_ in fpoints]
    for i in range(1, len(fpoints)):
        p1, _k11, _a11, k12, a12 = fpoints[i - 1]
        p2, k21, a21, _k22, _a22 = fpoints[i]
        scale = _handle_scale(p1.p, p2.p, k_curve)
        c1 = _handle_length(p1.p, scale * k12, a12)
        c2 = _handle_length(p2.p, scale * k21, a21)
        points[i - 1] = _with_start(points[i - 1], a12, c1)
        points[i] = _with_end(points[i], a21, c2)
    _register_spline_path(c, o, SplinePath(tuple(points)), tuple(p.label for p, *_ in fpoints))


def _with_start(p: SplinePoint, angle2: float, length2: float) -> SplinePoint:
    """SetAngle2 (which also turns angle1 to the opposite side) and SetLength2."""
    from dataclasses import replace

    return replace(p.with_angle2(angle2), length2=length2)


def _with_end(p: SplinePoint, angle1: float, length1: float) -> SplinePoint:
    from dataclasses import replace

    return replace(p.with_angle1(angle1), length1=length1)
