# Landmark sheet

Names for the points and lines of the basic pattern set, for pattern makers to confirm or correct.

- `basic-set-landmarks.xlsx` is the sheet for pattern makers: one tab per piece, a picture, and two tables. The first has a row per outline point or curve (red numbers on the picture). The second, "Not on the outline", has a row per dart apex, the bust point, guide line (waist, hip, bust, knee) and centre-front or centre-back line (blue marks i1, i2 ... on the picture). The yellow columns are theirs to fill in.
- "Also named (same object)": where one Seamly2D object carries two names (a point two pieces share, one long curve cut into several rows, one guide line two pieces use), every row that shares it shows the others' names.
- Darts are named the same way everywhere: `<where>_dart<N>_leg_a`, `_leg_b`, `_apex` (inside the piece; a fish dart has `_apex_upper` and `_apex_lower`) and `_cap` (the bump in the outline of the basic piece), for example `skirt_back.waist_dart1_cap`.
- Sleeve points are named front or back (`sleeve.cap_notch_front`).
- The `Seam pairs` tab is where pattern makers say which edges are sewn to which (by the piece tabs' numbers); the seam-length check will read it.
- `proposed_names.yaml` (outline) and `proposed_internal.yaml` (not on the outline) hold our best guesses (name, confidence, reason). Every entry is **proposed and unverified**; nothing may use a name until a pattern maker has confirmed it.
- Rebuild the sheet with `uv run python scripts/make_landmark_sheet.py` (outline rows come from `scripts/landmark_rows.py`, internal rows from `scripts/landmark_internal.py`, which also checks each proposal against the basic set: labels exist, a level line joins two points at one height, a vertical line two points at one x, an apex is where dash-dot lines meet).
- Asked for but not drawn in the basic set (listed on the Read me tab): a bust point (the nearest candidate is `bodice_front.BP` = C23), a guide line for the trousers back's waist.

**The sheet has not been sent to anyone.** Do not send it without Kasi's word.
