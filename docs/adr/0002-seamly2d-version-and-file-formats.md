# 0002. Seamly2D version pin and file formats

Status: accepted (Addendum 1 §3)

**Facts, checked against the Seamly2D source (develop branch, 2026-10-07):**
- Latest tag: `v2026.10.5.154` (commit `0627ac315f7b9aae6109e0961a59b98852e7aae0`). Its maximum pattern format is **0.7.5** (`src/libs/ifc/xml/vpatternconverter.h`, `PatternMaxVer`).
- Our basic set: format **0.6.8**, saved by v2023.12.4. Our measurement file: format **0.4.4** (`<vst>`, multisize), saved by v2023.11.20.
- Format changes in between (from the addendum): 0.6.9 `increments` becomes `variables`; 0.7.1 background `images`; 0.7.4 curve `autoSmooth` and `lengthMode`; 0.7.5 `finalMeasurements`. `byGroup` line style exists. Newer Seamly2D opens older files, not the reverse.

**Decisions:**
1. **Pin `v2026.10.5.154`** for the oracle and for the pattern makers.
2. **Read** every pattern format 0.6.8 to 0.7.5 and the matching measurement formats.
3. **Write** back the format version that was read, so the lossless round trip holds per version.
4. Provide an explicit **upgrade 0.6.8 to the pinned format**, verified by the oracle against what the pinned Seamly2D does on open and save.
5. Moving the pin is deliberate: re-run the oracle suite and add an ADR that supersedes this one's pin.

**Consequence for the engine:** the file model keeps `increments` and `variables` as one concept with a per-format name. Plan-amount variables (ADR 0006) are written with whichever name the file's format uses.
