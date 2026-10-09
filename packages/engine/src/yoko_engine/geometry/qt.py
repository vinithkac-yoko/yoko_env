"""`QPointF` and `QLineF` as Seamly2D uses them.

Seamly2D computes every point with Qt's QLineF (`setAngle`, `setLength`, `normalVector`,
`intersects`, `angleTo`). To match it, these functions follow Qt 6's implementation, including its
conventions:

- Coordinates are screen coordinates: x grows to the right, **y grows downward**.
- Angles are in degrees, counter-clockwise **as seen on screen** (0 = right, 90 = up on screen, so
  `dy = -sin(angle) * length`). `Line.angle()` is in [0, 360).
- Equality of points is fuzzy (`qFuzzyCompare`, with a zero-aware variant), so a line whose ends are
  fuzzily equal is "null" and `set_length` leaves it unchanged.

All values are millimetres in the engine; Qt's own thresholds are relative or around 1e-12, so the
unit does not change behaviour.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from yoko_engine.fuzzy import fuzzy_compare, fuzzy_is_null

_M_2PI = 6.28318530717958647692


def _coord_equal(a: float, b: float) -> bool:
    # QPointF::operator== treats a zero coordinate with an absolute test, others relatively.
    if a == 0.0 or b == 0.0:
        return fuzzy_is_null(a - b)
    return fuzzy_compare(a, b)


@dataclass(frozen=True, slots=True)
class Pt:
    x: float
    y: float

    def __add__(self, other: Pt) -> Pt:
        return Pt(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Pt) -> Pt:
        return Pt(self.x - other.x, self.y - other.y)

    def scaled(self, k: float) -> Pt:
        return Pt(self.x * k, self.y * k)


def points_equal(a: Pt, b: Pt) -> bool:
    """QPointF::operator== (fuzzy)."""
    return _coord_equal(a.x, b.x) and _coord_equal(a.y, b.y)


class IntersectType(Enum):
    NO_INTERSECTION = 0
    BOUNDED = 1
    UNBOUNDED = 2


@dataclass(frozen=True, slots=True)
class Line:
    """QLineF. Immutable: `set_angle` and `set_length` return a new line."""

    p1: Pt
    p2: Pt

    @property
    def dx(self) -> float:
        return self.p2.x - self.p1.x

    @property
    def dy(self) -> float:
        return self.p2.y - self.p1.y

    def is_null(self) -> bool:
        return points_equal(self.p1, self.p2)

    def length(self) -> float:
        return math.hypot(self.dx, self.dy)

    def angle(self) -> float:
        """Angle in [0, 360), counter-clockwise on screen (QLineF::angle)."""
        theta = math.degrees(math.atan2(-self.dy, self.dx))
        normalized = theta + 360 if theta < 0 else theta
        if fuzzy_compare(normalized, 360.0):
            return 0.0
        return normalized

    def angle_to(self, other: Line) -> float:
        """Counter-clockwise angle from this line to `other` (QLineF::angleTo)."""
        if self.is_null() or other.is_null():
            return 0.0
        delta = other.angle() - self.angle()
        normalized = delta + 360 if delta < 0 else delta
        if fuzzy_compare(delta, 360.0):
            return 0.0
        return normalized

    def set_angle(self, angle: float) -> Line:
        """Rotate about p1 keeping the length (QLineF::setAngle)."""
        angle_r = angle * _M_2PI / 360.0
        length = self.length()
        dx = math.cos(angle_r) * length
        dy = -math.sin(angle_r) * length
        return Line(self.p1, Pt(self.p1.x + dx, self.p1.y + dy))

    def unit_vector(self) -> Line:
        x = self.dx
        y = self.dy
        length = math.hypot(x, y)
        if length == 0.0:
            return Line(self.p1, Pt(math.nan, math.nan))
        return Line(self.p1, Pt(self.p1.x + x / length, self.p1.y + y / length))

    def set_length(self, length: float) -> Line:
        """Scale about p1 (QLineF::setLength). A null line is returned unchanged."""
        if self.is_null():
            return self
        v = self.unit_vector()
        return Line(self.p1, Pt(self.p1.x + v.dx * length, self.p1.y + v.dy * length))

    def normal_vector(self) -> Line:
        """Perpendicular through p1, same length, rotated 90 degrees counter-clockwise on screen."""
        return Line(self.p1, Pt(self.p1.x + self.dy, self.p1.y - self.dx))

    def translated(self, d: Pt) -> Line:
        return Line(self.p1 + d, self.p2 + d)

    def intersects(self, other: Line) -> tuple[IntersectType, Pt | None]:
        """QLineF::intersects (Graphics Gems III, "Faster Line Segment Intersection")."""
        a = self.p2 - self.p1
        b = other.p1 - other.p2
        c = self.p1 - other.p1
        denominator = a.y * b.x - a.x * b.y
        if denominator == 0 or not math.isfinite(denominator):
            return IntersectType.NO_INTERSECTION, None
        reciprocal = 1 / denominator
        na = (b.y * c.x - b.x * c.y) * reciprocal
        point = self.p1 + a.scaled(na)
        if na < 0 or na > 1:
            return IntersectType.UNBOUNDED, point
        nb = (a.x * c.y - a.y * c.x) * reciprocal
        if nb < 0 or nb > 1:
            return IntersectType.UNBOUNDED, point
        return IntersectType.BOUNDED, point
