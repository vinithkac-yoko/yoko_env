"""Tool specifications: one YAML file per tool (`config/tools/<name>.yaml`).

A file names the tool, describes it for a model, gives its parameters as JSON Schema (with two
hints, `x-ref` for a parameter that names an object and `x-formula` for one that holds a formula),
and, for a primitive tool, says which Seamly2D element a call builds (`engine`). The loader checks
every file, builds the JSON Schema and the Pydantic model, and hashes the file's content so a run
can record exactly which tool text it used.

Edit and delete tools are not written: `derive_edit` and `derive_delete` make them from the file of
the tool that creates the object.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import jsonschema
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

TIERS = ("primitive", "read", "library", "structure", "variable", "plan", "edit", "delete")
BUILDERS = ("simple", "spline_path", "bezier_path", "operation", "true_darts")

_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "version", "tier", "description", "parameters", "examples"],
    "properties": {
        "name": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$", "maxLength": 48},
        "version": {"type": "integer", "minimum": 1},
        "tier": {"enum": list(TIERS)},
        "description": {"type": "string", "minLength": 40},
        "parameters": {"type": "object"},
        "required": {"type": "array", "items": {"type": "string"}},
        "examples": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["instruction", "call"],
                "properties": {"instruction": {"type": "string"}, "call": {"type": "object"}},
            },
        },
        "engine": {"type": "object"},
        "handler": {"type": "string"},
    },
}


class SpecError(ValueError):
    """A tool file is not valid."""


@dataclass(frozen=True, slots=True)
class Example:
    instruction: str
    call: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    version: int
    tier: str
    description: str
    parameters: Mapping[str, Any]  # parameter name -> JSON Schema fragment (with x- hints)
    required: tuple[str, ...]
    examples: tuple[Example, ...]
    engine: Mapping[str, Any] | None = None  # how a primitive call builds an element
    handler: str | None = None  # name of the Python function behind a non-primitive tool
    source: str = ""  # the YAML text, for hashing
    derived_from: str | None = None  # for edit_x and delete_x: the tool x
    _model: type[BaseModel] | None = field(default=None, repr=False, compare=False)

    # -- schema --------------------
    def json_schema(self) -> dict[str, Any]:
        """JSON Schema of the arguments, without our `x-` hints (model APIs reject some)."""
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {k: _strip(v) for k, v in self.parameters.items()},
            "additionalProperties": False,
        }
        if self.required:
            schema["required"] = list(self.required)
        return schema

    def refs(self) -> dict[str, str]:
        """Parameter name -> kind of object it names, for the parameters that name one (directly or
        as a list of them)."""
        out: dict[str, str] = {}
        for k, v in self.parameters.items():
            items = cast("dict[str, Any]", v.get("items") or {})
            kind = cast("str | None", v.get("x-ref") or items.get("x-ref"))
            if kind:
                out[k] = kind
        return out

    def digest(self) -> str:
        """SHA-256 of what a model sees and what a call does: description, schema, engine."""
        payload = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.json_schema(),
            "engine": self.engine,
            "examples": [[e.instruction, e.call] for e in self.examples],
        }
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()

    def model(self) -> type[BaseModel]:
        if self._model is None:
            object.__setattr__(self, "_model", _build_model(self.name, self.json_schema()))
        assert self._model is not None
        return self._model

    def validate(self, args: Mapping[str, Any]) -> dict[str, Any]:
        """The arguments as the model sees them (defaults filled in), or SpecError."""
        try:
            return self.model().model_validate(dict(args)).model_dump(exclude_unset=True)
        except ValidationError as err:
            first = err.errors()[0]
            where = ".".join(str(p) for p in first["loc"])
            raise SpecError(f"{where or 'arguments'}: {first['msg']}") from None


def _strip(node: Any) -> Any:
    if isinstance(node, dict):
        d = cast(dict[str, Any], node)
        return {k: _strip(v) for k, v in d.items() if not k.startswith("x-")}
    if isinstance(node, list):
        return [_strip(v) for v in cast(list[Any], node)]
    return node


# -- Pydantic model from JSON Schema --------------------
def _annotation(name: str, schema: Mapping[str, Any]) -> tuple[Any, dict[str, Any]]:
    """(type, Field kwargs) for one schema fragment."""
    kwargs: dict[str, Any] = {"description": schema.get("description", "")}
    if "default" in schema:
        kwargs["default"] = schema["default"]
    kind = schema.get("type")
    if "enum" in schema:
        values = tuple(schema["enum"])
        return Literal[values], kwargs  # type: ignore[valid-type]
    if kind == "string":
        if "maxLength" in schema:
            kwargs["max_length"] = schema["maxLength"]
        kwargs["min_length"] = schema.get("minLength", 1)
        return str, kwargs
    if kind == "number":
        if "minimum" in schema:
            kwargs["ge"] = schema["minimum"]
        if "maximum" in schema:
            kwargs["le"] = schema["maximum"]
        return float, kwargs
    if kind == "integer":
        if "minimum" in schema:
            kwargs["ge"] = schema["minimum"]
        if "maximum" in schema:
            kwargs["le"] = schema["maximum"]
        return int, kwargs
    if kind == "boolean":
        return bool, kwargs
    if kind == "array":
        inner, _ = _annotation(name + "_item", schema.get("items", {"type": "string"}))
        if "minItems" in schema:
            kwargs["min_length"] = schema["minItems"]
        if "maxItems" in schema:
            kwargs["max_length"] = schema["maxItems"]
        return list[inner], kwargs  # type: ignore[valid-type]
    if kind == "object":
        return _build_model(name, dict(schema)), kwargs
    raise SpecError(f"{name}: unsupported schema {dict(schema)!r}")


def _build_model(name: str, schema: Mapping[str, Any]) -> type[BaseModel]:
    props = cast(Mapping[str, Mapping[str, Any]], schema.get("properties", {}))
    required = set(schema.get("required", ()))
    fields: dict[str, Any] = {}
    for key, sub in props.items():
        ann, kwargs = _annotation(f"{name}_{key}", sub)
        if key in required:
            kwargs.pop("default", None)
            fields[key] = (ann, Field(..., **kwargs))
        else:
            default = kwargs.pop("default", None)
            fields[key] = (ann | None, Field(default, **kwargs))
    return create_model(
        "".join(p.capitalize() for p in name.split("_")),
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


# -- loading --------------------
def parse_tool(text: str, *, filename: str = "") -> ToolSpec:
    """Read and check one tool file."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as err:
        raise SpecError(f"{filename}: not valid YAML: {err}") from None
    try:
        jsonschema.validate(data, _FILE_SCHEMA)
    except jsonschema.ValidationError as err:
        where = ".".join(str(p) for p in err.absolute_path)
        raise SpecError(f"{filename}: {where or 'file'}: {err.message}") from None
    name = data["name"]
    if filename and Path(filename).stem != name:
        raise SpecError(f"{filename}: the file must be named {name}.yaml")
    params = cast(dict[str, Any], data["parameters"])
    required = tuple(data.get("required", ()))
    for r in required:
        if r not in params:
            raise SpecError(f"{name}: required parameter {r!r} is not defined")
    tier = data["tier"]
    engine = data.get("engine")
    if tier == "primitive":
        if engine is None or engine.get("builder") not in BUILDERS:
            raise SpecError(f"{name}: a primitive tool needs engine.builder (one of {BUILDERS})")
        _check_engine(name, engine, params)
        d = data["description"]
        if "Use it when" not in d or "Do not use it when" not in d:
            raise SpecError(f"{name}: the description must say when to use it and when not to")
    elif data.get("handler") is None:
        raise SpecError(f"{name}: a {tier} tool needs a handler")
    spec = ToolSpec(
        name=name,
        version=data["version"],
        tier=tier,
        description=data["description"].strip(),
        parameters=params,
        required=required,
        examples=tuple(Example(e["instruction"], e["call"]) for e in data["examples"]),
        engine=engine,
        handler=data.get("handler"),
        source=text,
    )
    for ex in spec.examples:
        try:
            spec.validate(ex.call)
        except SpecError as err:
            raise SpecError(f"{name}: example {ex.instruction!r} is invalid: {err}") from None
    return spec


def _check_engine(name: str, engine: Mapping[str, Any], params: Mapping[str, Any]) -> None:
    if "tag" not in engine:
        raise SpecError(f"{name}: engine.tag is missing")
    used: set[str] = set()
    for rule in cast(Mapping[str, Any], engine.get("set", {})).values():
        if isinstance(rule, str):
            used.update(_template_params(rule))
        elif isinstance(rule, dict) and "param" in rule:
            used.add(cast(str, rule["param"]))
    for p in used:
        if p not in params:
            raise SpecError(f"{name}: engine uses parameter {p!r}, which is not defined")


def _template_params(template: str) -> list[str]:
    out: list[str] = []
    i = 0
    while (a := template.find("{", i)) != -1:
        b = template.find("}", a)
        if b == -1:
            break
        out.append(template[a + 1 : b])
        i = b + 1
    return out


def template_params(template: str) -> list[str]:
    return _template_params(template)


def load_tools(directory: Path) -> dict[str, ToolSpec]:
    """Every `*.yaml` tool in a directory, checked, by name."""
    tools: dict[str, ToolSpec] = {}
    for path in sorted(directory.glob("*.yaml")):
        spec = parse_tool(path.read_text(), filename=path.name)
        tools[spec.name] = spec
    return tools


# -- derived tools --------------------
def derive_edit(spec: ToolSpec) -> ToolSpec:
    """`edit_<tool>`: change the formulas and references of an object the tool made. Every
    parameter of the tool is optional; `target` names the object."""
    if spec.engine is None or spec.engine.get("builder") not in ("simple",):
        raise SpecError(f"{spec.name}: only simple tools have a derived edit tool")
    params: dict[str, Any] = {
        "target": {
            "type": "string",
            "x-ref": "object",
            "description": (
                "The object to change: its label (a point), its name (a curve or arc), or #<id> "
                "(a line, for example #31)."
            ),
        }
    }
    settable = _settable(spec)
    for k, v in spec.parameters.items():
        if k in settable:
            params[k] = copy.deepcopy(v)
    desc = (
        f"Change an object made with {spec.name}. Give the object as `target` and only the "
        "parameters you want to change; the others stay as they are. Everything built from the "
        "object is recomputed.\n"
        f"Use it when a {spec.name} object has a wrong value or reference. Do not use it when "
        "you want a new object: use the creating tool."
    )
    first = spec.examples[0]
    example_call: dict[str, Any] = {
        "target": _example_target(spec),
        **_one_param(spec, first.call, settable),
    }
    return ToolSpec(
        name=f"edit_{spec.name}",
        version=spec.version,
        tier="edit",
        description=desc,
        parameters=params,
        required=("target",),
        examples=(Example(f"Change an object made with {spec.name}", example_call),),
        engine=spec.engine,
        derived_from=spec.name,
        source=spec.source,
    )


def derive_delete(spec: ToolSpec) -> ToolSpec:
    """`delete_<tool>`: remove an object the tool made, if nothing depends on it."""
    desc = (
        f"Delete an object made with {spec.name}. It is refused, with the list of objects that "
        "use it, if anything depends on it.\n"
        f"Use it when a {spec.name} object was a mistake or is a leftover nothing uses. Do not use "
        "it when other objects use it: change those first, or edit this one instead."
    )
    params = {
        "target": {
            "type": "string",
            "x-ref": "object",
            "description": (
                "The object to delete: its label (a point), its name (a curve or arc), or #<id> "
                "(a line, for example #31)."
            ),
        }
    }
    return ToolSpec(
        name=f"delete_{spec.name}",
        version=spec.version,
        tier="delete",
        description=desc,
        parameters=params,
        required=("target",),
        examples=(Example(f"Delete a {spec.name} object", {"target": _example_target(spec)}),),
        engine=spec.engine,
        derived_from=spec.name,
        source=spec.source,
    )


def _settable(spec: ToolSpec) -> set[str]:
    """Parameters that map to one attribute each, so that an edit can change them alone."""
    assert spec.engine is not None
    out: set[str] = set()
    for rule in cast(Mapping[str, Any], spec.engine.get("set", {})).values():
        if isinstance(rule, str):
            ps = _template_params(rule)
            if len(ps) == 1 and rule == "{" + ps[0] + "}":
                out.add(ps[0])
        elif isinstance(rule, dict) and "param" in rule:
            out.add(cast(str, rule["param"]))
    return out


def _example_target(spec: ToolSpec) -> str:
    call = spec.examples[0].call
    for key in ("label", "label1"):
        if key in call:
            return str(call[key])
    return "Spl_A_B"


def _one_param(spec: ToolSpec, call: Mapping[str, Any], settable: set[str]) -> dict[str, Any]:
    for k, v in call.items():
        if k in settable and k != "label":
            return {k: v}
    return {}


def all_tools(directory: Path) -> dict[str, ToolSpec]:
    """The written tools and the edit and delete tools derived from the simple primitives."""
    tools = load_tools(directory)
    for spec in list(tools.values()):
        if spec.tier == "primitive" and spec.engine and spec.engine.get("builder") == "simple":
            tools[f"edit_{spec.name}"] = derive_edit(spec)
            tools[f"delete_{spec.name}"] = derive_delete(spec)
    return tools
