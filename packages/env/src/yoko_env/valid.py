"""Valid actions: which tools can be called now, and what each reference argument may name.

`valid_actions` is what an LLM drafter is shown at each step (only the valid tools of its run's
subset) and what the small models of `yoko-model` use as masks. A tool is valid when its
preconditions hold: a tool that needs a point is not valid in an empty pattern, `undo` is not valid
with nothing to undo, `edit_x` needs an object made with x.

`random_action` draws a valid action at random, for the noise that data generation injects.
"""

from __future__ import annotations

import random
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from yoko_engine.pieces_edit import pieces_of
from yoko_tools.runtime import Toolbox
from yoko_tools.spec import ToolSpec
from yoko_tools.teacher import Call

NOISE_TIERS = ("primitive", "edit", "delete")  # what a random action may be
ANGLES = (0, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330)


@dataclass(slots=True)
class Index:
    """The names in the pattern now, by kind. Built once per state."""

    points: list[str] = field(default_factory=lambda: list[str]())
    curves: list[str] = field(default_factory=lambda: list[str]())
    lines: list[str] = field(default_factory=lambda: list[str]())
    landmark_points: list[str] = field(default_factory=lambda: list[str]())
    landmark_curves: list[str] = field(default_factory=lambda: list[str]())
    made_by: dict[str, list[str]] = field(default_factory=lambda: dict[str, list[str]]())
    pieces: list[str] = field(default_factory=lambda: list[str]())
    variables: list[str] = field(default_factory=lambda: list[str]())
    blocks: list[str] = field(default_factory=lambda: list[str]())

    def candidates(self, kind: str) -> list[str]:
        if kind == "point":
            return [*self.points, *self.landmark_points]
        if kind == "curve":
            return [*self.curves, *self.landmark_curves]
        return [
            *self.points,
            *self.curves,
            *self.lines,
            *self.landmark_points,
            *self.landmark_curves,
        ]


def build_index(box: Toolbox) -> Index:
    s = box.session
    ev = s.evaluation
    idx = Index()
    idx.points = [g.label for g in ev.points.values() if g.label]
    idx.curves = [c.name for c in ev.curves.values()]
    for obj in s.pattern.objects():
        if obj.tag == "line":
            idx.lines.append(f"#{obj.id}")
        tool = box.tool_for(obj)
        if tool is not None:
            idx.made_by.setdefault(tool, []).append(box.name_of(obj.id))
    if box.landmarks is not None:
        found, _ = box.landmarks.resolve(ev)
        idx.landmark_points = sorted(n for n, i in found.items() if i in ev.points)
        idx.landmark_curves = sorted(n for n, i in found.items() if i in ev.curves)
    idx.pieces = [p.get("name") or "" for _, p, _ in pieces_of(s.pattern)]
    idx.variables = [v.name for v in s.pattern.variables]
    idx.blocks = [b.name for b in s.pattern.blocks]
    return idx


@dataclass(frozen=True, slots=True)
class ValidActions:
    """What can be called now. Candidates are listed once by kind, not once per tool, so a record of
    every step stays small; `candidates` gives what one argument of one tool may name."""

    tools: tuple[str, ...]
    refs: Mapping[str, tuple[str, ...]]  # kind (point | curve | object) -> names
    targets: Mapping[str, tuple[str, ...]]  # creating tool -> names of the objects made with it
    pieces: tuple[str, ...] = ()
    variables: tuple[str, ...] = ()
    blocks: tuple[str, ...] = ()

    def candidates(self, spec: ToolSpec, param: str) -> tuple[str, ...]:
        kind = spec.refs().get(param)
        if kind is not None:
            if param == "target" and spec.tier in ("edit", "delete"):
                return self.targets.get(spec.derived_from or "", ())
            return self.refs.get(kind, ())
        if param in ("piece", "first_piece", "second_piece"):
            return self.pieces
        if param == "name" and spec.name == "delete_variable":
            return self.variables
        if param == "block":
            return self.blocks
        return ()

    def as_json(self) -> dict[str, Any]:
        return {
            "tools": list(self.tools),
            "refs": {k: list(v) for k, v in self.refs.items()},
            "targets": {k: list(v) for k, v in self.targets.items()},
            "pieces": list(self.pieces),
            "variables": list(self.variables),
            "blocks": list(self.blocks),
        }


def valid_actions(
    box: Toolbox,
    tools: Collection[str] | None = None,
    *,
    step_open: bool = False,
    index: Index | None = None,
) -> ValidActions:
    """The tools that can be called now (their preconditions hold) and the names each reference
    argument may take.

    `step_open`: the plan has an active step with a recipe and something left to do, so `apply_step`
    is valid. `tools` is the run's subset; None means every tool."""
    idx = index or build_index(box)
    refs = {k: tuple(idx.candidates(k)) for k in ("point", "curve", "object")}
    targets = {k: tuple(v) for k, v in idx.made_by.items()}
    found = ValidActions(
        (), refs, targets, tuple(idx.pieces), tuple(idx.variables), tuple(idx.blocks)
    )
    valid = [
        name
        for name, spec in box.specs.items()
        if (tools is None or name in tools) and _can_call(box, spec, found, step_open)
    ]
    return ValidActions(tuple(valid), refs, targets, found.pieces, found.variables, found.blocks)


def _can_call(box: Toolbox, spec: ToolSpec, valid: ValidActions, step_open: bool) -> bool:
    """Do the tool's preconditions hold now?"""
    name = spec.name
    if name == "apply_step":
        return step_open
    if name == "done":
        return True
    if name == "undo":
        return box.session.can_undo
    if name in ("set_piece", "delete_piece"):
        return bool(valid.pieces)
    if name == "union_pieces":
        return len(valid.pieces) >= 2
    if name == "add_piece":
        return len(valid.refs["point"]) >= 3
    if name == "delete_variable":
        return bool(valid.variables)
    if name in ("rename_block", "delete_block"):
        return bool(valid.blocks)
    if name in ("search_library", "load_pattern"):
        return box.library is not None
    if name == "copy_piece_from":
        return bool(box.loaded)
    return all(valid.candidates(spec, p) for p in spec.refs() if p in spec.required)


# -- random actions --------------------------------------------------------------------------------
def random_action(
    box: Toolbox,
    rng: random.Random,
    tools: Collection[str] | None = None,
    *,
    tries: int = 40,
) -> Call | None:
    """A valid action chosen at random: a tool that can be called now with arguments that are
    accepted (tried on a copy of the pattern). Only drawing, edit and delete tools are drawn: noise
    is a wrong construction step, not a wrong read, a library search or an early `done`. None if
    nothing could be found."""
    idx = build_index(box)
    valid = valid_actions(box, tools, index=idx)
    names = sorted(n for n in valid.tools if box.specs[n].tier in NOISE_TIERS)
    for _ in range(tries):
        if not names:
            return None
        name = rng.choice(names)
        spec = box.specs[name]
        args = _sample_args(spec, valid, idx, rng)
        if box.fork().call(name, args)["ok"]:
            return Call(name, args)
    return None


def _sample_args(
    spec: ToolSpec, valid: ValidActions, idx: Index, rng: random.Random
) -> dict[str, Any]:
    args: dict[str, Any] = {}
    for param, schema in spec.parameters.items():
        if param not in spec.required and rng.random() > 0.35:
            continue
        cands = valid.candidates(spec, param) if param in spec.refs() else None
        value = _sample(param, cast("Mapping[str, Any]", schema), cands, idx, rng)
        if value is not None:
            args[param] = value
    return args


def _fresh_label(idx: Index, rng: random.Random) -> str:
    taken = set(idx.points) | set(idx.curves)
    while True:
        label = f"N{rng.randrange(10_000)}"
        if label not in taken:
            return label


def _sample(
    param: str,
    schema: Mapping[str, Any],
    cands: Sequence[str] | None,
    idx: Index,
    rng: random.Random,
) -> Any:
    kind = schema.get("type")
    if kind == "array":
        items = cast("Mapping[str, Any]", schema.get("items") or {})
        low = int(schema.get("minItems", 1))
        count = rng.randint(max(low, 2), max(low, 4))
        if cands is not None and "x-ref" in items:
            return [rng.choice(cands) for _ in range(count)] if cands else None
        if items.get("type") == "object":
            props = cast("Mapping[str, Mapping[str, Any]]", items.get("properties") or {})
            pts = idx.candidates("point")
            if not pts:
                return None
            need = cast("list[str]", items.get("required", []))
            rows: list[dict[str, Any]] = []
            for _ in range(count):
                row: dict[str, Any] = {}
                for k, sub in props.items():
                    if k in need or rng.random() < 0.3:
                        row[k] = (
                            rng.choice(pts) if "x-ref" in sub else _sample(k, sub, None, idx, rng)
                        )
                rows.append(row)
            return rows
        return None
    if cands is not None:
        return rng.choice(cands) if cands else None
    if "x-ref" in schema:
        return None
    if "enum" in schema:
        return rng.choice(list(schema["enum"]))
    if kind == "boolean":
        return rng.random() < 0.5
    if kind == "integer":
        low, high = int(schema.get("minimum", 0)), int(schema.get("maximum", 10))
        return rng.randint(low, min(high, low + 10))
    if kind == "number":
        low = float(schema.get("minimum", 0))
        high = min(float(schema.get("maximum", 10)), low + 10)
        return round(rng.uniform(low, high), 1)
    if kind == "string":
        if param in ("label", "label1", "label2", "name", "suffix"):
            return _fresh_label(idx, rng)
        if "angle" in param:
            return str(rng.choice(ANGLES))
        if schema.get("x-formula"):
            return str(round(rng.uniform(0.5, 12), 1))
        return _fresh_label(idx, rng)
    return None
