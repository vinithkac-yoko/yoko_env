"""The pattern library, as the studio sees it. Phase 1: the locked basic set."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from yoko_engine.evaluator import Evaluation
from yoko_engine.model import MeasurementSet, Pattern
from yoko_engine.session import PatternSession
from yoko_io.render import render_svg
from yoko_io.seamly import read_measurements, read_pattern

from yoko_server.buildinfo import fixtures_dir

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
        "curves": len(ev.curves),
        "variables": len(pattern.variables),
        "issues": len(session.issues()),
        "state_hash": session.state_hash(),
        "size": table.base_size,
        "height": table.base_height,
    }
