"""Elliptical arcs: lengths and angles equal to what the pinned Seamly2D computes (Qt's `arcTo`
and path flattening, reproduced in `yoko_engine.geometry.ellipse`)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from yoko_engine.evaluator import evaluate
from yoko_engine.geometry import Pt
from yoko_engine.geometry.ellipse import ElArc
from yoko_io.seamly import read_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ORACLE = json.loads((FIXTURES / "oracle/cases/elliptical_arcs.seamly2d.json").read_text())


@pytest.fixture(scope="module")
def evaluated() -> object:
    pattern = read_pattern(FIXTURES / "patterns/cases/elliptical_arcs.sm2d")
    return evaluate(pattern, {})


def test_twenty_elliptical_arcs_have_seamly2ds_length_and_angles_exactly(evaluated: object) -> None:
    ev = evaluated  # type: ignore[assignment]
    assert not ev.issues  # type: ignore[attr-defined]
    assert len(ORACLE["curves"]) == 20
    for want in ORACLE["curves"]:
        mine = ev.curves[want["id"]]  # type: ignore[attr-defined]
        assert mine.name == want["name"]
        assert mine.geom.length() == want["length_px"], want["name"]
        assert mine.geom.start_angle() == want["start_angle"], want["name"]
        assert mine.geom.end_angle() == want["end_angle"], want["name"]


def test_the_variables_of_an_elliptical_arc(evaluated: object) -> None:
    ev = evaluated  # type: ignore[assignment]
    assert ev.symbols["Radius1ElArc_A_2"] == 2.0  # type: ignore[attr-defined]
    assert ev.symbols["Radius2ElArc_A_2"] == 3.0  # type: ignore[attr-defined]
    assert ev.symbols["Angle2ElArc_A_3"] == 90  # type: ignore[attr-defined]
    for name, value in ORACLE["variables"].items():
        assert ev.symbols[name] == value, name  # type: ignore[attr-defined]


def test_a_full_ellipse_is_about_its_perimeter() -> None:
    arc = ElArc(Pt(0.0, 0.0), 100.0, 60.0, 0.0, 360.0)
    assert arc.length() == pytest.approx(arc.max_length(), rel=1e-3)
    circle = ElArc(Pt(0.0, 0.0), 50.0, 50.0, 0.0, 180.0)
    assert circle.length() == pytest.approx(math.pi * 50.0, rel=1e-3)
