"""The rows of the landmark sheet: every node of every piece of the basic set, with the evidence a
pattern maker needs to name it (where it is, how it was drawn, what measurements it uses).

    uv run python scripts/landmark_rows.py            # print them
    from landmark_rows import piece_rows               # used by make_landmark_sheet.py
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path

from yoko_engine.evaluator import Evaluator
from yoko_engine.formula import parse
from yoko_engine.model import Obj
from yoko_engine.pieces import PieceNode, modeling_objects, node_marks, piece_nodes
from yoko_engine.units import px_to_mm
from yoko_io.seamly import read_measurements, read_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BASE = FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d"
TABLE = FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms"


@dataclass(frozen=True)
class Row:
    number: int  # the number drawn on the picture
    kind: str  # "point" or "curve"
    label: str  # the Seamly2D label (A13) or curve name
    tool: str  # how Seamly2D draws it (endLine, alongLine, cubicBezier, ...)
    how: str  # the formulas, short
    measurements: str  # body measurements it uses, directly
    x_mm: float
    y_mm: float
    object_id: int


@dataclass(frozen=True)
class PieceRows:
    piece_id: int
    name: str
    rows: tuple[Row, ...]
    outline_px: tuple[tuple[float, float], ...]
    marks_px: tuple[tuple[int, tuple[float, float]], ...]


_SHOWN = ("angle", "length", "radius", "x", "y", "angle1", "angle2", "length1", "length2")


def _how(o: Obj) -> str:
    parts = [f"{k}={v}" for k, v in o.attrs if k in _SHOWN]
    return "; ".join(parts)


def piece_rows() -> list[PieceRows]:
    pattern = read_pattern(BASE)
    table = read_measurements(TABLE)
    evaluator = Evaluator()
    ev = evaluator.run(pattern, table.values())
    # a point may be made by an object with another id (trueDarts makes two, operations copy)
    producer = {pid: oid for oid, rec in evaluator.records.items() for pid in rec.points}
    block = pattern.blocks[0]
    modeling = modeling_objects(block.sections, ev)
    objects = {o.id: o for o in pattern.objects()}
    source: dict[int, int] = {}
    for sec in block.sections:
        if sec.tag == "modeling":
            for n in sec.children:
                mid, sid = n.get("id"), n.get("idObject")
                if mid and sid:
                    source[int(mid)] = int(sid)
    measurements = set(table.values())
    from yoko_engine.pieces import evaluate_pieces

    geoms = evaluate_pieces(pattern, ev)
    out: list[PieceRows] = []
    for sec in block.sections:
        if sec.tag != "pieces":
            continue
        for piece in sec.children:
            pid = int(piece.get("id", "0") or 0)
            nodes: tuple[PieceNode, ...] = piece_nodes(piece)
            marks = node_marks(nodes, modeling)
            rows: list[Row] = []
            numbered: list[tuple[int, tuple[float, float]]] = []
            for number, (index, pt) in enumerate(marks, start=1):
                node = nodes[index]
                src_id = source.get(node.id, -1)
                o = objects.get(producer.get(src_id, src_id))
                if o is None:
                    continue
                names: set[str] = set()
                for _k, v in o.attrs:
                    with contextlib.suppress(Exception):
                        names |= set(parse(v).names) & measurements
                is_point = node.type == "NodePoint"
                label = ev.points[src_id].label if is_point else ev.curves[src_id].name
                rows.append(
                    Row(
                        number,
                        "point" if is_point else "curve",
                        label,
                        o.kind,
                        _how(o),
                        ", ".join(sorted(names)),
                        round(px_to_mm(pt.x), 1),
                        round(px_to_mm(pt.y), 1),
                        o.id,
                    )
                )
                numbered.append((number, (pt.x, pt.y)))
            outline = tuple((p.x, p.y) for p in geoms[pid].outline)
            out.append(
                PieceRows(pid, piece.get("name", "") or "", tuple(rows), outline, tuple(numbered))
            )
    return out


if __name__ == "__main__":
    for pr in piece_rows():
        print(f"== {pr.name} ({len(pr.rows)} rows)")
        for r in pr.rows:
            print(
                f"{r.number:3d} {r.kind:5s} {r.label:14s} {r.tool:16s} ({r.x_mm:8.1f},{r.y_mm:8.1f}) {r.how[:70]}"
            )
