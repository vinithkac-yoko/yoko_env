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
from dataclasses import dataclass

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
) -> list[SizePoint]:
    """The sizes and heights to check a plan at.

    A person's file has one point. A multisize table has `steps` sizes counting up from its base
    size (the basic set's table, UK 6 to 14, is sizes 34 to 42) and the heights the pattern switches
    on that are also reachable, or the base height alone."""
    if table.kind == "individual":
        return [SizePoint("your measurements", 0.0, 0.0, table.values())]
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
