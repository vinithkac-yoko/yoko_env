"""Evaluate a pattern: run the construction graph in order and compute geometry.

This mirrors how Seamly2D loads a file (src/app/seamly2d/xml/vpattern.cpp): measurements first, then
variables in file order, then every draft block's objects in file order. Each object is built from
earlier objects plus formulas; a formula sees measurements, variables, and the geometric variables
(`Line_A_B`, `AngleLine_A_B`, ...) that earlier objects registered.

Geometry is computed in Seamly2D's native 96-dpi pixel scale with its exact arithmetic (see
`yoko_engine.units`); `Evaluation` converts to mm for callers.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from yoko_engine.formula import FormulaError, parse
from yoko_engine.fuzzy import fuzzy_compare_possible_nulls
from yoko_engine.geometry import Line, Pt, points_equal
from yoko_engine.geometry.axis import curve_axis_point
from yoko_engine.geometry.circle_line import find_circle_line_point
from yoko_engine.geometry.curves import Arc, Bezier, BezierPath, Spline, normalize_angle
from yoko_engine.geometry.cut import cut_spline, cut_spline_path, length_by_point
from yoko_engine.geometry.qt import IntersectType
from yoko_engine.geometry.transform import flip_point
from yoko_engine.model import Obj, Pattern
from yoko_engine.units import from_pixel, px_to_mm, to_pixel

CURRENT_LENGTH = "CurrentLength"


@dataclass(frozen=True, slots=True)
class Issue:
    """A problem found while evaluating. `code` is stable; `hint` says what to try."""

    code: str
    message: str
    object_id: int | None = None
    field: str | None = None
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class PointGeom:
    id: int
    label: str
    p: Pt  # pixels

    @property
    def x_mm(self) -> float:
        return px_to_mm(self.p.x)

    @property
    def y_mm(self) -> float:
        return px_to_mm(self.p.y)


@dataclass(frozen=True, slots=True)
class CurveGeom:
    id: int
    name: str
    geom: Arc | Bezier | BezierPath
    # labels of the points that define the curve, in order (needed to name pieces cut from it)
    labels: tuple[str, ...] = ()


class Evaluation:
    """The result of evaluating a pattern."""

    def __init__(self) -> None:
        self.points: dict[int, PointGeom] = {}
        self.curves: dict[int, CurveGeom] = {}
        self.symbols: dict[str, float] = {}
        # symbol name -> id of the object that registered it (for dependency tracking)
        self.owners: dict[str, int] = {}
        # object id -> ids of the objects it was built from
        self.deps: dict[int, frozenset[int]] = {}
        self.issues: list[Issue] = []

    def point_mm(self, label: str) -> tuple[float, float]:
        for g in self.points.values():
            if g.label == label:
                return g.x_mm, g.y_mm
        raise KeyError(label)


class _ObjectError(Exception):
    """Aborts one object; recorded as an Issue and evaluation carries on."""

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message)
        self.issue = issue


class _Ctx:
    def __init__(self, unit: str, ev: Evaluation) -> None:
        self.unit = unit
        self.ev = ev
        self.deps: set[int] = set()

    # -- inputs -----------------------------------------------------------------------------
    def point(self, o: Obj, attr: str) -> PointGeom:
        raw = o.get(attr)
        if raw is None:
            raise _ObjectError(Issue("missing_attribute", f"{o.kind} has no '{attr}'", o.id, attr))
        try:
            pid = int(raw)
        except ValueError:
            raise _ObjectError(
                Issue("bad_reference", f"'{attr}' is not an object id: {raw!r}", o.id, attr)
            ) from None
        geom = self.ev.points.get(pid)
        if geom is None:
            raise _ObjectError(
                Issue(
                    "missing_reference",
                    f"'{attr}' refers to object {pid}, which does not exist (yet) as a point",
                    o.id,
                    attr,
                    hint="objects can only use points defined earlier in the pattern",
                )
            )
        self.deps.add(pid)
        return geom

    def point_by_id(self, o: Obj, pid: int, attr: str) -> PointGeom:
        geom = self.ev.points.get(pid)
        if geom is None:
            raise _ObjectError(
                Issue(
                    "missing_reference",
                    f"'{attr}' refers to object {pid}, which does not exist (yet) as a point",
                    o.id,
                    attr,
                    hint="objects can only use points defined earlier in the pattern",
                )
            )
        self.deps.add(pid)
        return geom

    def curve(self, o: Obj, attr: str) -> CurveGeom:
        raw = o.get(attr)
        try:
            cid = int(raw) if raw is not None else -1
        except ValueError:
            cid = -1
        geom = self.ev.curves.get(cid)
        if geom is None:
            raise _ObjectError(
                Issue(
                    "missing_reference",
                    f"'{attr}' does not refer to an earlier curve ({raw!r})",
                    o.id,
                    attr,
                    hint="objects can only use curves defined earlier in the pattern",
                )
            )
        self.deps.add(cid)
        return geom

    def number(self, o: Obj, attr: str, default: str | None = None) -> float:
        raw = o.get(attr, default)
        if raw is None:
            raise _ObjectError(Issue("missing_attribute", f"{o.kind} has no '{attr}'", o.id, attr))
        try:
            return float(raw)
        except ValueError:
            raise _ObjectError(
                Issue("bad_number", f"'{attr}' is not a number: {raw!r}", o.id, attr)
            ) from None

    def check(self, o: Obj, attr: str, default: str) -> float:
        """Evaluate a formula attribute in the pattern unit.

        Like Seamly2D's `VAbstractTool::CheckFormula`, an infinite or NaN result becomes 0.
        """
        text = o.get(attr, default) or default
        try:
            f = parse(text)
            value = f.evaluate(self.ev.symbols)
        except FormulaError as err:
            raise _ObjectError(
                Issue(
                    f"formula_{err.code.value}",
                    err.message,
                    o.id,
                    attr,
                    err.hint,
                )
            ) from err
        for name in f.names:
            owner = self.ev.owners.get(name)
            if owner is not None:
                self.deps.add(owner)
        if math.isinf(value) or math.isnan(value):
            self.ev.issues.append(
                Issue(
                    "invalid_formula_value",
                    f"formula {text!r} is not a finite number; Seamly2D uses 0",
                    o.id,
                    attr,
                    "check for division by zero or an impossible root",
                )
            )
            return 0.0
        return value

    # -- outputs ----------------------------------------------------------------------------
    def add_point(self, o: Obj, p: Pt, *, key: int | None = None, label: str | None = None) -> None:
        pid = o.id if key is None else key
        self.ev.points[pid] = PointGeom(pid, o.label if label is None else label, p)

    def set_symbol(self, name: str, value: float, owner: int) -> None:
        self.ev.symbols[name] = value
        self.ev.owners[name] = owner

    def add_curve_variables(
        self,
        owner: int,
        name: str,
        length_px: float,
        start_angle: float,
        end_angle: float,
    ) -> None:
        """VContainer::AddCurve: the curve's length and its start and end angles."""
        self.set_symbol(name, from_pixel(length_px, self.unit), owner)
        self.set_symbol(f"Angle1{name}", start_angle, owner)
        self.set_symbol(f"Angle2{name}", end_angle, owner)

    def add_control_lengths(self, owner: int, name: str, c1_px: float, c2_px: float) -> None:
        self.set_symbol(f"C1Length{name}", from_pixel(c1_px, self.unit), owner)
        self.set_symbol(f"C2Length{name}", from_pixel(c2_px, self.unit), owner)

    def add_line(self, owner: int, first: PointGeom, second: PointGeom) -> None:
        """VContainer::AddLine: registers `Line_A_B` and `AngleLine_A_B`."""
        line = Line(first.p, second.p)
        suffix = f"{first.label}_{second.label}"
        self.set_symbol(f"Line_{suffix}", from_pixel(line.length(), self.unit), owner)
        # Angles are truncated, not rounded, to 5 decimals (VLineAngle::SetValue).
        angle = math.floor(line.angle() * 100000.0) / 100000.0
        self.set_symbol(f"AngleLine_{suffix}", angle, owner)


Handler = Callable[[_Ctx, Obj], None]


# -- point kinds (src/libs/vtools/tools/drawTools/toolpoint) -------------------------------------
def _single(c: _Ctx, o: Obj) -> None:
    # VPattern::ParseToolBasePoint: x and y default to 10.0 and are in the pattern unit.
    x = to_pixel(c.number(o, "x", "10.0"), c.unit)
    y = to_pixel(c.number(o, "y", "10.0"), c.unit)
    c.add_point(o, Pt(x, y))


def _end_line(c: _Ctx, o: Obj) -> None:
    base = c.point(o, "basePoint")
    line = Line(base.p, Pt(base.p.x + 100, base.p.y))
    line = line.set_angle(c.check(o, "angle", "0.0"))  # the angle is set first
    line = line.set_length(to_pixel(c.check(o, "length", "100.0"), c.unit))
    c.add_point(o, line.p2)
    c.add_line(o.id, base, c.ev.points[o.id])


def _along_line(c: _Ctx, o: Obj) -> None:
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
    c.add_point(o, line.set_length(length).p2)
    new = c.ev.points[o.id]
    c.add_line(o.id, first, new)
    c.add_line(o.id, new, second)


def _normal(c: _Ctx, o: Obj) -> None:
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


def _bisector(c: _Ctx, o: Obj) -> None:
    first = c.point(o, "firstPoint")
    second = c.point(o, "secondPoint")
    third = c.point(o, "thirdPoint")
    length = to_pixel(c.check(o, "length", "100.0"), c.unit)
    line = Line(second.p, first.p)
    line = line.set_angle(_bisector_angle(first.p, second.p, third.p))
    c.add_point(o, line.set_length(length).p2)
    c.add_line(o.id, second, c.ev.points[o.id])


def _intersect_xy(c: _Ctx, o: Obj) -> None:
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


def _line_intersect_axis(c: _Ctx, o: Obj) -> None:
    base = c.point(o, "basePoint")
    axis = Line(base.p, Pt(base.p.x + 100, base.p.y))
    axis = axis.set_angle(c.check(o, "angle", "0.0"))
    first = c.point(o, "p1Line")
    second = c.point(o, "p2Line")
    found = _line_intersect_axis_point(axis, Line(first.p, second.p))
    if found is None:
        # Seamly2D warns and uses the origin as a placeholder until the pattern is corrected.
        c.ev.issues.append(
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


def _line(c: _Ctx, o: Obj) -> None:
    c.add_line(o.id, c.point(o, "firstPoint"), c.point(o, "secondPoint"))


def _point_of_contact(c: _Ctx, o: Obj) -> None:
    center = c.point(o, "center")
    first = c.point(o, "firstPoint")
    second = c.point(o, "secondPoint")
    radius = to_pixel(c.check(o, "radius", "0"), c.unit)
    found = find_circle_line_point(radius, center.p, first.p, second.p)
    if found is None:
        c.ev.issues.append(
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


def _true_darts(c: _Ctx, o: Obj) -> None:
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


def _arc(c: _Ctx, o: Obj) -> None:
    center = c.point(o, "center")
    radius = to_pixel(c.check(o, "radius", "10"), c.unit)
    f1 = normalize_angle(c.check(o, "angle1", "180"), 0.0, 360.0)
    f2 = normalize_angle(c.check(o, "angle2", "270"), 0.0, 360.0)
    arc = Arc(center.p, radius, f1, f2)
    name = f"Arc_{center.label}_{o.id}"
    c.ev.curves[o.id] = CurveGeom(o.id, name, arc, (center.label,))
    c.add_curve_variables(o.id, name, arc.length(), arc.start_angle(), arc.end_angle())
    c.set_symbol(f"Radius{name}", from_pixel(radius, c.unit), o.id)


def _cubic_bezier(c: _Ctx, o: Obj) -> None:
    pts = [c.point(o, f"point{i}") for i in (1, 2, 3, 4)]
    bez = Bezier(pts[0].p, pts[1].p, pts[2].p, pts[3].p)
    name = f"Spl_{pts[0].label}_{pts[3].label}"
    c.ev.curves[o.id] = CurveGeom(o.id, name, bez, tuple(p.label for p in pts))
    c.add_curve_variables(o.id, name, bez.length(), bez.start_angle(), bez.end_angle())
    c.add_control_lengths(o.id, name, bez.c1_length(), bez.c2_length())


def _cubic_bezier_path(c: _Ctx, o: Obj) -> None:
    points: list[PointGeom] = []
    for child in o.children:
        if child.tag != "pathPoint":
            continue
        raw = child.get("pSpline")
        if raw is None or not raw.isdigit():
            raise _ObjectError(Issue("bad_reference", "pathPoint without pSpline", o.id))
        points.append(c.point_by_id(o, int(raw), "pSpline"))
    path = BezierPath(tuple(p.p for p in points))
    if path.count() < 1:
        raise _ObjectError(
            Issue("too_few_points", "a Bezier path needs at least 4 points", o.id, "pathPoint")
        )
    name = f"SplPath_{points[0].label}_{points[-1].label}"
    c.ev.curves[o.id] = CurveGeom(o.id, name, path, tuple(p.label for p in points))
    c.add_curve_variables(o.id, name, path.length(), path.start_angle(), path.end_angle())
    c.add_control_lengths(o.id, name, path.c1_length(), path.c2_length())
    for i, seg in enumerate(path.segments(), start=1):
        seg_name = f"{name}_Seg_{i}"
        c.add_curve_variables(o.id, seg_name, seg.length(), seg.start_angle(), seg.end_angle())
        c.add_control_lengths(o.id, seg_name, seg.c1_length(), seg.c2_length())


def _flip_by_line(c: _Ctx, o: Obj) -> None:
    """VToolMirrorByLine: mirror the listed objects across the line through two points. The mirrored
    copies take the destination ids from the file and the label of the original plus `suffix`."""
    first = c.point(o, "p1Line")
    second = c.point(o, "p2Line")
    suffix = o.get("suffix", "") or ""
    axis = Line(first.p, second.p)
    sources = [n for n in o.children if n.tag == "source"]
    dests = [n for n in o.children if n.tag == "destination"]
    src_items = sources[0].children if sources else ()
    dst_items = dests[0].children if dests else ()
    if len(src_items) != len(dst_items):
        raise _ObjectError(
            Issue("bad_operation", "source and destination lists differ in length", o.id)
        )
    for src, dst in zip(src_items, dst_items, strict=True):
        sid = int(src.get("idObject", "-1") or -1)
        did = int(dst.get("idObject", "-1") or -1)
        original = c.point_by_id(o, sid, "source")
        flipped = flip_point(axis, original.p)
        c.add_point(o, flipped, key=did, label=original.label + suffix)


def _curve_points(curve: CurveGeom) -> list[Pt]:
    return curve.geom.points()


def _curve_intersect_axis(c: _Ctx, o: Obj) -> None:
    base = c.point(o, "basePoint")
    curve = c.curve(o, "curve")
    angle = c.check(o, "angle", "0.0")
    found = curve_axis_point(base.p, angle, _curve_points(curve))
    if found is None:
        c.ev.issues.append(
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


def _register_spline_variables(c: _Ctx, owner: int, name: str, spl: Spline) -> None:
    """VContainer::AddSpline for a piece cut from a curve (it has no id, only variables)."""
    c.add_curve_variables(owner, name, spl.length(), spl.start_angle(), spl.end_angle())
    c.add_control_lengths(owner, name, spl.c1_length(), spl.c2_length())


def _register_cut_pieces(
    c: _Ctx, o: Obj, curve: CurveGeom, cut_point: PointGeom, seg_length: float
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
            raise _ObjectError(
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


def _register_empty(c: _Ctx, owner: int, name: str) -> None:
    c.add_curve_variables(owner, name, 0.0, 0.0, 0.0)
    c.add_control_lengths(owner, name, 0.0, 0.0)


HANDLERS: dict[str, Handler] = {
    "single": _single,
    "endLine": _end_line,
    "alongLine": _along_line,
    "normal": _normal,
    "bisector": _bisector,
    "intersectXY": _intersect_xy,
    "lineIntersectAxis": _line_intersect_axis,
    "line:line": _line,
    "pointOfContact": _point_of_contact,
    "trueDarts": _true_darts,
    "curveIntersectAxis": _curve_intersect_axis,
    "arc:simple": _arc,
    "spline:cubicBezier": _cubic_bezier,
    "spline:cubicBezierPath": _cubic_bezier_path,
    "operation:flippingByLine": _flip_by_line,
}

# Kinds that are part of the language but not computed yet; the evaluator reports them.
PENDING_KINDS: frozenset[str] = frozenset()


def kind_key(o: Obj) -> str:
    """Points are keyed by their type; other objects by element and type (so arcs and elliptical
    arcs, both `simple`, stay apart)."""
    return o.kind if o.tag == "point" else f"{o.tag}:{o.kind}"


def evaluate(pattern: Pattern, measurements: Mapping[str, float]) -> Evaluation:
    """Run the whole pattern. Never raises for a bad pattern: problems come back as issues."""
    ev = Evaluation()
    ev.symbols.update(measurements)
    ctx = _Ctx(pattern.unit, ev)

    for var in pattern.variables:
        try:
            ev.symbols[var.name] = parse(var.formula).evaluate(ev.symbols)
        except FormulaError as err:
            ev.symbols[var.name] = 0.0
            ev.issues.append(
                Issue(
                    f"formula_{err.code.value}",
                    f"variable {var.name}: {err.message}",
                    None,
                    var.name,
                    err.hint,
                )
            )

    for block in pattern.blocks:
        for o in block.objects:
            key = kind_key(o)
            handler = HANDLERS.get(key)
            if handler is None:
                code = "pending_kind" if key in PENDING_KINDS else "unknown_kind"
                ev.issues.append(
                    Issue(code, f"object kind {o.kind!r} is not evaluated yet", o.id, None)
                )
                continue
            ctx.deps = set()
            try:
                handler(ctx, o)
            except _ObjectError as err:
                ev.issues.append(err.issue)
            ev.deps[o.id] = frozenset(ctx.deps)
    return ev


__all__ = ["Evaluation", "Issue", "PointGeom", "evaluate", "points_equal"]
