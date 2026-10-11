"""Elliptical arcs, ported from `VEllipticalArc` (src/libs/vgeometry/vellipticalarc.cpp).

Seamly2D draws an elliptical arc with Qt: `QPainterPath::arcTo` turns the arc into cubic Beziers,
`QTransform::map` moves them, and `toSubpathPolygons` flattens them (`QBezier::addToPolygon`). The
length of the arc is the length of that polyline, so the Qt routines are reproduced here
(`qt_find_ellipse_coords`, `qt_t_for_arc_angle`, `qt_curves_for_arc`, `QBezier`). Qt version 6.4.2,
checked against the pinned Seamly2D's own output by `tests/test_elliptical_arc.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from yoko_engine.fuzzy import fuzzy_compare, fuzzy_compare_possible_nulls, fuzzy_is_null
from yoko_engine.geometry.curves import path_length
from yoko_engine.geometry.qt import Line, Pt, points_equal
from yoko_engine.geometry.transform import Transform, flip_transform
from yoko_engine.units import to_pixel

KAPPA = 0.5522847498  # QT_PATH_KAPPA


# -- QBezier --------------------------------------------------------------------------------------
class _Bezier:
    __slots__ = ("x1", "x2", "x3", "x4", "y1", "y2", "y3", "y4")

    def __init__(self, p1: Pt, p2: Pt, p3: Pt, p4: Pt) -> None:
        self.x1, self.y1 = p1.x, p1.y
        self.x2, self.y2 = p2.x, p2.y
        self.x3, self.y3 = p3.x, p3.y
        self.x4, self.y4 = p4.x, p4.y

    def pts(self) -> tuple[Pt, Pt, Pt, Pt]:
        return (
            Pt(self.x1, self.y1),
            Pt(self.x2, self.y2),
            Pt(self.x3, self.y3),
            Pt(self.x4, self.y4),
        )

    def split(self) -> tuple[_Bezier, _Bezier]:
        """QBezier::split: de Casteljau at t = 0.5."""
        p1, p2, p3, p4 = self.pts()

        def mid(a: Pt, b: Pt) -> Pt:
            return Pt((a.x + b.x) * 0.5, (a.y + b.y) * 0.5)

        mid_12 = mid(p1, p2)
        mid_23 = mid(p2, p3)
        mid_34 = mid(p3, p4)
        mid_12_23 = mid(mid_12, mid_23)
        mid_23_34 = mid(mid_23, mid_34)
        centre = mid(mid_12_23, mid_23_34)
        return _Bezier(p1, mid_12, mid_12_23, centre), _Bezier(centre, mid_23_34, mid_34, p4)

    def parameter_split_left(self, t: float) -> _Bezier:
        """QBezier::parameterSplitLeft: returns the left part, `self` becomes the right part."""
        lx2 = self.x1 + t * (self.x2 - self.x1)
        ly2 = self.y1 + t * (self.y2 - self.y1)
        lx3 = self.x2 + t * (self.x3 - self.x2)
        ly3 = self.y2 + t * (self.y3 - self.y2)
        self.x3 = self.x3 + t * (self.x4 - self.x3)
        self.y3 = self.y3 + t * (self.y4 - self.y3)
        self.x2 = lx3 + t * (self.x3 - lx3)
        self.y2 = ly3 + t * (self.y3 - ly3)
        lx3 = lx2 + t * (lx3 - lx2)
        ly3 = ly2 + t * (ly3 - ly2)
        lx4 = lx3 + t * (self.x2 - lx3)
        ly4 = ly3 + t * (self.y2 - ly3)
        left = _Bezier(Pt(self.x1, self.y1), Pt(lx2, ly2), Pt(lx3, ly3), Pt(lx4, ly4))
        self.x1, self.y1 = lx4, ly4
        return left

    def on_interval(self, t0: float, t1: float) -> _Bezier:
        """QBezier::bezierOnInterval."""
        if t0 == 0 and t1 == 1:
            return self
        work = _Bezier(*self.pts())
        result = work.parameter_split_left(t0)
        true_t = (t1 - t0) / (1 - t0)
        result = work.parameter_split_left(true_t)
        return result

    def add_to_polygon(self, polygon: list[Pt], threshold: float = 0.5) -> None:
        """QBezier::addToPolygon: adaptive flattening with a stack of at most ten curves."""
        stack: list[_Bezier] = [self]
        levels = [9]
        while stack:
            b = stack[-1]
            y4y1 = b.y4 - b.y1
            x4x1 = b.x4 - b.x1
            length = abs(x4x1) + abs(y4y1)
            if length > 1.0:
                d = abs(x4x1 * (b.y1 - b.y2) - y4y1 * (b.x1 - b.x2)) + abs(
                    x4x1 * (b.y1 - b.y3) - y4y1 * (b.x1 - b.x3)
                )
            else:
                d = abs(b.x1 - b.x2) + abs(b.y1 - b.y2) + abs(b.x1 - b.x3) + abs(b.y1 - b.y3)
                length = 1.0
            if d < threshold * length or levels[-1] == 0:
                polygon.append(Pt(b.x4, b.y4))
                stack.pop()
                levels.pop()
            else:
                first, second = b.split()
                # the second half goes lower in the stack, so it is processed after the first
                stack[-1] = second
                level = levels[-1] - 1
                levels[-1] = level
                stack.append(first)
                levels.append(level)


# -- QPainterPath::arcTo ---------------------------------------------------------------------------
def _coefficients(t: float) -> tuple[float, float, float, float]:
    """QBezier::coefficients."""
    m_t = 1.0 - t
    b = m_t * m_t
    c = t * t
    d = c * t
    a = b * m_t
    b *= 3.0 * t
    c *= 3.0 * m_t
    return a, b, c, d


def t_for_arc_angle(angle: float) -> float:
    """qt_t_for_arc_angle: the Bezier parameter whose point on a quarter-circle curve lies at
    `angle` degrees (two Newton steps each for cosine and sine, then the mean)."""
    if fuzzy_is_null(angle):
        return 0.0
    if fuzzy_compare(angle, 90.0):
        return 1.0
    radians = math.radians(angle)
    cos_angle = math.cos(radians)
    sin_angle = math.sin(radians)
    k = KAPPA
    tc = angle / 90
    for _ in range(2):
        tc -= ((((2 - 3 * k) * tc + 3 * (k - 1)) * tc) * tc + 1 - cos_angle) / (
            ((6 - 9 * k) * tc + 6 * (k - 1)) * tc
        )
    ts = tc
    for _ in range(2):
        ts -= ((((3 * k - 2) * ts - 6 * k + 3) * ts + 3 * k) * ts - sin_angle) / (
            ((9 * k - 6) * ts + 12 * k - 6) * ts + 3 * k
        )
    return 0.5 * (tc + ts)


@dataclass(frozen=True, slots=True)
class _Rect:
    x: float
    y: float
    w: float
    h: float

    def center(self) -> Pt:
        return Pt(self.x + self.w / 2.0, self.y + self.h / 2.0)


def find_ellipse_coords(r: _Rect, angle: float, length: float) -> tuple[Pt, Pt]:
    """qt_find_ellipse_coords: the points of the ellipse at `angle` and `angle + length`."""
    if r.w == 0 and r.h == 0:
        return Pt(0.0, 0.0), Pt(0.0, 0.0)
    w2 = r.w / 2
    h2 = r.h / 2
    out: list[Pt] = []
    for a in (angle, angle + length):
        theta = a - 360 * math.floor(a / 360)
        t = theta / 90
        quadrant = int(t)
        t -= quadrant
        t = t_for_arc_angle(90 * t)
        if quadrant & 1:
            t = 1 - t
        ca, cb, cc, cd = _coefficients(t)
        px = ca + cb + cc * KAPPA
        py = cd + cc + cb * KAPPA
        if quadrant in (1, 2):
            px = -px
        if quadrant in (0, 1):
            py = -py
        c = r.center()
        out.append(Pt(c.x + w2 * px, c.y + h2 * py))
    return out[0], out[1]


def curves_for_arc(rect: _Rect, start_angle: float, sweep_length: float) -> tuple[Pt, list[Pt]]:
    """qt_curves_for_arc: the start point and the control points of the cubics (three per curve)
    that approximate an arc of the ellipse in `rect`."""
    if rect.w == 0 and rect.h == 0:
        return Pt(0.0, 0.0), []
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    w2 = w / 2
    w2k = w2 * KAPPA
    h2 = h / 2
    h2k = h2 * KAPPA
    points = [
        Pt(x + w, y + h2),
        Pt(x + w, y + h2 + h2k),
        Pt(x + w2 + w2k, y + h),
        Pt(x + w2, y + h),
        Pt(x + w2 - w2k, y + h),
        Pt(x, y + h2 + h2k),
        Pt(x, y + h2),
        Pt(x, y + h2 - h2k),
        Pt(x + w2 - w2k, y),
        Pt(x + w2, y),
        Pt(x + w2 + w2k, y),
        Pt(x + w, y + h2 - h2k),
        Pt(x + w, y + h2),
    ]
    sweep_length = max(-360.0, min(360.0, sweep_length))
    if start_angle == 0.0:
        if sweep_length == 360.0:
            return points[12], [points[i] for i in range(11, -1, -1)]
        if sweep_length == -360.0:
            return points[0], [points[i] for i in range(1, 13)]

    start_segment = math.floor(start_angle / 90)
    end_segment = math.floor((start_angle + sweep_length) / 90)
    start_t = (start_angle - start_segment * 90) / 90
    end_t = (start_angle + sweep_length - end_segment * 90) / 90
    delta = 1 if sweep_length > 0 else -1
    if delta < 0:
        start_t = 1 - start_t
        end_t = 1 - end_t
    if fuzzy_is_null(start_t - 1.0):
        start_t = 0.0
        start_segment += delta
    if fuzzy_is_null(end_t):
        end_t = 1.0
        end_segment -= delta
    start_t = t_for_arc_angle(start_t * 90)
    end_t = t_for_arc_angle(end_t * 90)
    split_at_start = not fuzzy_is_null(start_t)
    split_at_end = not fuzzy_is_null(end_t - 1.0)
    end = end_segment + delta

    if start_segment == end:
        quadrant = 3 - ((start_segment % 4) + 4) % 4
        j = 3 * quadrant
        return (points[j + 3] if delta > 0 else points[j]), []

    start_point, end_point = find_ellipse_coords(rect, start_angle, sweep_length)
    curves: list[Pt] = []
    i = start_segment
    while i != end:
        quadrant = 3 - ((i % 4) + 4) % 4
        j = 3 * quadrant
        if delta > 0:
            b = _Bezier(points[j + 3], points[j + 2], points[j + 1], points[j])
        else:
            b = _Bezier(points[j], points[j + 1], points[j + 2], points[j + 3])
        if start_segment == end_segment and fuzzy_compare(start_t, end_t):
            return start_point, []
        if i == start_segment:
            if i == end_segment and split_at_end:
                b = b.on_interval(start_t, end_t)
            elif split_at_start:
                b = b.on_interval(start_t, 1.0)
        elif i == end_segment and split_at_end:
            b = b.on_interval(0.0, end_t)
        _, c2, c3, c4 = b.pts()
        curves.extend((c2, c3, c4))
        i += delta
    curves[-1] = end_point
    return start_point, curves


# -- VEllipticalArc ------------------------------------------------------------------------------
def _normalize_angle(angle: float) -> float:
    """VEllipticalArc::normalizeAngle."""
    return angle - 360.0 * math.floor(angle / 360.0)


def _transform_key(t: Transform) -> tuple[float, ...]:
    return (t.m11, t.m12, t.m13, t.m21, t.m22, t.m23, t.m_dx, t.m_dy, t.m33)


@dataclass(frozen=True, slots=True, eq=False)
class ElArc:
    """An elliptical arc: `f1` to `f2` degrees on the ellipse with half-axes `radius1` (along the
    x axis before `rotation`) and `radius2`, centred on `center`. `transform` is what a mirror,
    rotation or move has done to it since it was drawn (it never changes the stored numbers)."""

    center: Pt
    radius1: float
    radius2: float
    f1: float
    f2: float
    rotation: float = 0.0
    flipped: bool = False
    transform: Transform = field(default_factory=Transform)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ElArc)
            and (self.center, self.radius1, self.radius2, self.f1, self.f2, self.rotation)
            == (other.center, other.radius1, other.radius2, other.f1, other.f2, other.rotation)
            and self.flipped == other.flipped
            and _transform_key(self.transform) == _transform_key(other.transform)
        )

    def __hash__(self) -> int:
        return hash((self.center, self.radius1, self.radius2, self.f1, self.f2, self.rotation))

    def real_center(self) -> Pt:
        """VEllipticalArc::GetCenter: the centre after the transform."""
        return self.transform.map(self.center)

    def _point(self, angle: float) -> Pt:
        """VEllipticalArc::getPoint: the point of the (untransformed) ellipse at `angle`."""
        if fuzzy_is_null(self.radius1) and fuzzy_is_null(self.radius2):
            return self.real_center()
        line = Line(Pt(0.0, 0.0), Pt(100.0, 0.0)).set_angle(angle)
        a = line.p2.x / self.radius1 if not fuzzy_is_null(self.radius1) else 0.0
        b = line.p2.y / self.radius2 if not fuzzy_is_null(self.radius2) else 0.0
        k = math.sqrt(a * a + b * b)
        if fuzzy_is_null(k):
            return self.real_center()
        p = Pt(line.p2.x / k, line.p2.y / k)
        line2 = Line(Pt(0.0, 0.0), p)
        line2 = line2.set_angle(line2.angle() + self.rotation)
        return Pt(line2.p2.x + self.center.x, line2.p2.y + self.center.y)

    def p1(self) -> Pt:
        return self.transform.map(self._point(self.f1))

    def p2(self) -> Pt:
        return self.transform.map(self._point(self.f2))

    def start_angle(self) -> float:
        """VEllipticalArc::GetStartAngle (the angle of the start point seen from the centre)."""
        return Line(self.real_center(), self.p1()).angle() - self.rotation

    def end_angle(self) -> float:
        return Line(self.real_center(), self.p2()).angle() - self.rotation

    def _real_end_angle(self) -> float:
        end = _normalize_angle(self.f2)
        if (
            fuzzy_is_null(end)
            or fuzzy_compare_possible_nulls(end, 90)
            or fuzzy_compare_possible_nulls(end, 180)
            or fuzzy_compare_possible_nulls(end, 270)
            or fuzzy_compare_possible_nulls(end, 360)
        ):
            return end
        return math.degrees(
            math.atan2(
                self.radius1 * math.sin(math.radians(end)),
                self.radius2 * math.cos(math.radians(end)),
            )
        )

    def points(self) -> list[Pt]:
        """VEllipticalArc::getPoints."""
        c = self.center
        box = _Rect(c.x - self.radius1, c.y - self.radius2, self.radius1 * 2, self.radius2 * 2)
        start_line = Line(c, Pt(c.x + self.radius1, c.y)).set_angle(self.f1)
        end_line = Line(c, Pt(c.x + self.radius1, c.y)).set_angle(self._real_end_angle())
        sweep = start_line.angle_to(end_line)
        if fuzzy_is_null(sweep):
            sweep = 360.0

        # The path is moveTo(P1), arcTo (a line to the arc's start, then cubics), moveTo(P2); only
        # its first subpath matters.
        first = self.p1()
        curve_start, controls = curves_for_arc(box, self.f1, sweep)

        t = self.transform.copy()
        t.translate(c.x, c.y)
        t.rotate(-self.rotation)
        t.translate(-c.x, -c.y)

        # QPainterPath::lineTo ignores a point that equals the last one (fuzzy), so when the arc
        # starts where the path started there is no line, and the first cubic starts at `first`.
        polygon: list[Pt] = [t.map(first)]
        previous = first
        if not points_equal(curve_start, first):
            polygon.append(t.map(curve_start))
            previous = curve_start
        for i in range(0, len(controls), 3):
            bezier = _Bezier(
                t.map(previous), t.map(controls[i]), t.map(controls[i + 1]), t.map(controls[i + 2])
            )
            bezier.add_to_polygon(polygon)
            previous = controls[i + 2]
        if polygon and not points_equal(first, polygon[0]):
            polygon.pop(0)  # remove the point the path started from
        return polygon

    def length(self) -> float:
        length = path_length(self.points())
        return -length if self.flipped else length

    # The operations (VEllipticalArc::Rotate, Flip, Move): the numbers stay, the transform changes.
    def _inverse(self) -> Transform:
        inv = self.transform.inverted()
        if inv is None:
            raise ValueError("the arc's transform cannot be inverted")
        return inv

    def rotate(self, origin: Pt, degrees: float) -> ElArc:
        origin = self._inverse().map(origin)
        t = self.transform.copy()
        t.translate(origin.x, origin.y)
        t.rotate(degrees if self.flipped else -degrees)
        t.translate(-origin.x, -origin.y)
        return replace(self, transform=t)

    def flip(self, axis: Line) -> ElArc:
        inv = self._inverse()
        t = self.transform.copy().multiply(flip_transform(Line(inv.map(axis.p1), inv.map(axis.p2))))
        return replace(self, flipped=not self.flipped, transform=t)

    def move(self, length: float, angle: float) -> ElArc:
        old = self.center  # VAbstractArc::GetCenter: the stored centre, before the transform
        new = Line(old, Pt(old.x + length, old.y)).set_angle(angle).p2
        inv = self._inverse()
        a, b = inv.map(new), inv.map(old)
        t = self.transform.copy()
        t.translate(a.x - b.x, a.y - b.y)
        return replace(self, transform=t)

    @staticmethod
    def from_length(
        length: float, center: Pt, radius1: float, radius2: float, f1: float, rotation: float
    ) -> ElArc:
        """`VEllipticalArc(length, ...)` with `FindF2`: the arc that starts at `f1` and is `length`
        long (a negative length runs the other way round), found by halving the angle step until
        the flattened length is within 0.001 mm."""
        gap = 180.0
        flipped = length < 0
        if flipped:
            gap = -gap
        arc = ElArc(center, radius1, radius2, f1, 0.0, rotation, flipped=flipped)
        length = min(length, arc.max_length())
        ray = Line(center, Pt(center.x + radius1, center.y)).set_angle(arc.start_angle())
        ray = ray.set_angle(ray.angle() + gap)
        end = ray.angle()
        arc = replace(arc, f2=end)
        found = arc.length()
        eps = to_pixel(0.001, "mm")
        while abs(found - length) > eps:
            gap /= 2
            if gap < 0.0001:
                break
            ray = ray.set_angle(end - abs(gap) if found > length else end + abs(gap))
            end = ray.angle()
            arc = replace(arc, f2=end)
            found = arc.length()
        return arc

    def cut(self, length: float) -> tuple[Pt, ElArc, ElArc] | None:
        """`VEllipticalArc::CutArc`: split at arc length `length` from the start. None when the arc
        is not longer than 1 mm."""
        min_length = to_pixel(1.0, "mm")
        full = self.length()
        if full <= min_length:
            return None
        max_length = full - min_length
        length = min_length if length < min_length else min(length, max_length)
        centre = self.real_center()
        first = ElArc.from_length(
            length, centre, self.radius1, self.radius2, self.start_angle(), self.rotation
        )
        second = ElArc(
            centre, self.radius1, self.radius2, first.end_angle(), self.end_angle(), self.rotation
        )
        return first.p1(), first, second

    def max_length(self) -> float:
        """VEllipticalArc::MaxLength: Ramanujan's approximation of the whole ellipse."""
        h = (self.radius1 - self.radius2) ** 2 / (self.radius1 + self.radius2) ** 2
        return math.pi * (self.radius1 + self.radius2) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))


__all__ = ["ElArc", "curves_for_arc", "find_ellipse_coords", "t_for_arc_angle"]
