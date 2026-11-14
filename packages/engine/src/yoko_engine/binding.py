"""Which measurements a pattern is drafted for: the table's sizes, or a person's own file.

A pattern is bound to a measurement file. The basic set is bound to a multisize table (one set of
formulas, a size and a height choose the numbers). A style made for one person is bound to that
person's individual file instead. Both give a `MeasurementSet`; `values()` turns either into the
numbers a pattern is evaluated with. This module checks that a table has every measurement the
pattern uses, and lists the sizes a plan has to hold at.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from yoko_engine.evaluator import evaluate
from yoko_engine.model import Measurement, MeasurementSet, Pattern, RawNode

_NAME_IN_MESSAGE = re.compile(r"^'([^']+)' is not a known")
# Names the objects of a pattern make (line lengths, curve lengths, radii ...). When a measurement
# is missing, objects that depend on it fail and these names go missing too; they are not
# measurements, so they are not reported.
_DERIVED_PREFIXES = (
    "Line_", "AngleLine_", "Spl_", "SplPath_", "Arc_", "ElArc_", "Radius", "Angle1", "Angle2",
    "C1Length", "C2Length", "CurrentLength", "CurrentSeamAllowance",
)  # fmt: skip


class MeasurementError(ValueError):
    """A measurement table cannot be used for a pattern."""

    def __init__(self, message: str, missing: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.missing = tuple(missing)


def individual_table(values: Mapping[str, float], unit: str = "cm") -> MeasurementSet:
    """A person's measurements as a table, for tests and for building a file from numbers."""
    rows = tuple(Measurement(name, float(v)) for name, v in sorted(values.items()))
    return MeasurementSet(unit, 0.0, 0.0, rows, kind="individual")


def missing_measurements(pattern: Pattern, values: Mapping[str, float]) -> list[str]:
    """The measurement names the pattern uses that `values` does not have, sorted."""
    ev = evaluate(pattern, values)
    names = {
        m.group(1)
        for i in ev.issues
        if i.code == "formula_undefined_name" and (m := _NAME_IN_MESSAGE.match(i.message))
    }
    return sorted(n for n in names if not n.startswith(("#", *_DERIVED_PREFIXES)))


def check_measurements(pattern: Pattern, table: MeasurementSet) -> dict[str, float]:
    """The table's numbers for the pattern, or `MeasurementError` naming what is missing."""
    values = table.values()
    missing = missing_measurements(pattern, values)
    if missing:
        raise MeasurementError(
            f"the measurement file lacks {', '.join(missing)}, which the pattern uses", missing
        )
    return values


# How much a person's own measurements are nudged (in cm) for the two extra copies that a plan and
# the teacher are checked at. A person's file has one size; a number written into a formula that
# happens to equal a measurement at that size would pass everywhere. Kasi, Phase 4 answers.
NUDGES_CM: Mapping[str, float] = {
    "bust_circ": 2.0,
    "waist_circ": 2.0,
    "hip_circ": 2.0,
    "height": 3.0,
}
_CM_IN = {"cm": 1.0, "mm": 10.0, "inch": 1 / 2.54}


def nudged_tables(
    table: MeasurementSet,
    grading: MeasurementSet | None = None,
    nudges: Mapping[str, float] = NUDGES_CM,
) -> tuple[MeasurementSet, MeasurementSet]:
    """Two copies of a person's own file, one nudged up and one down.

    With `grading` (the multisize table the pattern was drafted from), every measurement moves by
    the same fraction of a size step, the fraction that moves bust_circ by its nudge (half a step in
    the basic set's table: bust, waist and hip 2 cm, everything else in proportion). A measurement
    the table does not grade (height, in the basic set's table) takes its own nudge. Without a
    table, only the measurements in `nudges` move. Measurements given as formulas follow."""
    if table.kind != "individual":
        raise MeasurementError("only a person's own measurement file is nudged")
    factor = _CM_IN.get(table.unit, 1.0)
    steps: dict[str, float] = {}  # measurement -> how much it moves, in the person's unit
    if grading is not None and grading.kind != "individual":
        to_person = factor / _CM_IN.get(grading.unit, 1.0)
        graded = {m.name: m.size_increase for m in grading.measurements}
        anchor = graded.get("bust_circ", 0.0)
        fraction = nudges.get("bust_circ", 0.0) / anchor if anchor else 0.0
        steps = {n: fraction * inc * to_person for n, inc in graded.items() if inc}
    for name, cm in nudges.items():
        if name not in steps:
            steps[name] = cm * factor
    out: list[MeasurementSet] = []
    for sign in (1.0, -1.0):
        rows = tuple(
            replace(m, base=m.base + sign * steps[m.name])
            if m.name in steps and not m.formula
            else m
            for m in table.measurements
        )
        out.append(replace(table, measurements=rows, document=None))
    return out[0], out[1]


@dataclass(frozen=True, slots=True)
class SizePoint:
    """One size of a multisize table: a name for messages, and the numbers."""

    label: str
    size: float
    height: float
    values: Mapping[str, float]


def gradation(pattern: Pattern) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """The sizes and heights a pattern's header switches on (`<gradation>`), if it has any."""

    def flags(node: RawNode, prefix: str) -> tuple[float, ...]:
        out = [
            float(k[len(prefix) :])
            for k, v in node.attrs
            if k.startswith(prefix) and k[len(prefix) :].isdigit() and v == "true"
        ]
        return tuple(sorted(out))

    for header in pattern.header:
        if header.tag != "gradation":
            continue
        sizes: tuple[float, ...] = ()
        heights: tuple[float, ...] = ()
        for child in header.children:
            if child.tag == "sizes":
                sizes = flags(child, "s")
            elif child.tag == "heights":
                heights = flags(child, "h")
        return sizes, heights
    return (), ()


def size_grid(
    pattern: Pattern,
    table: MeasurementSet,
    *,
    sizes: Sequence[float] | None = None,
    heights: Sequence[float] | None = None,
    steps: int = 5,
    grading: MeasurementSet | None = None,
) -> list[SizePoint]:
    """The sizes and heights to check a plan at.

    A person's file has three points: their own measurements and two nudged copies
    (`nudged_tables`, graded like `grading`, the table the pattern was drafted from, when given).
    A multisize table has `steps` sizes counting up from its base size (the basic set's table,
    UK 6 to 14, is sizes 34 to 42) and the heights the pattern switches on that are also
    reachable, or the base height alone."""
    if table.kind == "individual":
        up, down = nudged_tables(table, grading)
        return [
            SizePoint("your measurements", 0.0, 0.0, table.values()),
            SizePoint("your measurements, nudged up", 0.0, 0.0, up.values()),
            SizePoint("your measurements, nudged down", 0.0, 0.0, down.values()),
        ]
    size_list = (
        list(sizes)
        if sizes is not None
        else [table.base_size + table.size_step_cm * k for k in range(steps)]
    )
    if heights is not None:
        height_list = list(heights)
    else:
        _, graded = gradation(pattern)
        height_list = [h for h in graded if abs(h - table.base_height) <= 2 * table.height_step_cm]
        height_list = height_list or [table.base_height]
    return [
        SizePoint(f"size {s:g}, height {h:g}", s, h, table.values(s, h))
        for s in size_list
        for h in height_list
    ]
