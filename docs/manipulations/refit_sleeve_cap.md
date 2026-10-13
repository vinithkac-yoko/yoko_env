# Re-fit the sleeve cap to the armhole

Recipe name: `refit_sleeve_cap`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

After the armhole changes, change the sleeve cap so its length equals the armhole length plus an amount of ease. Applies to set-in sleeves.

## 2. Required landmarks

Names are proposals from the landmark sheet and are not verified yet.

| Landmark | Used for |
| --- | --- |
| `sleeve.cap curve (front and back)` | the curve to change **(?)** |
| `bodice_front.armhole, bodice_back.armhole` | the armhole curves to measure |

## 3. Parameters

Each becomes a variable `#s<step>_<name>` that the steps use.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `ease` | extra length of the cap over the armhole | cm | | | |

## 4. Preconditions

The sleeve cap and both armholes are curves that can be measured.

## 5. Steps

| # | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- |
| 1 | add | ``measure`` | length of the front armhole and of the back armhole | two lengths |
| 2 | edit | ``edit_curve_spline`` | `length_mode` = 3 and `target_length` = front armhole + back armhole + `#s_ease`, which makes the engine set the handle lengths so the cap has that length | the re-fitted cap |

## 6. Landmarks it creates

None.

## 7. What must be re-trued

The cap height and the sleeve width at the biceps may change; notches. **(?)**

## 8. Completion check

Cap length minus armhole length equals `ease` within 0.1 mm.

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `ease` | cap length minus the sum of the two armhole lengths (`measure`) |

## 10. Incompatible with

Any manipulation that reshapes the armhole must run this one after it.

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set, saved as copies of it (see the template), with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

1. Do you re-fit by changing handle lengths (cap shape) or by changing the cap height? The engine can set a curve to a given length by moving handle lengths; is that how you would do it?
2. Is the ease one number for the whole cap, or split front and back?
3. Most and least ease, and the default.
