"""The pattern library, as the studio sees it. Phase 1: the locked basic set."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from yoko_engine.evaluator import Evaluation
from yoko_engine.library import PatternMeta, ancestors, descendants, family_tree, search
from yoko_engine.model import MeasurementSet, Pattern
from yoko_engine.session import PatternSession
from yoko_io.library import DirectoryLibrary
from yoko_io.render import render_svg
from yoko_io.seamly import read_measurements, read_pattern

from yoko_server.buildinfo import fixtures_dir, repo_root

BASE_PATTERN = "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d"
BASE_MEASUREMENTS = "measurements/Aldrich-Womens-MultiSize-06-14.smms"


@lru_cache(maxsize=1)
def base_session() -> tuple[Pattern, MeasurementSet, PatternSession]:
    """The basic set, locked (read-only) and evaluated at the measurement file's base size."""
    root = fixtures_dir()
    pattern = read_pattern(root / BASE_PATTERN)
    table = read_measurements(root / BASE_MEASUREMENTS)
    return pattern, table, PatternSession(pattern, table, read_only=True)


def base_evaluation() -> Evaluation:
    return base_session()[2].evaluation


@lru_cache(maxsize=1)
def base_svg() -> str:
    pattern, _, session = base_session()
    return render_svg(pattern, session.evaluation)


def base_summary() -> dict[str, Any]:
    pattern, table, session = base_session()
    ev = session.evaluation
    return {
        "name": "Aldrich 6th Ed Basic Pattern",
        "locked": session.read_only,
        "format": pattern.version,
        "unit": pattern.unit,
        "objects": len(pattern.objects()),
        "points": len(ev.points),
        "curves": sum(1 for curve in ev.curves.values() if curve.drawn),
        "variables": len(pattern.variables),
        "issues": len(session.issues()),
        "state_hash": session.state_hash(),
        "size": table.base_size,
        "height": table.base_height,
    }


def library() -> DirectoryLibrary:
    """The pattern library on disk (`library/`: the locked base area and the styles area)."""
    return DirectoryLibrary(repo_root() / "library", fixtures_dir())


def _meta_dict(meta: PatternMeta) -> dict[str, Any]:
    return {
        "id": meta.id,
        "name": meta.name,
        "area": meta.area,
        "locked": meta.locked,
        "parent": meta.parent,
        "description": meta.description,
        "garment_type": meta.garment_type,
        "tags": list(meta.tags),
    }


def library_tree() -> dict[str, Any]:
    return {"roots": [node.to_dict() for node in family_tree(library().metas())]}


def library_search(
    text: str = "",
    tags: tuple[str, ...] = (),
    garment_type: str | None = None,
    area: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    found = search(
        library().metas().values(),
        text,
        tags=tags,
        garment_type=garment_type,
        area=area,
        limit=limit,
    )
    return {"results": [_meta_dict(m) for m in found]}


def library_pattern(pattern_id: str) -> dict[str, Any]:
    lib = library()
    metas = lib.metas()
    session = lib.session(pattern_id)
    ev = session.evaluation
    return {
        **_meta_dict(metas[pattern_id]),
        "ancestors": [m.id for m in ancestors(metas, pattern_id)],
        "descendants": [m.id for m in descendants(metas, pattern_id)],
        "objects": len(session.pattern.objects()),
        "points": len(ev.points),
        "curves": sum(1 for curve in ev.curves.values() if curve.drawn),
        "pieces": [p.name for _, p in sorted(session.pieces().items())],
        "issues": len(session.issues()),
        "state_hash": session.state_hash(),
    }
