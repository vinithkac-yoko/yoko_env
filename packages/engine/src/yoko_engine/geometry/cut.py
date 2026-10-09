"""Cutting curves, from Seamly2D's `VAbstractCubicBezier::CutSpline`, `CutSplinePath`,
`VToolCutSplinePath::CutSplinePath` and `VAbstractCurve::GetLengthByPoint`.

Used by the cut tools and by `curveIntersectAxis`, which splits the curve it crosses and
registers the two pieces as new curve variables.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from yoko_engine.fuzzy import fuzzy_is_null
from yoko_engine.geometry.circle_line import is_point_on_line_segment
from yoko_engine.geometry.curves import (
    Bezier,
    BezierPath,
    Spline,
    flatten_bezier,
    path_length,
)
from yoko_engine.geometry.qt import Line, Pt, points_equal
from yoko_engine.units import to_pixel

MIN_CUT_LENGTH = to_pixel(1, "mm")  # ToPixel(1, Unit::Mm)


def q_round(d: float) -> int:
    """qRound(double)."""
    if d >= 0.0:
        return int(d + 0.5)
    return int(d - float(int(d - 1)) + 0.5) + int(d - 1)


def same_int_point(a: Pt, b: Pt) -> bool:
    """QPointF::toPoint() equality: both points rounded to whole pixels."""
    return q_round(a.x) == q_round(b.x) and q_round(a.y) == q_round(b.y)


# -- polyline helpers (VAbstractCurve) ---------------------------------------------------------
def from_begin(points: list[Pt], begin: Pt) -> tuple[list[Pt], bool]:
    """The polyline from `begin` to its end, and whether `begin` was found on it."""
    if len(points) < 2:
        return points, False
    if same_int_point(points[0], begin):
        return points, True
    segment: list[Pt] = []
    started = False
    last = len(points) - 2
    for i in range(len(points) - 1):
        if not started:
            if is_point_on_line_segment(begin, points[i], points[i + 1]):
                started = True
                if not points_equal(begin, points[i + 1]):
                    segment.append(begin)
                if i == last:
                    segment.append(points[i + 1])
        else:
            segment.append(points[i])
            if i == last:
                segment.append(points[i + 1])
    if not segment:
        return points, False
    return segment, True


def to_end(points: list[Pt], end: Pt) -> tuple[list[Pt], bool]:
    reversed_points, ok = from_begin(list(reversed(points)), end)
    return list(reversed(reversed_points)), ok


def length_by_point(points: list[Pt], point: Pt) -> float:
    """VAbstractCurve::GetLengthByPoint: arc length from the start of the curve to `point`, or -1
    when `point` is not on it."""
    if len(points) < 2:
        return -1.0
    if same_int_point(points[0], point):
        return 0.0
    segment, ok = to_end(points, point)
    if not ok:
        return -1.0
    return path_length(segment)


# -- cutting one Bezier ------------------------------------------------------------------------
def _scaled(a: Pt, b: Pt, t: float) -> Pt:
    seg = Line(a, b)
    return seg.set_length(seg.length() * t).p2


def _de_casteljau(p1: Pt, c1: Pt, c2: Pt, p4: Pt, t: float) -> tuple[Pt, Pt, Pt, Pt, Pt, Pt]:
    """The six intermediate points of the construction, each found with QLineF::setLength as
    Seamly2D does (not with plain interpolation, which differs in the last bits)."""
    p12 = _scaled(p1, c1, t)
    p23 = _scaled(c1, c2, t)
    p123 = _scaled(p12, p23, t)
    p34 = _scaled(c2, p4, t)
    p234 = _scaled(p23, p34, t)
    p1234 = _scaled(p123, p234, t)
    return p12, p23, p123, p34, p234, p1234


def length_at(curve: Bezier | Spline, t: float) -> float:
    """VAbstractCubicBezier::LengthT: length of the part of the curve up to parameter `t`."""
    if t < 0 or t > 1:
        return 0.0
    p12, _p23, p123, _p34, _p234, p1234 = _de_casteljau(curve.p1, curve.c1, curve.c2, curve.p4, t)
    return path_length(flatten_bezier(curve.p1, p12, p123, p1234))


def param_t(curve: Bezier | Spline, length: float) -> float:
    """VAbstractCubicBezier::GetParmT: the parameter at which the curve has the given length, found
    by bisection to within 0.1%."""
    if length < 0:
        return 0.0
    total = curve.length()
    if length > total:
        length = total
    eps = 0.001 * length
    par = 0.5
    step = par
    spl_length = length_at(curve, par)
    while abs(spl_length - length) > eps:
        step /= 2.0
        par = par - step if spl_length > length else par + step
        spl_length = length_at(curve, par)
    return par


@dataclass(frozen=True, slots=True)
class CutResult:
    point: Pt
    spl1_p2: Pt
    spl1_p3: Pt
    spl2_p2: Pt
    spl2_p3: Pt


def cut_spline(curve: Bezier | Spline, length: float) -> CutResult | None:
    """VAbstractCubicBezier::CutSpline. Always yields two pieces, so `length` is clamped to between
    1 mm and (total - 1 mm); None when the curve is shorter than 1 mm."""
    full = curve.length()
    if full <= MIN_CUT_LENGTH:
        return None
    max_length = full - MIN_CUT_LENGTH
    if length < MIN_CUT_LENGTH:
        length = MIN_CUT_LENGTH
    elif length > max_length:
        length = max_length
    t = param_t(curve, length)
    p12, _p23, p123, p34, p234, p1234 = _de_casteljau(curve.p1, curve.c1, curve.c2, curve.p4, t)
    return CutResult(p1234, p12, p123, p234, p34)


# -- spline paths (VSplinePath) ----------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SplinePoint:
    """`VSplinePoint`: a path point with a handle angle and length on each side."""

    p: Pt
    label: str
    angle1: float = 0.0
    angle2: float = 0.0
    length1: float = 0.0
    length2: float = 0.0

    def with_angle2(self, value: float) -> SplinePoint:
        """SetAngle2: normalise, and set angle1 to the opposite direction."""
        angle2 = Line(Pt(0, 0), Pt(100, 0)).set_angle(value).angle()
        angle1 = Line(Pt(0, 0), Pt(100, 0)).set_angle(angle2 + 180).angle()
        return replace(self, angle2=angle2, angle1=angle1)

    def with_angle1(self, value: float) -> SplinePoint:
        """SetAngle1: normalise, and set angle2 to the opposite direction."""
        angle1 = Line(Pt(0, 0), Pt(100, 0)).set_angle(value).angle()
        angle2 = Line(Pt(0, 0), Pt(100, 0)).set_angle(angle1 + 180).angle()
        return replace(self, angle1=angle1, angle2=angle2)


@dataclass(frozen=True, slots=True)
class SplinePath:
    """`VSplinePath`: Bezier segments defined by angles and handle lengths at each point."""

    points: tuple[SplinePoint, ...]

    def append(self, point: SplinePoint) -> SplinePath:
        """VSplinePath::append ignores a point equal to the last one."""
        if self.points and points_equal(self.points[-1].p, point.p):
            return self
        return SplinePath((*self.points, point))

    def count(self) -> int:
        return len(self.points) - 1 if self.points else 0

    def segment(self, index: int) -> Spline:
        if index < 1 or index > self.count():
            raise ValueError("this spline does not exist")
        a = self.points[index - 1]
        b = self.points[index]
        return Spline(a.p, b.p, a.angle2, b.angle1, a.length2, b.length1)

    def segments(self) -> list[Spline]:
        return [self.segment(i) for i in range(1, self.count() + 1)]

    def length(self) -> float:
        total = 0.0
        for seg in self.segments():
            total += seg.length()
        return total

    def start_angle(self) -> float:
        return self.points[0].angle2 if self.points else 0.0

    def end_angle(self) -> float:
        return self.points[-1].angle1 if self.points else 0.0

    def c1_length(self) -> float:
        return self.points[0].length2 if self.points else 0.0

    def c2_length(self) -> float:
        return self.points[-1].length1 if self.points else 0.0

    @property
    def name(self) -> str:
        if not self.points:
            return ""
        name = f"SplPath_{self.points[0].label}"
        if self.count() >= 1:
            name += f"_{self.points[-1].label}"
        return name


def spline_path_points(path: BezierPath, labels: tuple[str, ...]) -> list[SplinePoint]:
    """VCubicBezierPath::GetSplinePath: the path re-expressed as angle-and-length points."""
    size = path.count()
    pts = [SplinePoint(Pt(0.0, 0.0), "") for _ in range(size + 1)]
    for i in range(1, size + 1):
        seg = path.segment(i)
        first = pts[i - 1].with_angle2(seg.start_angle())
        pts[i - 1] = replace(first, p=seg.p1, label=labels[(i - 1) * 3], length2=seg.c1_length())
        last = pts[i].with_angle1(seg.end_angle())
        pts[i] = replace(last, p=seg.p4, label=labels[i * 3], length1=seg.c2_length())
    return pts


@dataclass(frozen=True, slots=True)
class PathCut:
    point: Pt
    first: SplinePath
    second: SplinePath


def cut_spline_path(
    path: BezierPath, labels: tuple[str, ...], length: float, cut_label: str
) -> PathCut | None:
    """VAbstractCubicBezierPath::CutSplinePath combined with VToolCutSplinePath::CutSplinePath:
    cut a path at `length` and return the cut point and the two resulting spline paths."""
    if path.count() < 1:
        raise ValueError("can't cut this spline")
    full = path.length()
    if full <= MIN_CUT_LENGTH:
        return None
    max_length = full - MIN_CUT_LENGTH
    length = min(max(length, MIN_CUT_LENGTH), max_length)

    points = spline_path_points(path, labels)
    running = 0.0
    for i in range(1, path.count() + 1):
        spl = path.segment(i)
        spl_length = spl.length()
        running += spl_length
        if running <= length:
            continue
        p1, p2 = i - 1, i
        cut = cut_spline(spl, length - (running - spl_length))
        if cut is None:
            return None
        spl1_p2, spl2_p3 = cut.spl1_p2, cut.spl2_p3
        if p1 > 0:
            anchor = points[p1]
            if fuzzy_is_null(Line(anchor.p, spl1_p2).length()):
                nudged = Pt(spl1_p2.x + to_pixel(0.1, "mm"), spl1_p2.y)
                line = Line(anchor.p, nudged).set_length(to_pixel(0.1, "mm"))
                spl1_p2 = line.set_angle(anchor.angle1 + 180).p2
        if p2 < len(points) - 1:
            anchor = points[p2]
            if fuzzy_is_null(Line(anchor.p, spl2_p3).length()):
                nudged = Pt(spl2_p3.x + to_pixel(0.1, "mm"), spl2_p3.y)
                spl2_p3 = Line(anchor.p, nudged).set_angle(anchor.angle2 + 180).p2
        return _build_cut_paths(
            points, p1, p2, cut.point, spl1_p2, cut.spl1_p3, cut.spl2_p2, spl2_p3, cut_label
        )
    return None


def _build_cut_paths(
    points: list[SplinePoint],
    p1: int,
    p2: int,
    cut_point: Pt,
    spl1_p2: Pt,
    spl1_p3: Pt,
    spl2_p2: Pt,
    spl2_p3: Pt,
    cut_label: str,
) -> PathCut:
    sp1 = points[p1]
    sp2 = points[p2]
    spl1 = Spline.from_points(sp1.p, spl1_p2, spl1_p3, cut_point)
    spl2 = Spline.from_points(cut_point, spl2_p2, spl2_p3, sp2.p)
    first = SplinePath(())
    second = SplinePath(())
    for i, point in enumerate(points):
        if i <= p1 and i < p2:
            if i == p1:
                first = first.append(
                    SplinePoint(
                        sp1.p,
                        sp1.label,
                        spl1.start_angle() + 180,
                        spl1.start_angle(),
                        sp1.length1,
                        spl1.c1_length(),
                    )
                )
                first = first.append(
                    SplinePoint(
                        cut_point,
                        cut_label,
                        spl1.end_angle(),
                        spl1.end_angle() + 180,
                        spl1.c2_length(),
                        spl2.c1_length(),
                    )
                )
                continue
            first = first.append(point)
        else:
            if i == p2:
                second = second.append(
                    SplinePoint(
                        cut_point,
                        cut_label,
                        spl2.start_angle() + 180,
                        spl2.start_angle(),
                        spl1.c2_length(),
                        spl2.c1_length(),
                    )
                )
                second = second.append(
                    SplinePoint(
                        sp2.p,
                        sp2.label,
                        spl2.end_angle(),
                        spl2.end_angle() + 180,
                        spl2.c2_length(),
                        sp2.length2,
                    )
                )
                continue
            second = second.append(point)
    return PathCut(cut_point, first, second)


__all__ = [
    "MIN_CUT_LENGTH",
    "CutResult",
    "PathCut",
    "SplinePath",
    "SplinePoint",
    "cut_spline",
    "cut_spline_path",
    "from_begin",
    "length_at",
    "length_by_point",
    "param_t",
    "q_round",
    "same_int_point",
    "spline_path_points",
    "to_end",
]
