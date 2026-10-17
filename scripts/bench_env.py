"""How fast is the environment? Steps per second on the basic set, over a pool of workers.

    uv run python scripts/bench_env.py                    # all cores, 200 episodes
    uv run python scripts/bench_env.py --workers 8 --episodes 400
    uv run python scripts/bench_env.py --mode env         # teacher-driven env.step only

Target for now (Kasi): 100 steps per second on 8 cores. Measure before optimising; this script is
the measurement. The recipe is the test example from tests/toy.py (a hem edit on the skirt back):
the speed of the framework, not of any real recipe.

`--mode data` times whole teacher episodes as the data generator runs them (observation, valid
actions, the teacher's label and the record for every step, with noise). `--mode env` times only
`PatternEnv.step` calls, driven by the teacher's first action, with the teacher's labelling on or
off (`--no-teacher`).
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from toy import HemOnly  # noqa: E402  (the example recipe, see tests/toy.py)
from yoko_data import run_episode  # noqa: E402
from yoko_engine.landmarks import Landmarks  # noqa: E402
from yoko_env import EnvConfig, PatternEnv, Task  # noqa: E402
from yoko_io.library import DirectoryLibrary  # noqa: E402
from yoko_tools.recipes import RecipeRegistry  # noqa: E402
from yoko_tools.spec import all_tools  # noqa: E402
from yoko_tools.teacher import Call  # noqa: E402

_STATE: dict[str, Any] = {}


def make_plan(n_steps: int, amount: float) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "design_summary": "benchmark",
        "starting_pattern": {"id": "aldrich-womens-6th-basic"},
        "steps": [
            {
                "step": i + 1,
                "transformation": "lengthen_or_shorten",
                "summary": f"lengthen by {amount} cm",
                "params": {"amount": {"value": amount, "unit": "cm"}},
                "refs": {"hem": "skirt_back.hem_left"},
            }
            for i in range(n_steps)
        ],
    }


def init(mode: str, teacher: bool) -> None:
    library = DirectoryLibrary(ROOT / "library", ROOT / "fixtures")
    _, pattern, table = library.load("aldrich-womens-6th-basic")
    landmarks = Landmarks.from_mapping(
        {"version": 1, "landmarks": {"skirt_back.hem_left": {"label": "A3"}}}
    )
    specs = all_tools(ROOT / "config/tools")
    recipes = RecipeRegistry([HemOnly()])
    _STATE.update(
        mode=mode,
        pattern=pattern,
        table=table,
        landmarks=landmarks,
        env=PatternEnv(EnvConfig(specs, recipes, teacher=teacher, max_steps=60)),
        # a teacher-on env to find the actions an env with the teacher off is then timed on
        guide=PatternEnv(EnvConfig(specs, recipes, max_steps=60)),
    )


def work(seed: int) -> tuple[int, float, str]:
    env: PatternEnv = _STATE["env"]
    n_steps = 1 + seed % 3
    plan = make_plan(n_steps, 2.0 + seed % 5)
    task = Task(_STATE["pattern"], _STATE["table"], plan, _STATE["landmarks"], plan_id=f"b{seed}")
    t0 = time.perf_counter()
    if _STATE["mode"] == "data":
        ep = run_episode(env, task, seed, episode=f"b{seed}")
        return len(ep.steps), time.perf_counter() - t0, ep.outcome
    guide: PatternEnv = _STATE["guide"]
    guide.reset(task, seed, author="teacher")
    actions: list[Call] = []
    while True:  # not timed: the actions the teacher would take
        accepted = guide.expert()
        pick = accepted[0] if accepted else Call("done")
        actions.append(pick)
        if guide.step(pick).done:
            break
    t0 = time.perf_counter()
    env.reset(task, seed, author="teacher")
    outcome = "?"
    for pick in actions:  # timed: only reset and the steps (with the teacher's labelling if on)
        result = env.step(pick)
        if result.done:
            outcome = result.info["outcome"] or "?"
    return len(actions), time.perf_counter() - t0, outcome


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--mode", choices=("data", "env"), default="data")
    ap.add_argument("--no-teacher", action="store_true")
    args = ap.parse_args()
    ctx = mp.get_context("fork")
    t0 = time.perf_counter()
    with ctx.Pool(
        args.workers, initializer=init, initargs=(args.mode, not args.no_teacher)
    ) as pool:
        ready = time.perf_counter()
        results = pool.map(work, range(args.episodes), chunksize=4)
    wall = time.perf_counter() - ready
    steps = sum(r[0] for r in results)
    busy = sum(r[1] for r in results)
    outcomes: dict[str, int] = {}
    for r in results:
        outcomes[r[2]] = outcomes.get(r[2], 0) + 1
    report = {
        "mode": args.mode,
        "teacher": not args.no_teacher,
        "workers": args.workers,
        "cpus": os.cpu_count(),
        "episodes": args.episodes,
        "steps": steps,
        "wall_seconds": round(wall, 2),
        "startup_seconds": round(ready - t0, 2),
        "steps_per_second": round(steps / wall, 1),
        "steps_per_second_per_worker": round(steps / busy, 1),
        "projected_on_8_cores": round(8 * steps / busy, 1),
        "ms_per_step": round(1000 * busy / steps, 1),
        "outcomes": outcomes,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
