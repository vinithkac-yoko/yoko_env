"""Prompts and bundles.

A **prompt** is a markdown file with front matter (`name`, `variant`, `version`, `slots`) and
`{{slot}}` placeholders. A **bundle** is a prompt plus the tools a run may use (the subset). Its
digest covers the prompt text, the subset and every tool's digest, so a run can record exactly what
the model was shown, and changing a description makes a different bundle. A prompt variant that a
past run used is never edited: a change is a new variant file.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from yoko_tools.adapters import to_anthropic, to_openai, to_text
from yoko_tools.spec import ToolSpec

_SLOT = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


class BundleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Prompt:
    name: str
    variant: str
    version: int
    slots: tuple[str, ...]
    template: str
    text: str  # the whole file, for hashing

    def render(self, values: Mapping[str, str]) -> str:
        used = set(_SLOT.findall(self.template))
        missing = used - set(values)
        if missing:
            raise BundleError(f"slots without a value: {', '.join(sorted(missing))}")
        extra = set(values) - set(self.slots)
        if extra:
            raise BundleError(f"slots this prompt does not have: {', '.join(sorted(extra))}")
        return _SLOT.sub(lambda m: values[m.group(1)], self.template)


def parse_prompt(text: str) -> Prompt:
    if not text.startswith("---\n"):
        raise BundleError("a prompt starts with front matter between --- lines")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise BundleError("the front matter is not closed")
    meta = yaml.safe_load(text[4:end])
    if not isinstance(meta, dict):
        raise BundleError("the front matter must be a mapping")
    front = cast("dict[str, Any]", meta)
    for key in ("name", "variant", "version", "slots"):
        if key not in front:
            raise BundleError(f"front matter lacks {key!r}")
    template = text[end + 5 :].lstrip("\n")
    slots = tuple(str(s) for s in front["slots"])
    undeclared = set(_SLOT.findall(template)) - set(slots)
    if undeclared:
        raise BundleError(
            f"the text uses slots the front matter does not declare: {sorted(undeclared)}"
        )
    return Prompt(
        str(front["name"]), str(front["variant"]), int(front["version"]), slots, template, text
    )


def load_prompt(path: Path) -> Prompt:
    prompt = parse_prompt(path.read_text())
    if path.stem != prompt.variant:
        raise BundleError(f"{path.name}: the file must be named {prompt.variant}.md")
    return prompt


@dataclass(frozen=True, slots=True)
class Bundle:
    prompt: Prompt
    tools: tuple[ToolSpec, ...]

    @staticmethod
    def make(prompt: Prompt, specs: Mapping[str, ToolSpec], subset: Iterable[str] | None) -> Bundle:
        names = sorted(specs) if subset is None else sorted(set(subset))
        unknown = [n for n in names if n not in specs]
        if unknown:
            raise BundleError(f"unknown tools in the subset: {', '.join(unknown)}")
        return Bundle(prompt, tuple(specs[n] for n in names))

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.tools)

    def digest(self) -> str:
        h = hashlib.sha256()
        h.update(self.prompt.text.encode())
        for t in self.tools:
            h.update(b"\0" + t.name.encode() + b"\0" + t.digest().encode())
        return h.hexdigest()

    def system_prompt(self, values: Mapping[str, str], *, tools_in_prompt: bool = False) -> str:
        """The prompt with its slots filled. The tool list goes into the text only for models that
        are not given tools through an API (`tools_in_prompt`)."""
        spec_map = {t.name: t for t in self.tools}
        summary = (
            to_text(spec_map)
            if tools_in_prompt
            else "The tools are given to you separately: " + ", ".join(self.tool_names) + "."
        )
        return self.prompt.render({"tool_summary": summary, **values})

    def anthropic_tools(self) -> list[dict[str, Any]]:
        return to_anthropic({t.name: t for t in self.tools})

    def openai_tools(self) -> list[dict[str, Any]]:
        return to_openai({t.name: t for t in self.tools})
