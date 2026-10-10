"""The engine against real Seamly2D on the basic set, exactly.

`fixtures/oracle/base_set.seamly2d.json` is what Seamly2D v2026.10.5.154 computed for the basic set
(see docs/adr/0002 and docker/oracle/). Every point and variable the engine computes must equal
Seamly2D's, bit for bit. `MIN_POINTS` and `MIN_VARIABLES` only ever go up: they are the ratchet for
how much of the pattern language the engine covers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from yoko_engine.evaluator import Evaluation, evaluate
from yoko_io.seamly import read_measurements, read_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
# The CI oracle job points this at a dump it just made with a freshly built Seamly2D.
ORACLE_FILE = Path(
    os.environ.get("YOKO_ORACLE_BASE_SET", FIXTURES / "oracle/base_set.seamly2d.json")
)
ORACLE = json.loads(ORACLE_FILE.read_text())

# 302 = all 447 points Seamly2D holds minus the 145 piece nodes in the <modeling> section
# (Phase 3). 1573 = every variable.
MIN_POINTS = 302
MIN_VARIABLES = 1573


@pytest.fixture(scope="module")
def result() -> Evaluation:
    pattern = read_pattern(FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d")
    table = read_measurements(FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms")
    return evaluate(pattern, table.values())


def test_points_equal_seamly2d_exactly(result: Evaluation) -> None:
    compared = 0
    wrong = []
    for o in ORACLE["points"]:
        mine = result.points.get(o["id"])
        if mine is None:
            continue
        compared += 1
        if (mine.p.x, mine.p.y) != (o["x_px"], o["y_px"]):
            wrong.append((o["id"], o["name"], mine.p.x - o["x_px"], mine.p.y - o["y_px"]))
    assert wrong == []
    assert compared >= MIN_POINTS


def test_variables_equal_seamly2d_exactly(result: Evaluation) -> None:
    compared = 0
    wrong = []
    for name, value in ORACLE["variables"].items():
        if name not in result.symbols:
            continue
        compared += 1
        if result.symbols[name] != value:
            wrong.append((name, result.symbols[name], value))
    assert wrong == []
    assert compared >= MIN_VARIABLES


def test_point_names_match(result: Evaluation) -> None:
    for o in ORACLE["points"]:
        mine = result.points.get(o["id"])
        if mine is not None:
            assert mine.label == o["name"]
