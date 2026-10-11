"""Object handlers, one per Seamly2D object kind, grouped by what they build."""

from __future__ import annotations

from yoko_engine.evalcore import Handler
from yoko_engine.handlers import curves, cuts, intersections, operations, points

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
    "lineIntersect": points.line_intersect,
    "height": points.height,
    "shoulder": points.shoulder,
    "triangle": points.triangle,
    "curveIntersectAxis": cuts.curve_intersect_axis,
    "cutSpline": cuts.cut_spline_point,
    "cutSplinePath": cuts.cut_spline_path_point,
    "cutArc": cuts.cut_arc_point,
    "pointOfIntersectionCircles": intersections.circles,
    "pointFromCircleAndTangent": intersections.circle_tangent,
    "pointOfIntersectionArcs": intersections.arcs,
    "pointFromArcAndTangent": intersections.arc_tangent,
    "pointOfIntersectionCurves": intersections.curves,
    "arc:simple": curves.arc,
    "arc:arcWithLength": curves.arc_with_length,
    "spline:cubicBezier": curves.cubic_bezier,
    "spline:cubicBezierPath": curves.cubic_bezier_path,
    "spline:simpleInteractive": curves.spline_interactive,
    "spline:simple": curves.spline_simple,
    "spline:pathInteractive": curves.spline_path_interactive,
    "spline:path": curves.spline_path_simple,
    "operation:flippingByLine": operations.flip_by_line,
    "operation:flippingByAxis": operations.flip_by_axis,
    "operation:rotation": operations.rotation,
    "operation:moving": operations.moving,
}

# Kinds that are part of the language but not computed yet; the evaluator reports them.
PENDING_KINDS: frozenset[str] = frozenset()
