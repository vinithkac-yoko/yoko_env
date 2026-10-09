"""SVG render and landmarks."""

from __future__ import annotations

from pathlib import Path

import pytest
from defusedxml import ElementTree as SafeET
from yoko_engine.evaluator import evaluate
from yoko_engine.landmarks import Landmarks
from yoko_engine.model import DraftBlock, Obj, Pattern
from yoko_io.landmarks import read_landmarks
from yoko_io.render import render_svg
from yoko_io.seamly import read_measurements, read_pattern

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def small(*objs: Obj) -> Pattern:
    return Pattern("cm", "0.6.8", "m", (), (DraftBlock("b", tuple(objs)),))


def o(id_: int, kind: str, tag: str = "point", **attrs: str) -> Obj:
    return Obj(id_, tag, kind, tuple(attrs.items()))


ORIGIN = o(1, "single", name="A", x="1", y="1")


def test_basic_set_renders_every_point_and_curve() -> None:
    p = read_pattern(FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d")
    t = read_measurements(FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms")
    ev = evaluate(p, t.values())
    svg = render_svg(p, ev)
    root = SafeET.fromstring(svg)  # well-formed
    assert root.tag.endswith("svg")
    assert svg.count("<circle") == 302
    assert svg.count("<polyline") == 37
    assert svg.count("<text") == 302
    assert svg.count("<line") > 100
    assert render_svg(p, ev, labels=False).count("<text") == 0


def test_line_type_none_draws_no_line_but_still_draws_the_point() -> None:
    solid = small(
        ORIGIN,
        o(2, "endLine", name="B", basePoint="1", length="5", angle="0", lineType="solidLine"),
    )
    none = small(
        ORIGIN, o(2, "endLine", name="B", basePoint="1", length="5", angle="0", lineType="none")
    )
    a = render_svg(solid, evaluate(solid, {}))
    b = render_svg(none, evaluate(none, {}))
    assert a.count("<line") == 1
    assert b.count("<line") == 0
    assert a.count("<circle") == b.count("<circle") == 2


def test_each_tool_draws_the_line_seamly2d_draws() -> None:
    pat = small(
        ORIGIN,
        o(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
        o(3, "endLine", name="C", basePoint="1", length="10", angle="90"),
        o(4, "alongLine", name="D", firstPoint="1", secondPoint="2", length="2"),
        o(5, "intersectXY", name="E", firstPoint="2", secondPoint="3"),
        o(6, "pointOfContact", name="F", center="1", firstPoint="2", secondPoint="3", radius="8"),
        o(7, "line", tag="line", firstPoint="2", secondPoint="3", lineType="dotLine"),
    )
    svg = render_svg(pat, evaluate(pat, {}))
    # endLine x2, alongLine x1, intersectXY x2, explicit line x1; pointOfContact draws none
    assert svg.count("<line") == 6


def test_focus_zooms_the_view_without_hiding_anything() -> None:
    pat = small(
        ORIGIN,
        o(2, "endLine", name="B", basePoint="1", length="50", angle="0"),
        o(3, "endLine", name="C", basePoint="2", length="1", angle="0"),
    )
    ev = evaluate(pat, {})
    whole = render_svg(pat, ev)
    zoomed = render_svg(pat, ev, focus_ids={2, 3})
    assert whole.count("<circle") == zoomed.count("<circle") == 3
    assert whole.split('viewBox="')[1].split('"')[0] != zoomed.split('viewBox="')[1].split('"')[0]


def test_labels_are_escaped() -> None:
    pat = small(o(1, "single", name="<A&B>", x="1", y="1"))
    svg = render_svg(pat, evaluate(pat, {}))
    SafeET.fromstring(svg)
    assert "&lt;A&amp;B&gt;" in svg


# -- landmarks -------------------------------------------------------------------------------------
YAML = """
version: 1
landmarks:
  bodice_front.origin: {label: A}
  bodice_front.shoulder: {id: 2, note: "best guess, medium"}
"""


def test_landmarks_resolve_by_label_and_id() -> None:
    pat = small(ORIGIN, o(2, "endLine", name="B", basePoint="1", length="5", angle="0"))
    ev = evaluate(pat, {})
    marks = read_landmarks(YAML)
    resolved, issues = marks.resolve(ev)
    assert issues == []
    assert resolved == {"bodice_front.origin": 1, "bodice_front.shoulder": 2}
    assert marks.label_for("bodice_front.shoulder", ev) == "B"
    assert marks.label_for("nope.nothing", ev) is None
    assert marks.names() == ("bodice_front.origin", "bodice_front.shoulder")


def test_unresolved_landmarks_are_reported() -> None:
    ev = evaluate(small(ORIGIN), {})
    resolved, issues = read_landmarks(YAML).resolve(ev)
    assert resolved == {"bodice_front.origin": 1}
    assert [i.code for i in issues] == ["landmark_unresolved"]
    assert issues[0].field == "bodice_front.shoulder"


def test_landmarks_can_name_curves() -> None:
    pat = small(
        ORIGIN,
        o(2, "endLine", name="B", basePoint="1", length="10", angle="0"),
        o(3, "endLine", name="C", basePoint="1", length="20", angle="0"),
        o(4, "endLine", name="D", basePoint="1", length="30", angle="0"),
    )
    marks = read_landmarks("version: 1\nlandmarks:\n  skirt_front.hem: {label: B}\n")
    resolved, _ = marks.resolve(evaluate(pat, {}))
    assert resolved["skirt_front.hem"] == 2


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("version: 2\nlandmarks: {}\n", "unsupported landmarks version"),
        ("version: 1\nlandmarks: []\n", "must be a mapping"),
        ("version: 1\nlandmarks:\n  Bad Name: {label: A}\n", "bad landmark name"),
        ("version: 1\nlandmarks:\n  bodice.x: {label: A, id: 1}\n", "exactly one"),
        ("version: 1\nlandmarks:\n  bodice.x: {}\n", "exactly one"),
        ("version: 1\nlandmarks:\n  bodice.x: A\n", "target must be a mapping"),
        ("- just a list\n", "must be a mapping"),
    ],
)
def test_bad_landmark_files_are_refused_with_a_reason(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_landmarks(text)


def test_landmarks_file_can_be_read_from_disk(tmp_path: Path) -> None:
    f = tmp_path / "x.landmarks.yaml"
    f.write_text(YAML)
    assert isinstance(read_landmarks(f), Landmarks)
    assert read_landmarks(str(f)).names() == ("bodice_front.origin", "bodice_front.shoulder")
