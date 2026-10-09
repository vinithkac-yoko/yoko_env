# Formula language: where we follow Seamly2D, and where we deliberately differ

The formula parser in `yoko_engine.formula` is a port of Seamly2D's muparser fork (`src/libs/qmuparser`, develop branch checked 2026-10-07). Default rule (Kasi, 2026-10-09): **copy Seamly2D's behaviour, quirks included, so results match the real app.** The oracle (Phase 2) will confirm each item against the pinned binary.

## Copied on purpose (quirks)

| Behaviour | Source |
| --- | --- |
| Unary minus binds looser than `^`: `-2^2` is -4. It has the same level as `*` and `/` | `qmuparserdef.h` `EOprtPrecedence` |
| `^` is right associative: `2^3^2` is 512 | `qmuparserbase.cpp` `GetOprtAssociativity` |
| All six comparisons share one level and are left associative: `1<2==1` is `(1<2)==1` | same |
| No unary plus (`+5` is an error) and no stacked minus (`--5` is an error; `2--3` is fine) | `qmuparsertokenreader.cpp` `IsInfixOpTok`, `m_iSynFlags` |
| `==` and `!=` are fuzzy (`qFuzzyCompare`, with zero compared against `1e-12`) | `qmudef.h` `QmuFuzzyComparePossibleNulls` |
| `cond ? a : b` takes `b` when `abs(cond) <= 1e-12`; one branch is evaluated, but every name in the formula must exist | `ParseCmdCodeBulk` cmIF; `Calculator::InitVariables` |
| `&&` and `||` use a C++ bool cast: any non-zero value, and NaN, is true | `ParseCmdCodeBulk` |
| Division by zero is IEEE (inf or nan), never an error | `MUP_MATH_EXCEPTIONS` is off |
| `log` is base 10; `ln` is natural; `rint` is `floor(v + 0.5)`; `asinh` is `log(v + sqrt(v*v+1))` | `qmuparser.cpp` |
| `min`/`max` use Qt's `qMin`/`qMax`, so NaN behaves as in Qt | same |
| A function name must be directly followed by `(`: `sin (1)` reads `sin` as a name | `IsFunTok` |
| `;` separates function arguments | `SetSepForEval` |
| A malformed number such as `5.` or `1e` is rejected as a whole. A sign straight after exponent digits is too, so `2e3-1` does not read as `2e3` minus 1 (it reads `2e3` as a name; `2e3 -1` works) | `qmudef.cpp` `ReadVal` state table |

## Deliberate differences

| Behaviour | Seamly2D | Ours | Why |
| --- | --- | --- | --- |
| Comma in a formula | Evaluation locale makes `,` a thousands separator: `1,000` reads as 1000 and `1,5` fails | Always an error, with a hint to use `;` | A model that writes `max(1,2)` gets a clear message, not a silent wrong number. No real file uses a comma |
| Identifier letters | A fixed list of alphabets | Any Unicode letter, digits, and `_ @ # ' °` | Same practical set, simpler |
| Formula size | No cap | 1000 characters, 300 tokens, 40 nesting levels | Robustness (Addendum 1 §14) |
| Errors | Translated message strings | A code, position, token and a hint | Models need to learn from errors (spec principle 9) |

## Not here yet

Geometry names such as `Line_A11_A13a`, `AngleLine_A10_A10a`, `SplPath_C11_D4`, `RadiusArc_A13_153` and `CurrentLength` parse as ordinary names. Giving them values is the evaluation graph's job (next slice).
