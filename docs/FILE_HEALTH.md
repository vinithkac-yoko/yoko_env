# File health: fixtures

What the engine should report when it opens these files. We change no data; the report is the deliverable (Addendum 1 §1 Q3).

## `Aldrich-Womens-MultiSize-06-14.smms` (format 0.4.4, `<vst>`, v2023.11.20)

| Finding | Detail | Action |
| --- | --- | --- |
| Base height mismatch | Header `<height base="164">`, but measurement `height` has base 166 | Honour as written. Log it. The oracle confirms. |
| `height_increase` is 0 everywhere | `height` stays 166 at heights 158, 164, 170, so `#CM` = `height/#BaseHeight` = 1 at every height | Honour as written. |
| `height` and `size` are ordinary rows | `height` = A01 and `size` = G12 are Seamly2D standard measurements, separate from the table's base size and height | Read as is. `size` = 6 is UK dress size, +2 per size step. |
| Size coverage | File name says UK 6 to 14, which I read as header sizes 34 to 42. The file stores only a base and increments, so the range is not in the file | Multi-size checks use 34 to 42. Beyond that is extrapolation: report, never fail. To confirm with the oracle. |
| Unused rows | 11 measurements are defined and never used by the basic set; 5 of them have base 0 | Keep, ignore. |

## `Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d` (format 0.6.8, v2023.12.4)

| Finding | Detail |
| --- | --- |
| One draft block, one origin | Origin `A` is the only `single` point |
| 425 construction objects, 7 pieces, 15 groups | 12 of 15 groups hidden; 117 objects with `lineType="none"` (no line is drawn, ADR 0003) |
| Variables | 17 `increment` rows including 2 separator rows |
| Formulas | Ternaries (`size>22?4.75:...`), `CurrentLength`, geometry references such as `Line_A11_A13a` |
| Measurements | Uses 17 of 28 rows |
| Seam allowance | 1 cm on all 7 pieces. Out of scope, kept unchanged |
