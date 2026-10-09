"""PatternSession on the real basic set: atomic edits, undo, fork, hash, diff, incremental."""

from __future__ import annotations

import random
import time
from pathlib import Path

import pytest
from yoko_engine.evaluator import evaluate
from yoko_engine.model import MeasurementSet, Obj, Pattern
from yoko_engine.session import (
    ActionMeta,
    AddObject,
    DeleteObject,
    DeleteVariable,
    PatternSession,
    SetAttrs,
    SetVariable,
)
from yoko_io.seamly import read_measurements, read_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def base() -> tuple[Pattern, MeasurementSet]:
    return (
        read_pattern(FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d"),
        read_measurements(FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms"),
    )


@pytest.fixture
def session(base: tuple[Pattern, MeasurementSet]) -> PatternSession:
    return PatternSession(base[0], base[1])


def obj_by_label(s: PatternSession, label: str) -> Obj:
    return next(o for o in s.pattern.objects() if o.label == label)


def test_session_starts_clean_and_hashes_are_stable(
    base: tuple[Pattern, MeasurementSet],
) -> None:
    a = PatternSession(base[0], base[1])
    b = PatternSession(base[0], base[1])
    assert a.issues() == []
    assert a.state_hash() == b.state_hash()
    assert len(a.state_hash()) == 64
    other_size = PatternSession(base[0], base[1], size=36.0)
    assert other_size.state_hash() != a.state_hash()


def test_editing_a_formula_moves_points_and_records_provenance(session: PatternSession) -> None:
    a1 = obj_by_label(session, "A1")
    before = session.state_hash()
    res = session.apply(
        SetAttrs(a1.id, (("length", "6*#CM"),)),
        ActionMeta(step="s1", op="lengthen", author="teacher", episode="ep1", on_plan=True),
    )
    assert res.ok
    assert res.changed == (a1.id,)
    assert res.moved.count > 30  # one early formula moves a good part of the pattern
    assert res.moved.top[0][1] == pytest.approx(10.0, abs=1e-6)  # 1 cm = 10 mm at the top
    assert 50 < res.reevaluated < 425  # early cut-off: far fewer than all 425
    assert session.state_hash() != before
    (entry,) = session.provenance(a1.id)
    assert entry.kind == "edited"
    assert entry.meta.step == "s1"
    assert entry.meta.on_plan is True
    assert [(c.field, c.old, c.new) for c in entry.changes] == [("length", "5*#CM", "6*#CM")]


def test_a_bad_edit_is_rejected_and_changes_nothing(session: PatternSession) -> None:
    a1 = obj_by_label(session, "A1")
    before = session.state_hash()
    res = session.apply(SetAttrs(a1.id, (("length", "ghost+1"),)))
    assert not res.ok
    assert res.error is not None
    assert res.error.code == "formula_undefined_name"
    assert res.error.object_id == a1.id
    assert res.error.field == "length"
    assert res.error.hint
    assert session.state_hash() == before
    assert session.issues() == []
    assert session.undo().ok is False  # nothing was recorded


def test_unknown_object_and_immutable_fields_are_rejected(session: PatternSession) -> None:
    assert session.apply(SetAttrs(999999, (("length", "1"),))).error.code == "unknown_object"  # type: ignore[union-attr]
    a1 = obj_by_label(session, "A1")
    assert session.apply(SetAttrs(a1.id, (("id", "5"),))).error.code == "immutable_field"  # type: ignore[union-attr]
    assert session.apply(SetAttrs(a1.id, (("type", "alongLine"),))).error.code == "immutable_field"  # type: ignore[union-attr]


def test_a_forward_reference_is_rejected(session: PatternSession) -> None:
    objs = session.pattern.objects()
    first_end = next(o for o in objs if o.kind == "endLine")
    last = objs[-1]
    res = session.apply(SetAttrs(first_end.id, (("basePoint", str(last.id)),)))
    assert not res.ok
    assert res.error is not None
    assert res.error.code == "forward_reference"
    assert "before" in (res.error.hint or "")


def test_a_formula_may_not_use_a_later_objects_variables(session: PatternSession) -> None:
    """Line_A_A1 is registered by A1; an earlier object must not be able to use it."""
    a1 = obj_by_label(session, "A1")
    objs = session.pattern.objects()
    earlier = objs[objs.index(a1) - 1]
    assert earlier.kind == "single"
    # A1 itself is the first user: make a new object just before A1 that tries to use Line_A_A1
    res = session.apply(
        AddObject(
            Obj(
                0,
                "point",
                "endLine",
                (
                    ("basePoint", str(earlier.id)),
                    ("length", "Line_A_A1"),
                    ("angle", "0"),
                    ("name", "Z"),
                ),
            ),
            after=None,
        )
    )
    # appended at the end it is allowed (A1 is earlier than the end)
    assert res.ok
    # but inserted right after the origin, before A1, it must fail
    res2 = session.apply(
        AddObject(
            Obj(
                0,
                "point",
                "endLine",
                (
                    ("basePoint", str(earlier.id)),
                    ("length", "Line_A_A1"),
                    ("angle", "0"),
                    ("name", "Y"),
                ),
            ),
            after=earlier.id,
        )
    )
    assert not res2.ok
    assert res2.error is not None
    assert res2.error.code == "formula_undefined_name"


def test_add_object_assigns_ids_and_records_provenance(session: PatternSession) -> None:
    a = obj_by_label(session, "A")
    res = session.apply(
        AddObject(
            Obj(
                0,
                "point",
                "endLine",
                (("basePoint", str(a.id)), ("length", "3"), ("angle", "0"), ("name", "NEW")),
            )
        ),
        ActionMeta(author="human"),
    )
    assert res.ok
    (new_id,) = res.created
    assert new_id == max(o.id for o in session.pattern.objects())
    assert session.evaluation.point_mm("NEW")[0] == pytest.approx(
        session.evaluation.point_mm("A")[0] + 30.0
    )
    (entry,) = session.provenance(new_id)
    assert entry.kind == "created"
    assert entry.meta.author == "human"
    assert "Line_A_NEW" in session.evaluation.symbols


def test_duplicate_labels_and_ids_are_rejected(session: PatternSession) -> None:
    a = obj_by_label(session, "A")
    dup_label = Obj(
        0,
        "point",
        "endLine",
        (("basePoint", str(a.id)), ("length", "1"), ("angle", "0"), ("name", "A1")),
    )
    res = session.apply(AddObject(dup_label))
    assert not res.ok
    assert res.error is not None
    assert res.error.code == "duplicate_label"
    dup_id = Obj(
        a.id,
        "point",
        "endLine",
        (("basePoint", str(a.id)), ("length", "1"), ("angle", "0"), ("name", "Q")),
    )
    assert session.apply(AddObject(dup_id)).error.code == "duplicate_id"  # type: ignore[union-attr]


def test_delete_refuses_objects_that_are_used_and_allows_leaves(session: PatternSession) -> None:
    a = obj_by_label(session, "A")
    res = session.apply(DeleteObject(a.id))
    assert not res.ok
    assert res.error is not None
    assert res.error.code == "has_dependents"
    new = session.apply(
        AddObject(
            Obj(
                0,
                "point",
                "endLine",
                (("basePoint", str(a.id)), ("length", "3"), ("angle", "0"), ("name", "TMP")),
            )
        )
    )
    (tmp,) = new.created
    gone = session.apply(DeleteObject(tmp))
    assert gone.ok
    assert gone.deleted == (tmp,)
    assert tmp not in session.evaluation.points
    assert "Line_A_TMP" not in session.evaluation.symbols
    assert session.provenance(tmp) == ()
    assert session.apply(DeleteObject(tmp)).error.code == "unknown_object"  # type: ignore[union-attr]


def test_deleting_an_object_whose_variables_are_used_is_refused(session: PatternSession) -> None:
    a1 = obj_by_label(session, "A1")
    # A1 registers Line_A_A1, which later formulas use
    res = session.apply(DeleteObject(a1.id))
    assert not res.ok
    assert res.error is not None
    assert res.error.code == "has_dependents"


def test_variables_can_be_added_edited_and_deleted(session: PatternSession) -> None:
    assert session.apply(SetVariable("#s1_hem", "2.5", "step 1: hem")).ok
    assert session.evaluation.symbols["#s1_hem"] == 2.5
    assert session.apply(SetVariable("#s1_hem", "3")).ok
    assert session.evaluation.symbols["#s1_hem"] == 3.0
    flare = session.apply(SetVariable("#SkirtFlair", "6"))
    assert flare.ok
    assert flare.moved.count > 0  # the skirt flare moves skirt points
    assert session.apply(DeleteVariable("#s1_hem")).ok
    assert "#s1_hem" not in session.evaluation.symbols
    in_use = session.apply(DeleteVariable("#CM"))
    assert not in_use.ok
    assert in_use.error is not None
    assert in_use.error.code == "has_dependents"
    assert session.apply(DeleteVariable("#nope")).error.code == "unknown_variable"  # type: ignore[union-attr]


def test_a_bad_variable_formula_is_rejected(session: PatternSession) -> None:
    before = session.state_hash()
    res = session.apply(SetVariable("#CM", "height/"))
    assert not res.ok
    assert session.state_hash() == before


def test_undo_restores_the_exact_state(session: PatternSession) -> None:
    start = session.state_hash()
    a1 = obj_by_label(session, "A1")
    assert session.apply(SetAttrs(a1.id, (("length", "7*#CM"),))).ok
    assert session.apply(SetVariable("#X", "1")).ok
    assert session.state_hash() != start
    assert session.undo().ok
    assert session.undo().ok
    assert session.state_hash() == start
    assert session.evaluation.symbols == evaluate(session.pattern, session._values).symbols
    assert session.undo().ok is False


def _full_evaluation_ms(session: PatternSession) -> float:
    best = float("inf")
    for _ in range(3):
        start = time.perf_counter()
        evaluate(session.pattern, session._values)
        best = min(best, (time.perf_counter() - start) * 1000)
    return best


def test_fork_is_independent_and_cheap(session: PatternSession) -> None:
    child = session.fork()
    a1 = obj_by_label(session, "A1")
    assert child.apply(SetAttrs(a1.id, (("length", "9*#CM"),))).ok
    assert child.state_hash() != session.state_hash()
    assert session.evaluation.symbols["Line_A_A1"] == pytest.approx(5.0)
    assert child.evaluation.symbols["Line_A_A1"] == pytest.approx(9.0)
    full = _full_evaluation_ms(session)
    start = time.perf_counter()
    for _ in range(100):
        session.fork()
    per_fork_ms = (time.perf_counter() - start) * 10
    # Relative, so it holds under coverage and on slow machines; scripts/bench_engine.py reports
    # the absolute figure (the spec asks for under 1 ms on a 500-object pattern).
    assert per_fork_ms < full * 0.1


def test_read_only_sessions_refuse_every_action(
    base: tuple[Pattern, MeasurementSet],
) -> None:
    locked = PatternSession(base[0], base[1], read_only=True)
    res = locked.apply(SetVariable("#x", "1"))
    assert not res.ok
    assert res.error is not None
    assert res.error.code == "read_only"
    assert "fork" in (res.error.hint or "")
    free = locked.fork()
    free.read_only = False
    assert free.apply(SetVariable("#x", "1")).ok


def test_diff_lists_added_edited_removed_and_variables(session: PatternSession) -> None:
    original = session.fork()
    a1 = obj_by_label(session, "A1")
    a = obj_by_label(session, "A")
    session.apply(SetAttrs(a1.id, (("length", "6*#CM"),)))
    added = session.apply(
        AddObject(
            Obj(
                0,
                "point",
                "endLine",
                (("basePoint", str(a.id)), ("length", "3"), ("angle", "0"), ("name", "NEW")),
            )
        )
    )
    session.apply(SetVariable("#NewVar", "1"))
    session.apply(SetVariable("#SkirtFlair", "7"))
    d = session.diff(original)
    assert d.added == added.created
    assert [i for i, _ in d.edited] == [a1.id]
    assert d.variables_added == ("#NewVar",)
    assert d.variables_edited == (("#SkirtFlair", "5", "7"),)
    assert not d.empty
    assert original.diff(original).empty


def test_dependencies_and_dependents(session: PatternSession) -> None:
    a1 = obj_by_label(session, "A1")
    a = obj_by_label(session, "A")
    assert a.id in session.dependencies(a1.id)
    assert a1.id in session.dependents(a.id)


def test_incremental_update_equals_a_full_evaluation(session: PatternSession) -> None:
    """Random formula edits: whatever the session holds always equals a fresh evaluation."""
    rng = random.Random(7)
    editable = [
        o
        for o in session.pattern.objects()
        if o.kind in ("endLine", "alongLine", "normal", "bisector") and o.get("length")
    ]
    accepted = rejected = 0
    for _ in range(40):
        o = rng.choice(editable)
        value = f"{rng.uniform(0.5, 25):.3f}"
        res = session.apply(SetAttrs(o.id, (("length", value),)))
        accepted += res.ok
        rejected += not res.ok
        fresh = evaluate(session.pattern, session._values)
        ev = session.evaluation
        assert {k: v.p for k, v in ev.points.items()} == {k: v.p for k, v in fresh.points.items()}
        assert ev.symbols == fresh.symbols
        assert ev.issues == fresh.issues
        editable = [e for e in session.pattern.objects() if e.id in {x.id for x in editable}]
    assert accepted > 10
    print(f"accepted {accepted}, rejected {rejected}")


def test_a_late_edit_reevaluates_few_objects_and_is_fast(session: PatternSession) -> None:
    objs = session.pattern.objects()
    target = next(o for o in reversed(objs) if o.kind == "alongLine" and o.get("length"))
    full = _full_evaluation_ms(session)
    start = time.perf_counter()
    res = session.apply(SetAttrs(target.id, (("length", "1.5*#CM"),)))
    ms = (time.perf_counter() - start) * 1000
    assert res.ok
    assert res.reevaluated < 20
    assert ms < full * 0.5  # an edit far down the pattern costs a fraction of a full evaluation


def test_sidecar_records_provenance_and_the_parent_hash(session: PatternSession) -> None:
    import json

    session.parent_hash = session.state_hash()
    a1 = obj_by_label(session, "A1")
    session.apply(
        SetAttrs(a1.id, (("length", "6*#CM"),)),
        ActionMeta(step="s2", op="op-7", author="teacher", episode="e9", on_plan=False),
    )
    car = session.sidecar()
    assert json.loads(json.dumps(car)) == car  # plain JSON
    assert car["parent_hash"] != car["state_hash"]
    entry = car["objects"][str(a1.id)][0]  # type: ignore[index]
    assert entry["step"] == "s2"
    assert entry["op"] == "op-7"
    assert entry["on_plan"] is False
    assert entry["changes"] == [{"field": "length", "old": "5*#CM", "new": "6*#CM"}]
    assert session.fork().parent_hash == session.parent_hash
