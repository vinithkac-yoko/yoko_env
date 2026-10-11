"""Copying objects by rotating, moving or mirroring them.

Seamly2D's operation tools (`VToolRotation`, `VToolMove`, `VToolMirrorByLine`, `VToolMirrorByAxis`)
build each copy by mapping the defining points of the original, then rebuilding the object from them
(`VSpline::Rotate`, `VArc::Flip`, ...). The rebuild matters: a `VSpline` re-derives its handles from
an angle and a length, so it is not the same as mapping the handles. Every function here follows the
Seamly2D method of the same name.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from yoko_engine.geometry.curves import (
    Arc,
    Bezier,
    BezierPath,
    Spline,
    SplinePath,
    SplinePoint,
)
from yoko_engine.geometry.qt import Line, Pt
from yoko_engine.geometry.transform import flip_point

Mapper = Callable[[Pt], Pt]
Geom = Arc | Bezier | Spline | BezierPath | SplinePath


def rotate_mapper(origin: Pt, degrees: float) -> Mapper:
    """`VPointF::RotatePF`."""

    def rotate(p: Pt) -> Pt:
        axis = Line(origin, p)
        return axis.set_angle(axis.angle() + degrees).p2

    return rotate


def move_mapper(length: float, angle: float) -> Mapper:
    """`VPointF::MovePF`."""

    def move(p: Pt) -> Pt:
        return Line(p, Pt(p.x + length, p.y)).set_angle(angle).p2

    return move


def flip_mapper(axis: Line) -> Mapper:
    """`VPointF::FlipPF`."""

    def flip(p: Pt) -> Pt:
        return flip_point(axis, p)

    return flip


def map_geom(geom: Geom, f: Mapper, *, mirror: bool = False) -> Geom:
    """The same kind of curve with every defining point mapped. `mirror` is true for a reflection,
    which turns an arc the other way round."""
    if isinstance(geom, Arc):
        center = f(geom.center)
        p1 = f(geom.p1())
        p2 = f(geom.p2())
        f1 = Line(center, p1).angle()
        f2 = Line(center, p2).angle()
        return Arc(center, geom.radius, f1, f2, geom.flipped != mirror)
    if isinstance(geom, Bezier):
        return Bezier(f(geom.p1), f(geom.c1), f(geom.c2), f(geom.p4))
    if isinstance(geom, Spline):
        return Spline.from_points(f(geom.p1), f(geom.c1), f(geom.c2), f(geom.p4))
    if isinstance(geom, BezierPath):
        return BezierPath(tuple(f(p) for p in geom.pts))
    return _map_spline_path(geom, f)


def _map_spline_path(path: SplinePath, f: Mapper) -> SplinePath:
    """`VSplinePath::Rotate` and friends: each segment is mapped, then the points are rebuilt from
    the mapped segments in order (a point's angles are set from the segment that starts at it last,
    which is why interior points end up with opposite angles)."""
    nodes = [SplinePoint(Pt(0.0, 0.0), n.label) for n in path.nodes]
    for i in range(1, path.count() + 1):
        spl = map_geom(path.segment(i), f)
        assert isinstance(spl, Spline)
        nodes[i - 1] = replace(
            nodes[i - 1].with_angle2(spl.start_angle()), p=spl.p1, length2=spl.c1_length()
        )
        nodes[i] = replace(nodes[i].with_angle1(spl.end_angle()), p=spl.p4, length1=spl.c2_length())
    return SplinePath(tuple(nodes))
