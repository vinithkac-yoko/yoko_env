"""Editing blocks and pieces: add, change and delete them without touching what Seamly2D keeps that
we do not compute (labels, grainlines, seam allowance, notches, ...).

A piece lists *modeling* copies of draft objects (`<modeling>`), and its nodes name those copies.
Creating a piece therefore adds one copy per draft object it uses (reusing an existing copy), then
the `<piece>` element. Seamly2D opens a piece with just an id, a name and its nodes (the other
attributes take their defaults), which `scripts/oracle_cases.sh` checks.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from yoko_engine.evalcore import Evaluation
from yoko_engine.geometry.curves import Arc, BezierPath, SplinePath
from yoko_engine.geometry.ellipse import ElArc
from yoko_engine.model import DraftBlock, Pattern, RawNode


class EditError(ValueError):
    """An edit that cannot be done; `code` is a stable machine-readable reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """One node of a piece's main path: a draft object (point, arc, curve) and which way a curve
    runs along the path."""

    object_id: int
    reverse: bool = False


def _ids(node: RawNode) -> Iterable[int]:
    raw = node.get("id")
    if raw is not None and raw.isdigit():
        yield int(raw)
    for child in node.children:
        yield from _ids(child)


def used_ids(pattern: Pattern) -> set[int]:
    """Every numeric id in the pattern's blocks (objects, copies, pieces, groups, paths)."""
    out = {o.id for o in pattern.objects()}
    for block in pattern.blocks:
        for section in block.sections:
            out.update(_ids(section))
    return out


def next_id(pattern: Pattern) -> int:
    return max(used_ids(pattern), default=0) + 1


def node_type(ev: Evaluation, object_id: int) -> str:
    """The piece node type for a point or curve the evaluation has."""
    if object_id in ev.points:
        return "NodePoint"
    curve = ev.curves.get(object_id)
    if curve is None:
        raise EditError("unknown_object", f"there is no point or curve {object_id}")
    geom = curve.geom
    if isinstance(geom, Arc):
        return "NodeArc"
    if isinstance(geom, ElArc):
        return "NodeElArc"
    if isinstance(geom, BezierPath | SplinePath):
        return "NodeSplinePath"
    return "NodeSpline"


_MODELING = {
    "NodePoint": ("point", "modeling"),
    "NodeArc": ("arc", "modeling"),
    "NodeElArc": ("elArc", "modeling"),
    "NodeSpline": ("spline", "modelingSpline"),
    "NodeSplinePath": ("spline", "modelingPath"),
}


def _modeling_attrs(kind: str, source: int, new_id: int) -> tuple[str, tuple[tuple[str, str], ...]]:
    """(tag, attributes) of the modeling copy of a draft object."""
    tag, type_ = _MODELING[kind]
    base = (("id", str(new_id)), ("idObject", str(source)), ("inUse", "true"))
    if kind == "NodePoint":
        return tag, (*base, ("mx", "0"), ("my", "0"), ("type", type_))
    return tag, (*base, ("type", type_))


def _section_index(block: DraftBlock, tag: str) -> int:
    for i, s in enumerate(block.sections):
        if s.tag == tag:
            return i
    return -1


def _with_sections(block: DraftBlock) -> DraftBlock:
    """The block with `modeling` and `pieces` sections present (in front of `groups`)."""
    sections = list(block.sections)
    for tag in ("modeling", "pieces"):
        if any(s.tag == tag for s in sections):
            continue
        at = next((i for i, s in enumerate(sections) if s.tag == "groups"), len(sections))
        sections.insert(at, RawNode(tag))
    return replace(block, sections=tuple(sections))


def _replace_block(pattern: Pattern, index: int, block: DraftBlock) -> Pattern:
    blocks = list(pattern.blocks)
    blocks[index] = block
    return replace(pattern, blocks=tuple(blocks))


def _block_of_object(pattern: Pattern, object_id: int, producer: Mapping[int, int]) -> int:
    """The block that defines a point or curve: the one holding the object that made it (an
    operation or a dart tool makes objects of its own)."""
    maker = producer.get(object_id, object_id)
    for i, b in enumerate(pattern.blocks):
        if any(o.id == maker for o in b.objects):
            return i
    return -1


def piece_nodes(piece: RawNode) -> list[RawNode]:
    for child in piece.children:
        if child.tag == "nodes":
            return [n for n in child.children if n.tag == "node"]
    return []


def pieces_of(pattern: Pattern) -> list[tuple[int, RawNode, RawNode]]:
    """(block index, piece, its block's modeling section) for every piece."""
    out: list[tuple[int, RawNode, RawNode]] = []
    for bi, block in enumerate(pattern.blocks):
        modeling = next((s for s in block.sections if s.tag == "modeling"), RawNode("modeling"))
        for section in block.sections:
            if section.tag == "pieces":
                out.extend((bi, p, modeling) for p in section.children if p.tag == "piece")
    return out


def pieces_using(pattern: Pattern, object_id: int) -> list[int]:
    """Ids of the pieces that use a draft object (through a modeling copy of it)."""
    users: list[int] = []
    for _, piece, modeling in pieces_of(pattern):
        copies = {
            _int(m.get("id")) for m in modeling.children if _int(m.get("idObject")) == object_id
        }
        if any(_int(n.get("idObject")) in copies for n in piece_nodes(piece)):
            pid = _int(piece.get("id"))
            if pid is not None:
                users.append(pid)
    return users


def _int(raw: str | None) -> int | None:
    return int(raw) if raw is not None and raw.isdigit() else None


def add_piece(
    pattern: Pattern,
    ev: Evaluation,
    producer: Mapping[int, int],
    name: str,
    nodes: Iterable[NodeSpec],
    *,
    piece_id: int | None = None,
) -> tuple[Pattern, int]:
    """A new piece in the block that holds its first node. Returns the pattern and the piece id."""
    specs = list(nodes)
    if not name.strip():
        raise EditError("empty_name", "a piece needs a name")
    if len(specs) < 3:
        raise EditError("too_few_nodes", "a piece outline needs at least three nodes")
    kinds = {spec.object_id: node_type(ev, spec.object_id) for spec in specs}
    block_index = _block_of_object(pattern, specs[0].object_id, producer)
    if block_index < 0:
        raise EditError("unknown_object", f"there is no object {specs[0].object_id}")
    for spec in specs:
        if _block_of_object(pattern, spec.object_id, producer) != block_index:
            raise EditError("mixed_blocks", "a piece's nodes must all come from one draft block")
    block = _with_sections(pattern.blocks[block_index])
    taken = used_ids(pattern)
    counter = max(taken, default=0)

    def fresh() -> int:
        nonlocal counter
        counter += 1
        return counter

    mi = _section_index(block, "modeling")
    modeling = block.sections[mi]
    copies: dict[int, int] = {}
    for m in modeling.children:
        src, mid = _int(m.get("idObject")), _int(m.get("id"))
        if src is not None and mid is not None and m.get("idTool") is None:
            copies.setdefault(src, mid)
    new_children = list(modeling.children)
    node_nodes: list[RawNode] = []
    for spec in specs:
        kind = kinds[spec.object_id]
        if spec.object_id not in copies:
            mid = fresh()
            tag, attrs = _modeling_attrs(kind, spec.object_id, mid)
            new_children.append(RawNode(tag, attrs))
            copies[spec.object_id] = mid
        attrs_n: tuple[tuple[str, str], ...] = (("idObject", str(copies[spec.object_id])),)
        if kind != "NodePoint":
            attrs_n = (*attrs_n, ("reverse", "1" if spec.reverse else "0"))
        node_nodes.append(RawNode("node", (*attrs_n, ("type", kind))))
    pid = piece_id if piece_id is not None else fresh()
    if pid in taken or pid in copies.values():
        raise EditError("duplicate_id", f"id {pid} is already in use")
    piece = RawNode(
        "piece",
        (("id", str(pid)), ("name", name), ("version", "2")),
        children=(RawNode("nodes", children=tuple(node_nodes)),),
    )
    sections = list(block.sections)
    sections[mi] = replace(modeling, children=tuple(new_children))
    pi = _section_index(block, "pieces")
    sections[pi] = replace(sections[pi], children=(*sections[pi].children, piece))
    return _replace_block(pattern, block_index, replace(block, sections=tuple(sections))), pid


def _find_piece(pattern: Pattern, piece_id: int) -> tuple[int, int, int]:
    """(block index, pieces-section index, piece index)."""
    for bi, block in enumerate(pattern.blocks):
        for si, section in enumerate(block.sections):
            if section.tag != "pieces":
                continue
            for pi, p in enumerate(section.children):
                if p.tag == "piece" and _int(p.get("id")) == piece_id:
                    return bi, si, pi
    raise EditError("unknown_piece", f"there is no piece {piece_id}")


def delete_piece(pattern: Pattern, piece_id: int) -> Pattern:
    """Remove a piece and the modeling copies nothing else uses."""
    bi, si, pi = _find_piece(pattern, piece_id)
    block = pattern.blocks[bi]
    pieces = block.sections[si]
    gone = pieces.children[pi]
    remaining = (*pieces.children[:pi], *pieces.children[pi + 1 :])
    sections = list(block.sections)
    sections[si] = replace(pieces, children=remaining)
    still_used = {
        _int(n.get("idObject")) for p in remaining if p.tag == "piece" for n in piece_nodes(p)
    }
    # copies made by a union tool, anchors or internal paths of other pieces are not ours to drop
    keep_always = {
        _int(c.text) for s in block.sections for c in s.children if c.tag in ("record", "child")
    }
    for mi, section in enumerate(sections):
        if section.tag != "modeling":
            continue
        kept = tuple(
            m
            for m in section.children
            if not (
                _int(m.get("id")) in {_int(n.get("idObject")) for n in piece_nodes(gone)}
                and _int(m.get("id")) not in still_used
                and _int(m.get("id")) not in keep_always
                and m.get("idTool") is None
            )
        )
        sections[mi] = replace(section, children=kept)
    return _replace_block(pattern, bi, replace(block, sections=tuple(sections)))


def set_piece(
    pattern: Pattern,
    ev: Evaluation,
    producer: Mapping[int, int],
    piece_id: int,
    *,
    name: str | None = None,
    nodes: Iterable[NodeSpec] | None = None,
) -> Pattern:
    """Rename a piece and/or give it a new outline (its other attributes stay)."""
    bi, si, pi = _find_piece(pattern, piece_id)
    if nodes is None:
        if name is None or not name.strip():
            raise EditError("empty_name", "a piece needs a name")
        block = pattern.blocks[bi]
        pieces = block.sections[si]
        old = pieces.children[pi]
        attrs = tuple((k, name if k == "name" else v) for k, v in old.attrs)
        sections = list(block.sections)
        children = list(pieces.children)
        children[pi] = replace(old, attrs=attrs)
        sections[si] = replace(pieces, children=tuple(children))
        return _replace_block(pattern, bi, replace(block, sections=tuple(sections)))
    # a new outline: build it as a new piece with the same id, then carry the old attributes over
    old = pattern.blocks[bi].sections[si].children[pi]
    without = delete_piece(pattern, piece_id)
    rebuilt, _ = add_piece(
        without,
        ev,
        producer,
        name if name is not None else (old.get("name") or ""),
        nodes,
        piece_id=piece_id,
    )
    bj, sj, pj = _find_piece(rebuilt, piece_id)
    block = rebuilt.blocks[bj]
    pieces = block.sections[sj]
    new_piece = pieces.children[pj]
    merged = replace(
        old,
        attrs=tuple((k, new_piece.get("name") if k == "name" else v) for k, v in old.attrs),
        children=tuple(new_piece.children[0] if c.tag == "nodes" else c for c in old.children)
        if any(c.tag == "nodes" for c in old.children)
        else (*old.children, new_piece.children[0]),
    )
    children = list(pieces.children)
    children[pj] = merged
    sections = list(block.sections)
    sections[sj] = replace(pieces, children=tuple(children))
    return _replace_block(rebuilt, bj, replace(block, sections=tuple(sections)))


# -- draft blocks ---------------------------------------------------------------------------------
def add_block(pattern: Pattern, name: str) -> Pattern:
    if not name.strip():
        raise EditError("empty_name", "a draft block needs a name")
    if any(b.name == name for b in pattern.blocks):
        raise EditError("duplicate_name", f"there is already a draft block named {name!r}")
    return replace(pattern, blocks=(*pattern.blocks, DraftBlock(name, ())))


def rename_block(pattern: Pattern, old: str, new: str) -> Pattern:
    if not new.strip():
        raise EditError("empty_name", "a draft block needs a name")
    if all(b.name != old for b in pattern.blocks):
        raise EditError("unknown_block", f"there is no draft block named {old!r}")
    if new != old and any(b.name == new for b in pattern.blocks):
        raise EditError("duplicate_name", f"there is already a draft block named {new!r}")
    return replace(
        pattern, blocks=tuple(replace(b, name=new) if b.name == old else b for b in pattern.blocks)
    )


def delete_block(pattern: Pattern, name: str) -> Pattern:
    """Delete a block that holds no objects and no pieces."""
    for b in pattern.blocks:
        if b.name != name:
            continue
        if b.objects:
            raise EditError(
                "block_not_empty", f"draft block {name!r} still has {len(b.objects)} objects"
            )
        if any(s.tag == "pieces" and s.children for s in b.sections):
            raise EditError("block_not_empty", f"draft block {name!r} still has pieces")
        index = pattern.blocks.index(b)
        layout = tuple(
            (kind, i - 1 if kind == "block" and i > index else i)
            for kind, i in pattern.layout
            if not (kind == "block" and i == index)
        )
        blocks = tuple(x for x in pattern.blocks if x is not b)
        return replace(pattern, blocks=blocks, layout=layout)
    raise EditError("unknown_block", f"there is no draft block named {name!r}")
