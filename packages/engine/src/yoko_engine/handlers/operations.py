"""Operations that copy objects: mirror (by line or by axis), rotate and move.

Each lists source objects and the ids their copies take (`<source>` and `<destination>`). A copy of
a point is named like the original plus the operation's `suffix`; a copy of a curve gets the
original's name plus the suffix, and registers the same variables as any curve of its kind.
"""

from __future__ import annotations

from yoko_engine.evalcore import Ctx, CurveGeom, Issue, ObjectError
from yoko_engine.geometry import Line, Pt
from yoko_engine.geometry.curves import Arc, Bezier, Spline
from yoko_engine.geometry.ellipse import ElArc
from yoko_engine.geometry.operate import (
    Mapper,
    flip_mapper,
    map_geom,
    move_mapper,
    rotate_mapper,
)
from yoko_engine.handlers.curves import register_path, register_spline
from yoko_engine.model import Obj, RawNode
from yoko_engine.units import from_pixel, to_pixel


def _items(o: Obj, tag: str) -> tuple[RawNode, ...]:
    for n in o.children:
        if n.tag == tag:
            return n.children
    return ()


def _id(n: RawNode) -> int:
    raw = n.get("idObject", "-1") or "-1"
    return int(raw) if raw.lstrip("-").isdigit() else -1


def _copy_all(c: Ctx, o: Obj, mappers: list[Mapper], *, mirror: bool) -> None:
    """Copy every source object through `mappers` (applied one after the other; a curve is rebuilt
    after each, as Seamly2D does when it moves and then rotates)."""
    suffix = o.get("suffix", "") or ""
    sources = _items(o, "source")
    dests = _items(o, "destination")
    if len(sources) != len(dests):
        raise ObjectError(
            Issue("bad_operation", "source and destination lists differ in length", o.id)
        )
    for src, dst in zip(sources, dests, strict=True):
        sid, did = _id(src), _id(dst)
        if sid in c.ev.points and not c.is_forward(sid):
            original = c.point_by_id(o, sid, "source")
            p = original.p
            for f in mappers:
                p = f(p)
            c.add_point(o, p, key=did, label=original.label + suffix)
            continue
        curve = c.ev.curves.get(sid)
        if curve is None or c.is_forward(sid):
            raise ObjectError(
                Issue(
                    "missing_reference",
                    f"source object {sid} does not exist (yet)",
                    o.id,
                    "source",
                    hint="objects can only use objects defined earlier in the pattern",
                )
            )
        c.deps.add(sid)
        geom = curve.geom
        if isinstance(geom, ElArc):
            raise ObjectError(
                Issue(
                    "not_implemented",
                    "mirror, rotate and move of an elliptical arc are not evaluated yet",
                    o.id,
                    "source",
                )
            )
        for f in mappers:
            geom = map_geom(geom, f, mirror=mirror)
        name = curve.name + suffix
        copy = CurveGeom(did, name, geom, curve.labels)
        if isinstance(geom, Arc):
            c.add_curve(did, copy)
            c.add_curve_variables(o.id, name, geom.length(), geom.start_angle(), geom.end_angle())
            c.set_symbol(f"Radius{name}", from_pixel(geom.radius, c.unit), o.id)
        elif isinstance(geom, Bezier | Spline):
            register_spline(c, o, geom, name, curve.labels, curve_id=did)
        else:
            register_path(c, o, geom, name, curve.labels, curve_id=did)


def flip_by_line(c: Ctx, o: Obj) -> None:
    """`VToolMirrorByLine`: mirror across the line through two points."""
    first = c.point(o, "p1Line")
    second = c.point(o, "p2Line")
    _copy_all(c, o, [flip_mapper(Line(first.p, second.p))], mirror=True)


def flip_by_axis(c: Ctx, o: Obj) -> None:
    """`VToolMirrorByAxis`: mirror across a vertical (`axisType` 1) or horizontal axis through a
    point."""
    origin = c.point(o, "center")
    if (o.get("axisType", "1") or "1") == "1":
        second = Pt(origin.p.x, origin.p.y + 100)
    else:
        second = Pt(origin.p.x + 100, origin.p.y)
    _copy_all(c, o, [flip_mapper(Line(origin.p, second))], mirror=True)


def rotation(c: Ctx, o: Obj) -> None:
    """`VToolRotation`: turn the objects by an angle around a point."""
    origin = c.point(o, "center")
    angle = c.check(o, "angle", "0")
    _copy_all(c, o, [rotate_mapper(origin.p, angle)], mirror=False)


def _bounding_center(points: list[Pt]) -> Pt:
    """`QPolygonF::boundingRect().center()`."""
    left = min(p.x for p in points)
    right = max(p.x for p in points)
    top = min(p.y for p in points)
    bottom = max(p.y for p in points)
    return Pt(left + (right - left) / 2.0, top + (bottom - top) / 2.0)


def _rotation_origin(c: Ctx, o: Obj, length: float, angle: float) -> Pt:
    """`VToolMove::findRotationOrigin`: the pivot for the rotation that follows the move. The chosen
    point (or the centre of the moved objects' bounding box), shifted by the move when it is itself
    among the moved objects."""
    raw = o.get("center", "0") or "0"
    origin_id = int(raw) if raw.isdigit() else 0
    ids = [_id(n) for n in _items(o, "source")]
    if origin_id != 0:
        pivot = c.point_by_id(o, origin_id, "center").p
        if origin_id not in ids:
            return pivot
    else:
        cloud: list[Pt] = []
        for sid in ids:
            if sid in c.ev.points:
                cloud.append(c.ev.points[sid].p)
                c.deps.add(sid)
            elif sid in c.ev.curves:
                cloud.extend(c.ev.curves[sid].geom.points())
                c.deps.add(sid)
        if not cloud:
            raise ObjectError(Issue("bad_operation", "nothing to move", o.id, "source"))
        pivot = _bounding_center(cloud)
    return Line(pivot, Pt(pivot.x + length, pivot.y)).set_angle(angle).p2


def moving(c: Ctx, o: Obj) -> None:
    """`VToolMove`: move by a length at an angle, then rotate about a pivot."""
    angle = c.check(o, "angle", "0")
    length = to_pixel(c.check(o, "length", "0"), c.unit)
    rotation_angle = c.check(o, "rotationAngle", "0")
    pivot = _rotation_origin(c, o, length, angle)
    _copy_all(
        c,
        o,
        [move_mapper(length, angle), rotate_mapper(pivot, rotation_angle)],
        mirror=False,
    )


__all__ = ["flip_by_axis", "flip_by_line", "moving", "rotation"]
