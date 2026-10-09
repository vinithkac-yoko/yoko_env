"""Our Qt ports against real Qt, bit for bit.

`fixtures/oracle/qt_lines.jsonl.gz` holds Qt's QLineF results for 4000 random lines, produced by
`tools/oracle/qt_vectors.cpp` (Qt 6.4.2 on Linux/glibc). The QTransform flip and QPainterPath length
vectors come from `qt_flip.cpp` and `qt_polyline_length.cpp`. Every comparison is exact equality:
Seamly2D truncates angles to 5 decimals, which magnifies last-bit differences, so near enough is not
enough. The CI oracle job regenerates the files with Qt 6.11.1.
"""

from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
from typing import Any

import pytest
from yoko_engine.geometry import Line, Pt

VECTORS = Path(__file__).resolve().parents[1] / "fixtures/oracle/qt_lines.jsonl.gz"


def _load() -> list[dict[str, Any]]:
    text = gzip.decompress(VECTORS.read_bytes()).decode()
    fixed = text.replace("-nan", "NaN").replace(":nan", ":NaN").replace("[nan", "[NaN")
    fixed = fixed.replace(",nan", ",NaN")
    return [json.loads(line) for line in fixed.splitlines()]


ROWS = _load()


def same(a: float, b: float) -> bool:
    return a == b or (math.isnan(a) and math.isnan(b))


def same_pt(p: Pt, q: list[float]) -> bool:
    return same(p.x, q[0]) and same(p.y, q[1])


def test_vectors_are_present() -> None:
    assert len(ROWS) == 4000


@pytest.mark.parametrize("op", ["length", "angle", "angle_to", "set_angle", "set_length"])
def test_scalar_and_point_operations_match_qt_exactly(op: str) -> None:
    bad = []
    for r in ROWS:
        line = Line(Pt(*r["p1"]), Pt(*r["p2"]))
        other = Line(Pt(*r["q1"]), Pt(*r["q2"]))
        if op == "length":
            ok = same(line.length(), r["length"])
        elif op == "angle":
            ok = same(line.angle(), r["angle"]) or (line.angle() == 0 and r["angle"] == 0)
        elif op == "angle_to":
            ok = same(line.angle_to(other), r["angle_to"])
        elif op == "set_angle":
            ok = same_pt(line.set_angle(r["angle_in"]).p2, r["set_angle"])
        else:
            ok = same_pt(line.set_length(r["len_in"]).p2, r["set_length"])
        if not ok:
            bad.append(r["i"])
    assert bad == []


def test_unit_vector_normal_vector_and_intersection_match_qt_exactly() -> None:
    from yoko_engine.geometry.qt import IntersectType

    bad = []
    for r in ROWS:
        line = Line(Pt(*r["p1"]), Pt(*r["p2"]))
        other = Line(Pt(*r["q1"]), Pt(*r["q2"]))
        if not line.is_null() and not same_pt(line.unit_vector().p2, r["unit"]):
            bad.append(("unit", r["i"]))
        if not same_pt(line.normal_vector().p2, r["normal"]):
            bad.append(("normal", r["i"]))
        kind, point = line.intersects(other)
        if kind.value != r["isect_type"]:
            bad.append(("type", r["i"]))
        elif (
            kind is not IntersectType.NO_INTERSECTION
            and point is not None
            and not same_pt(point, r["isect"])
        ):
            bad.append(("point", r["i"]))
    assert bad == []


# -- QTransform flip and QPainterPath::length ----------------------------------------
def _load_gz(name: str) -> list[dict[str, Any]]:
    path = VECTORS.parent / name
    return [json.loads(line) for line in gzip.decompress(path.read_bytes()).decode().splitlines()]


def test_flip_across_a_line_matches_qt_exactly() -> None:
    from yoko_engine.geometry.transform import flip_point

    rows = _load_gz("qt_flip.jsonl.gz")
    assert len(rows) == 2000
    bad = []
    for i, r in enumerate(rows):
        axis = Line(Pt(r["a"][0], r["a"][1]), Pt(r["a"][2], r["a"][3]))
        got = flip_point(axis, Pt(*r["p"]))
        if (got.x, got.y) != tuple(r["r"]):
            bad.append(i)
    assert bad == []


def test_polyline_length_matches_qpainterpath_exactly() -> None:
    from yoko_engine.geometry.curves import path_length

    rows = _load_gz("qt_polyline_length.jsonl.gz")
    assert len(rows) == 400
    bad = [i for i, r in enumerate(rows) if path_length([Pt(*p) for p in r["pts"]]) != r["len"]]
    assert bad == []
