"""Tools that split a curve: intersection with an axis, and (next) the cut tools."""

from __future__ import annotations

from yoko_engine.evalcore import Ctx, CurveGeom, Issue, ObjectError, PointGeom
from yoko_engine.geometry import Pt
from yoko_engine.geometry.axis import curve_axis_point
from yoko_engine.geometry.curves import Arc, Bezier, Spline
from yoko_engine.geometry.cut import cut_spline, cut_spline_path, length_by_point
from yoko_engine.model import Obj
from yoko_engine.units import from_pixel


def _curve_points(curve: CurveGeom) -> list[Pt]:
    return curve.geom.points()


def curve_intersect_axis(c: Ctx, o: Obj) -> None:
    base = c.point(o, "basePoint")
    curve = c.curve(o, "curve")
    angle = c.check(o, "angle", "0.0")
    found = curve_axis_point(base.p, angle, _curve_points(curve))
    if found is None:
        c.rec.issues.append(
            Issue(
                "no_intersection",
                f"the axis from {base.label} at {angle}° does not meet curve {curve.name}",
                o.id,
                "angle",
                "change the axis angle or the curve",
            )
        )
        found = Pt(0.0, 0.0)
    c.add_point(o, found)
    new = c.ev.points[o.id]
    c.add_line(o.id, base, new)
    _register_cut_pieces(c, o, curve, new, length_by_point(_curve_points(curve), found))


def _register_spline_variables(c: Ctx, owner: int, name: str, spl: Spline) -> None:
    """VContainer::AddSpline for a piece cut from a curve (it has no id, only variables)."""
    c.add_curve_variables(owner, name, spl.length(), spl.start_angle(), spl.end_angle())
    c.add_control_lengths(owner, name, spl.c1_length(), spl.c2_length())


def _register_cut_pieces(
    c: Ctx, o: Obj, curve: CurveGeom, cut_point: PointGeom, seg_length: float
) -> None:
    """VToolCurveIntersectAxis::InitSegments: the curve is split at the new point and both pieces
    are registered as curve variables (`Spl_A_X`, `SplPath_X_B`, ...). If the point is not on the
    curve (`seg_length` is -1) the pieces are registered empty, with the same names."""
    on_curve = seg_length != -1.0
    length = seg_length if on_curve else 0.0
    geom = curve.geom
    if isinstance(geom, Bezier):
        cut = cut_spline(geom, length)
        zero = Pt(0.0, 0.0)
        if cut is None:
            p2a = p3a = p2b = p3b = zero
        else:
            p2a, p3a, p2b, p3b = cut.spl1_p2, cut.spl1_p3, cut.spl2_p2, cut.spl2_p3
        first = Spline.from_points(geom.p1, p2a, p3a, cut_point.p)
        second = Spline.from_points(cut_point.p, p2b, p3b, geom.p4)
        names = (
            f"Spl_{curve.labels[0]}_{cut_point.label}",
            f"Spl_{cut_point.label}_{curve.labels[3]}",
        )
        for name, spl in zip(names, (first, second), strict=True):
            if on_curve:
                _register_spline_variables(c, o.id, name, spl)
            else:
                _register_empty(c, o.id, name)
    elif isinstance(geom, Arc):
        # InitArc: the pieces get ids p+1 and p+2 (their names contain the id).
        cut_arc = geom.cut(length)
        pieces = (Arc(geom.center, geom.radius, 0.0, 0.0),) * 2 if cut_arc is None else cut_arc[1:]
        for offset, arc in enumerate(pieces, start=1):
            name = f"Arc_{curve.labels[0]}_{cut_point.id + offset}"
            if on_curve:
                c.add_curve_variables(o.id, name, arc.length(), arc.start_angle(), arc.end_angle())
                c.set_symbol(f"Radius{name}", from_pixel(arc.radius, c.unit), o.id)
            else:
                _register_empty(c, o.id, name)
                c.set_symbol(f"Radius{name}", 0.0, o.id)
    else:
        pcut = cut_spline_path(geom, curve.labels, length, cut_point.label)
        if pcut is None:
            raise ObjectError(
                Issue("cut_failed", "could not split the curve at the intersection", o.id)
            )
        for spath in (pcut.first, pcut.second):
            if on_curve:
                c.add_curve_variables(
                    o.id, spath.name, spath.length(), spath.start_angle(), spath.end_angle()
                )
                c.add_control_lengths(o.id, spath.name, spath.c1_length(), spath.c2_length())
            else:
                _register_empty(c, o.id, spath.name)


def _register_empty(c: Ctx, owner: int, name: str) -> None:
    c.add_curve_variables(owner, name, 0.0, 0.0, 0.0)
    c.add_control_lengths(owner, name, 0.0, 0.0)
