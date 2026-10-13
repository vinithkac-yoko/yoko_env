# Lengthen or shorten at a line

Recipe name: `lengthen_or_shorten`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

Make a piece longer or shorter by moving everything on one side of a horizontal line (a hem, a waist, a point along the length) by an amount. The usual way is to change the formula of the points that sit below the line. Applies to skirts, trousers, bodices, sleeves.

## 2. Required landmarks

Names are proposals from the landmark sheet and are not verified yet.

| Landmark | Used for |
| --- | --- |
| `<piece>.length_line` | the line the length is added or taken at **(?)**: at the hem, or higher up? |
| `<piece>.hem points` | the points that move |

## 3. Parameters

Each becomes a variable `#s<step>_<name>` that the steps use.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `amount` | how much longer (positive) or shorter (negative) | cm | | | |

## 4. Preconditions

The piece is built from points whose positions depend on a hem or length formula that can be edited. **(?)**

## 5. Steps

| # | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- |
| 1 | edit | ``edit_point_at_distance_angle`` | target = each point below the line; length = its old length + `#s_amount` (read the old formula with `get_object`) | moved points |
| 2 | edit | ``edit_curve_spline`` | handle lengths of curves that cross the line, if the shape should be kept **(?)** | adjusted curves |

## 6. Landmarks it creates

None, unless the line is new **(?)**.

## 7. What must be re-trued

Side seams that must stay parallel or matched; hem facings; pocket and notch positions below the line. **(?)**

## 8. Completion check

The distance from the length line to the hem changed by exactly `amount`; the outline is still closed and has no crossings.

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `amount` | distance from the length line to the hem now, minus the same distance at the start (`measure`) |

## 10. Incompatible with

**(?)**

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set, saved as copies of it (see the template), with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

1. Where is the line: always at the hem, or at a named line such as the knee or hip? If at a line, how do side seams and curves near it follow?
2. When lengthening a flared skirt, do side seams keep their slope (so the hem gets wider)?
3. Least and most amount, and the default.
