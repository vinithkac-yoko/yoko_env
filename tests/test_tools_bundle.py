"""Prompts and bundles: slots, subsets and the digest."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from yoko_tools.bundle import Bundle, BundleError, load_prompt, parse_prompt
from yoko_tools.spec import all_tools

ROOT = Path(__file__).resolve().parents[1]
SPECS = all_tools(ROOT / "config/tools")
PROMPT = load_prompt(ROOT / "config/prompts/drafter/v1.md")
VALUES = {"pattern_summary": "unit: cm", "plan": "step 1: hem", "status_card": "step 1 active"}


def test_the_first_drafter_prompt_loads_and_fills_every_slot() -> None:
    assert PROMPT.variant == "v1" and set(PROMPT.slots) == {
        "tool_summary", "pattern_summary", "plan", "status_card",
    }  # fmt: skip
    text = Bundle.make(PROMPT, SPECS, ["point_origin", "undo"]).system_prompt(VALUES)
    assert "{{" not in text and "unit: cm" in text and "point_origin, undo" in text


def test_tools_can_be_written_into_the_prompt_for_text_only_models() -> None:
    text = Bundle.make(PROMPT, SPECS, ["point_origin"]).system_prompt(VALUES, tools_in_prompt=True)
    assert "point_origin(label: string" in text


def test_a_prompt_with_a_missing_or_unknown_slot_is_refused() -> None:
    with pytest.raises(BundleError, match="without a value"):
        PROMPT.render({"tool_summary": "x"})
    with pytest.raises(BundleError, match="does not have"):
        PROMPT.render({**VALUES, "tool_summary": "x", "colour": "red"})
    with pytest.raises(BundleError, match="not declare"):
        parse_prompt("---\nname: n\nvariant: v\nversion: 1\nslots: []\n---\nhello {{ x }}\n")
    with pytest.raises(BundleError):
        parse_prompt("no front matter")


def test_the_digest_changes_with_the_prompt_the_subset_and_any_tool_text() -> None:
    base = Bundle.make(PROMPT, SPECS, ["point_origin", "undo"])
    assert base.digest() == Bundle.make(PROMPT, SPECS, ["undo", "point_origin"]).digest()
    assert base.digest() != Bundle.make(PROMPT, SPECS, ["point_origin"]).digest()
    other_prompt = replace(PROMPT, text=PROMPT.text + "\nExtra.")
    assert base.digest() != Bundle.make(other_prompt, SPECS, ["point_origin", "undo"]).digest()
    edited = dict(SPECS)
    edited["undo"] = replace(SPECS["undo"], description=SPECS["undo"].description + " Really.")
    assert base.digest() != Bundle.make(PROMPT, edited, ["point_origin", "undo"]).digest()


def test_an_unknown_tool_in_a_subset_is_refused() -> None:
    with pytest.raises(BundleError, match="nope"):
        Bundle.make(PROMPT, SPECS, ["nope"])


def test_the_bundle_hands_the_chosen_tools_to_each_api() -> None:
    b = Bundle.make(PROMPT, SPECS, ["line", "point_origin"])
    assert [t["name"] for t in b.anthropic_tools()] == ["line", "point_origin"]
    assert [t["function"]["name"] for t in b.openai_tools()] == ["line", "point_origin"]
