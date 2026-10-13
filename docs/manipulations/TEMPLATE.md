# <Manipulation name>

Recipe name: `<snake_case_name>`
Status: **draft** / reviewed / approved (who, date)
Written by: <pattern maker, or "Claude, from the tools; not drafting practice" for a first draft>

> How to use this template. Copy it to `docs/manipulations/<snake_case_name>.md` and fill every
> section. Say "none" rather than leaving a section out. If something is a matter of drafting
> practice, write what *you* do; nobody else should guess it. The tool names are the ones in
> `docs/COVERAGE.md`; a step is one tool call.

## 1. Purpose and where it applies

What the manipulation does to a pattern, in plain words, and which blocks or pieces it is used on
(for example "bodice front and back", "any piece with a hem").

## 2. Required landmarks

The named points, lines and curves the manipulation needs to exist, using the landmark names
(`<piece>.<landmark>`, see `docs/landmarks/`). Say what each is used for.

| Landmark | Used for |
| --- | --- |
| `bodice_front.CF_neck` | |

## 3. Parameters

Every amount the planner decides. Each becomes a pattern variable `#s<step>_<name>` and the steps
below use the variable, never a number.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `hem_flare` | | cm | | | |

Units: `cm`, `mm`, `inch`, `deg`, `count` (a whole number), `ratio`.

## 4. Preconditions

What must be true before the manipulation starts (for example "the piece has a closed outline",
"the dart tip lies inside the piece").

## 5. Steps

Numbered. Each step is one tool call, with what it refers to and the formulas it uses. Say whether it
**adds** an object or **edits** an existing one (editing the formula of a point the style copied is
normal drafting). Use landmark names for references and `#s<step>_<name>` for amounts.

| # | Add or edit | Tool | References and formulas | Result (a new landmark, if any) |
| --- | --- | --- | --- | --- |
| 1 | add | `point_along_line` | first = `...`, second = `...`, length = `#s_<name>/2` | `...` |

## 6. Landmarks it creates

Names for the new points and curves, so later steps and recipes can refer to them.

## 7. What must be re-trued

Things that must still hold afterwards, and what to do about them (for example "the sleeve cap must
still match the new armhole: run `refit_sleeve_cap`").

## 8. Completion check

How we know the manipulation is done and right. Must be something that can be measured on the
pattern (for example "the dart legs are equal in length", "the new piece is closed", "the hem is
`hem_flare` lower than before").

## 9. Measurements for the status card

For each parameter, how to measure its current value on the pattern, so the status card can say
"target 6.0 cm, now 0.0 cm".

| Parameter | How to measure it now |
| --- | --- |

## 10. Incompatible with

Other manipulations that cannot be used together with this one, or only in a certain order.

## 11. Worked examples

Two or three examples drafted by hand in Seamly2D from the basic set. Save each as a copy of the
basic set (the parent is recorded in the library) and give the parameter values and the lengths a
checker should find. These become the golden tests: the recipe must reproduce them exactly.

| Example | Parent pattern | Seamly2D file | Parameter values | What to measure, and the answer |
| --- | --- | --- | --- | --- |

## 12. Questions and notes

Anything unclear, anything the next reader should know.
