"""Sections of a piece: `piece.section(landmark_a, landmark_b)`.

Rotate, move and mirror work on a list of points, curves and arcs. A plan rarely wants to list them
one by one; it wants "the part of the bodice front between the side neck point and the underarm".
A section names that: the points and curves along the piece's outline from landmark a to landmark
b, going round the outline in its own direction (so `section(b, a)` is the other part), both ends
included. After it, `+ name` adds a single object and `- name` leaves one out:

    C - Bodice Front.section(bodice_front.SNP, bodice_front.underarm) + X1 - bodice_front.BP

The piece is its name, `#<id>`, or its name without the block letter in lower case with underscores
(`bodice_front` for `C - Bodice Front`), which is how landmarks name pieces.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yoko_engine.model import RawNode
from yoko_engine.pieces import piece_nodes
from yoko_engine.pieces_edit import pieces_of

from yoko_tools.plan import section_parts

if TYPE_CHECKING:
    from yoko_tools.runtime import Toolbox

from yoko_tools.runtime import ToolError


def short_name(name: str) -> str:
    """`C - Bodice Front` -> `bodice_front`."""
    bare = re.sub(r"^[A-Za-z0-9]\s*[-:]\s+", "", name.strip())
    return re.sub(r"[^a-z0-9]+", "_", bare.lower()).strip("_")


def _piece(box: Toolbox, ref: str, field: str) -> tuple[RawNode, dict[str, int]]:
    """The piece element and its modeling copy -> drawn object map."""
    found: list[tuple[RawNode, dict[str, int]]] = []
    names: list[str] = []
    for _, piece, modeling in pieces_of(box.session.pattern):
        name = piece.get("name") or ""
        names.append(name)
        copies = {
            m.get("id") or "": int(m.get("idObject") or 0)
            for m in modeling.children
            if (m.get("idObject") or "").isdigit()
        }
        if ref == name or ref == f"#{piece.get('id')}" or ref == short_name(name):
            found.append((piece, copies))
    if len(found) == 1:
        return found[0]
    if not found:
        raise ToolError(
            "unknown_piece",
            f"there is no piece {ref!r}",
            field,
            "pieces: " + (", ".join(names) or "none yet"),
        )
    raise ToolError("ambiguous_piece", f"{len(found)} pieces match {ref!r}", field, "use #<id>")


def section_ids(box: Toolbox, text: str, field: str) -> list[int]:
    """The ids of the points and curves a section expression stands for, in outline order."""
    parts = section_parts(text)
    if parts is None:
        raise ToolError("bad_section", f"{text!r} is not piece.section(a, b)", field)
    piece_ref, a_name, b_name, mods = parts
    piece, copies = _piece(box, piece_ref, field)
    outline: list[int] = []
    for node in piece_nodes(piece):
        source = copies.get(str(node.id))
        if source is None or (
            source not in box.session.evaluation.points
            and source not in box.session.evaluation.curves
        ):
            raise ToolError(
                "unsupported_piece",
                f"piece {piece_ref!r} uses objects a union made; sections of it are not supported",
                field,
            )
        outline.append(source)
    a = box.resolve(a_name, "object", field).id
    b = box.resolve(b_name, "object", field).id
    for name, oid in ((a_name, a), (b_name, b)):
        if oid not in outline:
            raise ToolError(
                "not_on_outline",
                f"{name} is not on the outline of {piece_ref!r}",
                field,
                "a section runs between two landmarks that are on the piece's outline",
            )
    ia, ib = outline.index(a), outline.index(b)
    count = (ib - ia) % len(outline) + 1
    ids = [outline[(ia + k) % len(outline)] for k in range(count)]
    for sign, name in mods:
        oid = box.resolve(name, "object", field).id
        if sign == "+":
            if oid not in ids:
                ids.append(oid)
        else:
            ids = [i for i in ids if i != oid]
    return ids
