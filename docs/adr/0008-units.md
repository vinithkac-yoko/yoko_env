# 0008. Units

Status: accepted (Addendum 1 §1 Q10)

Evaluate every formula in the **pattern's own unit**, exactly as Seamly2D does, and convert only geometry. The UI and tools show cm; the engine stores geometry in mm. The Aldrich pattern and measurement file are both cm.

File-health note (Addendum 1 §1 Q3): `height` is Seamly2D's standard measurement A01 and `size` is G12; both are separate from the table's base size and base height. The Aldrich file has base height 164 but `height` = 166 with `height_increase` = 0, so `#CM` = 166/166 = 1 at every height. We honour that as written and report it; see `docs/FILE_HEALTH.md`.
