# Landmark sheet

Names for the outline points of the basic pattern set, for pattern makers to confirm or correct.

- `basic-set-landmarks.xlsx` is the sheet to hand to pattern makers: one tab per piece, a picture with numbered circles, and a row per outline point or curve. The yellow columns are theirs to fill in.
- The `Seam pairs` tab is where pattern makers say which edges are sewn to which (by the piece tabs' numbers); the seam-length check will read it.
- `proposed_names.yaml` holds our best guesses (name, confidence, reason). Every entry is **proposed and unverified**; nothing may use a name until a pattern maker has confirmed it.
- Rebuild the sheet with `uv run python scripts/make_landmark_sheet.py` (rows come from `scripts/landmark_rows.py`, which reads the basic set and its evaluated outlines).

Do not send the sheet to anyone without Kasi's word.
