"""How much of Seamly2D's own test patterns does the engine reproduce exactly?

Compares the engine with what the pinned Seamly2D computed for each upgraded pattern in
fixtures/external/seamly2d (points, bit for bit) and lists the kinds the engine does not know yet.

    uv run python scripts/external_report.py            # print the table
    uv run python scripts/external_report.py --write    # also raise the ratchet
                                                        # (tests/external_ratchet.json)

The ratchet only goes up: tests fail when the engine gets a point wrong, or reproduces fewer points
than the ratchet says.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from yoko_engine.evaluator import evaluate
from yoko_io.seamly import read_measurements, read_pattern

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "fixtures/external/seamly2d"
RATCHET = ROOT / "tests/external_ratchet.json"


def compare(rel: Path) -> tuple[int, int, int, Counter[str]]:
    """(exact, wrong, missing, unknown kinds) for one upgraded pattern."""
    pattern = read_pattern(EXT / "upgraded" / rel)
    values: dict[str, float] = {}
    if pattern.measurements_file:
        m = EXT / "original" / rel.parent / pattern.measurements_file
        if m.is_file():
            values = read_measurements(m).values()
    ev = evaluate(pattern, values)
    oracle = json.loads((EXT / "oracle" / f"{rel}.seamly2d.json").read_text())
    exact = wrong = missing = 0
    for o in oracle["points"]:
        mine = ev.points.get(o["id"])
        if mine is None:
            missing += 1
        elif (mine.p.x, mine.p.y) == (o["x_px"], o["y_px"]):
            exact += 1
        else:
            wrong += 1
    kinds: Counter[str] = Counter()
    for i in ev.issues:
        if i.code == "unknown_kind":
            kinds[i.message] += 1
    return exact, wrong, missing, kinds


def main() -> None:
    rows = {}
    all_kinds: Counter[str] = Counter()
    for f in sorted((EXT / "upgraded").rglob("*.sm2d")):
        rel = f.relative_to(EXT / "upgraded")
        exact, wrong, missing, kinds = compare(rel)
        rows[rel.as_posix()] = exact
        all_kinds.update(kinds)
        print(f"{rel.as_posix():66s} exact {exact:4d}  wrong {wrong:3d}  not computed {missing:4d}")
    print("\nnot implemented yet (issues per kind):")
    for msg, n in all_kinds.most_common():
        print(f"  {n:4d}  {msg}")
    if "--write" in sys.argv:
        old = json.loads(RATCHET.read_text()) if RATCHET.exists() else {}
        new = {k: max(v, old.get(k, 0)) for k, v in rows.items()}
        RATCHET.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {RATCHET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
