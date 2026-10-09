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
from yoko_engine.geometry.qt import IntersectType
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


class Evaluation:
    """The result of evaluating a pattern."""

    def __init__(self) -> None:
        self.points: dict[int, PointGeom] = {}
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


HANDLERS: dict[str, Handler] = {
    "single": _single,
    "endLine": _end_line,
    "alongLine": _along_line,
    "normal": _normal,
    "bisector": _bisector,
    "intersectXY": _intersect_xy,
    "lineIntersectAxis": _line_intersect_axis,
    "line": _line,
}

# Kinds that are part of the language but not computed yet; the evaluator reports them.
PENDING_KINDS = frozenset(
    {
        "pointOfContact",
        "trueDarts",
        "curveIntersectAxis",
        "simple",
        "cubicBezier",
        "cubicBezierPath",
        "flippingByLine",
    }
)


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
            handler = HANDLERS.get(o.kind)
            if handler is None:
                code = "pending_kind" if o.kind in PENDING_KINDS else "unknown_kind"
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
