"""The pattern library's logic: what a pattern is called, where it comes from, how to find it.

Every pattern has a **parent link** (basic set -> style -> variant): deriving a style copies its
parent, then appends manipulations. Each has a description, a garment type and style tags so a
planner can find a similar starting pattern. Search is tag and text matching; `SearchIndex` is the
interface a later embedding search plugs into. Storage (files, a database) lives outside the
engine; see `yoko_io.library`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

AREAS = ("base", "styles")  # base patterns are read-only; the engine refuses writes to them


@dataclass(frozen=True, slots=True)
class PatternMeta:
    """What the library knows about one pattern."""

    id: str  # short, stable, lower-case with dashes
    name: str
    area: str = "styles"  # "base" (locked) or "styles"
    parent: str | None = None  # id of the pattern this one was derived from
    description: str = ""
    garment_type: str = ""  # skirt, trousers, bodice, sleeve, dress, ...
    tags: tuple[str, ...] = ()
    measurements: str = ""  # the measurement file this pattern is bound to

    @property
    def locked(self) -> bool:
        return self.area == "base"


@dataclass(frozen=True, slots=True)
class TreeNode:
    meta: PatternMeta
    children: tuple[TreeNode, ...] = field(default=())

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.meta.id,
            "name": self.meta.name,
            "area": self.meta.area,
            "garment_type": self.meta.garment_type,
            "tags": list(self.meta.tags),
            "children": [c.to_dict() for c in self.children],
        }


class LibraryError(ValueError):
    """A library rule was broken; `code` is stable and machine-readable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def check_meta(metas: Mapping[str, PatternMeta]) -> None:
    """The family tree must be a forest: known parents, no cycles, one root kind (base) per tree."""
    for meta in metas.values():
        if meta.area not in AREAS:
            raise LibraryError("bad_area", f"{meta.id}: area must be one of {AREAS}")
        if meta.parent is not None and meta.parent not in metas:
            raise LibraryError(
                "unknown_parent", f"{meta.id}: parent {meta.parent!r} is not in the library"
            )
        if meta.locked and meta.parent is not None:
            raise LibraryError("base_has_parent", f"{meta.id}: a base pattern has no parent")
        seen = {meta.id}
        node = meta
        while node.parent is not None:
            if node.parent in seen:
                raise LibraryError("cycle", f"{meta.id}: the parent links form a loop")
            seen.add(node.parent)
            node = metas[node.parent]


def family_tree(metas: Mapping[str, PatternMeta]) -> tuple[TreeNode, ...]:
    """The roots of the library, each with its descendants (sorted by name)."""
    check_meta(metas)
    kids: dict[str | None, list[PatternMeta]] = {}
    for meta in metas.values():
        kids.setdefault(meta.parent, []).append(meta)

    def build(meta: PatternMeta) -> TreeNode:
        children = sorted(kids.get(meta.id, []), key=lambda m: (m.name.lower(), m.id))
        return TreeNode(meta, tuple(build(c) for c in children))

    roots = sorted(kids.get(None, []), key=lambda m: (m.name.lower(), m.id))
    return tuple(build(r) for r in roots)


def ancestors(metas: Mapping[str, PatternMeta], pattern_id: str) -> tuple[PatternMeta, ...]:
    """The parent, grandparent, ... up to the root."""
    check_meta(metas)
    out: list[PatternMeta] = []
    node = metas[pattern_id]
    while node.parent is not None:
        node = metas[node.parent]
        out.append(node)
    return tuple(out)


def descendants(metas: Mapping[str, PatternMeta], pattern_id: str) -> tuple[PatternMeta, ...]:
    """Everything derived from a pattern, directly or not."""
    check_meta(metas)
    out: list[PatternMeta] = []
    frontier = [pattern_id]
    while frontier:
        parent = frontier.pop(0)
        for meta in sorted(metas.values(), key=lambda m: m.id):
            if meta.parent == parent:
                out.append(meta)
                frontier.append(meta.id)
    return tuple(out)


class SearchIndex(Protocol):
    """Anything that can rank patterns for a query; the text search below is the first one, an
    embedding index can replace it without changing callers."""

    def search(self, query: str, limit: int) -> Sequence[str]: ...


def _words(text: str) -> list[str]:
    return [w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split() if w]


def search(
    metas: Iterable[PatternMeta],
    text: str = "",
    *,
    tags: Iterable[str] = (),
    garment_type: str | None = None,
    area: str | None = None,
    limit: int = 20,
) -> list[PatternMeta]:
    """Patterns matching *all* the tags and the garment type, ranked by how many words of `text`
    appear in the name (most), tags and description. Without `text`, sorted by name."""
    wanted_tags = {t.lower() for t in tags}
    words = _words(text)
    scored: list[tuple[int, str, PatternMeta]] = []
    for meta in metas:
        if garment_type is not None and meta.garment_type.lower() != garment_type.lower():
            continue
        if area is not None and meta.area != area:
            continue
        if not wanted_tags <= {t.lower() for t in meta.tags}:
            continue
        name_words = set(_words(meta.name))
        tag_words = {w for t in meta.tags for w in _words(t)}
        body_words = set(_words(meta.description)) | set(_words(meta.garment_type))
        score = sum(3 * (w in name_words) + 2 * (w in tag_words) + (w in body_words) for w in words)
        if words and score == 0:
            continue
        scored.append((-score, meta.name.lower(), meta))
    scored.sort(key=lambda s: (s[0], s[1], s[2].id))
    return [m for _, _, m in scored[:limit]]
