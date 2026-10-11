"""Operations that copy objects: mirror, and later rotate and move."""

from __future__ import annotations

from yoko_engine.evalcore import Ctx, Issue, ObjectError
from yoko_engine.geometry import Line
from yoko_engine.geometry.transform import flip_point
from yoko_engine.model import Obj


def flip_by_line(c: Ctx, o: Obj) -> None:
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
        raise ObjectError(
            Issue("bad_operation", "source and destination lists differ in length", o.id)
        )
    for src, dst in zip(src_items, dst_items, strict=True):
        sid = int(src.get("idObject", "-1") or -1)
        did = int(dst.get("idObject", "-1") or -1)
        original = c.point_by_id(o, sid, "source")
        flipped = flip_point(axis, original.p)
        c.add_point(o, flipped, key=did, label=original.label + suffix)
