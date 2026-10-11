"""What every object handler works with: results (`Evaluation`), problems (`Issue`) and the context
(`Ctx`) that gives a handler its inputs (points, curves, formulas) and takes its outputs.

Split from `evaluator.py` so that the handlers (`yoko_engine.handlers`) and the evaluation loop do
not import each other.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from yoko_engine.formula import FormulaError, FormulaErrorCode, parse
from yoko_engine.geometry import Line, Pt
from yoko_engine.geometry.curves import Arc, Bezier, BezierPath, Spline, SplinePath
from yoko_engine.model import Obj, RawNode
from yoko_engine.units import from_pixel, px_to_mm

CURRENT_LENGTH = "CurrentLength"


@dataclass(frozen=True, slots=True)
class Issue:
    """A problem found while evaluating. `code` is stable; `hint` says what to try."""

    code: str
    message: str
    object_id: int | None = None
    field: str | None = None
    hint: str | None = None
    severity: str = "error"  # "error" rejects an action that introduces it; "warning" does not


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
    geom: Arc | Bezier | Spline | BezierPath | SplinePath
    # labels of the points that define the curve, in order (needed to name pieces cut from it)
    labels: tuple[str, ...] = ()
    # False for the arcs a cut tool leaves behind: real objects, but Seamly2D does not draw them
    drawn: bool = True


class ObjRecord:
    """What one object produced and used when it was evaluated. Never mutated after evaluation
    (a re-run makes a new record), so copies of an Evaluator can share records."""

    __slots__ = ("curves", "issues", "points", "symbols", "uses_ids", "uses_names")

    def __init__(self) -> None:
        self.points: set[int] = set()
        self.curves: set[int] = set()
        self.symbols: set[str] = set()
        self.uses_ids: set[int] = set()
        self.uses_names: set[str] = set()
        self.issues: list[Issue] = []


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

    def copy(self) -> Evaluation:
        """A copy that can be changed without affecting this one (values are immutable)."""
        other = Evaluation()
        other.points = dict(self.points)
        other.curves = dict(self.curves)
        other.symbols = dict(self.symbols)
        other.owners = dict(self.owners)
        other.deps = dict(self.deps)
        other.issues = list(self.issues)
        return other

    def point_mm(self, label: str) -> tuple[float, float]:
        for g in self.points.values():
            if g.label == label:
                return g.x_mm, g.y_mm
        raise KeyError(label)


class ObjectError(Exception):
    """Aborts one object; recorded as an Issue and evaluation carries on."""

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message)
        self.issue = issue


class Ctx:
    def __init__(self, unit: str, ev: Evaluation) -> None:
        self.unit = unit
        self.ev = ev
        self.rec = ObjRecord()
        self.deps: set[int] = self.rec.uses_ids
        # file position of every object, and of the one being evaluated: an object may only use
        # what comes before it, even if a later object's old results are still in `ev`.
        self.order: dict[int, int] = {}
        self.current = -1

    def is_forward(self, ref_id: int, *, own_is_forward: bool = True) -> bool:
        pos = self.order.get(ref_id, -1)
        if self.current < 0:
            return False
        return pos >= self.current if own_is_forward else pos > self.current

    def begin(self) -> ObjRecord:
        self.rec = ObjRecord()
        self.deps = self.rec.uses_ids
        return self.rec

    # -- inputs -----------------------------------------------------------------------------
    def point(self, o: Obj, attr: str) -> PointGeom:
        raw = o.get(attr)
        if raw is None:
            raise ObjectError(Issue("missing_attribute", f"{o.kind} has no '{attr}'", o.id, attr))
        try:
            pid = int(raw)
        except ValueError:
            raise ObjectError(
                Issue("bad_reference", f"'{attr}' is not an object id: {raw!r}", o.id, attr)
            ) from None
        geom = self.ev.points.get(pid)
        if geom is None or self.is_forward(pid):
            raise ObjectError(
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
        if geom is None or self.is_forward(pid):
            raise ObjectError(
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
        if geom is None or self.is_forward(cid):
            raise ObjectError(
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
            raise ObjectError(Issue("missing_attribute", f"{o.kind} has no '{attr}'", o.id, attr))
        try:
            return float(raw)
        except ValueError:
            raise ObjectError(
                Issue("bad_number", f"'{attr}' is not a number: {raw!r}", o.id, attr)
            ) from None

    def check(self, o: Obj, attr: str, default: str, node: RawNode | None = None) -> float:
        """Evaluate a formula attribute in the pattern unit. `node` is a child element of `o` (a
        `pathPoint`) when the formula sits there instead of on the object.

        Like Seamly2D's `VAbstractTool::CheckFormula`, an infinite or NaN result becomes 0.
        """
        text = (node if node is not None else o).get(attr, default) or default
        try:
            f = parse(text)
            self.rec.uses_names.update(f.names)
            for name in f.names:
                owner = self.ev.owners.get(name)
                if owner is not None and self.is_forward(owner, own_is_forward=False):
                    raise FormulaError(
                        FormulaErrorCode.UNDEFINED_NAME,
                        f"{name!r} is built from this object or a later one",
                        text,
                        None,
                        name,
                        "a formula can only use objects defined before it",
                    )
            value = f.evaluate(self.ev.symbols)
        except FormulaError as err:
            raise ObjectError(
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
            self.rec.issues.append(
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
        self.rec.points.add(pid)

    def add_curve(self, cid: int, curve: CurveGeom) -> None:
        self.ev.curves[cid] = curve
        self.rec.curves.add(cid)

    def set_symbol(self, name: str, value: float, owner: int) -> None:
        self.ev.symbols[name] = value
        self.ev.owners[name] = owner
        self.rec.symbols.add(name)

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


Handler = Callable[[Ctx, Obj], None]
