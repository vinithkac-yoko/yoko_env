"""Qt's fuzzy float comparisons, shared by the formula and geometry layers."""

from __future__ import annotations


def fuzzy_is_null(d: float) -> bool:
    """qFuzzyIsNull(double)."""
    return abs(d) <= 0.000000000001


def fuzzy_compare(p1: float, p2: float) -> bool:
    """qFuzzyCompare(double, double)."""
    return abs(p1 - p2) * 1000000000000.0 <= min(abs(p1), abs(p2))


def fuzzy_compare_possible_nulls(p1: float, p2: float) -> bool:
    """QmuFuzzyComparePossibleNulls / VFuzzyComparePossibleNulls: zero is compared absolutely."""
    if fuzzy_is_null(p1):
        return fuzzy_is_null(p2)
    if fuzzy_is_null(p2):
        return False
    return fuzzy_compare(p1, p2)
