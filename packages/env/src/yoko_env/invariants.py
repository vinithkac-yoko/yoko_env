"""What must still hold when the work is declared done, whatever the steps were (Kasi, Phase 4
answers). A step's own check is measured once, when the step completes; these are re-checked at
`done`:

- no formula error at any size (every size of the table, or a person's file and its two nudged
  copies);
- every touched piece is closed (it has an outline with an area) at every size;
- every seam pair matches: the two edges sewn together have the same length (plus the ease the
  pair allows) at every size.

Seam pairs come from the pattern makers (the landmark sheet's Seam pairs tab). Until they are filled
in, there are none, and the result says so instead of passing silently.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from yoko_engine.binding import SizePoint, size_grid
from yoko_engine.model import MeasurementSet
from yoko_engine.session import PatternSession
from yoko_engine.units import px_to_mm
from yoko_tools.runtime import Toolbox, ToolError
from yoko_tools.sections import section_ids


@dataclass(frozen=True, slots=True)
class SeamPair:
    """Two edges that are sewn together, each a section of a piece: `piece.section(a, b)`."""

    first: str
    second: str
    ease_cm: float = 0.0  # the first edge may be this much longer than the second
    tolerance_mm: float = 1.0


def section_length_mm(box: Toolbox, expr: str) -> float:
    """The length along the outline objects a section stands for: the curves' own lengths, and
    straight lines between consecutive points."""
    ev = box.session.evaluation
    path: list[tuple[float, float]] = []
    for oid in section_ids(box, expr, "section"):
        if oid in ev.points:
            p = ev.points[oid].p
            path.append((px_to_mm(p.x), px_to_mm(p.y)))
        elif oid in ev.curves:
            pts = [(px_to_mm(q.x), px_to_mm(q.y)) for q in ev.curves[oid].geom.points()]
            if path and pts and _dist(path[-1], pts[-1]) < _dist(path[-1], pts[0]):
                pts.reverse()  # the curve runs against the outline here
            path.extend(pts)
    return sum(_dist(a, b) for a, b in pairwise(path))


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def check_points(
    table: MeasurementSet, box: Toolbox, grading: MeasurementSet | None = None
) -> list[SizePoint]:
    return size_grid(box.session.pattern, table, grading=grading)


def distinct(points: Sequence[SizePoint]) -> list[SizePoint]:
    """Sizes with the same numbers are one check (the basic set's table does not grade by height,
    so its three heights of a size are the same pattern)."""
    seen: dict[tuple[tuple[str, float], ...], SizePoint] = {}
    for p in points:
        key = tuple(sorted(p.values.items()))
        if key in seen:
            first = seen[key]
            seen[key] = SizePoint(
                f"{first.label}; {p.label}", first.size, first.height, first.values
            )
        else:
            seen[key] = p
    return list(seen.values())


def check_invariants(
    box: Toolbox,
    table: MeasurementSet,
    touched: Collection[int],
    seam_pairs: Sequence[SeamPair] = (),
    grading: MeasurementSet | None = None,
    only: Sequence[Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    """Every invariant at every size (or at the sizes in `only`). `ok` is False if any fails."""
    pattern = box.session.pattern
    points = distinct(check_points(table, box, grading))
    if only is not None:
        points = [SizePoint(f"check size {i + 1}", 0.0, 0.0, v) for i, v in enumerate(only)]
    errors: list[dict[str, Any]] = []
    pieces: list[dict[str, Any]] = []
    seams: list[dict[str, Any]] = []
    for point in points:
        session = PatternSession(pattern, point.values)
        for issue in session.issues():
            if issue.severity == "error":
                errors.append({"at": point.label, "code": issue.code, "message": issue.message})
        for issue in session.piece_issues(touched):
            if issue.severity == "error":
                pieces.append({"at": point.label, "code": issue.code, "message": issue.message})
        sized = Toolbox(session, box.specs, landmarks=box.landmarks)
        for pair in seam_pairs:
            seams.append(_seam(sized, pair, point.label))
    bad_seams = [s for s in seams if not s["ok"]]
    return {
        "ok": not errors and not pieces and not bad_seams,
        "formula_errors": errors[:20],
        "formula_error_count": len(errors),
        "open_pieces": pieces[:20],
        "seam_pairs": "none defined yet" if not seam_pairs else bad_seams[:20],
        "sizes": [p.label for p in points],
    }


def _seam(box: Toolbox, pair: SeamPair, where: str) -> dict[str, Any]:
    try:
        a = section_length_mm(box, pair.first)
        b = section_length_mm(box, pair.second)
    except ToolError as err:
        return {"at": where, "ok": False, "pair": [pair.first, pair.second], "error": str(err)}
    off = a - b - pair.ease_cm * 10.0
    return {
        "at": where,
        "ok": abs(off) <= pair.tolerance_mm,
        "pair": [pair.first, pair.second],
        "lengths_mm": [round(a, 3), round(b, 3)],
        "off_mm": round(off, 3),
    }
