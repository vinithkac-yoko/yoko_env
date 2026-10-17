"""Teacher episodes: run the teacher in the environment and record what it labels.

At each state the teacher's acceptable set is the label that is stored. The action that is executed
is the teacher's first (canonical) choice, except that with the episode's noise rate it is a random
valid action instead, so the data also holds the states after mistakes, labelled with the way back.
Only the label is stored, never the noisy action.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from yoko_env import PatternEnv, Task, random_action
from yoko_tools.teacher import Call

from yoko_data.records import NOISE_RATES, RecordWriter, level_for

SOURCE = "teacher"


@dataclass(slots=True)
class Episode:
    header: dict[str, Any]
    steps: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    end: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())

    @property
    def outcome(self) -> str:
        return str(self.end.get("outcome"))


def draw_noise_rate(rng: random.Random) -> float:
    return rng.choice(NOISE_RATES)


def run_episode(
    env: PatternEnv,
    task: Task,
    seed: int,
    *,
    episode: str,
    noise_rate: float | None = None,
    source: str = SOURCE,
) -> Episode:
    """One episode. The seed fixes everything (the noise rate if not given, which steps are noisy,
    which random action), so a killed worker replays its episode exactly."""
    if task.plan is None:
        raise ValueError("a teacher episode needs a plan")
    rng = random.Random(seed)
    rate = draw_noise_rate(rng) if noise_rate is None else noise_rate
    plan_id = task.plan_id or episode
    level = task.level if task.level is not None else level_for(task.plan)
    obs = env.reset(task, seed, episode=episode, author="teacher")
    out = Episode(
        {
            "episode": episode,
            "plan_id": plan_id,
            "level": level,
            "source": source,
            "seed": seed,
            "noise_rate": rate,
            "plan": dict(task.plan),
        }
    )
    stopped = "done"
    while True:
        acceptable = env.expert()
        if acceptable is None or not acceptable:
            stopped = "no_label" if acceptable is None else "no_way_forward"
            break
        noisy = rng.random() < rate
        action: Call | None = (
            random_action(env.box, rng, env.cfg.tools) if noisy and env.box else None
        )
        noisy = action is not None
        if action is None:
            action = acceptable[0]
        out.steps.append(
            {
                "episode": episode,
                "plan_id": plan_id,
                "level": level,
                "step": obs.step,
                "observation": _visible(obs.as_json()),
                "valid_actions": obs.valid_actions.as_json(),
                "acceptable": [c.as_json() for c in acceptable],
                "noise": noisy,
                "progress": obs.progress,
            }
        )
        result = env.step(action)
        obs = result.observation
        if result.done:
            stopped = result.info["outcome"] or "done"
            break
    analysis = env.analysis()
    out.end = {
        "outcome": stopped,
        "steps": len(out.steps),
        "noisy_steps": sum(1 for s in out.steps if s["noise"]),
        "plan_complete": analysis.complete if analysis is not None else False,
        "state_hash": env.box.session.state_hash() if env.box else None,
    }
    return out


def _visible(obs: Mapping[str, Any]) -> dict[str, Any]:
    """The observation as stored: the valid actions are a field of the record, not repeated here."""
    return {k: v for k, v in obs.items() if k != "valid_actions"}


def write_episode(writer: RecordWriter, episode: Episode) -> None:
    writer.write_episode(episode.header, episode.steps, episode.end)
