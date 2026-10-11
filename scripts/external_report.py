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


def compare(rel: Path) -> tuple[dict[str, int], Counter[str]]:
    """Counts for one upgraded pattern: points and variables Seamly2D computed that the engine gets
    exactly right, wrong, or does not compute; and the kinds the engine does not know yet."""
    pattern = read_pattern(EXT / "upgraded" / rel)
    values: dict[str, float] = {}
    if pattern.measurements_file:
        m = EXT / "original" / rel.parent / pattern.measurements_file
        if m.is_file():
            values = read_measurements(m).values()
    ev = evaluate(pattern, values)
    oracle = json.loads((EXT / "oracle" / f"{rel}.seamly2d.json").read_text())
    counts = {"points": 0, "wrong_points": 0, "missing_points": 0}
    counts.update({"variables": 0, "wrong_variables": 0})
    for o in oracle["points"]:
        mine = ev.points.get(o["id"])
        if mine is None:
            counts["missing_points"] += 1
        elif (mine.p.x, mine.p.y) == (o["x_px"], o["y_px"]):
            counts["points"] += 1
        else:
            counts["wrong_points"] += 1
    for name, value in oracle["variables"].items():
        if name not in ev.symbols:
            continue
        if ev.symbols[name] == value:
            counts["variables"] += 1
        else:
            counts["wrong_variables"] += 1
    kinds: Counter[str] = Counter()
    for i in ev.issues:
        if i.code == "unknown_kind":
            kinds[i.message] += 1
    return counts, kinds


def main() -> None:
    rows: dict[str, dict[str, int]] = {}
    all_kinds: Counter[str] = Counter()
    for f in sorted((EXT / "upgraded").rglob("*.sm2d")):
        rel = f.relative_to(EXT / "upgraded")
        counts, kinds = compare(rel)
        rows[rel.as_posix()] = {"points": counts["points"], "variables": counts["variables"]}
        all_kinds.update(kinds)
        print(
            f"{rel.as_posix():62s} points {counts['points']:4d} (wrong {counts['wrong_points']}, "
            f"not computed {counts['missing_points']:3d})  variables {counts['variables']:5d} "
            f"(wrong {counts['wrong_variables']})"
        )
    print("\nnot implemented yet (issues per kind):")
    for msg, n in all_kinds.most_common():
        print(f"  {n:4d}  {msg}")
    if "--write" in sys.argv:
        old = json.loads(RATCHET.read_text()) if RATCHET.exists() else {}
        new = {k: {m: max(v[m], old.get(k, {}).get(m, 0)) for m in v} for k, v in rows.items()}
        RATCHET.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {RATCHET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
