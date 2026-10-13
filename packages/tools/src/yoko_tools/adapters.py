"""Tools in the formats models use, and calls parsed back to one canonical form.

    ToolCall(name, args)  <->  Anthropic `tool_use` block
                          <->  OpenAI `tool_calls` entry
                          <->  one line of the compact text DSL:  name(key=value, ...)

The DSL is for models that only produce text. Values are JSON (strings in double quotes with the
usual escapes), so any argument survives the trip. Every adapter has a round-trip test.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from yoko_tools.spec import ToolSpec

_NAME = re.compile(r"[a-z][a-z0-9_]*")


class AdapterError(ValueError):
    """A model's output could not be read as a tool call."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One call, the same whichever format it came in."""

    name: str
    args: Mapping[str, Any] = field(default_factory=lambda: dict[str, Any]())
    id: str | None = None  # the model API's id for the call, if it has one


# -- tool lists --------------------------------------------------------------------------------
def _pick(specs: Mapping[str, ToolSpec], names: Iterable[str] | None) -> list[ToolSpec]:
    if names is None:
        return list(specs.values())
    return [specs[n] for n in names]


def to_anthropic(
    specs: Mapping[str, ToolSpec], names: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    return [
        {"name": s.name, "description": s.description, "input_schema": s.json_schema()}
        for s in _pick(specs, names)
    ]


def to_openai(
    specs: Mapping[str, ToolSpec], names: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": s.name,
                "description": s.description,
                "parameters": s.json_schema(),
            },
        }
        for s in _pick(specs, names)
    ]


def to_text(specs: Mapping[str, ToolSpec], names: Iterable[str] | None = None) -> str:
    """The tools as plain text for a model that writes DSL lines: signature, then description and
    an example call."""
    lines: list[str] = []
    for s in _pick(specs, names):
        required = set(s.required)
        params = ", ".join(
            f"{k}{'' if k in required else '?'}: {_type_name(v)}" for k, v in s.parameters.items()
        )
        lines.append(f"{s.name}({params})")
        lines.append("  " + s.description.replace("\n", "\n  "))
        ex = s.examples[0]
        lines.append(f"  e.g. {ex.instruction}: {render_dsl(ToolCall(s.name, ex.call))}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _type_name(schema: Mapping[str, Any]) -> str:
    if "enum" in schema:
        return "|".join(json.dumps(v) for v in schema["enum"])
    kind = schema.get("type", "any")
    if kind == "array":
        return "[" + _type_name(cast("Mapping[str, Any]", schema.get("items", {}))) + "]"
    return cast(str, kind)


# -- Anthropic -----------------------------------------------------------------------------------
def to_anthropic_call(call: ToolCall) -> dict[str, Any]:
    return {
        "type": "tool_use",
        "id": call.id or "call",
        "name": call.name,
        "input": dict(call.args),
    }


def from_anthropic_call(block: Mapping[str, Any]) -> ToolCall:
    if block.get("type") != "tool_use" or "name" not in block:
        raise AdapterError("not a tool_use block")
    args = block.get("input", {})
    if not isinstance(args, dict):
        raise AdapterError("a tool_use input must be an object")
    return ToolCall(
        str(block["name"]), cast("dict[str, Any]", args), cast("str | None", block.get("id"))
    )


# -- OpenAI --------------------------------------------------------------------------------------
def to_openai_call(call: ToolCall) -> dict[str, Any]:
    return {
        "id": call.id or "call",
        "type": "function",
        "function": {
            "name": call.name,
            "arguments": json.dumps(dict(call.args), separators=(",", ":")),
        },
    }


def from_openai_call(entry: Mapping[str, Any]) -> ToolCall:
    fn = entry.get("function")
    if not isinstance(fn, dict) or "name" not in fn:
        raise AdapterError("not a function call")
    fn = cast("dict[str, Any]", fn)
    raw = fn.get("arguments", "{}")
    try:
        args = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as err:
        raise AdapterError(f"the arguments are not valid JSON: {err.msg}") from None
    if not isinstance(args, dict):
        raise AdapterError("the arguments must be a JSON object")
    return ToolCall(
        str(fn["name"]), cast("dict[str, Any]", args), cast("str | None", entry.get("id"))
    )


# -- text DSL ------------------------------------------------------------------------------------
def render_dsl(call: ToolCall) -> str:
    """`name(key=value, ...)`, keys in the order given, values as compact JSON."""
    inner = ", ".join(
        f"{k}={json.dumps(v, ensure_ascii=False, separators=(',', ':'))}"
        for k, v in call.args.items()
    )
    return f"{call.name}({inner})"


def parse_dsl(text: str) -> ToolCall:
    """One DSL line back to a call. Raises `AdapterError` with what is wrong and where."""
    line = text.strip()
    open_at = line.find("(")
    if open_at <= 0 or not line.endswith(")"):
        raise AdapterError("expected name(key=value, ...)")
    name = line[:open_at].strip()
    if not _NAME.fullmatch(name):
        raise AdapterError(f"bad tool name {name!r}")
    body = line[open_at + 1 : -1]
    args: dict[str, Any] = {}
    for part in _split_top_level(body):
        key, eq, value = part.partition("=")
        key = key.strip()
        if not eq or not key.isidentifier():
            raise AdapterError(f"expected key=value, got {part.strip()!r}")
        if key in args:
            raise AdapterError(f"{key} is given twice")
        try:
            args[key] = json.loads(value.strip())
        except json.JSONDecodeError as err:
            raise AdapterError(f"{key}: the value is not valid JSON ({err.msg})") from None
    return ToolCall(name, args)


def _split_top_level(body: str) -> list[str]:
    """Split on commas that are not inside a string, array or object."""
    parts: list[str] = []
    depth = 0
    in_string = False
    escaped = False
    start = 0
    for i, ch in enumerate(body):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth < 0:
                raise AdapterError("unbalanced brackets")
        elif ch == "," and depth == 0:
            parts.append(body[start:i])
            start = i + 1
    if in_string or depth != 0:
        raise AdapterError("unterminated string or bracket")
    last = body[start:]
    if last.strip():
        parts.append(last)
    elif parts:
        raise AdapterError("trailing comma")
    return parts


def parse_dsl_lines(text: str) -> list[ToolCall]:
    """Every non-empty line of a model's reply that is not a comment."""
    return [
        parse_dsl(ln) for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    ]
