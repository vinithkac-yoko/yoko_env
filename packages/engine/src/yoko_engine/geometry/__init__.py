"""Plane geometry, ported from the Qt behaviour Seamly2D relies on."""

from yoko_engine.fuzzy import fuzzy_compare, fuzzy_is_null
from yoko_engine.geometry.qt import Line, Pt, points_equal

__all__ = ["Line", "Pt", "fuzzy_compare", "fuzzy_is_null", "points_equal"]
