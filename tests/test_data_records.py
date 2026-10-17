"""Teacher data: the record format, truncation tolerance, noise injection, seeds and splits."""

from __future__ import annotations

import gzip
import json
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
from toy import RECIPES, SPECS, plan, toy_task
from yoko_data import (
    NOISE_RATES,
    SEED_RANGES,
    RecordWriter,
    check_seed,
    draw_noise_rate,
    level_for,
    load_episodes,
    plan_family,
    read_lines,
    run_episode,
    split_of,
    write_episode,
)
from yoko_env import EnvConfig, PatternEnv

SPEC_KEYS = {
    "episode", "plan_id", "level", "step", "observation", "valid_actions", "acceptable", "noise",
    "progress", "kind",
}  # fmt: skip


def env(**kw: Any) -> PatternEnv:
    return PatternEnv(EnvConfig(SPECS, RECIPES, **kw))


def episodes(n: int = 3, noise: float = 0.0) -> list[Any]:
    out = []
    for i in range(n):
        task = toy_task(plan(5, mark="no"), plan_id=f"toy-{i}")
        out.append(run_episode(env(), task, seed=i, episode=f"e{i}", noise_rate=noise))
    return out


# -- the record format -----------------------------------------------------------------------------
def test_an_episode_is_written_with_the_plan_once_and_one_record_per_step(tmp_path: Path) -> None:
    path = tmp_path / "teacher.jsonl.gz"
    ep = episodes(1)[0]
    write_episode(RecordWriter(path), ep)
    lines = list(read_lines(path))
    assert [r["kind"] for r in lines] == ["plan", *["step"] * len(ep.steps), "end"]
    assert sum("plan" in r for r in lines) == 1  # the plan is in the first line only
    first = lines[1]
    assert set(first) == SPEC_KEYS
    assert first["step"] == 0 and first["progress"] == 1 and first["noise"] is False
    assert first["acceptable"][0]["tool"] == "edit_point_at_distance_angle"
    assert first["valid_actions"]["tools"] and "valid_actions" not in first["observation"]
    assert lines[0]["source"] == "teacher" and lines[0]["level"] == 1
    assert lines[-1]["outcome"] == "done" and lines[-1]["plan_complete"] is True
    [loaded] = load_episodes(path)
    assert loaded.complete and loaded.plan["steps"][0]["transformation"] == "lengthen_or_shorten"
    assert len(loaded.steps) == len(ep.steps)
    # the last state's label is `done`
    assert loaded.steps[-1]["acceptable"] == [{"args": {}, "tool": "done"}]


def test_what_is_stored_never_holds_the_privileged_fields_of_the_policys_side(
    tmp_path: Path,
) -> None:
    path = tmp_path / "t.jsonl.gz"
    write_episode(RecordWriter(path), episodes(1)[0])
    for rec in read_lines(path):
        if rec["kind"] == "step":
            blob = json.dumps(rec["observation"])
            for secret in ("on_plan", "expert", "acceptable", "teacher"):
                assert secret not in blob


def test_an_episode_is_on_disk_when_write_episode_returns(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl.gz"
    writer = RecordWriter(path)
    for ep in episodes(2):
        write_episode(writer, ep)
        # a second process reads the file while the writer is still alive
        assert load_episodes(path)[-1].complete
    assert [e.episode for e in load_episodes(RecordWriter(path).path)] == ["e0", "e1"]


def test_a_new_writer_appends_to_a_file_an_old_one_started(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl.gz"
    eps = episodes(2)
    write_episode(RecordWriter(path), eps[0])
    write_episode(RecordWriter(path), eps[1])
    assert [e.episode for e in load_episodes(path)] == ["e0", "e1"]
    assert gzip.decompress(path.read_bytes()).count(b'"kind":"plan"') == 2  # members join cleanly


# -- truncation ------------------------------------------------------------------------------------
def test_the_loader_keeps_every_complete_line_before_a_truncation(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl.gz"
    eps = episodes(3)
    for ep in eps:
        write_episode(RecordWriter(path), ep)
    blob = path.read_bytes()
    whole = [(r["kind"], r.get("step")) for r in read_lines(path)]
    cut_path = tmp_path / "cut.jsonl.gz"
    previous = 0
    for cut in range(0, len(blob), 53):
        cut_path.write_bytes(blob[:cut])
        got = [(r["kind"], r.get("step")) for r in read_lines(cut_path)]
        assert got == whole[: len(got)]  # a prefix, never anything else
        assert len(got) >= previous  # more bytes never give fewer lines
        previous = len(got)
        loaded = load_episodes(cut_path)
        assert all(e.complete for e in loaded[:-1])  # only the last episode can be cut off
    cut_path.write_bytes(blob)
    assert all(e.complete for e in load_episodes(cut_path)) and len(load_episodes(cut_path)) == 3


def test_a_file_that_ends_in_garbage_or_is_empty_loads_what_it_can(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl.gz"
    assert list(read_lines(_touch(path))) == []
    write_episode(RecordWriter(path), episodes(1)[0])
    good = path.read_bytes()
    path.write_bytes(good + b"\x00not gzip at all")
    assert [e.complete for e in load_episodes(path)] == [True]
    path.write_bytes(good[:-60])  # the end line is cut off
    [partial] = load_episodes(path)
    assert not partial.complete and partial.steps


def _touch(path: Path) -> Path:
    path.write_bytes(b"")
    return path


# -- noise injection -------------------------------------------------------------------------------
def test_an_episode_without_noise_follows_the_teacher_to_done() -> None:
    ep = episodes(1, noise=0.0)[0]
    assert ep.outcome == "done" and all(not s["noise"] for s in ep.steps)
    assert ep.end["noisy_steps"] == 0 and ep.header["noise_rate"] == 0.0


def test_noise_executes_random_valid_actions_but_stores_only_the_teachers_label() -> None:
    task = toy_task(plan(5, mark="no"), plan_id="noisy")
    ep = run_episode(env(max_steps=60), task, seed=4, episode="n", noise_rate=0.3)
    noisy = [s for s in ep.steps if s["noise"]]
    assert noisy and ep.end["noisy_steps"] == len(noisy)
    for s in ep.steps:
        assert "action" not in s and s["acceptable"]
    # after a random action the label is the way back, undo first
    after = ep.steps[ep.steps.index(noisy[0]) + 1]
    assert after["acceptable"][0]["tool"] == "undo" or after["acceptable"][0]["tool"].startswith(
        ("delete_", "edit_")
    )
    assert ep.outcome == "done"  # the teacher still gets the episode home


def test_the_same_seed_gives_the_same_episode() -> None:
    task = toy_task(plan(5, 3, mark="no"), plan_id="p")
    a = run_episode(env(max_steps=80), task, seed=9, episode="x", noise_rate=0.2)
    b = run_episode(env(max_steps=80), task, seed=9, episode="x", noise_rate=0.2)
    assert json.dumps(a.steps, sort_keys=True) == json.dumps(b.steps, sort_keys=True)
    assert a.end == b.end
    c = run_episode(env(max_steps=80), task, seed=10, episode="x", noise_rate=0.2)
    assert json.dumps(c.steps, sort_keys=True) != json.dumps(a.steps, sort_keys=True)


def test_an_episode_draws_its_noise_rate_from_the_list() -> None:
    import random

    rates = [draw_noise_rate(random.Random(s)) for s in range(500)]
    assert set(rates) == set(NOISE_RATES)
    assert 0.3 < rates.count(0.0) / len(rates) < 0.5  # 0 is in the list twice of five
    ep = run_episode(env(), toy_task(plan(5), plan_id="d"), seed=1, episode="d")
    assert ep.header["noise_rate"] in NOISE_RATES


def test_a_step_no_recipe_covers_ends_the_episode_with_no_label() -> None:
    the_plan = plan(5)
    the_plan["steps"][0]["transformation"] = "pleats"
    ep = run_episode(env(), toy_task(the_plan, plan_id="u"), seed=0, episode="u", noise_rate=0.0)
    assert ep.outcome == "no_label" and ep.steps == []


def test_a_teacher_episode_needs_a_plan() -> None:
    with pytest.raises(ValueError, match="needs a plan"):
        run_episode(env(), toy_task(None), seed=0, episode="x")


# -- seeds, levels, splits -------------------------------------------------------------------------
def test_seed_ranges_are_disjoint_and_checked() -> None:
    spans = sorted(SEED_RANGES.values())
    assert all(a[1] < b[0] for a, b in pairwise(spans))
    assert check_seed("teacher", 5) == 5 and check_seed("dagger", 1_000_000) == 1_000_000
    with pytest.raises(ValueError, match="outside the rl range"):
        check_seed("rl", 5)


def test_a_plans_level_comes_from_its_number_of_steps() -> None:
    def level(n: int) -> int:
        return level_for({"steps": [{}] * n})

    assert [level(n) for n in (1, 2, 3, 5, 6, 7, 8, 9, 10, 12, 13)] == [
        1,
        2,
        3,
        3,
        4,
        4,
        5,
        5,
        6,
        6,
        0,
    ]


def test_splits_are_by_family_and_stable() -> None:
    a, b = plan(5, 3), plan(7, 1)
    assert plan_family(a) == plan_family(b) == "lengthen_or_shorten+lengthen_or_shorten"
    fractions = {"train": 0.8, "val": 0.1, "test": 0.1}
    assert split_of(plan_family(a), fractions, "v1") == split_of(plan_family(b), fractions, "v1")
    counts = {"train": 0, "val": 0, "test": 0}
    for i in range(2000):
        counts[split_of(f"family-{i}", fractions, "v1")] += 1
    assert 1500 < counts["train"] < 1700 and 100 < counts["val"] < 300 and counts["test"] > 100
    assert split_of("same", fractions, "v1") == split_of("same", fractions, "v1")
    assert [split_of(f"k{i}", fractions, "v1") for i in range(50)] != [
        split_of(f"k{i}", fractions, "v2") for i in range(50)
    ]
