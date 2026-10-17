# Seamly2D parity matrix

Target: pinned Seamly2D `v2026.10.5.154` (ADR 0002). Phase 3 is done when every in-scope row is green.

Source of the rows: every `ToolType` string in `src/libs/vtools` of the pinned release (found with `grep` over the source on 2026-10-11: all of them are in the tables below) plus the actions of the `Tool` enum in `src/libs/vmisc/def.h`. **Tool names are my proposals** (snake_case; the final names are fixed in Phase 4 with the YAML tool files).

How a row is checked ("exact vs Seamly2D"): the engine's points, curves, variables and piece outlines equal what the pinned Seamly2D computes **bit for bit**, on the basic set, on 23 of Seamly2D's own test patterns (`tests/test_external_seamly2d.py`, ratchet in `tests/external_ratchet.json`) and on case patterns written for one tool (`fixtures/patterns/cases/`, oracle output in `fixtures/oracle/cases/`, refreshed by CI). "In test patterns" counts objects of that kind over the basic set and Seamly2D's 41 test patterns.

Status words: **evaluates, exact** = the engine computes it like Seamly2D. **creates** = a session action makes or changes it. **preserved** = read, kept and written back unchanged, not computed (the lossless round trip).

## Points

| Seamly2D action | XML `type` | Proposed tool | In test patterns | Status |
| --- | --- | --- | --- | --- |
| Base (origin) point | `single` | `point_origin` | 44 | evaluates, exact |
| Point at distance and angle | `endLine` | `point_at_distance_angle` | 466 | evaluates, exact |
| Point along line | `alongLine` | `point_along_line` | 696 | evaluates, exact |
| Point perpendicular to line | `normal` | `point_perpendicular` | 279 | evaluates, exact |
| Point on bisector | `bisector` | `point_bisector` | 9 | evaluates, exact |
| Point from X of one point and Y of another | `intersectXY` | `point_from_xy` | 149 | evaluates, exact |
| Intersection of line and axis | `lineIntersectAxis` | `point_line_axis` | 31 | evaluates, exact |
| Intersection of curve (or arc) and axis | `curveIntersectAxis` | `point_curve_axis` | 31 | evaluates, exact (not for elliptical arcs: the engine says `not_implemented`; see the note below) |
| Intersection of arc and line | `pointOfContact` | `point_arc_line` | 8 | evaluates, exact |
| Intersection of two lines | `lineIntersect` | `point_line_line` | 46 | evaluates, exact |
| Intersection of two arcs | `pointOfIntersectionArcs` | `point_arc_arc` | 2 | evaluates, exact |
| Intersection of two circles | `pointOfIntersectionCircles` | `point_circle_circle` | 3 | evaluates, exact |
| Intersection of two curves | `pointOfIntersectionCurves` | `point_curve_curve` | 1 | evaluates, exact |
| Point from circle and tangent | `pointFromCircleAndTangent` | `point_circle_tangent` | 2 | evaluates, exact |
| Point from arc and tangent | `pointFromArcAndTangent` | `point_arc_tangent` | 1 | evaluates, exact |
| Height (foot of perpendicular) | `height` | `point_height` | 23 | evaluates, exact |
| Triangle point | `triangle` | `point_triangle` | 1 | evaluates, exact |
| Shoulder point | `shoulder` | `point_shoulder` | 12 | evaluates, exact |
| Midpoint | none in this release | `point_midpoint` (an `alongLine` at half the length) | | nothing to build: Seamly2D has no separate tool |
| Cut arc | `cutArc` | `cut_arc` | 1 | evaluates, exact |
| Cut spline | `cutSpline` | `cut_curve` | 22 | evaluates, exact |
| Cut spline path | `cutSplinePath` | `cut_curve_path` | 9 | evaluates, exact |
| True darts (two points) | `trueDarts` | `true_darts` | 5 | evaluates, exact |
| Anchor point (modeling) | `anchor` | `anchor_point` | 16 in the basic set | preserved |

## Lines and curves

| Seamly2D action | XML | Proposed tool | In test patterns | Status |
| --- | --- | --- | --- | --- |
| Line | tag `line` | `line` | 662 | evaluates, exact |
| Arc (radius, angles) | `simple` | `arc_radius` | 18 | evaluates, exact |
| Arc with length | `arcWithLength` | `arc_length` | 3 | evaluates, exact (including the flipped arc of a negative length) |
| Elliptical arc | tag `elArc`, `simple` | `arc_elliptical` | 1 | evaluates, exact (20 arcs in `elliptical_arcs`: length and angles bit for bit; Qt's `arcTo` and path flattening are ported); rotate, mirror and move: exact (56 copies in `elliptical_arc_operations`, also one operation after another) |
| Simple curve (spline) | `simpleInteractive`, old `simple` | `curve_spline` | 66 + 90 | evaluates, exact, including `autoSmooth` and `lengthMode` (156 curves in `spline_length_modes`) |
| Spline path | `pathInteractive`, old `path` | `curve_spline_path` | 38 + 10 | evaluates, exact |
| Cubic Bezier | `cubicBezier` | `curve_bezier` | 22 | evaluates, exact, including `autoSmooth` and `lengthMode` |
| Cubic Bezier path | `cubicBezierPath` | `curve_bezier_path` | 17 | evaluates, exact (`autoSmooth` and `lengthMode` are refused: Seamly2D has them only on the single curves) |

## Operations

| Seamly2D action | XML | Proposed tool | In test patterns | Status |
| --- | --- | --- | --- | --- |
| Mirror by line | `flippingByLine` | `mirror_by_line` | 3 | evaluates, exact (points, arcs, elliptical arcs, curves) |
| Mirror by axis | `flippingByAxis` | `mirror_by_axis` | 1 | evaluates, exact |
| Rotate | `rotation` | `rotate` | 10 | evaluates, exact |
| Move | `moving` | `move` | 1 | evaluates, exact |
| Group | tag `group` | `group` | 15 in the basic set | preserved; a deleted object leaves its groups; visibility ignored (ADR 0003) |

**Elliptical arcs cut at an axis:** not built. The pinned Seamly2D itself hangs (no answer in 10 s) in most of the configurations tried (about 90 of 96 axis and arc combinations), so there is no reliable oracle to check a port against. The unverified port is kept out of the repository until Seamly2D's behaviour is understood (question for Kasi).

## Pieces

| Seamly2D action | XML | Proposed tool | In test patterns | Status |
| --- | --- | --- | --- | --- |
| Piece from a closed path of objects | tag `piece` | `piece_from_path` | 7 in the basic set, 61 in the 23 test patterns Seamly2D opens | evaluates, exact (outline); **creates** (`AddPiece`, `SetPiece`, `DeletePiece`); Seamly2D opens a piece we write and computes the same outline (`added_piece` case) |
| Internal path | tag `iPaths` | `piece_internal_path` | present | preserved, not computed (Phase 3 depth decided with Kasi: outline geometry and round trip) |
| Union (merge two pieces along an edge) | `union` | `piece_union` | 1 | evaluates, exact (the united piece's outline equals Seamly2D's); created by the `UnionPieces` action (tool `union_pieces`), checked by the oracle (case `union`) |
| Modeling nodes (`modeling`, `modelingSpline`, `modelingPath`) | tag `modeling` | internal to piece tools | 223 in the basic set | evaluates (copies of draft objects); created with a piece, dropped with it when nothing else uses them |

Seam allowance, grainline, notches, labels and `patternInfo` are out of scope and **kept unchanged on round trip**. A piece we create has only an id, a name and its nodes; Seamly2D fills in the rest when it saves.

## Pattern-level items

| Item | Status |
| --- | --- |
| Draft blocks (add, rename, delete an empty one) | creates (`AddBlock`, `RenameBlock`, `DeleteBlock`) |
| Variables (`increments` in 0.6.8, `variables` from 0.6.9): create, edit, delete | creates (`SetVariable`, `DeleteVariable`) |
| Measurement file binding and standard measurements (`height` = A01, `size` = G12) | evaluates |
| Pattern properties (name, number, notes, gradation block) | round trip only |
| Background images (0.7.1) | round trip only |
| Final measurements (0.7.5) | round trip only |

## Edit and delete (Addendum 1 section 8)

The session has one **edit** (`SetAttrs`: any formula, reference or label of any object; `SetVariable`; `SetPiece`; `RenameBlock`) and one **delete** (`DeleteObject`, `DeletePiece`, `DeleteVariable`, `DeleteBlock`) per kind of thing. The typed per-tool names (`edit_point_along_line` ...) are the Phase 4 YAML layer over these. Rules, all tested:

- an object other objects use cannot be deleted (it says which objects use it; the fix is to edit them, ADR 0007);
- an object that is part of a piece cannot be deleted (delete the piece or change its outline first);
- a variable used by a formula cannot be deleted;
- a block with objects or pieces cannot be deleted;
- the basic set refuses every write.

## Library

Parent links, family tree, description, garment type, tags, tag and text search, copy a single piece with what it depends on, locked base area: see `docs/PROGRESS.md` (Phase 3).

## Parity fixture

`all_tools_pattern/alltools_pattern.sm2d` (format 0.7.4) uses every tool. It is in `fixtures/external/seamly2d/`. The engine now evaluates every object in it without an issue, and every point, curve and variable it computes equals Seamly2D's.
