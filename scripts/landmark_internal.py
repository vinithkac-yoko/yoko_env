"""Rows for the things that are not on a piece's outline: dart apexes, the bust point, guide lines
(waist, hip, bust, knee), the centre-front and centre-back lines.

    from landmark_internal import internal_rows

Proposals come from docs/landmarks/proposed_internal.yaml. Each is checked against the basic set as
it is evaluated: the labels exist, a level line joins two points at the same height, a vertical line
two points with the same x, an apex is the end of dash-dot lines (which is how Seamly2D draws the
legs of a dart). A proposal that does not hold stops the build.
"""

from __future__ import annotations

import collections
import contextlib
from dataclasses import dataclass
from pathlib import Path

import yaml
from landmark_rows import BASE, TABLE, _how
from yoko_engine.evaluator import Evaluator
from yoko_engine.formula import parse
from yoko_engine.units import px_to_mm
from yoko_io.seamly import read_measurements, read_pattern

PROPOSED = Path(__file__).resolve().parents[1] / "docs/landmarks/proposed_internal.yaml"


@dataclass(frozen=True)
class InternalRow:
    number: str  # i1, i2 ...
    kind: str  # point | line
    label: str  # a point's label, or "A1 to A2"
    how: str
    measurements: str
    x_mm: float
    y_mm: float
    name: str
    confidence: str
    reason: str
    group: str
    points_px: tuple[tuple[float, float], ...]  # one point, or the two ends of a line


def internal_rows() -> dict[str, list[InternalRow]]:
    pattern = read_pattern(BASE)
    table = read_measurements(TABLE)
    evaluator = Evaluator()
    ev = evaluator.run(pattern, table.values())
    by_label = {g.label: g for g in ev.points.values() if g.label}
    objs = {o.id: o for o in pattern.objects()}
    measurements = set(table.values())
    dash: dict[int, int] = collections.Counter()
    for o in pattern.objects():
        if o.tag == "line" and o.get("lineType") == "dashDotLine":
            dash[int(o.get("firstPoint") or 0)] += 1
            dash[int(o.get("secondPoint") or 0)] += 1

    def names_used(label: str) -> set[str]:
        found: set[str] = set()
        o = objs.get(by_label[label].id)
        if o is not None:
            for _k, v in o.attrs:
                with contextlib.suppress(Exception):
                    found |= set(parse(v).names) & measurements
        return found

    def need(label: str, name: str) -> object:
        if label not in by_label:
            raise SystemExit(f"{name}: there is no point {label} in the basic set")
        return by_label[label]

    out: dict[str, list[InternalRow]] = {}
    proposals = yaml.safe_load(PROPOSED.read_text())["pieces"]
    for piece, entries in proposals.items():
        rows: list[InternalRow] = []
        for n, e in enumerate(entries, start=1):
            name = e["name"]
            if e["kind"] == "point":
                g = by_label[e["label"]] if e["label"] in by_label else need(e["label"], name)
                dart_part = name.endswith(
                    ("_apex", "_apex_upper", "_apex_lower", "_leg_a", "_leg_b")
                )
                if dart_part and dash[g.id] < 1:  # type: ignore[union-attr]
                    raise SystemExit(f"{name}: no dash-dot line meets {e['label']}")
                o = objs.get(g.id)  # type: ignore[union-attr]
                rows.append(
                    InternalRow(
                        f"i{n}",
                        "point",
                        e["label"],
                        (o.kind + ("; " + _how(o) if _how(o) else "")) if o else "",
                        ", ".join(sorted(names_used(e["label"]))),
                        round(px_to_mm(g.p.x), 1),  # type: ignore[union-attr]
                        round(px_to_mm(g.p.y), 1),  # type: ignore[union-attr]
                        name,
                        e["confidence"],
                        e["reason"],
                        e.get("group", ""),
                        ((g.p.x, g.p.y),),  # type: ignore[union-attr]
                    )
                )
                continue
            a, b = need(e["from"], name), need(e["to"], name)
            ay, by = px_to_mm(a.p.y), px_to_mm(b.p.y)  # type: ignore[attr-defined]
            ax, bx = px_to_mm(a.p.x), px_to_mm(b.p.x)  # type: ignore[attr-defined]
            vertical = name.endswith(("CB_line", "CF_line"))
            if vertical and abs(ax - bx) > 0.01:
                raise SystemExit(f"{name}: {e['from']} and {e['to']} are not on one vertical")
            if not vertical and abs(ay - by) > 0.01:
                raise SystemExit(f"{name}: {e['from']} and {e['to']} are not at one height")
            used = names_used(e["from"]) | names_used(e["to"])
            rows.append(
                InternalRow(
                    f"i{n}",
                    "line",
                    f"{e['from']} to {e['to']}",
                    f"straight line from {e['from']} to {e['to']}",
                    ", ".join(sorted(used)),
                    round((ax + bx) / 2, 1),
                    round((ay + by) / 2, 1),
                    name,
                    e["confidence"],
                    e["reason"],
                    e.get("group", ""),
                    ((a.p.x, a.p.y), (b.p.x, b.p.y)),  # type: ignore[attr-defined]
                )
            )
        out[piece] = rows
    return out


def not_drawn() -> list[str]:
    return list(yaml.safe_load(PROPOSED.read_text()).get("not_drawn", []))


if __name__ == "__main__":
    for piece, rows in internal_rows().items():
        print(f"== {piece} ({len(rows)})")
        for r in rows:
            print(
                f"{r.number:4s} {r.kind:5s} {r.label:14s} {r.name:44s} ({r.x_mm:7.1f},{r.y_mm:7.1f})"
            )
