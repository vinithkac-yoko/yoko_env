# Add or remove width at a seam (progressive taper)

Recipe name: `add_or_remove_width_at_seam`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

Move a seam out or in by an amount that grows (or shrinks) from nothing at one point along the seam to the full amount at another, for example taking in a side seam from the underarm to the hem. Applies to side seams, sleeve seams, trouser seams.

## 2. Required landmarks

Names are proposals from the landmark sheet and are not verified yet.

| Landmark | Used for |
| --- | --- |
| `<piece>.seam_start` | where the change begins, with no change **(?)** |
| `<piece>.seam_end` | where the change is full **(?)** |
| `<piece>.seam points` | the points between, which move by a share of the amount |

## 3. Parameters

Each becomes a variable `#s<step>_<name>` that the steps use.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `amount` | full change at the far end of the taper | cm | | | |

## 4. Preconditions

The seam is a line or a chain of points that can be moved sideways by editing their formulas. **(?)**

## 5. Steps

| # | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- |
| 1 | edit | ``edit_point_at_distance_angle` / `edit_point_along_line`` | target = each seam point; add `#s_amount * (distance from seam_start / seam length)` to its sideways formula, so the share is proportional to distance **(?)** | moved points |
| 2 | edit | ``edit_curve_spline`` | handles of seam curves **(?)** | adjusted curves |

## 6. Landmarks it creates

None **(?)**.

## 7. What must be re-trued

The matching edge on the other piece (it must change by the same amount); darts and notches near the seam. **(?)**

## 8. Completion check

Each seam point has moved by its share; the seam is smooth; the matching edge is the same length. **(?)**

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `amount` | sideways distance between the old and new position of the seam_end point |

## 10. Incompatible with

**(?)**

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set, saved as copies of it (see the template), with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

1. Is the taper straight (proportional to distance) or does it follow a curve?
2. Does the amount apply to one seam or is it split between front and back? Is the amount per seam or total?
3. How do I tell which points are 'on the seam'? Landmarks, or a chain between two points?
