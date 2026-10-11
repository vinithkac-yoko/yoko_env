"""Handle lengths for cubic Beziers: Hobby's smooth curves and target-length solvers.

Ported from `VAbstractCubicBezier::HobbyHandleLengths`, `CubicBezierLengthGL`, `SolveHandleLengths`
and `SolveHobbyTension` (src/libs/vgeometry/vabstractcubicbezier.cpp), which Seamly2D 0.7.4 added
behind the `autoSmooth` and `lengthMode` options of the spline tools. Pixel scale, angles in
degrees counter-clockwise on screen.
"""

from __future__ import annotations

import math

from yoko_engine.geometry.qt import Line, Pt
from yoko_engine.units import to_pixel

_EPSILON_PX = to_pixel(0.05, "mm")  # the solvers stop within 0.05 mm of the target length

_GL_T = (
    0.01985071506835568,
    0.10166676129318664,
    0.23723379504183550,
    0.40828267875217509,
    0.59171732124782494,
    0.76276620495816450,
    0.89833323870681336,
    0.98014928493164430,
)
_GL_W = (
    0.05061426814518813,
    0.11119051722668723,
    0.15685332293894364,
    0.18134189168918099,
    0.18134189168918099,
    0.15685332293894364,
    0.11119051722668723,
    0.05061426814518813,
)
_PANELS = 16


def hobby_handle_lengths(
    p1: Pt,
    p4: Pt,
    angle1: float,
    angle2: float,
    tension_start: float = 1.0,
    tension_end: float = 1.0,
) -> tuple[float, float]:
    """`HobbyHandleLengths`: handle lengths that make a smooth curve from p1, leaving at `angle1`,
    to p4, arriving with the handle at `angle2`."""
    chord = Line(p1, p4)
    d = chord.length()
    if abs(d) <= 0.000000000001:
        return 0.0, 0.0
    chord_rad = math.radians(chord.angle())
    theta = math.radians(angle1) - chord_rad
    phi = math.radians(chord.angle() + 180.0) - math.radians(angle2)
    two_pi = 2.0 * math.pi
    while theta > math.pi:
        theta -= two_pi
    while theta < -math.pi:
        theta += two_pi
    while phi > math.pi:
        phi -= two_pi
    while phi < -math.pi:
        phi += two_pi

    sq2 = math.sqrt(2.0)
    sqrt5 = math.sqrt(5.0)
    c_a = 0.5 * (sqrt5 - 1.0)
    c_b = 0.5 * (3.0 - sqrt5)

    def velocity(a: float, b: float) -> float:
        num = 2.0 + sq2 * (math.sin(a) - math.sin(b) / 16.0) * (
            math.sin(b) - math.sin(a) / 16.0
        ) * (math.cos(a) - math.cos(b))
        den = 3.0 * (1.0 + c_a * math.cos(a) + c_b * math.cos(b))
        return num / den if abs(den) > 1e-9 else 1.0 / 3.0

    tau_start = tension_start if tension_start > 1e-6 else 1e-6
    tau_end = tension_end if tension_end > 1e-6 else 1e-6
    c1 = max(1e-4, min(velocity(theta, phi) * d / tau_start, d * 8.0))
    c2 = max(1e-4, min(velocity(phi, theta) * d / tau_end, d * 8.0))
    return c1, c2


def cubic_bezier_length_gl(p1: Pt, p2: Pt, p3: Pt, p4: Pt) -> float:
    """`CubicBezierLengthGL`: arc length by 8-point Gauss-Legendre quadrature over 16 panels."""
    length = 0.0
    for panel in range(_PANELS):
        for t, w in zip(_GL_T, _GL_W, strict=True):
            s = (panel + t) / _PANELS
            q = 1.0 - s
            dx = (
                3.0 * (p2.x - p1.x) * (q * q)
                + 6.0 * (p3.x - p2.x) * (q * s)
                + 3.0 * (p4.x - p3.x) * (s * s)
            )
            dy = (
                3.0 * (p2.y - p1.y) * (q * q)
                + 6.0 * (p3.y - p2.y) * (q * s)
                + 3.0 * (p4.y - p3.y) * (s * s)
            )
            length += w * math.sqrt(dx * dx + dy * dy) / _PANELS
    return length


def _controls(
    p1: Pt, p4: Pt, cos1: float, sin1: float, cos2: float, sin2: float, h: tuple[float, float]
) -> tuple[Pt, Pt]:
    return (
        Pt(p1.x + h[0] * cos1, p1.y + -h[0] * sin1),
        Pt(p4.x + h[1] * cos2, p4.y + -h[1] * sin2),
    )


def solve_handle_lengths(
    p1: Pt,
    p4: Pt,
    angle1: float,
    angle2: float,
    base_c1: float,
    base_c2: float,
    target_px: float,
    mode: int,
) -> tuple[float, float]:
    """`SolveHandleLengths`: scale the handles (mode 1 start, 2 end, otherwise both) so the curve
    is `target_px` long, by bisection."""
    if base_c1 <= 0.0 and base_c2 <= 0.0:
        return base_c1, base_c2
    a1 = math.radians(angle1)
    a2 = math.radians(angle2)
    cos1, sin1, cos2, sin2 = math.cos(a1), math.sin(a1), math.cos(a2), math.sin(a2)

    def handles(scale: float) -> tuple[float, float]:
        c1, c2 = base_c1, base_c2
        if mode == 1:
            c1 = base_c1 * scale
        elif mode == 2:
            c2 = base_c2 * scale
        else:
            c1 = base_c1 * scale
            c2 = base_c2 * scale
        return c1, c2

    def curve_len(scale: float) -> float:
        c1, c2 = _controls(p1, p4, cos1, sin1, cos2, sin2, handles(scale))
        return cubic_bezier_length_gl(p1, c1, c2, p4)

    if target_px <= curve_len(0.0):
        return 0.0, 0.0
    hi = 1.0
    guard = 0
    while guard < 64 and curve_len(hi) < target_px:
        hi *= 2.0
        guard += 1
    lo = 0.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        f = curve_len(mid) - target_px
        if abs(f) < _EPSILON_PX:
            return handles(mid)
        if f < 0.0:
            lo = mid
        else:
            hi = mid
    return handles(0.5 * (lo + hi))


def solve_hobby_tension(
    p1: Pt, p4: Pt, angle1: float, angle2: float, target_px: float, mode: int
) -> tuple[float, float]:
    """`SolveHobbyTension`: vary the Hobby tension (mode 1 start, 2 end, otherwise both) until the
    curve is `target_px` long, by bisection on a log scale."""
    a1 = math.radians(angle1)
    a2 = math.radians(angle2)
    cos1, sin1, cos2, sin2 = math.cos(a1), math.sin(a1), math.cos(a2), math.sin(a2)

    def handles(tau: float) -> tuple[float, float]:
        tau_start = tau_end = 1.0
        if mode == 1:
            tau_start = tau
        elif mode == 2:
            tau_end = tau
        else:
            tau_start = tau_end = tau
        return hobby_handle_lengths(p1, p4, angle1, angle2, tau_start, tau_end)

    def len_for(tau: float) -> float:
        c1, c2 = _controls(p1, p4, cos1, sin1, cos2, sin2, handles(tau))
        return cubic_bezier_length_gl(p1, c1, c2, p4)

    tau_min = 1.0 / 1024.0
    tau_max = 1024.0
    len_max = len_for(tau_min)
    len_min = len_for(tau_max)
    if target_px >= len_max:
        return handles(tau_min)
    if target_px <= len_min:
        return handles(tau_max)
    lo, hi = tau_min, tau_max
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        f = len_for(mid) - target_px
        if abs(f) < _EPSILON_PX:
            return handles(mid)
        if f > 0.0:
            lo = mid
        else:
            hi = mid
    return handles(math.sqrt(lo * hi))
