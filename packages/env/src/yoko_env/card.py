"""The status card: where the plan stands, in a form a policy can read.

Every observation carries one (Addendum 1 section 9). Each plan step is done, active or pending.
For the active step: each target amount against the amount measured on the pattern now, the
landmarks the plan names for it and the pieces it touches. It says nothing about which actions the
teacher accepts: that is privileged.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from yoko_tools.teacher import Analysis


def status_card(plan: Mapping[str, Any] | None, analysis: Analysis | None) -> dict[str, Any]:
    if plan is None:
        return {"steps": [], "active": None}
    raw = cast("list[Mapping[str, Any]]", plan["steps"])
    if analysis is None or not analysis.steps:
        card_steps = [_row(s, "pending") for s in raw]
        note = analysis.problem if analysis is not None else ""
        return {"steps": card_steps, "active": None, "note": note}
    steps = [_row(raw[i], st.state) for i, st in enumerate(analysis.steps)]
    active: dict[str, Any] | None = None
    if analysis.active is not None:
        st = analysis.step(analysis.active)
        step = raw[analysis.active - 1]
        amounts: list[dict[str, Any]] = []
        params = cast("Mapping[str, Mapping[str, Any]]", step["params"])
        for name, amount in params.items():
            amounts.append(
                {
                    "name": name,
                    "unit": amount["unit"],
                    "target": st.targets.get(name),
                    "now": st.measured.get(name),
                }
            )
        note = ""
        if not st.covered:
            note = "no recipe covers this step: follow the step's text"
        elif st.error:
            note = st.error
        elif st.check is not None and not st.check.done:
            note = st.check.detail
        active = {
            "step": analysis.active,
            "recipe": st.transformation,
            "summary": st.summary,
            "amounts": amounts,
            "landmarks": dict(cast("Mapping[str, str]", step.get("refs") or {})),
            "options": dict(cast("Mapping[str, str]", step.get("options") or {})),
            "pieces": list(cast("list[str]", step.get("pieces") or [])),
            "note": note,
        }
    return {"steps": steps, "active": active, "note": analysis.problem}


def _row(step: Mapping[str, Any], state: str) -> dict[str, Any]:
    return {
        "step": step["step"],
        "recipe": step["transformation"],
        "summary": step["summary"],
        "state": state,
    }


def card_text(card: Mapping[str, Any]) -> str:
    """The card as plain lines, for small models and for people."""
    lines: list[str] = []
    for row in cast("list[Mapping[str, Any]]", card["steps"]):
        mark = {"done": "[x]", "active": "[>]", "pending": "[ ]"}[cast(str, row["state"])]
        lines.append(f"{mark} step {row['step']}: {row['summary']}")
    active = cast("Mapping[str, Any] | None", card.get("active"))
    if active is not None:
        lines.append(f"now: step {active['step']} ({active['recipe']})")
        for a in cast("list[Mapping[str, Any]]", active["amounts"]):
            now = "not measured" if a["now"] is None else f"{a['now']:g} {a['unit']}"
            target = "?" if a["target"] is None else f"{a['target']:g} {a['unit']}"
            lines.append(f"  {a['name']}: target {target}, now {now}")
        if active["landmarks"]:
            lines.append("  at: " + ", ".join(f"{k}={v}" for k, v in active["landmarks"].items()))
        if active["options"]:
            lines.append(
                "  choices: " + ", ".join(f"{k}={v}" for k, v in active["options"].items())
            )
        if active["pieces"]:
            lines.append("  pieces: " + ", ".join(active["pieces"]))
        if active["note"]:
            lines.append(f"  note: {active['note']}")
    if card.get("note"):
        lines.append(f"note: {card['note']}")
    return "\n".join(lines)
