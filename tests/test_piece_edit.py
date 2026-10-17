"""Adding, changing and deleting pieces and draft blocks through the session."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from yoko_engine.evaluator import evaluate
from yoko_engine.pieces import evaluate_pieces
from yoko_engine.pieces_edit import NodeSpec
from yoko_engine.session import (
    AddBlock,
    AddPiece,
    DeleteBlock,
    DeleteObject,
    DeletePiece,
    PatternSession,
    RenameBlock,
    SetPiece,
)
from yoko_io.seamly import read_measurements, read_pattern, write_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BASE = FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d"
TABLE = FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms"


@pytest.fixture(scope="module")
def table() -> object:
    return read_measurements(TABLE)


def session(table: object) -> PatternSession:
    return PatternSession(read_pattern(BASE), table)  # type: ignore[arg-type]


def square_nodes(s: PatternSession) -> tuple[NodeSpec, ...]:
    """Four points of the basic set that are not in a line: a piece of our own."""
    points = [o.id for o in s.pattern.objects() if o.kind == "single" or o.kind == "endLine"][:12]
    # pick four whose positions make a quadrilateral
    pts = sorted(points, key=lambda i: (s.evaluation.points[i].p.x, s.evaluation.points[i].p.y))
    chosen = [pts[0], pts[len(pts) // 3], pts[2 * len(pts) // 3], pts[-1]]
    return tuple(NodeSpec(i) for i in chosen)


def test_a_piece_we_add_gets_the_outline_seamly2d_computes(table: object) -> None:
    case = FIXTURES / "patterns/cases/added_piece.sm2d"
    oracle = json.loads((FIXTURES / "oracle/cases/added_piece.seamly2d.json").read_text())
    pattern = read_pattern(case)
    ev = evaluate(pattern, read_measurements(TABLE).values())
    pieces = evaluate_pieces(pattern, ev)
    assert len(oracle["pieces"]) == 14  # the seven of the basic set and our seven copies
    for want in oracle["pieces"]:
        mine = pieces[want["id"]]
        assert mine.problems == ()
        assert [(p.x, p.y) for p in mine.outline] == [tuple(xy) for xy in want["outline"]], (
            mine.name
        )
    copies = [p for p in oracle["pieces"] if p["name"].startswith("Copy of ")]
    for copy in copies:
        original = next(p for p in oracle["pieces"] if p["name"] == copy["name"][len("Copy of ") :])
        assert copy["outline"] == original["outline"]


def test_add_piece_then_undo_leaves_the_pattern_as_it_was(table: object) -> None:
    s = session(table)
    before = s.state_hash()
    result = s.apply(AddPiece("Test piece", square_nodes(s)))
    assert result.ok and len(result.created) == 1
    assert s.state_hash() != before
    assert s.pieces()[result.created[0]].name == "Test piece"
    assert s.undo().ok
    assert s.state_hash() == before


def test_a_piece_survives_writing_and_reading_the_file(table: object) -> None:
    s = session(table)
    result = s.apply(AddPiece("Test piece", square_nodes(s)))
    again = read_pattern(write_pattern(s.pattern))
    ev = evaluate(again, read_measurements(TABLE).values())
    pid = result.created[0]
    assert [(p.x, p.y) for p in evaluate_pieces(again, ev)[pid].outline] == [
        (p.x, p.y) for p in s.pieces()[pid].outline
    ]


def test_a_piece_needs_three_corners_and_real_objects(table: object) -> None:
    s = session(table)
    nodes = square_nodes(s)
    few = s.apply(AddPiece("Two", nodes[:2]))
    assert not few.ok and few.error and few.error.code == "too_few_nodes"
    missing = s.apply(AddPiece("Ghost", (*nodes[:2], NodeSpec(999999))))
    assert not missing.ok and missing.error and missing.error.code == "unknown_object"
    unnamed = s.apply(AddPiece("  ", nodes))
    assert not unnamed.ok and unnamed.error and unnamed.error.code == "empty_name"


def test_a_point_that_is_part_of_a_piece_cannot_be_deleted(table: object) -> None:
    s = session(table)
    # the basic set's own pieces use modeling copies of draft points
    piece_point = int(
        next(
            m.get("idObject") or "0"
            for b in s.pattern.blocks
            for sec in b.sections
            if sec.tag == "modeling"
            for m in sec.children
            if m.tag == "point" and m.get("idTool") is None
        )
    )
    result = s.apply(DeleteObject(piece_point))
    assert not result.ok and result.error
    assert result.error.code in ("used_by_piece", "has_dependents")


def test_rename_change_and_delete_a_piece(table: object) -> None:
    s = session(table)
    nodes = square_nodes(s)
    pid = s.apply(AddPiece("First", nodes)).created[0]
    assert s.apply(SetPiece(pid, name="Renamed")).ok
    assert s.pieces()[pid].name == "Renamed"
    assert s.apply(SetPiece(pid, nodes=(*nodes[:3],))).ok
    assert len(s.pieces()[pid].nodes) == 3
    assert not s.apply(SetPiece(pid, nodes=nodes[:2])).ok
    assert s.apply(DeletePiece(pid)).ok
    assert pid not in s.pieces()
    assert not s.apply(DeletePiece(pid)).ok


def test_deleting_a_piece_removes_the_copies_only_it_used(table: object) -> None:
    s = session(table)
    before = s.state_hash()
    pid = s.apply(AddPiece("Short lived", square_nodes(s))).created[0]
    assert s.apply(DeletePiece(pid)).ok
    # the pattern is back to what it was, apart from empty-section bookkeeping
    assert s.state_hash() == before


def test_a_base_pattern_cannot_be_edited(table: object) -> None:
    s = PatternSession(read_pattern(BASE), table, read_only=True)  # type: ignore[arg-type]
    result = s.apply(AddPiece("Nope", square_nodes(s)))
    assert not result.ok and result.error and result.error.code == "read_only"
    assert not s.apply(AddBlock("Nope")).ok


def test_draft_blocks_can_be_added_renamed_and_deleted_when_empty(table: object) -> None:
    s = session(table)
    names = [b.name for b in s.pattern.blocks]
    assert s.apply(AddBlock("Sleeve")).ok
    assert [b.name for b in s.pattern.blocks] == [*names, "Sleeve"]
    assert not s.apply(AddBlock("Sleeve")).ok  # names are unique
    assert s.apply(RenameBlock("Sleeve", "Sleeve 2")).ok
    assert not s.apply(RenameBlock("Nothing", "x")).ok
    assert not s.apply(DeleteBlock(names[0])).ok  # it still has objects
    assert s.apply(DeleteBlock("Sleeve 2")).ok
    assert [b.name for b in s.pattern.blocks] == names


def test_an_added_block_is_written_last_and_a_deleted_one_leaves_no_gap(table: object) -> None:
    s = session(table)
    first = s.pattern.blocks[0].name
    assert s.apply(AddBlock("Two")).ok and s.apply(AddBlock("Three")).ok
    assert s.apply(DeleteBlock("Two")).ok
    again = read_pattern(write_pattern(s.pattern))
    assert [b.name for b in again.blocks] == [first, "Three"]


def _square_session() -> tuple[PatternSession, list[int]]:
    from yoko_engine.model import DraftBlock, Obj, Pattern

    def single(i: int, name: str, x: float, y: float) -> Obj:
        attrs = (("name", name), ("type", "single"), ("x", str(x)), ("y", str(y)))
        return Obj(i, "point", "single", attrs)

    corners = [(1, "A", 0, 0), (2, "B", 10, 0), (3, "C", 10, 10), (4, "D", 0, 10)]
    block = DraftBlock("Square", tuple(single(*c) for c in corners))
    pattern = Pattern("cm", "0.7.5", "", (), (block,))
    return PatternSession(pattern, {}), [1, 2, 3, 4]


def test_a_path_that_crosses_itself_is_reported_as_a_warning() -> None:
    s, ids = _square_session()
    a, b, c, d = ids
    good = s.apply(AddPiece("Square", tuple(NodeSpec(i) for i in (a, b, c, d))))
    assert good.ok
    assert s.piece_issues() == []
    bow = s.apply(AddPiece("Bow tie", tuple(NodeSpec(i) for i in (a, c, b, d))))
    assert bow.ok  # a loop is Seamly2D's to cut out, not a reason to refuse
    issues = s.piece_issues()
    assert [i.code for i in issues] == ["piece_self_intersecting"]
    assert issues[0].severity == "warning" and issues[0].object_id == bow.created[0]


def test_a_piece_made_of_one_repeated_spot_is_refused() -> None:
    s, ids = _square_session()
    a = ids[0]
    result = s.apply(AddPiece("Dot", (NodeSpec(a), NodeSpec(a), NodeSpec(a))))
    assert not result.ok and result.error and result.error.code == "piece_invalid"


def test_a_deleted_object_leaves_its_groups(table: object) -> None:
    s = session(table)
    groups = next(sec for b in s.pattern.blocks for sec in b.sections if sec.tag == "groups")
    in_group = {c.get("object") for g in groups.children for c in g.children if c.tag == "item"}
    free = [
        o.id
        for o in s.pattern.objects()
        if o.tag == "line" and str(o.id) in in_group and not s.dependents(o.id)
    ]
    assert free, "the basic set has lines in groups that nothing depends on"
    target = free[0]
    assert s.apply(DeleteObject(target)).ok
    after = next(sec for b in s.pattern.blocks for sec in b.sections if sec.tag == "groups")
    assert str(target) not in {
        c.get("object") for g in after.children for c in g.children if c.tag == "item"
    }


# ---- uniting pieces ---------------------------------------------------------------------------


def test_seamly2d_computes_the_united_pieces_we_make_exactly() -> None:
    oracle = json.loads((FIXTURES / "oracle/cases/union.seamly2d.json").read_text())
    pattern = read_pattern(FIXTURES / "patterns/cases/union.sm2d")
    ev = evaluate(pattern, read_measurements(TABLE).values())
    pieces = evaluate_pieces(pattern, ev)
    names = sorted(p["name"] for p in oracle["pieces"])
    assert (
        "A - Skirt Back + A - Skirt Front" in names
        and "B - Trousers Front + B - Trousers Back" in names
    )
    assert len(oracle["pieces"]) == 5  # seven pieces, four of them replaced by two united ones
    for want in oracle["pieces"]:
        mine = pieces[want["id"]]
        assert mine.problems == (), mine
        assert [(p.x, p.y) for p in mine.outline] == [tuple(xy) for xy in want["outline"]], want[
            "name"
        ]


def _corners(s: PatternSession, name: str) -> tuple[int, list[int]]:
    from yoko_engine.pieces import NODE_POINT, piece_nodes
    from yoko_engine.pieces_edit import pieces_of

    for _, piece, modeling in pieces_of(s.pattern):
        if piece.get("name") == name:
            src = {m.get("id"): int(m.get("idObject") or 0) for m in modeling.children}
            pts = [src[str(n.id)] for n in piece_nodes(piece) if n.type == NODE_POINT]
            return int(piece.get("id") or 0), pts
    raise AssertionError(name)


def test_uniting_replaces_two_pieces_with_one_and_can_be_undone(table: object) -> None:
    from yoko_engine.session import UnionPieces

    s = session(table)
    before = s.state_hash()
    (p1, a), (p2, b) = _corners(s, "A - Skirt Back"), _corners(s, "A - Skirt Front")
    r = s.apply(UnionPieces(p1, a[2], p2, b[5], "Skirt"))
    assert r.ok, r.error
    assert sorted(r.deleted) == sorted([p1, p2]) and len(r.created) == 1
    names = [p.name for p in s.pieces().values()]
    assert "Skirt" in names and "A - Skirt Back" not in names and len(names) == 6
    assert not s.piece_issues() or all(i.severity == "warning" for i in s.piece_issues())
    assert s.undo().ok and s.state_hash() == before


def test_a_union_that_cannot_be_made_is_refused(table: object) -> None:
    from yoko_engine.session import UnionPieces

    s = session(table)
    (p1, a), (p2, b) = _corners(s, "A - Skirt Back"), _corners(s, "A - Skirt Front")
    same = s.apply(UnionPieces(p1, a[0], p1, a[1]))
    assert same.error and same.error.code == "same_piece"
    stranger = s.apply(UnionPieces(p1, b[0], p2, b[1]))  # a point of the other piece
    assert stranger.error and stranger.error.code == "not_a_corner"
    other_block = s.apply(UnionPieces(p1, a[0], 999999, b[1]))
    assert other_block.error and other_block.error.code in ("unknown_piece", "not_a_corner")
    assert s.state_hash() == session(table).state_hash()
