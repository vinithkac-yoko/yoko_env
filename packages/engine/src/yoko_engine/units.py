"""Unit conversion, exactly as Seamly2D does it (src/libs/vmisc/def.cpp: ToPixel / FromPixel).

Seamly2D keeps geometry in 96-dpi pixels internally. The engine's evaluator does the same, with the
same arithmetic in the same order, so that rounding noise matches Seamly2D's (this matters: line
angles are truncated to 5 decimals, which magnifies noise). Public values are in mm or cm.
"""

from __future__ import annotations

PRINT_DPI = 96.0

UNITS = ("mm", "cm", "inch")


def to_pixel(val: float, unit: str) -> float:
    if unit == "mm":
        return (val / 25.4) * PRINT_DPI
    if unit == "cm":
        return ((val * 10.0) / 25.4) * PRINT_DPI
    if unit == "inch":
        return val * PRINT_DPI
    raise ValueError(f"unknown unit {unit!r}")


def from_pixel(pix: float, unit: str) -> float:
    if unit == "mm":
        return (pix / PRINT_DPI) * 25.4
    if unit == "cm":
        return ((pix / PRINT_DPI) * 25.4) / 10.0
    if unit == "inch":
        return pix / PRINT_DPI
    raise ValueError(f"unknown unit {unit!r}")


def px_to_mm(pix: float) -> float:
    return (pix / PRINT_DPI) * 25.4
