"""`autoSmooth` and `lengthMode` (format 0.7.4): Hobby handles and the target-length solvers give
Seamly2D's curves exactly (156 splines and cubic Beziers in every combination of the options)."""

from __future__ import annotations

import json
from pathlib import Path

from yoko_engine.evaluator import evaluate
from yoko_io.seamly import read_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ORACLE = json.loads((FIXTURES / "oracle/cases/spline_length_modes.seamly2d.json").read_text())


def test_every_combination_of_the_options_gives_seamly2ds_curve() -> None:
    ev = evaluate(read_pattern(FIXTURES / "patterns/cases/spline_length_modes.sm2d"), {})
    assert not ev.issues
    assert len(ORACLE["curves"]) == 156
    wrong: list[str] = []
    for want in ORACLE["curves"]:
        mine = ev.curves[want["id"]].geom
        got = (mine.length(), mine.start_angle(), mine.end_angle())
        if got != (want["length_px"], want["start_angle"], want["end_angle"]):
            wrong.append(f"{want['id']}: {got} != {want['length_px']}")
    assert wrong == []
