"""What the tools write is what Seamly2D understands: a pattern built only through tool calls
(scripts/make_case_tool_calls.py) is opened by the pinned Seamly2D, which computes the same points,
curves and variables as the engine."""

from __future__ import annotations

import json
from pathlib import Path

from yoko_engine.evaluator import evaluate
from yoko_io.seamly import read_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_seamly2d_computes_the_pattern_the_tools_built_exactly() -> None:
    oracle = json.loads((FIXTURES / "oracle/cases/tool_calls.seamly2d.json").read_text())
    ev = evaluate(read_pattern(FIXTURES / "patterns/cases/tool_calls.sm2d"), {})
    assert not ev.issues
    wrong: list[str] = []
    for want in oracle["points"]:
        mine = ev.points.get(want["id"])
        if mine is None or (mine.p.x, mine.p.y) != (want["x_px"], want["y_px"]):
            wrong.append(f"point {want['name']}")
    for want in oracle["curves"]:
        curve = ev.curves.get(want["id"])
        if curve is None or curve.geom.length() != want["length_px"]:
            wrong.append(f"curve {want['name']}")
    for name, value in oracle["variables"].items():
        if ev.symbols.get(name) != value:
            wrong.append(f"variable {name}")
    assert wrong == []
    assert len(oracle["points"]) >= 30 and len(oracle["curves"]) >= 10
