"""The real basic pattern set through the engine (Phase 1 checkpoint, in progress)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from yoko_engine.evaluator import PENDING_KINDS, evaluate
from yoko_engine.model import MeasurementSet, Pattern
from yoko_io.seamly import SeamlyFileError, read_measurements, read_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BASE = FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d"
SMMS = FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms"


@pytest.fixture(scope="module")
def pattern() -> Pattern:
    return read_pattern(BASE)


@pytest.fixture(scope="module")
def table() -> MeasurementSet:
    return read_measurements(SMMS)


def test_reads_the_basic_set(pattern: Pattern) -> None:
    assert (pattern.unit, pattern.version) == ("cm", "0.6.8")
    assert pattern.measurements_file == "Aldrich-Womens-MultiSize-06-14.smms"
    assert len(pattern.blocks) == 1
    assert len(pattern.objects()) == 425
    assert len(pattern.variables) == 17
    kinds = Counter(o.kind for o in pattern.objects())
    assert kinds["alongLine"] == 127
    assert kinds["endLine"] == 81
    assert kinds["single"] == 1
    # every attribute of every object survives (the Seamly2D round trip depends on it)
    origin = next(o for o in pattern.objects() if o.kind == "single")
    assert origin.get("name") == "A"
    assert origin.get("x") == "0.79375"
    assert origin.get("lineType") is None  # points carry their display attributes only if present


def test_reads_the_measurement_table(table: MeasurementSet) -> None:
    assert (table.unit, table.base_size, table.base_height) == ("cm", 34.0, 164.0)
    assert len(table.measurements) == 28
    base = table.values()
    assert base["bust_circ"] == 76.0
    assert base["size"] == 6.0
    assert base["height"] == 166.0
    size36 = table.values(size=36.0)
    assert size36["bust_circ"] == 80.0  # +4 per step
    assert size36["size"] == 8.0  # UK 8
    assert size36["height"] == 166.0  # height_increase is 0, so #CM stays 1 (docs/FILE_HEALTH.md)
    taller = table.values(height=170.0)
    assert taller["height"] == 166.0


def test_variables_evaluate_at_base_size(pattern: Pattern, table: MeasurementSet) -> None:
    ev = evaluate(pattern, table.values())
    assert ev.symbols["#CM"] == 1.0
    assert ev.symbols["#CrotchCurveBack"] == 4.0
    assert ev.symbols["#CrotchCurveFront"] == 2.75
    assert not [i for i in ev.issues if i.object_id is None]


def test_objects_before_the_first_unimplemented_kind_evaluate_cleanly(
    pattern: Pattern, table: MeasurementSet
) -> None:
    ev = evaluate(pattern, table.values())
    first_pending = next(o.id for o in pattern.objects() if o.kind in PENDING_KINDS)
    early = [i for i in ev.issues if i.object_id is not None and i.object_id < first_pending]
    assert early == []
    assert len(ev.points) > 100


def test_evaluation_is_fast_and_deterministic(pattern: Pattern, table: MeasurementSet) -> None:
    a = evaluate(pattern, table.values())
    b = evaluate(pattern, table.values())
    assert {k: v.p for k, v in a.points.items()} == {k: v.p for k, v in b.points.items()}
    assert a.symbols == b.symbols


def test_other_sizes_change_the_geometry(pattern: Pattern, table: MeasurementSet) -> None:
    base = evaluate(pattern, table.values())
    bigger = evaluate(pattern, table.values(size=42.0))
    assert base.point_mm("A4") != bigger.point_mm("A4")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("<nope/>", "expected a <pattern>"),
        (
            "<pattern><version>0.7.5</version><unit>cm</unit></pattern>",
            "0.7.5 is not supported yet",
        ),
        ("<pattern><version>0.6.8</version><unit>furlong</unit></pattern>", "unknown pattern unit"),
        ("not xml at all", "not valid XML"),
    ],
)
def test_bad_pattern_files_fail_with_a_clear_message(text: str, message: str) -> None:
    with pytest.raises(SeamlyFileError, match=message):
        read_pattern(text)


def test_individual_measurement_files_are_not_supported_yet() -> None:
    with pytest.raises(SeamlyFileError, match="not supported yet"):
        read_measurements("<vit><unit>cm</unit></vit>")


def test_xml_bombs_are_refused() -> None:
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE b [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
        "<pattern>&b;</pattern>"
    )
    with pytest.raises(SeamlyFileError, match="not allowed"):
        read_pattern(bomb)
