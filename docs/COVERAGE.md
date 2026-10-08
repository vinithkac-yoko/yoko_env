# Seamly2D parity matrix (DRAFT)

Target: pinned Seamly2D `v2026.10.5.154` (ADR 0002). Phase 3 is not done until every in-scope row is green.

Source of the rows: the `Tool` enum in `src/libs/vmisc/def.h` and the `ToolType` strings in `src/libs/vtools`, read from the develop branch on 2026-10-07. **Tool names are my proposals** (snake_case, final names are fixed in Phase 4 with the YAML tool files). "In basic set" counts come from `Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d`. Status: `todo` for everything today; nothing is implemented in Phase 0.

Every creating tool also needs an **edit** and a **delete** tool with dependency checks (Addendum 1 §8). That is listed once at the bottom, not per row.

## Points

| Seamly2D action | XML `type` | Proposed tool | In basic set | Phase | Status |
| --- | --- | --- | --- | --- | --- |
| Base (origin) point | `single` | `point_origin` | 1 | 1 | todo |
| Point at distance and angle | `endLine` | `point_at_distance_angle` | 81 | 1 | todo |
| Point along line | `alongLine` | `point_along_line` | 127 | 1 | todo |
| Point perpendicular to line (normal) | `normal` | `point_perpendicular` | 43 | 1 | todo |
| Point on bisector | `bisector` | `point_bisector` | 4 | 1 | todo |
| Point from X of one point and Y of another | `intersectXY` | `point_from_xy` | 22 | 1 | todo |
| Intersection of line and axis | `lineIntersectAxis` | `point_line_axis` | 5 | 1 | todo |
| Intersection of curve and axis | `curveIntersectAxis` | `point_curve_axis` | 6 | 3 | todo |
| Intersection of arc and axis | verify (may share `curveIntersectAxis`) | `point_arc_axis` | 0 | 3 | todo |
| Intersection of two lines | `lineIntersect` | `point_line_line` | 0 | 1 | todo |
| Intersection of arc and line | `pointOfContact` | `point_arc_line` | 4 | 3 | todo |
| Intersection of two arcs | `pointOfIntersectionArcs` | `point_arc_arc` | 0 | 3 | todo |
| Intersection of two circles | `pointOfIntersectionCircles` | `point_circle_circle` | 0 | 3 | todo |
| Intersection of two curves | `pointOfIntersectionCurves` | `point_curve_curve` | 0 | 3 | todo |
| Point from circle and tangent | `pointFromCircleAndTangent` | `point_circle_tangent` | 0 | 3 | todo |
| Point from arc and tangent | `pointFromArcAndTangent` | `point_arc_tangent` | 0 | 3 | todo |
| Height (foot of perpendicular) | `height` | `point_height` | 0 | 1 | todo |
| Triangle point | `triangle` | `point_triangle` | 0 | 1 | todo |
| Shoulder point | `shoulder` | `point_shoulder` | 0 | 1 | todo |
| Midpoint | verify (may emit `alongLine`) | `point_midpoint` | 0 | 1 | todo |
| Cut arc (point on arc) | `cutArc` | `cut_arc` | 0 | 3 | todo |
| Cut spline (point on curve) | `cutSpline` | `cut_curve` | 0 | 3 | todo |
| Cut spline path | `cutSplinePath` | `cut_curve_path` | 0 | 3 | todo |
| True darts (two points) | `trueDarts` | `true_darts` | 4 | 3 | todo |
| Anchor point | `anchor` | `anchor_point` | 16 (modeling) | keep | todo, preserve only |

## Lines and curves

| Seamly2D action | XML | Proposed tool | In basic set | Phase | Status |
| --- | --- | --- | --- | --- | --- |
| Line | tag `line` | `line` | 90 | 1 | todo |
| Arc (radius, angles) | `simple` | `arc_radius` | 15 | 1 | todo |
| Arc with length | `arcWithLength` | `arc_length` | 0 | 1 | todo |
| Elliptical arc | verify (`simple` under its own tag) | `arc_elliptical` | 0 | 3 | todo |
| Simple curve (spline) | `simpleInteractive` | `curve_spline` | 0 | 1 | todo |
| Spline path | `pathInteractive` | `curve_spline_path` | 0 | 1 | todo |
| Cubic Bezier | `cubicBezier` | `curve_bezier` | 9 | 1 | todo |
| Cubic Bezier path | `cubicBezierPath` | `curve_bezier_path` | 13 | 1 | todo |

Curve control points and handles are part of the curve objects. 0.7.4 adds `autoSmooth` and `lengthMode` (ADR 0002).

## Operations

| Seamly2D action | XML | Proposed tool | In basic set | Phase | Status |
| --- | --- | --- | --- | --- | --- |
| Mirror by line | `flippingByLine` | `mirror_by_line` | 1 | 3 | todo |
| Mirror by axis | `flippingByAxis` | `mirror_by_axis` | 0 | 3 | todo |
| Rotate | `rotation` | `rotate` | 0 | 3 | todo |
| Move | `moving` | `move` | 0 | 3 | todo |
| Group | tag `group` | `group` | 15 groups | 3 | todo, store, ignore visibility |

## Pieces

| Seamly2D action | XML | Proposed tool | In basic set | Phase | Status |
| --- | --- | --- | --- | --- | --- |
| Piece from closed path | tag `piece` | `piece_from_path` | 7 | 3 | todo |
| Internal path | tag `iPaths` | `piece_internal_path` | present | 3 | todo |
| Union (merge pieces) | `union` | `piece_union` | 0 | 3 | todo |
| Insert nodes | verify | `piece_insert_nodes` | 0 | 3 | todo |
| Modeling nodes (`modeling`, `modelingPath`, `modelingSpline`) | tag `modeling` | internal to piece tools | 223 | 3 | todo |

Seam allowance, grainline, notches, labels, `patternInfo`: out of scope, **kept unchanged on round trip** (the basic set has seam allowance 1 cm on all 7 pieces).

## Pattern-level items (not tools in the Seamly2D toolbar, but editable in the UI)

| Item | In basic set | Phase | Status |
| --- | --- | --- | --- |
| Draft blocks (add, rename, delete) | 1 | 1 | todo |
| Variables (`increments` in 0.6.8, `variables` from 0.6.9): create, edit, delete | 17 | 1 | todo |
| Measurement file binding and standard measurements (`height` = A01, `size` = G12) | yes | 1 | todo |
| Pattern properties (name, number, notes, gradation block) | yes | 2 | round trip only |
| Background images (0.7.1) | 0 | 2 | round trip only |
| Final measurements (0.7.5) | 0 | 2 | round trip only |

## Parity fixture

`src/test/CollectionTest/share/all_tools_pattern/alltools_pattern.sm2d` (format 0.7.4) uses every tool. It is the first parity fixture (Addendum 1 §17): every tool in it must parse, evaluate and round-trip. It is not downloaded yet; it goes to `fixtures/external/seamly2d/` in Phase 2 with a source note (GPL, Seamly2D project).

## Edit and delete

Each row above gets `edit_<object>` and `delete_<object>`. Delete refuses when other objects depend on the target (Seamly2D does the same); the fix is to edit, per ADR 0007.
