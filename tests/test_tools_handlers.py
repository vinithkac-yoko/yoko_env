"""Variables, pieces, blocks, undo, the read tools and the library tools."""

from __future__ import annotations

import base64
from dataclasses import replace
from pathlib import Path

import pytest
from yoko_engine.model import DraftBlock
from yoko_engine.session import PatternSession
from yoko_io.library import DirectoryLibrary
from yoko_io.seamly import blank_pattern
from yoko_tools.runtime import Toolbox
from yoko_tools.spec import all_tools

ROOT = Path(__file__).resolve().parents[1]
SPECS = all_tools(ROOT / "config/tools")


def square_box() -> Toolbox:
    box = Toolbox(PatternSession(blank_pattern("cm"), {"waist": 70.0}), SPECS)
    calls = [
        ("point_origin", {"label": "A", "x": 10, "y": 10}),
        ("set_variable", {"name": "#side", "formula": "waist/10", "description": "square side"}),
        (
            "point_at_distance_angle",
            {"label": "B", "base_point": "A", "length": "#side", "angle": "0"},
        ),
        (
            "point_at_distance_angle",
            {"label": "C", "base_point": "B", "length": "#side", "angle": "270"},
        ),
        (
            "point_at_distance_angle",
            {"label": "D", "base_point": "A", "length": "#side", "angle": "270"},
        ),
    ]
    for name, args in calls:
        r = box.call(name, args)
        assert r["ok"], (name, r)
    return box


def test_variables_are_created_changed_and_protected() -> None:
    box = square_box()
    assert box.call("set_variable", {"name": "#side", "formula": "8"})["ok"]
    assert box.call("measure", {"from": "A", "to": "B"})["data"]["distance"] == pytest.approx(8)
    bad = box.call("set_variable", {"name": "side", "formula": "8"})
    assert bad["error"]["code"] == "invalid_name"
    used = box.call("delete_variable", {"name": "#side"})
    assert used["error"]["code"] == "has_dependents"


def test_a_piece_can_be_made_renamed_changed_and_deleted() -> None:
    box = square_box()
    nodes = [{"object": n} for n in ("A", "B", "C", "D")]
    made = box.call("add_piece", {"name": "Square", "nodes": nodes})
    assert made["ok"], made
    assert box.call("get_state", {"scope": "pieces"})["data"]["pieces"] == ["Square"]
    assert box.call("set_piece", {"piece": "Square", "name": "Block"})["ok"]
    assert not box.call("set_piece", {"piece": "Nope", "name": "x"})["ok"]
    assert box.call("set_piece", {"piece": "Block", "nodes": nodes[:3]})["ok"]
    assert box.call("set_piece", {"piece": "Block"})["error"]["code"] == "nothing_to_change"
    # a point that is part of the piece cannot be deleted
    stuck = box.call("delete_point_at_distance_angle", {"target": "C"})
    assert stuck["error"]["code"] == "used_by_piece"
    assert box.call("delete_piece", {"piece": "Block"})["ok"]
    assert box.call("get_state", {"scope": "pieces"})["data"]["pieces"] == []
    unknown = box.call("delete_piece", {"piece": "Block"})
    assert unknown["error"]["code"] == "unknown_piece" and "none yet" in unknown["error"]["hint"]


def test_a_piece_node_must_be_a_point_or_a_curve() -> None:
    box = square_box()
    line = box.call("line", {"first_point": "A", "second_point": "B"})
    line_id = line["created"][0]["id"]
    nodes = [{"object": "A"}, {"object": "B"}, {"object": f"#{line_id}"}]
    r = box.call("add_piece", {"name": "Bad", "nodes": nodes})
    assert r["error"]["code"] == "wrong_kind"


def test_blocks_and_undo() -> None:
    box = square_box()
    assert box.call("add_block", {"name": "Facing"})["ok"]
    assert box.call("rename_block", {"block": "Facing", "name": "Neck facing"})["ok"]
    assert box.call("get_state", {})["data"]["blocks"][-1] == "Neck facing"
    assert box.call("delete_block", {"block": "Neck facing"})["ok"]
    assert not box.call("delete_block", {"block": "Pattern piece 1"})["ok"]
    before = box.session.state_hash()
    box.call("point_origin", {"label": "Z", "x": 1, "y": 1})
    assert box.call("undo", {})["ok"]
    assert box.session.state_hash() == before


def test_the_read_tools_answer_without_changing_anything() -> None:
    box = square_box()
    before = box.session.state_hash()
    state = box.call("get_state", {})["data"]
    assert state["points"] == 4 and state["errors"] == 0 and state["variables"] == 1
    assert box.call("get_state", {"scope": "variables"})["data"]["variables"][0][
        "value"
    ] == pytest.approx(7)
    assert box.call("get_state", {"scope": "problems"})["data"]["count"] == 0
    obj = box.call("get_object", {"object": "B"})["data"]
    assert (
        obj["tool"] == "point_at_distance_angle"
        and obj["edit_with"] == "edit_point_at_distance_angle"
    )
    assert obj["built_from"] == ["A"] and obj["used_by"] == ["C"]
    assert obj["x_mm"] == pytest.approx(170)
    near = box.call("find_objects", {"near": "A", "within_mm": 75})["data"]
    assert sorted(o["name"] for o in near["objects"]) == ["B", "D"]
    assert [o["name"] for o in box.call("find_objects", {"text": "c"})["data"]["objects"]] == ["C"]
    assert box.call("dependents", {"object": "A"})["data"]["used_by"]
    assert box.call("dependencies", {"object": "C"})["data"]["built_from"][0]["name"] in (
        "B",
        "#side",
    )
    m = box.call("measure", {"from": "A", "to": "C"})["data"]
    assert m["distance"] == pytest.approx(7 * 2**0.5, rel=1e-6) and m["angle_deg"] == pytest.approx(
        315
    )
    names = {
        x["name"]: x["value"] for x in box.call("list_measurements", {})["data"]["measurements"]
    }
    assert names == {"waist": 70.0}
    assert box.session.state_hash() == before


def test_measuring_a_curve_and_asking_for_a_second_point() -> None:
    box = square_box()
    arc = box.call(
        "arc_radius", {"center": "A", "radius": "5", "start_angle": "0", "end_angle": "180"}
    )
    name = arc["created"][0]["name"]
    assert box.call("measure", {"from": name})["data"]["length"] == pytest.approx(
        5 * 3.14159265, abs=1e-3
    )
    assert box.call("measure", {"from": "A"})["error"]["code"] == "need_second_point"


def test_render_gives_an_svg_and_a_png() -> None:
    box = square_box()
    svg = box.call("render", {})["data"]
    assert svg["svg"].startswith("<svg")
    png = box.call("render", {"format": "png", "width_px": 300})["data"]
    assert base64.b64decode(png["base64"])[:8] == b"\x89PNG\r\n\x1a\n"


def library_box() -> Toolbox:
    library = DirectoryLibrary(ROOT / "library", ROOT / "fixtures")
    _, base, table = library.load("aldrich-womens-6th-basic")
    pattern = replace(base, variables=(), blocks=(DraftBlock("Draft block 1", ()),))
    return Toolbox(PatternSession(pattern, table), SPECS, library=library)


def test_the_library_tools_search_load_and_copy_a_piece() -> None:
    box = library_box()
    found = box.call("search_library", {"brief": "bodice", "tags": ["basic"]})["data"]["results"]
    assert [r["id"] for r in found] == ["aldrich-womens-6th-basic"]
    assert box.call("search_library", {"brief": "dress"})["data"]["results"] == []
    assert not box.call("copy_piece_from", {"pattern": "aldrich-womens-6th-basic", "piece": "x"})[
        "ok"
    ]
    opened = box.call("load_pattern", {"pattern": "aldrich-womens-6th-basic"})
    assert opened["ok"] and "D - 1 Piece Sleeve" in opened["data"]["pieces"]
    copied = box.call(
        "copy_piece_from", {"pattern": "aldrich-womens-6th-basic", "piece": "D - 1 Piece Sleeve"}
    )
    assert copied["ok"], copied
    assert box.call("get_state", {"scope": "pieces"})["data"]["pieces"] == ["D - 1 Piece Sleeve"]
    again = box.call(
        "copy_piece_from", {"pattern": "aldrich-womens-6th-basic", "piece": "D - 1 Piece Sleeve"}
    )
    assert again["error"]["code"] == "label_conflict"
    assert box.call("load_pattern", {"pattern": "nope"})["error"]["code"] == "unknown_pattern"


def test_library_tools_need_a_library() -> None:
    box = square_box()
    assert box.call("search_library", {})["error"]["code"] == "not_available"


def test_a_curve_can_be_set_to_a_target_length_by_editing_it() -> None:
    """What the sleeve-cap procedure relies on: edit_curve_spline with a target length."""
    box = square_box()
    made = box.call(
        "curve_spline",
        {
            "start": "A",
            "end": "B",
            "start_angle": "60",
            "end_angle": "120",
            "start_handle": "2",
            "end_handle": "2",
        },
    )
    name = made["created"][0]["name"]
    r = box.call("edit_curve_spline", {"target": name, "length_mode": 3, "target_length": "12.5"})
    assert r["ok"], r
    assert box.call("measure", {"from": name})["data"]["length"] == pytest.approx(12.5, abs=0.006)


# ---- sections ---------------------------------------------------------------------------------


def basic_set_box() -> Toolbox:
    """The basic set as a working copy (the library's own session is locked)."""
    library = DirectoryLibrary(ROOT / "library", ROOT / "fixtures")
    _, pattern, table = library.load("aldrich-womens-6th-basic")
    return Toolbox(PatternSession(pattern, table), SPECS, library=library)


def test_a_section_of_a_piece_stands_for_the_outline_between_two_landmarks() -> None:
    from yoko_engine.landmarks import Landmarks
    from yoko_tools.sections import section_ids, short_name

    box = basic_set_box()
    assert (
        short_name("C - Bodice Front") == "bodice_front"
        and short_name("D - 1 Piece Sleeve") == "1_piece_sleeve"
    )
    piece = next(
        p
        for _, p, _ in __import__("yoko_engine.pieces_edit", fromlist=["x"]).pieces_of(
            box.session.pattern
        )
        if p.get("name") == "A - Skirt Back"
    )
    labels = [g.label for g in box.session.evaluation.points.values() if g.label]
    # use the first and fourth point nodes of the skirt back outline
    from yoko_engine.pieces import piece_nodes

    modeling = next(
        m
        for _, p, m in __import__("yoko_engine.pieces_edit", fromlist=["x"]).pieces_of(
            box.session.pattern
        )
        if p is piece
    )
    copies = {m.get("id"): int(m.get("idObject") or 0) for m in modeling.children}
    nodes = piece_nodes(piece)
    ev = box.session.evaluation
    point_nodes = [copies[str(n.id)] for n in nodes if n.type == "NodePoint"]
    first, fourth = point_nodes[0], point_nodes[3]
    box.landmarks = Landmarks.from_mapping(
        {
            "version": 1,
            "landmarks": {
                "skirt_back.one": {"id": first},
                "skirt_back.four": {"id": fourth},
            },
        }
    )
    ids = section_ids(box, "skirt_back.section(skirt_back.one, skirt_back.four)", "sources")
    assert ids[0] == first and ids[-1] == fourth
    assert [i for i in ids if i in ev.points] == point_nodes[
        :4
    ]  # four points; the curves between come too
    assert len(ids) > 4  # a curve node sits between points
    other = section_ids(box, "A - Skirt Back.section(skirt_back.four, skirt_back.one)", "sources")
    assert set(ids) | set(other) == {copies[str(n.id)] for n in nodes}
    plus = section_ids(
        box,
        "#" + str(piece.get("id")) + ".section(skirt_back.one, skirt_back.four) - skirt_back.four",
        "s",
    )
    assert fourth not in plus and len(plus) == len(ids) - 1
    assert labels


def test_a_section_is_used_wherever_a_list_of_objects_is() -> None:
    box = basic_set_box()
    # move the section: the first two point nodes of a piece, by landmark label
    from yoko_engine.pieces import piece_nodes
    from yoko_engine.pieces_edit import pieces_of

    _, piece, modeling = next(
        t for t in pieces_of(box.session.pattern) if t[1].get("name") == "A - Skirt Back"
    )
    copies = {m.get("id"): int(m.get("idObject") or 0) for m in modeling.children}
    pts = [copies[str(n.id)] for n in piece_nodes(piece) if n.type == "NodePoint"][:2]
    ev = box.session.evaluation
    a, b = ev.points[pts[0]].label, ev.points[pts[1]].label
    r = box.call(
        "move",
        {
            "length": "1",
            "angle": "0",
            "sources": [f"A - Skirt Back.section({a}, {b})"],
            "suffix": "_t",
        },
    )
    assert r["ok"], r
    assert {c["name"] for c in r["created"] if c["kind"] == "point"} >= {f"{a}_t", f"{b}_t"}


def test_a_bad_section_says_what_is_wrong() -> None:
    box = basic_set_box()
    r = box.call(
        "move", {"length": "1", "angle": "0", "sources": ["Nowhere.section(A, B)"], "suffix": "_t"}
    )
    assert r["error"]["code"] == "unknown_piece" and "A - Skirt Back" in r["error"]["hint"]
    ev = box.session.evaluation
    outside = next(
        g.label
        for g in ev.points.values()
        if g.label and g.label.startswith("A") and g.label != "A"
    )
    r2 = box.call(
        "move",
        {
            "length": "1",
            "angle": "0",
            "sources": [f"A - Skirt Back.section({outside}, {outside}7)"],
            "suffix": "_t",
        },
    )
    assert not r2["ok"]


def test_union_pieces_joins_two_pieces_through_the_tool() -> None:
    from yoko_engine.pieces import NODE_POINT, piece_nodes
    from yoko_engine.pieces_edit import pieces_of

    box = basic_set_box()

    def corners(name: str) -> list[str]:
        for _, piece, modeling in pieces_of(box.session.pattern):
            if piece.get("name") == name:
                src = {m.get("id"): int(m.get("idObject") or 0) for m in modeling.children}
                ev = box.session.evaluation
                return [
                    ev.points[src[str(n.id)]].label
                    for n in piece_nodes(piece)
                    if n.type == NODE_POINT
                ]
        raise AssertionError(name)

    a, b = corners("A - Skirt Back"), corners("A - Skirt Front")
    r = box.call(
        "union_pieces",
        {
            "first_piece": "A - Skirt Back",
            "first_corner": a[2],
            "second_piece": "A - Skirt Front",
            "second_corner": b[5],
            "name": "Skirt",
        },
    )
    assert r["ok"], r
    assert "Skirt" in box.call("get_state", {"scope": "pieces"})["data"]["pieces"]
    bad = box.call(
        "union_pieces",
        {
            "first_piece": "Skirt",
            "first_corner": a[0],
            "second_piece": "Skirt",
            "second_corner": a[1],
        },
    )
    assert bad["error"]["code"] == "same_piece"
