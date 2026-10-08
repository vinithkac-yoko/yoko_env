# 0006. Plan amounts become pattern variables

Status: accepted (Addendum 1 §7)

The planner decides every amount; the drafter never invents a number. Each amount becomes a pattern variable (`increment` in 0.6.8, `variable` from 0.6.9) named `#s<step>_<param>` (e.g. `#s3_hem_flare`), with the step's text as description and a constant or a formula over measurements as value. Recipes reference these variables, never literals, so a pattern maker can change an amount in Seamly2D's variable table and the whole style updates. Plan validation before approval checks that every recipe parameter is present, typed, in units, and within range.
