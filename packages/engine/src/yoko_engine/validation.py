"""Validation after every mutation.

Everything the evaluator reports (bad formulas, missing references, impossible intersections) plus
checks that need the whole result: duplicate labels, zero-length lines, non-finite geometry.
Piece checks (open or self-intersecting outlines, mismatched seams) arrive with pieces in Phase 3.
"""

from __future__ import annotations

import math

from yoko_engine.evaluator import Evaluation, Issue
from yoko_engine.geometry import Line
from yoko_engine.model import Pattern


def validate(pattern: Pattern, ev: Evaluation) -> list[Issue]:
    """All issues for an evaluated pattern: what the evaluator found, then whole-result checks."""
    issues = list(ev.issues)

    seen: dict[str, int] = {}
    for pid in sorted(ev.points):
        geom = ev.points[pid]
        if not (math.isfinite(geom.p.x) and math.isfinite(geom.p.y)):
            issues.append(
                Issue(
                    "nan_geometry",
                    f"point {geom.label} has a non-finite coordinate",
                    pid,
                    None,
                    "check the formulas it uses for division by zero",
                )
            )
        if geom.label:
            if geom.label in seen:
                issues.append(
                    Issue(
                        "duplicate_label",
                        f"label {geom.label!r} is already used by object {seen[geom.label]}",
                        pid,
                        "name",
                        "labels must be unique: Seamly2D builds variable names from them",
                    )
                )
            else:
                seen[geom.label] = pid

    for o in pattern.objects():
        if o.tag == "line":
            a = ev.points.get(_int(o.get("firstPoint")))
            b = ev.points.get(_int(o.get("secondPoint")))
            if a is not None and b is not None and Line(a.p, b.p).is_null():
                issues.append(
                    Issue(
                        "zero_length_line",
                        f"line between {a.label} and {b.label} has no length",
                        o.id,
                        None,
                        "the two points coincide",
                    )
                )
    return issues


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]


def _int(text: str | None) -> int:
    try:
        return int(text) if text is not None else -1
    except ValueError:
        return -1
