"""Write fixtures/patterns/cases/union.sm2d: the basic set with unions made by the session's
`UnionPieces` action, for the oracle to compute (scripts/oracle_cases.sh). It checks that Seamly2D
opens what we write and gets the same outline for the united piece.

    uv run python scripts/make_case_union.py
"""

from pathlib import Path

from yoko_engine.pieces import NODE_POINT, piece_nodes
from yoko_engine.pieces_edit import pieces_of
from yoko_engine.session import PatternSession, UnionPieces
from yoko_io.seamly import read_measurements, read_pattern, write_pattern

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures/patterns/cases/union.sm2d"

pattern = read_pattern(ROOT / "fixtures/patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d")
table = read_measurements(ROOT / "fixtures/measurements/Aldrich-Womens-MultiSize-06-14.smms")
session = PatternSession(pattern, table)


def corners(name: str) -> list[int]:
    """Draft object ids of the point nodes of a piece, in outline order."""
    for _, piece, modeling in pieces_of(session.pattern):
        if piece.get("name") == name:
            source = {m.get("id"): int(m.get("idObject") or 0) for m in modeling.children}
            return [source[str(n.id)] for n in piece_nodes(piece) if n.type == NODE_POINT]
    raise SystemExit(f"no piece {name}")


def piece_id(name: str) -> int:
    return next(
        int(p.get("id") or 0) for _, p, _ in pieces_of(session.pattern) if p.get("name") == name
    )


# skirt front and back along their first edges, then trousers front and back along other ones
for first, i, second, j in (
    ("A - Skirt Back", 2, "A - Skirt Front", 5),
    ("B - Trousers Front", 1, "B - Trousers Back", 4),
):
    a, b = corners(first), corners(second)
    result = session.apply(
        UnionPieces(piece_id(first), a[i], piece_id(second), b[j], f"{first} + {second}")
    )
    assert result.ok, result.error
OUT.write_bytes(write_pattern(session.pattern))
print(f"wrote {OUT}")
