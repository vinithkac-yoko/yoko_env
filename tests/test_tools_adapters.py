"""The adapters: every tool in every format, every call parsed back to itself."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from yoko_tools.adapters import (
    AdapterError,
    ToolCall,
    from_anthropic_call,
    from_openai_call,
    parse_dsl,
    parse_dsl_lines,
    render_dsl,
    to_anthropic,
    to_anthropic_call,
    to_openai,
    to_openai_call,
    to_text,
)
from yoko_tools.spec import all_tools

ROOT = Path(__file__).resolve().parents[1]
SPECS = all_tools(ROOT / "config/tools")
EXAMPLES = [(s.name, ex.call) for s in SPECS.values() for ex in s.examples]


def test_tool_lists_have_what_each_api_needs() -> None:
    for tool in to_anthropic(SPECS):
        assert set(tool) == {"name", "description", "input_schema"}
        assert tool["input_schema"]["type"] == "object"
        assert not any(k.startswith("x-") for k in json.dumps(tool["input_schema"]).split('"'))
    for tool in to_openai(SPECS):
        assert tool["type"] == "function" and tool["function"]["parameters"]["type"] == "object"
    assert [t["name"] for t in to_anthropic(SPECS, ["line", "undo"])] == ["line", "undo"]
    text = to_text(SPECS, ["point_origin"])
    assert text.startswith("point_origin(label: string, x: number, y: number)")


@pytest.mark.parametrize(
    ("name", "args"), EXAMPLES, ids=[f"{n}-{i}" for i, (n, _) in enumerate(EXAMPLES)]
)
def test_every_example_call_survives_every_format(name: str, args: dict[str, Any]) -> None:
    call = ToolCall(name, args, "call_1")
    assert from_anthropic_call(to_anthropic_call(call)) == call
    assert from_openai_call(to_openai_call(call)) == call
    assert parse_dsl(render_dsl(call)).name == name
    assert dict(parse_dsl(render_dsl(call)).args) == args


text_values = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=0, max_size=40)
json_values = st.recursive(
    st.one_of(
        text_values,
        st.integers(-(10**6), 10**6),
        st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False),
        st.booleans(),
    ),
    lambda inner: (
        st.lists(inner, max_size=4)
        | st.dictionaries(st.from_regex(r"[a-z][a-z_]{0,8}", fullmatch=True), inner, max_size=3)
    ),
    max_leaves=10,
)
arg_dicts = st.dictionaries(
    st.from_regex(r"[a-z][a-z0-9_]{0,12}", fullmatch=True), json_values, max_size=6
)


@settings(max_examples=300, deadline=None)
@given(args=arg_dicts)
def test_any_arguments_survive_the_text_dsl_the_json_formats_and_back(args: dict[str, Any]) -> None:
    call = ToolCall("some_tool", args)
    line = render_dsl(call)
    assert "\n" not in line
    assert dict(parse_dsl(line).args) == args
    assert dict(from_openai_call(to_openai_call(call)).args) == args
    assert dict(from_anthropic_call(to_anthropic_call(call)).args) == args


def test_awkward_strings_in_a_formula_are_safe() -> None:
    nasty = 'if(a>1; "x, y)"; \\n) # (z=1), {w}'
    call = ToolCall("point_origin", {"label": nasty, "x": 1.5, "y": 2})
    assert dict(parse_dsl(render_dsl(call)).args)["label"] == nasty


@pytest.mark.parametrize(
    "text",
    [
        "",
        "no parens",
        "(x=1)",
        "Name(x=1)",
        "t(x=1",
        "t(x)",
        "t(x=1,)",
        "t(x=1, x=2)",
        "t(x='a')",
        "t(1=2)",
        't(x="a)',
    ],
)
def test_malformed_dsl_is_refused_with_a_reason(text: str) -> None:
    with pytest.raises(AdapterError):
        parse_dsl(text)


def test_several_lines_and_comments() -> None:
    calls = parse_dsl_lines('# plan\nundo()\n\npoint_origin(label="A", x=1, y=2)\n')
    assert [c.name for c in calls] == ["undo", "point_origin"]


def test_bad_json_formats_are_refused() -> None:
    with pytest.raises(AdapterError):
        from_openai_call({"function": {"name": "x", "arguments": "{not json"}})
    with pytest.raises(AdapterError):
        from_openai_call({"function": {"name": "x", "arguments": "[1]"}})
    with pytest.raises(AdapterError):
        from_anthropic_call({"type": "text", "text": "hi"})


def test_a_dsl_line_runs_as_a_tool_call() -> None:
    from yoko_engine.session import PatternSession
    from yoko_io.seamly import blank_pattern
    from yoko_tools.runtime import Toolbox

    box = Toolbox(PatternSession(blank_pattern("cm"), {}), SPECS)
    for line in (
        'point_origin(label="A", x=10, y=10)',
        'point_at_distance_angle(label="B", base_point="A", length="12", angle="0")',
    ):
        call = parse_dsl(line)
        assert box.call(call.name, call.args)["ok"], line
    assert box.session.evaluation.point_mm("B") == pytest.approx((220.0, 100.0))
