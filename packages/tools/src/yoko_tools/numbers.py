"""Numbers as Seamly2D writes them."""

from __future__ import annotations


def fmt_number(value: float) -> str:
    """No exponent, no trailing zeros."""
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text
