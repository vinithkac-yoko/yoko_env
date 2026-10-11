"""Write fixtures/patterns/cases/added_piece.sm2d: the basic set with extra pieces made by the
session's `AddPiece` action, for the oracle to compute (scripts/oracle_cases.sh). It checks that
Seamly2D opens what we write and gets the same outline.

    uv run python scripts/make_case_added_piece.py
"""

from pathlib import Path

from yoko_engine.pieces_edit import NodeSpec
from yoko_engine.session import AddPiece, PatternSession
from yoko_io.seamly import read_measurements, read_pattern, write_pattern

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures/patterns/cases/added_piece.sm2d"

pattern = read_pattern(ROOT / "fixtures/patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d")
table = read_measurements(ROOT / "fixtures/measurements/Aldrich-Womens-MultiSize-06-14.smms")
session = PatternSession(pattern, table)

# the draft object behind each modeling copy
source = {
    m.get("id"): m.get("idObject")
    for block in pattern.blocks
    for section in block.sections
    if section.tag == "modeling"
    for m in section.children
}
made = 0
for block in pattern.blocks:
    for section in block.sections:
        if section.tag != "pieces":
            continue
        for piece in section.children:
            nodes = [n for c in piece.children if c.tag == "nodes" for n in c.children]
            specs = tuple(
                NodeSpec(int(source[n.get("idObject") or ""] or 0), n.get("reverse") == "1")
                for n in nodes
            )
            result = session.apply(AddPiece(f"Copy of {piece.get('name')}", specs))
            assert result.ok, result.error
            made += 1
OUT.write_bytes(write_pattern(session.pattern))
print(f"wrote {OUT} with {made} added pieces")
