# 0003. Display rule

Status: accepted (Addendum 1 §4)

- Draw everything Seamly2D draws, with every group switched on. Group visibility is ignored for display.
- One style for everything. Colours, pen styles and weights are ignored for display (still stored and written back).
- `lineType="none"` means the tool draws **no line**: Seamly2D maps it to `Qt::NoPen` (`src/libs/ifc/ifcdef.cpp`). Draw the point, never invent a line. In the basic set this covers 117 objects.
- The studio canvas and every image sent to a model zoom to the pieces the current plan step touches. This is scoping, not hiding.
- "Scaffolding vs piece outline" exists only as a query.

If layers or visibility cause trouble, stop and ask.
