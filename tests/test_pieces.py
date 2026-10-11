"""Piece outlines: exact against Seamly2D on the basic set, and the path-cleaning helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from yoko_engine.evaluator import evaluate
from yoko_engine.geometry.outline import (
    check_loops,
    correct_equidistant_points,
    crossing,
    remove_duplicates,
    segment_points,
    sub_path,
    sum_trapezoids,
)
from yoko_engine.geometry.qt import Pt
from yoko_engine.pieces import evaluate_pieces, modeling_objects
from yoko_io.seamly import read_measurements, read_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ORACLE = json.loads((FIXTURES / "oracle/base_set.seamly2d.json").read_text())


@pytest.fixture(scope="module")
def base() -> tuple[object, object]:
    pattern = read_pattern(FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d")
    table = read_measurements(FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms")
    return pattern, evaluate(pattern, table.values())


def test_the_seven_basic_pieces_have_seamly2ds_outlines_exactly(
    base: tuple[object, object],
) -> None:
    pattern, ev = base
    pieces = evaluate_pieces(pattern, ev)  # type: ignore[arg-type]
    assert len(pieces) == len(ORACLE["pieces"]) == 7
    for want in ORACLE["pieces"]:
        mine = pieces[want["id"]]
        assert mine.name == want["name"]
        assert mine.problems == ()
        assert [(p.x, p.y) for p in mine.outline] == [tuple(xy) for xy in want["outline"]]


def test_modeling_copies_sit_where_seamly2d_puts_them(base: tuple[object, object]) -> None:
    pattern, ev = base
    modeling = modeling_objects(pattern.blocks[0].sections, ev)  # type: ignore[attr-defined]
    assert len(modeling.points) == 145 and len(modeling.curves) == 48
    by_id = {o["id"]: o for o in ORACLE["points"]}
    for mid, (label, pt) in modeling.points.items():
        assert (pt.x, pt.y) == (by_id[mid]["x_px"], by_id[mid]["y_px"])
        assert label == by_id[mid]["name"]


def test_a_piece_that_points_at_nothing_reports_it_and_has_no_outline(
    base: tuple[object, object],
) -> None:
    _, ev = base
    text = (FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d").read_bytes()
    broken = text.replace(b'<node before="0" idObject="94"', b'<node before="0" idObject="99999"')
    pieces = evaluate_pieces(read_pattern(broken), ev)  # type: ignore[arg-type]
    assert pieces[110].outline == ()
    assert pieces[110].problems == ("node 99999: no such point",)
    assert pieces[135].outline  # the others are unaffected


# ---- the helpers ------------------------------------------------------------------------------


def pts(*xy: tuple[float, float]) -> list[Pt]:
    return [Pt(x, y) for x, y in xy]


def test_remove_duplicates_drops_repeated_points() -> None:
    out = remove_duplicates(pts((0, 0), (0, 0), (5, 0), (5, 5), (5, 5)), False)
    assert out == pts((0, 0), (5, 0), (5, 5))
    closed = remove_duplicates(pts((0, 0), (5, 0), (5, 5), (0, 0)), True)
    assert closed == pts((0, 0), (5, 0), (5, 5))


def test_only_equal_points_and_spikes_are_removed() -> None:
    # a collinear point between two different neighbours is kept (Seamly2D only drops a point that
    # sits on the line between two neighbours that are the same point)
    square = pts((0, 0), (5, 0), (10, 0), (10, 10), (0, 10))
    assert correct_equidistant_points(square) == square
    dup = pts((0, 0), (10, 0), (10, 0), (10, 10), (0, 10))
    assert correct_equidistant_points(dup) == pts((0, 0), (10, 0), (10, 10), (0, 10))
    assert correct_equidistant_points(pts((0, 0), (1, 1), (2, 0))) == pts((0, 0), (1, 1), (2, 0))


def test_sub_path_wraps_around_the_end() -> None:
    p = pts((0, 0), (1, 0), (2, 0), (3, 0), (4, 0))
    assert sub_path(p, 3, 1) == pts((3, 0), (4, 0), (0, 0), (1, 0))
    assert sub_path(p, 1, 3) == pts((1, 0), (2, 0), (3, 0))
    assert sub_path(p, 2, 2) == p


def test_sum_of_trapezoids_is_a_signed_area() -> None:
    ccw = pts((0, 0), (10, 0), (10, 10), (0, 10))
    assert abs(sum_trapezoids(ccw)) == pytest.approx(200.0)  # twice the area
    assert sum_trapezoids(list(reversed(ccw))) == pytest.approx(-sum_trapezoids(ccw))


def test_a_bow_tie_loses_its_loop() -> None:
    bow = pts((0, 0), (10, 10), (10, 0), (0, 10), (0, 0))
    assert check_loops(bow) == pts((0, 0), (5, 5), (0, 10), (0, 0))


def test_a_path_without_loops_is_left_alone() -> None:
    square = pts((0, 0), (10, 0), (10, 10), (0, 10), (0, 0))
    assert check_loops(square) == square
    assert check_loops(pts((0, 0), (1, 1), (2, 0))) == pts((0, 0), (1, 1), (2, 0))


def test_polygons_overlap_when_edges_cross_or_one_contains_the_other() -> None:
    a = pts((0, 0), (10, 0), (10, 10), (0, 10))
    assert crossing(a, pts((5, 5), (15, 5), (15, 15), (5, 15)))
    assert crossing(a, pts((2, 2), (4, 2), (4, 4), (2, 4)))
    assert not crossing(a, pts((20, 20), (30, 20), (30, 30), (20, 30)))
    assert not crossing([], a)


def test_a_curves_segment_between_two_points() -> None:
    line = pts((0, 0), (10, 0), (20, 0), (30, 0))
    assert segment_points(line, Pt(10, 0), Pt(20, 0), False) == pts((10, 0), (20, 0))
    assert segment_points(line, Pt(20, 0), Pt(10, 0), True) == pts((20, 0), (10, 0))
    # begin == end means the whole curve
    assert segment_points(line, Pt(5, 5), Pt(5, 5), False) == line


def test_a_zero_area_polygon_overlaps_nothing() -> None:
    """Checked against Qt's QPainterPath::intersects on the loops of a real pattern."""
    sliver = pts((0, 0), (0, 10), (0, 0))
    assert not crossing(sliver, pts((-5, 2), (5, 2), (5, 8), (-5, 8)))
    assert not crossing(pts((3, 3)), pts((0, 0), (10, 0), (10, 10), (0, 10)))
