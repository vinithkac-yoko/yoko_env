# Seamly2D's own test patterns

These files belong to the **Seamly2D project** ([FashionFreedom/seamly2d](https://github.com/FashionFreedom/seamly2d),
licence **GNU GPL v3**, see its `LICENSE`). They are copied unchanged from
`src/test/CollectionTest/share` at tag `v2026.10.5.154` (commit `0627ac315f7b9aae6109e0961a59b98852e7aae0`),
the version this repository pins (ADR 0002). They are used only for engine tests and practice tasks,
never in the held-out benchmark (Addendum 1 §17), and they are not derived from our basic pattern set.

| Folder | What it is | Made by |
| --- | --- | --- |
| `original/` | the files exactly as Seamly2D ships them (`MANIFEST.sha256` pins them) | Seamly2D project |
| `upgraded/` | each pattern opened and saved again by the pinned Seamly2D: format 0.7.5 | `scripts/oracle_upgrade.sh` |
| `oracle/` | what the pinned Seamly2D computed for each (`*.seamly2d.json`: every point, curve, arc, variable), or why it could not open the file (`*.failed`) | `scripts/oracle_upgrade.sh` |

Most originals are old formats (0.2.x to 0.4.0). We do not read those: Seamly2D upgrades them and we read
the upgraded copies (format 0.7.5), which also gives us 23 real patterns to test the reader, the writer
and the engine against.

## Files the pinned Seamly2D itself cannot open (18 of 41)

| Files | Why (from Seamly2D's own message, kept in `oracle/*.failed`) |
| --- | --- |
| `suit/*.sm2d` (10) | they name `gost_man_ru.smms`, which is not in the folder (the folder has `measurements.smms`) |
| `seamtest/*` (3), `susan/mens_shirt_block`, `susan/test_puzzle` | their XML does not validate against Seamly2D's schema (`patternLabel`) |
| `test_grid_10cm_2.sm2d` | schema error (`draftBlock`) |
| `issue_1275/issue_1275.sm2d` | a test of a missing measurement (`height_scapula`), by design |
| `text/text.sm2d`, `text/*.smis`, `text/*.smms` | empty files, by design |

The `broken/*.smis` measurement files (duplicate name, empty name, empty value, a name with a blank)
must fail with a clear message; `tests/test_external_seamly2d.py` checks each.

## One change made for the oracle run

`all_tools_pattern/alltools_pattern.sm2d` has a background image whose path is on its author's Windows
disk (`D:/Github/...`). Seamly2D stops on a dialog when it cannot find an image, so `oracle_upgrade.sh`
points a temporary copy at the logo next to the file, and puts the original path back in the upgraded copy.
