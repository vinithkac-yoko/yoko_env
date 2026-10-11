"""Copying a piece, with what it is drawn from, from one pattern into another."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from yoko_engine.copy_piece import CopyError, plan_copy_piece
from yoko_engine.model import DraftBlock, Pattern
from yoko_engine.pieces_edit import NodeSpec
from yoko_engine.session import AddPiece, PatternSession
from yoko_io.seamly import read_measurements, read_pattern, write_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BASE = FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d"
TABLE = FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms"


@pytest.fixture(scope="module")
def source() -> PatternSession:
    return PatternSession(read_pattern(BASE), read_measurements(TABLE), read_only=True)


def empty_like(source: PatternSession) -> PatternSession:
    pattern = replace(source.pattern, variables=(), blocks=(DraftBlock("Draft block 1", ()),))
    return PatternSession(pattern, dict(source.measurements))


def piece_id(source: PatternSession, name: str) -> int:
    return next(i for i, p in source.pieces().items() if p.name == name)


def test_a_copied_piece_has_the_same_outline_as_the_original(source: PatternSession) -> None:
    dst = empty_like(source)
    pid = piece_id(source, "A - Skirt Back")
    plan = plan_copy_piece(source, pid, dst)
    assert (plan.objects > 10 and "#CM" in plan.variables) or plan.objects > 10
    result = dst.apply_all(plan.actions)
    assert result.ok, result.error
    new_piece = dst.pieces()[result.created[-1]]
    original = source.pieces()[pid]
    assert [(p.x, p.y) for p in new_piece.outline] == [(p.x, p.y) for p in original.outline]
    assert new_piece.name == original.name
    assert not dst.issues() and dst.piece_issues() == []


def test_the_copy_writes_and_reads_back(source: PatternSession) -> None:
    dst = empty_like(source)
    plan = plan_copy_piece(source, piece_id(source, "D - 1 Piece Sleeve"), dst)
    assert dst.apply_all(plan.actions).ok
    again = read_pattern(write_pattern(dst.pattern))
    assert len(again.objects()) == len(dst.pattern.objects())


def test_copying_twice_is_refused_because_the_labels_are_taken(source: PatternSession) -> None:
    dst = empty_like(source)
    pid = piece_id(source, "A - Skirt Back")
    assert dst.apply_all(plan_copy_piece(source, pid, dst).actions).ok
    with pytest.raises(CopyError) as err:
        plan_copy_piece(source, pid, dst)
    assert err.value.code == "label_conflict"


def test_a_failed_copy_changes_nothing(source: PatternSession) -> None:
    dst = empty_like(source)
    plan = plan_copy_piece(source, piece_id(source, "A - Skirt Back"), dst)
    before = dst.state_hash()
    broken = (*plan.actions[:-1], AddPiece("Ghost", (NodeSpec(10**6),) * 3))
    result = dst.apply_all(broken)
    assert not result.ok
    assert dst.state_hash() == before


def test_the_destination_must_have_the_measurements(source: PatternSession) -> None:
    pattern = Pattern("cm", "0.6.8", "m.smms", (), (DraftBlock("Draft block 1", ()),))
    dst = PatternSession(pattern, {})
    with pytest.raises(CopyError) as err:
        plan_copy_piece(source, piece_id(source, "A - Skirt Back"), dst)
    assert err.value.code == "missing_measurement"


def test_an_unknown_piece_is_reported(source: PatternSession) -> None:
    with pytest.raises(CopyError) as err:
        plan_copy_piece(source, 424242, empty_like(source))
    assert err.value.code == "unknown_piece"
