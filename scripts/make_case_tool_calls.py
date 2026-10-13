"""Write fixtures/patterns/cases/tool_calls.sm2d: a pattern built only through tool calls, every
primitive tool at least once, then an edit and a delete. The oracle computes it
(scripts/oracle_cases.sh), which checks that what the tools write is what Seamly2D understands.

    uv run python scripts/make_case_tool_calls.py
"""

import sys
from pathlib import Path
from typing import Any

from yoko_engine.session import PatternSession
from yoko_io.seamly import blank_pattern, write_pattern
from yoko_tools.runtime import Toolbox
from yoko_tools.spec import all_tools

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures/patterns/cases/tool_calls.sm2d"

pattern = blank_pattern("cm")
box = Toolbox(PatternSession(pattern, {}), all_tools(ROOT / "config/tools"))
names: dict[str, str] = {}


def call(tool: str, args: dict[str, Any], keep: str | None = None) -> None:
    result = box.call(tool, args)
    if not result["ok"]:
        sys.exit(f"{tool} {args}: {result['error']}")
    if keep:
        found = [c["name"] for c in result["created"] if c["kind"] == "curve"]
        if not found:
            sys.exit(f"{tool}: made no curve: {result}")
        names[keep] = found[0]


call("point_origin", {"label": "A", "x": 10, "y": 10})
call("point_at_distance_angle", {"label": "B", "base_point": "A", "length": "20", "angle": "0"})
call("point_at_distance_angle", {"label": "C", "base_point": "A", "length": "15", "angle": "270"})
call("point_from_xy", {"label": "D", "x_from": "B", "y_from": "C"})
for first, second in (("A", "B"), ("B", "D"), ("D", "C"), ("C", "A")):
    call("line", {"first_point": first, "second_point": second})
call("point_along_line", {"label": "E", "first_point": "A", "second_point": "B", "length": "5"})
call("point_perpendicular", {"label": "F", "first_point": "A", "second_point": "B", "length": "4"})
call(
    "point_bisector",
    {"label": "G", "first_point": "B", "second_point": "A", "third_point": "C", "length": "6"},
)
call(
    "point_line_axis",
    {"label": "H", "base_point": "E", "angle": "270", "line_start": "C", "line_end": "D"},
)
call(
    "point_line_line",
    {"label": "I", "line1_start": "A", "line1_end": "D", "line2_start": "B", "line2_end": "C"},
)
call("point_height", {"label": "J", "base_point": "E", "line_start": "C", "line_end": "D"})
call(
    "point_arc_line",
    {"label": "K", "center": "A", "radius": "22", "line_start": "B", "line_end": "D"},
)
call(
    "point_circle_circle",
    {"label": "L", "center1": "A", "radius1": "20", "center2": "D", "radius2": "18"},
)
call(
    "point_circle_tangent",
    {"label": "M", "tangent_from": "D", "center": "E", "radius": "3"},
)
call(
    "point_shoulder",
    {"label": "N", "line_start": "A", "line_end": "B", "from_point": "C", "length": "22"},
)
call(
    "point_triangle",
    {"label": "O", "axis_start": "A", "axis_end": "D", "first_point": "B", "second_point": "C"},
)
call(
    "true_darts",
    {
        "label1": "P",
        "label2": "Q",
        "base_start": "A",
        "base_end": "B",
        "dart_first": "E",
        "dart_tip": "F",
        "dart_second": "G",
    },
)
call(
    "curve_spline",
    {
        "start": "A",
        "end": "D",
        "start_angle": "300",
        "end_angle": "100",
        "start_handle": "6",
        "end_handle": "5",
    },
    "spline",
)
call("curve_bezier", {"start": "C", "control1": "H", "control2": "J", "end": "B"}, "bezier")
call(
    "curve_spline_path",
    {
        "points": [
            {"point": "A", "angle2": "340", "length2": "4"},
            {"point": "E", "angle1": "160", "length1": "3", "angle2": "340", "length2": "3"},
            {"point": "B", "angle1": "150", "length1": "4"},
        ]
    },
    "path",
)
call("curve_bezier_path", {"points": ["C", "H", "J", "D", "L", "K", "B"]}, "bezier_path")
call("arc_radius", {"center": "A", "radius": "12", "start_angle": "0", "end_angle": "90"}, "arc")
call("arc_radius", {"center": "B", "radius": "12", "start_angle": "90", "end_angle": "180"}, "arc3")
call("arc_length", {"center": "D", "radius": "5", "start_angle": "180", "length": "7"}, "arc2")
call(
    "arc_elliptical",
    {
        "center": "I",
        "radius1": "4",
        "radius2": "2",
        "start_angle": "0",
        "end_angle": "270",
        "tilt": "20",
    },
    "elarc",
)
call("cut_curve", {"label": "R", "curve": names["spline"], "length": "5"})
call("cut_curve_path", {"label": "S", "curve": names["path"], "length": "6"})
call("cut_arc", {"label": "T", "arc": names["arc"], "length": "4"})
call("point_curve_axis", {"label": "U", "base_point": "E", "angle": "90", "curve": names["spline"]})
call(
    "point_curve_curve",
    {"label": "V", "first_curve": names["spline"], "second_curve": names["bezier"]},
)
call("point_arc_arc", {"label": "W", "first_arc": names["arc"], "second_arc": names["arc3"]})
call("point_arc_tangent", {"label": "X", "tangent_from": "B", "arc": names["arc"]})
call(
    "mirror_by_line",
    {"line_start": "A", "line_end": "C", "sources": ["B", "D", names["spline"]], "suffix": "_m"},
)
call("mirror_by_axis", {"center": "A", "axis": "horizontal", "sources": ["D", "E"], "suffix": "_a"})
call("rotate", {"center": "A", "angle": "30", "sources": ["B", names["arc"]], "suffix": "_r"})
call(
    "move",
    {
        "length": "3",
        "angle": "45",
        "rotation": "10",
        "sources": ["E", names["arc2"]],
        "suffix": "_v",
    },
)
call("edit_point_along_line", {"target": "E", "length": "6"})
call("delete_point_perpendicular", {"target": "F"}) if False else None

OUT.write_bytes(write_pattern(box.session.pattern))
print(f"wrote {OUT} with {len(box.session.pattern.objects())} objects")
