"""Tool files and the runtime: every file is valid, and calls build the pattern."""

from __future__ import annotations

from pathlib import Path

import pytest
from yoko_engine.model import DraftBlock, Pattern
from yoko_engine.session import PatternSession
from yoko_tools.runtime import Toolbox
from yoko_tools.spec import all_tools

ROOT = Path(__file__).resolve().parents[1]
SPECS = all_tools(ROOT / "config/tools")


def empty_box() -> Toolbox:
    pattern = Pattern("cm", "0.7.5", "", (), (DraftBlock("Draft", ()),))
    return Toolbox(PatternSession(pattern, {"waist": 70.0}), SPECS)


def test_every_tool_file_loads_and_has_examples_that_validate() -> None:
    written = [s for s in SPECS.values() if s.derived_from is None]
    simple = [s for s in written if (s.engine or {}).get("builder") == "simple"]
    assert len(SPECS) == len(written) + 2 * len(simple)  # an edit and a delete for each simple one
    for spec in SPECS.values():
        assert spec.description and spec.examples
        spec.json_schema()
        spec.model()
        assert len(spec.digest()) == 64


def test_a_few_calls_build_points_with_the_geometry_asked_for() -> None:
    box = empty_box()
    assert box.call("point_origin", {"label": "A", "x": 10, "y": 10})["ok"]
    r = box.call(
        "point_at_distance_angle",
        {"label": "B", "base_point": "A", "length": "waist/10", "angle": "0"},
    )
    assert r["ok"], r
    b = r["created"][0]
    assert b["name"] == "B" and b["kind"] == "point"
    assert b["x_mm"] == pytest.approx(10 * 10 + 7 * 10, abs=1e-3)  # 10 cm + waist/10 = 7 cm
    r2 = box.call(
        "point_perpendicular",
        {"label": "C", "first_point": "A", "second_point": "B", "length": "5"},
    )
    assert r2["ok"], r2
    assert r2["created"][0]["y_mm"] == pytest.approx(100 - 50, abs=1e-3)  # perpendicular, 5 cm up


def built_box() -> Toolbox:
    box = empty_box()
    for call in (
        ("point_origin", {"label": "A", "x": 10, "y": 10}),
        (
            "point_at_distance_angle",
            {"label": "B", "base_point": "A", "length": "20", "angle": "0"},
        ),
        (
            "point_along_line",
            {"label": "C", "first_point": "A", "second_point": "B", "length": "5"},
        ),
        ("line", {"first_point": "A", "second_point": "B"}),
    ):
        assert box.call(*call)["ok"], call
    return box


def test_a_bad_name_says_what_was_meant() -> None:
    box = built_box()
    r = box.call(
        "point_along_line", {"label": "D", "first_point": "AA", "second_point": "B", "length": "1"}
    )
    assert not r["ok"]
    err = r["error"]
    assert err["code"] == "unknown_reference" and err["field"] == "first_point"
    assert "A" in err["hint"]
    assert r["created"] == [] and r["diff"] == {}


def test_arguments_are_checked_before_anything_happens() -> None:
    box = built_box()
    before = box.session.state_hash()
    bad = [
        ("point_origin", {"label": "Z", "x": "far", "y": 1}),
        ("point_origin", {"label": "Z", "x": 1}),
        ("point_origin", {"label": "Z", "x": 1, "y": 1, "colour": "red"}),
        ("point_origin", {"label": "Z", "x": 10**9, "y": 1}),
        (
            "point_along_line",
            {"label": "Z", "first_point": "A", "second_point": "B", "length": "1" * 600},
        ),
        ("no_such_tool", {}),
    ]
    for name, args in bad:
        r = box.call(name, args)
        assert not r["ok"], (name, args)
        assert r["error"]["code"] in ("invalid_arguments", "unknown_tool")
    assert box.session.state_hash() == before


def test_a_curve_is_not_a_point_and_the_other_way_round() -> None:
    box = built_box()
    made = box.call(
        "curve_spline",
        {
            "start": "A",
            "end": "B",
            "start_angle": "20",
            "end_angle": "160",
            "start_handle": "3",
            "end_handle": "3",
        },
    )
    name = made["created"][0]["name"]
    r = box.call(
        "point_along_line", {"label": "D", "first_point": name, "second_point": "B", "length": "1"}
    )
    assert r["error"]["code"] == "wrong_kind" and r["error"]["field"] == "first_point"
    r2 = box.call("cut_curve", {"label": "D", "curve": "A", "length": "1"})
    assert r2["error"]["code"] == "wrong_kind"


def test_edit_changes_a_formula_and_everything_after_it_moves() -> None:
    box = built_box()
    r = box.call("edit_point_at_distance_angle", {"target": "B", "length": "30"})
    assert r["ok"], r
    assert r["diff"]["moved"]["count"] >= 1  # B moved (C is 5 cm from A and stays)
    ev = box.session.evaluation
    assert next(g for g in ev.points.values() if g.label == "B").x_mm == pytest.approx(100 + 300)


def test_edit_and_delete_check_how_the_object_was_made() -> None:
    box = built_box()
    wrong = box.call("edit_point_along_line", {"target": "B", "length": "1"})
    assert wrong["error"]["code"] == "wrong_tool"
    nothing = box.call("edit_point_along_line", {"target": "C"})
    assert nothing["error"]["code"] == "nothing_to_change"
    # B is used by C and by the line: it cannot go
    used = box.call("delete_point_at_distance_angle", {"target": "B"})
    assert used["error"]["code"] == "has_dependents"
    # C is a leaf
    gone = box.call("delete_point_along_line", {"target": "C"})
    assert gone["ok"] and len(gone["deleted"]) == 1


def test_lines_are_reached_by_their_id() -> None:
    box = built_box()
    line_id = next(o.id for o in box.session.pattern.objects() if o.tag == "line")
    assert box.call("delete_line", {"target": f"#{line_id}"})["ok"]
    assert not box.call("delete_line", {"target": f"#{line_id}"})["ok"]


def test_the_common_result_shape() -> None:
    box = built_box()
    ok = box.call("point_origin", {"label": "Z", "x": 1, "y": 1})
    bad = box.call("point_origin", {"label": "A", "x": 1, "y": 1})  # label already used
    for r in (ok, bad):
        assert {"ok", "created", "changed", "deleted", "warnings", "diff"} <= set(r)
    assert bad["error"]["code"] == "duplicate_label"
    assert set(bad["error"]) == {"code", "field", "message", "hint"}


def test_a_landmark_name_works_wherever_a_label_does() -> None:
    from yoko_engine.landmarks import Landmarks

    box = built_box()
    box.landmarks = Landmarks.from_mapping(
        {"version": 1, "landmarks": {"test_piece.start": {"label": "A"}}}
    )
    r = box.call(
        "point_along_line",
        {"label": "D", "first_point": "test_piece.start", "second_point": "B", "length": "2"},
    )
    assert r["ok"], r


def test_the_tool_catalog_for_the_pattern_makers_is_up_to_date() -> None:
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts/tool_catalog.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
