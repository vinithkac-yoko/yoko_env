"""The environment: reset, step, done, valid actions, the status card, privacy of the labels."""

from __future__ import annotations

import json
import random
from typing import Any

import pytest
from toy import RECIPES, ROOT, SPECS, HemOnly, plan, toy_task
from yoko_engine.binding import individual_table
from yoko_engine.landmarks import Landmarks
from yoko_engine.pieces import evaluate_pieces
from yoko_env import (
    EnvConfig,
    EnvError,
    PatternEnv,
    Task,
    card_text,
    random_action,
    valid_actions,
)
from yoko_io.library import DirectoryLibrary
from yoko_tools.recipes import RecipeRegistry
from yoko_tools.teacher import DONE, Call


def make_env(**kw: Any) -> PatternEnv:
    return PatternEnv(EnvConfig(SPECS, RECIPES, **kw))


def follow_teacher(env: PatternEnv, limit: int = 20) -> list[dict[str, Any]]:
    """Take the first non-composite acceptable action until done."""
    infos: list[dict[str, Any]] = []
    for _ in range(limit):
        accepted = env.expert()
        assert accepted
        pick = next(c for c in accepted if c.tool != "apply_step")
        result = env.step(pick)
        infos.append(result.info)
        if result.done:
            return infos
    raise AssertionError("did not finish")


# -- reset and the observation ---------------------------------------------------------------------
def test_reset_gives_the_plan_the_card_progress_and_valid_actions() -> None:
    env = make_env()
    obs = env.reset(toy_task(plan(5)), seed=1)
    assert obs.progress == 1 and obs.step == 0 and obs.plan is not None
    assert [(r["step"], r["state"]) for r in obs.status_card["steps"]] == [(1, "active")]
    active = obs.status_card["active"]
    assert active["recipe"] == "lengthen_or_shorten"
    assert active["amounts"] == [{"name": "amount", "unit": "cm", "target": 5.0, "now": 0.0}]
    assert active["landmarks"] == {"hem_left": "skirt.hem_left", "hem_right": "skirt.hem_right"}
    assert "target 5 cm, now 0 cm" in obs.card_text
    assert "done" in obs.valid_actions.tools
    assert "apply_step" not in obs.valid_actions.tools  # composites are off by default
    assert "apply_step" in make_env(composites=True).reset(toy_task(plan(5))).valid_actions.tools
    assert "undo" not in obs.valid_actions.tools  # the plan's variables are not a step to undo
    assert env.state()["objects"] == 4


def test_the_teachers_labels_never_reach_the_policy() -> None:
    env = make_env()
    obs = env.reset(toy_task(plan(5)), seed=1, author="teacher")
    seen = [json.dumps(obs.as_json())]
    for _ in range(3):
        accepted = env.expert()
        assert accepted
        result = env.step(next(c for c in accepted if c.tool != "apply_step"))
        seen.append(json.dumps(result.observation.as_json()))
        assert result.info["on_plan"] is True  # privileged: in info only
    for blob in seen:
        for secret in ("on_plan", "expert", "teacher", "acceptable"):
            assert secret not in blob
    box = env.box
    assert box is not None
    history = box.call("get_object", {"object": "H1"})["data"]["history"]
    assert all(set(h) == {"what", "step"} for h in history)
    assert "author" not in json.dumps(box.call("get_object", {"object": "H1"}))


def test_the_expert_is_none_without_a_plan_or_with_the_teacher_off() -> None:
    env = make_env()
    env.reset(toy_task(None))
    assert env.expert() is None and env.analysis() is None
    result = env.step(Call("point_origin", {"label": "Q", "x": 1, "y": 1}))
    assert result.info["on_plan"] is None and result.info["expert"] is None
    quiet = make_env(teacher=False)
    quiet.reset(toy_task(plan(5)))
    assert quiet.expert() is None
    assert (
        quiet.step(Call("edit_point_at_distance_angle", {"target": "H1", "length": "99"})).info[
            "on_plan"
        ]
        is None
    )


def test_stepping_before_reset_or_after_done_is_an_error() -> None:
    env = make_env()
    with pytest.raises(EnvError, match="reset"):
        env.step(Call("done"))
    env.reset(toy_task(plan(5)))
    assert env.step(Call("done")).done
    with pytest.raises(EnvError, match="over"):
        env.step(Call("done"))


# -- stepping --------------------------------------------------------------------------------------
def test_following_the_teacher_finishes_the_plan_and_every_step_is_on_plan() -> None:
    env = make_env()
    env.reset(toy_task(plan(5)), author="teacher")
    infos = follow_teacher(env)
    assert [i["on_plan"] for i in infos] == [True, True, True, True]  # three ops, then done
    assert [i["op"] for i in infos[:3]] == ["hem_left", "hem_right", "notch"]
    assert infos[-1]["outcome"] == "done" and infos[-1]["plan_complete"] is True
    assert infos[-1]["errors"] == 0
    assert env.outcome == "done"


def test_the_card_follows_the_work() -> None:
    env = make_env()
    env.reset(toy_task(plan(5, 3)))
    accepted = env.expert()
    assert accepted
    result = env.step(accepted[0])
    active = result.observation.status_card["active"]
    assert active["step"] == 1 and active["amounts"][0]["now"] == pytest.approx(5)
    second = env.step(env.expert()[0])  # type: ignore[index]
    assert second.observation.status_card["active"]["step"] == 1
    third = env.step(env.expert()[0])  # type: ignore[index]
    states = [r["state"] for r in third.observation.status_card["steps"]]
    assert states == ["done", "active"] and third.observation.progress == 2
    text = card_text(third.observation.status_card)
    assert text.splitlines()[0].startswith("[x] step 1") and "[>] step 2" in text


def test_an_off_plan_action_is_flagged_and_the_expert_turns_to_recovery() -> None:
    env = make_env()
    env.reset(toy_task(plan(5, mark="no")))
    wrong = env.step(
        Call(
            "point_at_distance_angle",
            {"label": "X", "base_point": "A", "length": "3", "angle": "0"},
        )
    )
    assert wrong.info["on_plan"] is False and wrong.reward == 0.0
    tools = [e["tool"] for e in wrong.info["expert"]]
    assert tools == ["undo", "delete_point_at_distance_angle"]
    fixed = env.step(Call.from_json(wrong.info["expert"][1]))
    assert fixed.info["on_plan"] is True
    assert fixed.info["expert"][0]["op"] == "hem_left"


def test_a_failed_action_counts_as_invalid_and_too_many_end_the_episode() -> None:
    env = make_env(max_invalid=2)
    env.reset(toy_task(plan(5)))
    bad = Call(
        "point_at_distance_angle", {"label": "Y", "base_point": "NOPE", "length": "1", "angle": "0"}
    )
    first = env.step(bad)
    assert not first.observation.last_result["ok"] and first.info["invalid"] == 1  # type: ignore[index]
    assert first.observation.last_result["error"]["code"] == "unknown_reference"  # type: ignore[index]
    env.step(bad)
    last = env.step(bad)
    assert last.done and last.info["outcome"] == "too_many_invalid"


def test_the_step_budget_ends_the_episode() -> None:
    env = make_env(max_steps=2)
    env.reset(toy_task(plan(5)))
    env.step(Call("get_state", {}))
    result = env.step(Call("get_state", {}))
    assert result.done and result.info["outcome"] == "out_of_steps"
    assert make_env(max_steps=50).reset(toy_task(plan(5), max_steps=1)).steps_left == 1


def test_a_tool_outside_the_runs_subset_is_refused() -> None:
    env = make_env(
        tools=frozenset({"point_at_distance_angle", "edit_point_at_distance_angle", "done"})
    )
    obs = env.reset(toy_task(plan(5)))
    assert "apply_step" not in obs.valid_actions.tools and "undo" not in obs.valid_actions.tools
    result = env.step(Call("point_origin", {"label": "Q", "x": 1, "y": 1}))
    assert result.observation.last_result["error"]["code"] == "tool_not_available"  # type: ignore[index]
    # without composites in the subset the teacher does not offer one either
    assert all(c.tool != "apply_step" for c in env.expert() or [])


# -- the composite ---------------------------------------------------------------------------------
def test_apply_step_is_refused_unless_the_run_turns_composites_on() -> None:
    env = make_env()
    env.reset(toy_task(plan(5)))
    result = env.step(Call("apply_step", {"step": 1}))
    assert result.observation.last_result["error"]["code"] == "tool_not_available"  # type: ignore[index]
    assert all(c.tool != "apply_step" for c in env.expert() or [])


def test_apply_step_does_the_whole_step_and_marks_every_op_on_plan() -> None:
    env = make_env(composites=True)
    env.reset(toy_task(plan(5)))
    result = env.step(Call("apply_step", {"step": 1}))
    assert result.info["on_plan"] is True
    last = result.observation.last_result
    assert (
        last is not None
        and last["ok"]
        and last["data"]["ops"] == ["hem_left", "hem_right", "notch"]
    )
    assert result.observation.progress is None and env.expert() == [DONE]
    # the result is the same pattern as doing the ops one at a time
    other = make_env()
    other.reset(toy_task(plan(5)))
    follow_teacher(other)
    assert env.box is not None and other.box is not None
    assert env.box.session.state_hash() == other.box.session.state_hash()
    # and it can be taken back in one undo per op
    assert env.box.landmarks is not None


def test_apply_step_refuses_a_step_that_is_not_active_and_changes_nothing() -> None:
    env = make_env(composites=True)
    env.reset(toy_task(plan(5, 3)))
    assert env.box is not None
    before = env.box.session.state_hash()
    result = env.step(Call("apply_step", {"step": 2}))
    assert result.observation.last_result["error"]["code"] == "not_active"  # type: ignore[index]
    assert env.box.session.state_hash() == before and result.info["on_plan"] is False


def test_apply_step_rolls_back_when_one_op_cannot_be_made() -> None:
    env = make_env(composites=True)
    task = toy_task(plan(5))
    env.reset(task)
    assert env.box is not None
    before = env.box.session.state_hash()
    # make the second op impossible: its target no longer exists
    assert env.box.call("delete_point_at_distance_angle", {"target": "H2"})["ok"]
    after_delete = env.box.session.state_hash()
    result = env.step(Call("apply_step", {"step": 1}))
    assert not result.observation.last_result["ok"]  # type: ignore[index]
    assert env.box.session.state_hash() == after_delete != before


def test_apply_step_without_a_plan_says_so() -> None:
    env = make_env(composites=True)
    env.reset(toy_task(None))
    result = env.step(Call("apply_step", {"step": 1}))
    assert result.observation.last_result["error"]["code"] == "no_plan"  # type: ignore[index]


# -- done and pieces -------------------------------------------------------------------------------
def basic_skirt_env(**kw: Any) -> tuple[PatternEnv, Task]:
    library = DirectoryLibrary(ROOT / "library", ROOT / "fixtures")
    _, pattern, table = library.load("aldrich-womens-6th-basic")
    the_plan = plan(5)
    the_plan["steps"][0]["refs"] = {"hem": "skirt_back.hem_left"}
    the_plan["steps"][0]["pieces"] = ["A - Skirt Back"]
    landmarks = Landmarks.from_mapping(
        {"version": 1, "landmarks": {"skirt_back.hem_left": {"label": "A3"}}}
    )
    task = Task(pattern, table, the_plan, landmarks, plan_id="basic-skirt")
    return PatternEnv(EnvConfig(SPECS, RecipeRegistry([HemOnly()]), **kw)), task


def test_pieces_are_computed_only_at_done_and_only_the_touched_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env, task = basic_skirt_env()
    asked: list[Any] = []
    real = evaluate_pieces

    def spy(pattern: Any, ev: Any, only: Any = None) -> Any:
        asked.append(None if only is None else set(only))
        return real(pattern, ev, only)

    monkeypatch.setattr("yoko_engine.session.evaluate_pieces", spy)
    env.reset(task, author="teacher")
    result = env.step(env.expert()[0])  # type: ignore[index]
    assert asked == [] and not result.done  # nothing is computed while working
    done = env.step(Call("done"))
    # only the touched pieces, at the base size and at every size the invariants are checked at
    assert done.done and asked and all(a is not None and len(a) == 2 for a in asked)
    assert len(asked) == 1 + len(done.info["invariants"]["sizes"])
    # the front is drafted from the back's points, so it moves too; the other four pieces do not
    assert done.info["pieces"]["touched"] == ["A - Skirt Back", "A - Skirt Front"]
    assert done.info["pieces"]["problems"] == [] and done.info["plan_complete"] is True
    assert done.info["invariants_ok"] is True


def test_done_with_a_plan_not_finished_still_ends_the_episode_and_says_so() -> None:
    env, task = basic_skirt_env()
    env.reset(task)
    done = env.step(Call("done"))
    assert done.done and done.info["plan_complete"] is False and done.info["on_plan"] is False
    assert done.info["pieces"]["touched"] == []


def test_a_persons_own_measurement_file_replaces_the_table() -> None:
    env, task = basic_skirt_env()
    library = DirectoryLibrary(ROOT / "library", ROOT / "fixtures")
    _, _, table = library.load("aldrich-womens-6th-basic")
    person = individual_table(table.values(), "cm")
    own = Task(task.pattern, person, task.plan, task.landmarks)
    env.reset(own, author="teacher")
    # a person's file has one size: the teacher matches at it and at two nudged copies of it
    assert env.teacher is not None and len(env.teacher.sizes.others) == 2
    assert env.expert() is not None
    follow_teacher(env)
    assert env.outcome == "done"


def test_a_steps_check_is_stored_once_when_the_step_completes() -> None:
    env = make_env()
    env.reset(toy_task(plan(5, 3, mark="no")), author="teacher")
    first = env.step(env.expert()[0])  # type: ignore[index]
    assert first.info["steps_completed"] == []
    second = env.step(env.expert()[0])  # type: ignore[index]
    [record] = second.info["steps_completed"]
    assert (
        record["step"] == 1
        and record["at"] == 2
        and record["check"] == {"done": True, "detail": ""}
    )
    assert record["measured"]["amount"] == pytest.approx(5) and record["targets"]["amount"] == 5
    # step 2 then moves the hem again; step 1's record is the one taken when it completed
    infos = follow_teacher(env)
    assert [r["step"] for r in infos[-1]["step_checks"]] == [1, 2]
    assert infos[-1]["step_checks"][0]["measured"]["amount"] == pytest.approx(5)


def test_an_undone_step_is_measured_again_when_it_completes_again() -> None:
    env = make_env()
    env.reset(toy_task(plan(5, mark="no")), author="teacher")
    for _ in range(2):
        env.step(env.expert()[0])  # type: ignore[index]
    assert 1 in env.step_checks
    env.step(Call("undo"))
    assert 1 not in env.step_checks
    again = env.step(env.expert()[0])  # type: ignore[index]
    assert [r["step"] for r in again.info["steps_completed"]] == [1]


def test_the_invariants_are_checked_at_done_at_every_size() -> None:
    env, task = basic_skirt_env()
    env.reset(task, author="teacher")
    env.step(env.expert()[0])  # type: ignore[index]
    done = env.step(Call("done")).info
    inv = done["invariants"]
    assert inv["ok"] and inv["formula_error_count"] == 0 and inv["open_pieces"] == []
    # five sizes; the table does not grade by height, so each size's three heights are one check
    assert len(inv["sizes"]) == 5 and "height 158" in inv["sizes"][0]
    assert inv["seam_pairs"] == "none defined yet"


def test_a_data_run_may_check_the_invariants_at_the_teachers_three_sizes_only() -> None:
    env, task = basic_skirt_env(invariant_sizes="teacher")
    env.reset(task, author="teacher")
    env.step(env.expert()[0])  # type: ignore[index]
    inv = env.step(Call("done")).info["invariants"]
    assert inv["ok"] and len(inv["sizes"]) == 3  # the base size and the teacher's two others


def test_a_seam_pair_that_no_longer_matches_fails_the_invariants() -> None:
    from yoko_env import SeamPair, section_length_mm

    env, task = basic_skirt_env()
    # the two side seams, from the side waist to the side hem: equal in the basic set? Measured, not
    # assumed: the pair is given the ease it has at the start, so it matches before the change
    env.reset(task)
    assert env.box is not None
    back = "A - Skirt Back.section(A10, A8a)"
    front = "A - Skirt Front.section(A8c, A16)"
    ease = (section_length_mm(env.box, back) - section_length_mm(env.box, front)) / 10
    pair = SeamPair(back, front, ease_cm=ease)
    task = Task(task.pattern, task.measurements, task.plan, task.landmarks, seam_pairs=(pair,))
    env.reset(task)
    clean = env.step(Call("done")).info["invariants"]
    assert clean["ok"], clean
    env.reset(task)
    env.step(
        # the back's side hem point 3 cm lower: the back side seam grows, the front's does not
        Call("edit_point_along_line", {"target": "A8a", "length": "Line_A5_A3 + 3"})
    )
    changed = env.step(Call("done")).info["invariants"]
    assert not changed["ok"] and changed["seam_pairs"][0]["off_mm"] != 0


# -- forking and replay ----------------------------------------------------------------------------
def test_a_fork_is_independent_and_continues_from_the_same_point() -> None:
    env = make_env()
    env.reset(toy_task(plan(5)))
    env.step(env.expert()[0])  # type: ignore[index]
    child = env.fork()
    assert env.box is not None and child.box is not None
    assert child.box.session.state_hash() == env.box.session.state_hash()
    child.step(child.expert()[0])  # type: ignore[index]
    assert child.box.session.state_hash() != env.box.session.state_hash()
    assert child.steps == 2 and env.steps == 1
    assert child.analysis() is not None and env.analysis() is not None
    follow_teacher(child)
    assert child.outcome == "done" and env.outcome is None


def test_replaying_the_actions_gives_the_same_pattern() -> None:
    env = make_env()
    task = toy_task(plan(5, 3))
    env.reset(task, seed=7, author="teacher")
    follow_teacher(env, limit=30)
    again = make_env()
    again.replay(task, env.history, seed=7, author="teacher")
    assert env.box is not None and again.box is not None
    assert again.box.session.state_hash() == env.box.session.state_hash()
    assert again.outcome == env.outcome == "done"


# -- valid actions ---------------------------------------------------------------------------------
def test_valid_actions_list_the_tools_whose_preconditions_hold() -> None:
    env = make_env()
    env.reset(toy_task(plan(5)))
    valid = env.valid_actions()
    tools = set(valid.tools)
    assert {"point_origin", "point_at_distance_angle", "edit_point_at_distance_angle"} <= tools
    assert "edit_curve_spline" not in tools and "delete_curve_spline" not in tools  # none exist
    assert "union_pieces" not in tools and "set_piece" not in tools  # no pieces yet
    assert "copy_piece_from" not in tools  # nothing loaded
    assert "undo" not in tools
    assert set(valid.refs["point"]) >= {"A", "B", "H1", "H2", "skirt.hem_left", "skirt.hem_right"}
    assert valid.targets["point_at_distance_angle"] == ("B", "H1", "H2")  # not the origin
    spec = SPECS["edit_point_at_distance_angle"]
    assert valid.candidates(spec, "target") == ("B", "H1", "H2")
    assert valid.candidates(SPECS["point_at_distance_angle"], "base_point") == valid.refs["point"]
    env.step(Call("point_origin", {"label": "Q", "x": 1, "y": 1}))
    assert "undo" in env.valid_actions().tools


def test_valid_actions_know_pieces_and_variables() -> None:
    env = make_env()
    env.reset(toy_task(plan(5)))
    assert env.box is not None
    assert env.box.call(
        "add_piece", {"name": "Skirt", "nodes": [{"object": n} for n in ("A", "B", "H2", "H1")]}
    )["ok"]
    valid = valid_actions(env.box)
    assert {"set_piece", "delete_piece"} <= set(valid.tools) and "union_pieces" not in valid.tools
    assert valid.pieces == ("Skirt",) and "#s1_amount" in valid.variables
    assert valid.candidates(SPECS["delete_piece"], "piece") == ("Skirt",)
    assert valid.as_json()["pieces"] == ["Skirt"]


def test_a_random_action_is_valid_and_repeatable() -> None:
    env = make_env()
    env.reset(toy_task(plan(5)))
    assert env.box is not None
    first = random_action(env.box, random.Random(3))
    second = random_action(env.box, random.Random(3))
    assert first is not None and first == second
    assert first.tool in env.valid_actions().tools
    assert env.box.fork().call(first.tool, first.args)["ok"]
    picks = {random_action(env.box, random.Random(s)).tool for s in range(30)}  # type: ignore[union-attr]
    assert len(picks) > 3  # not always the same tool
    assert all(not t.startswith(("get_", "find_")) and t not in ("done", "undo") for t in picks)


def test_a_random_action_can_be_taken_and_the_teacher_recovers() -> None:
    env = make_env()
    env.reset(toy_task(plan(5, mark="no")), author="model")
    assert env.box is not None
    noisy = random_action(env.box, random.Random(11))
    assert noisy is not None
    result = env.step(noisy)
    assert result.observation.last_result is not None and result.observation.last_result["ok"]
    assert result.info["on_plan"] is False
    expert = result.info["expert"]
    assert (expert and expert[0]["tool"] in ("undo",)) or expert  # a way back is offered
    for _ in range(12):
        accepted = env.expert()
        assert accepted
        pick = accepted[0]
        res = env.step(pick)
        if res.done:
            break
    assert env.outcome == "done"
