"""Object handlers, one per Seamly2D object kind, grouped by what they build."""

from __future__ import annotations

from yoko_engine.evalcore import Handler
from yoko_engine.handlers import curves, cuts, operations, points

HANDLERS: dict[str, Handler] = {
    "single": points.single,
    "endLine": points.end_line,
    "alongLine": points.along_line,
    "normal": points.normal,
    "bisector": points.bisector,
    "intersectXY": points.intersect_xy,
    "lineIntersectAxis": points.line_intersect_axis,
    "line:line": points.line,
    "pointOfContact": points.point_of_contact,
    "trueDarts": points.true_darts,
    "curveIntersectAxis": cuts.curve_intersect_axis,
    "arc:simple": curves.arc,
    "spline:cubicBezier": curves.cubic_bezier,
    "spline:cubicBezierPath": curves.cubic_bezier_path,
    "operation:flippingByLine": operations.flip_by_line,
}

# Kinds that are part of the language but not computed yet; the evaluator reports them.
PENDING_KINDS: frozenset[str] = frozenset()
