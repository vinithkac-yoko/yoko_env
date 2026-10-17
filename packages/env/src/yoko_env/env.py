"""The environment: `reset`, `step`, `state`, `fork` (docs/BUILD_SPEC.md section 8, Addendum 1
sections 9 to 11).

    env = PatternEnv(EnvConfig(specs, recipes))
    obs = env.reset(task, seed=42)
    result = env.step(Call("edit_point_at_distance_angle", {...}))   # StepResult
    child = env.fork()

An action is a tool call (`Call`, a dict `{"tool", "args"}`, or `(name, args)`). `done` ends the
episode; only then are pieces computed, and only the ones the episode touched. There is no shaped
reward: `reward` is 0 unless a hook (`EnvConfig.reward`) says otherwise.

Observations are for the policy. The teacher's labels are not: `expert` (the acceptable set) and
`info["on_plan"]` are privileged, returned in `info`, and never put in an observation or in any tool
result. Provenance records them in the pattern's sidecar for training and scoring.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, cast

from yoko_engine.session import ActionMeta, PatternSession
from yoko_tools.plan import plan_variables
from yoko_tools.recipes import RecipeRegistry
from yoko_tools.runtime import Toolbox, ToolError
from yoko_tools.spec import ToolSpec
from yoko_tools.teacher import (
    APPLY_STEP,
    DONE_TOOL,
    Analysis,
    Call,
    Label,
    Teacher,
    teacher_sizes,
)

from yoko_env.card import card_text, status_card
from yoko_env.pieces import touched_pieces
from yoko_env.task import Task
from yoko_env.valid import ValidActions, valid_actions

OUTCOMES = ("done", "out_of_steps", "too_many_invalid")


class EnvError(RuntimeError):
    """The environment was used wrongly (a step after the episode ended, a step before reset)."""


@dataclass(frozen=True, slots=True)
class StepEvent:
    """What a reward hook sees after a step."""

    call: Call
    result: Mapping[str, Any]
    done: bool
    outcome: str | None


RewardHook = Callable[["PatternEnv", StepEvent], float]


@dataclass(frozen=True, slots=True)
class EnvConfig:
    specs: Mapping[str, ToolSpec]
    recipes: RecipeRegistry = field(default_factory=RecipeRegistry)
    tools: frozenset[str] | None = None  # the run's tool subset; None = every tool
    composites: bool = True  # `apply_step` in the acceptable set and the valid actions
    teacher: bool = True  # label every step (the privileged `expert` and `on_plan`)
    max_steps: int = 100
    max_invalid: int = 20
    library: Any = None
    reward: RewardHook | None = None  # no shaped reward by default


@dataclass(frozen=True, slots=True)
class Observation:
    """What the policy sees."""

    step: int
    steps_left: int
    progress: int | None  # the active plan step (1-based); None when every step is complete
    status_card: dict[str, Any]
    card_text: str
    state: dict[str, Any]
    last_result: dict[str, Any] | None
    valid_actions: ValidActions
    plan: Mapping[str, Any] | None = None  # given at reset only: it does not change

    def as_json(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "steps_left": self.steps_left,
            "progress": self.progress,
            "status_card": self.status_card,
            "card_text": self.card_text,
            "state": self.state,
            "last_result": self.last_result,
            "valid_actions": self.valid_actions.as_json(),
        }


@dataclass(frozen=True, slots=True)
class StepResult:
    observation: Observation
    reward: float
    done: bool
    info: dict[str, Any]  # privileged: on_plan, expert, op, outcome, pieces at done ...


class PatternEnv:
    def __init__(self, config: EnvConfig) -> None:
        self.cfg = config
        self._reset_fields()

    def _reset_fields(self) -> None:
        self.task: Task | None = None
        self.box: Toolbox | None = None
        self.teacher: Teacher | None = None
        self.plan: Mapping[str, Any] | None = None
        self.rng = random.Random(0)
        self.episode: str | None = None
        self.author = "model"
        self.steps = 0
        self.invalid = 0
        self.history: list[Call] = []
        self.outcome: str | None = None
        self._start: PatternSession | None = None
        self._analysis_cache: tuple[tuple[int, str], Analysis] | None = None
        self._max_steps = self.cfg.max_steps

    # -- starting -------------------------------------------------------------------------------
    def reset(
        self,
        task: Task,
        seed: int = 0,
        *,
        episode: str | None = None,
        author: str = "model",
    ) -> Observation:
        """Start an episode: the task's pattern as a working copy, with the plan's amounts as
        variables. `author` is recorded in provenance (`model`, `teacher`, `human`)."""
        self._reset_fields()
        self.task = task
        self.rng = random.Random(seed)
        self.episode = episode
        self.author = author
        self.plan = task.plan
        self._max_steps = task.max_steps or self.cfg.max_steps
        session = PatternSession(
            task.pattern, task.measurements, size=task.size, height=task.height
        )
        self.box = self._toolbox(session, task.landmarks)
        if task.plan is not None:
            for action in plan_variables(task.plan, task.pattern.unit):
                result = session.apply(action, ActionMeta(author="plan"))
                if not result.ok:
                    raise EnvError(f"the plan does not apply: {result.error}")
            session.forget_history()  # the plan's variables are the starting point, not a step
            composites = self.cfg.composites and self._allowed(APPLY_STEP)
            self.teacher = Teacher(
                self.cfg.recipes,
                others=teacher_sizes(task.pattern, task.measurements, session.measurements),
                composites=composites,
            )
        self._start = session.fork()
        return self._observe(None, first=True)

    def _toolbox(self, session: PatternSession, landmarks: Any) -> Toolbox:
        return Toolbox(
            session,
            self.cfg.specs,
            landmarks=landmarks,
            handlers={APPLY_STEP: self._apply_step},
            library=self.cfg.library,
        )

    def _allowed(self, tool: str) -> bool:
        return self.cfg.tools is None or tool in self.cfg.tools

    # -- the teacher's view (privileged) --------------------------------------------------------
    def analysis(self) -> Analysis | None:
        """Where the plan stands in the current state; None when there is no plan."""
        box, teacher, plan = self.box, self.teacher, self.plan
        if box is None or teacher is None or plan is None:
            return None
        key = (box.session.clock, box.session.state_hash())
        if self._analysis_cache is None or self._analysis_cache[0] != key:
            self._analysis_cache = (key, teacher.analyse(box, plan))
        return self._analysis_cache[1]

    def expert(self) -> list[Call] | None:
        """PRIVILEGED. The teacher's acceptable set for the current state; None when no recipe
        covers the step (no label), or when there is no plan or the teacher is off."""
        box, teacher, plan = self._live()
        analysis = self.analysis()
        if not self.cfg.teacher or teacher is None or plan is None or analysis is None:
            return None
        return teacher.acceptable(box, plan, analysis)

    def _live(self) -> tuple[Toolbox, Teacher | None, Mapping[str, Any] | None]:
        if self.box is None:
            raise EnvError("call reset first")
        return self.box, self.teacher, self.plan

    # -- stepping -------------------------------------------------------------------------------
    def step(self, action: Call | Mapping[str, Any] | tuple[str, Mapping[str, Any]]) -> StepResult:
        box, teacher, plan = self._live()
        if self.outcome is not None:
            raise EnvError(f"the episode is over ({self.outcome}); call reset")
        call = as_call(action)
        self.steps += 1
        analysis = self.analysis()
        label = Label(None, None, None)
        if self.cfg.teacher and teacher is not None and plan is not None and analysis is not None:
            label = teacher.label(box, plan, call, analysis)
        active = analysis.active if analysis is not None else None
        step_number = label.step if label.step is not None else active
        meta = ActionMeta(
            step=f"s{step_number}" if step_number is not None else None,
            op=label.op,
            author=self.author,
            episode=self.episode,
            on_plan=label.on_plan,
        )
        if not self._allowed(call.tool) and call.tool != DONE_TOOL:
            result = failed("tool_not_available", f"{call.tool} is not available in this run")
        else:
            result = box.call(call.tool, call.args, meta)
        self.history.append(call)
        if not result["ok"]:
            self.invalid += 1
        done = result["ok"] and call.tool == DONE_TOOL
        info: dict[str, Any] = {
            "on_plan": label.on_plan,
            "step_label": label.step,
            "op": label.op,
            "invalid": self.invalid,
        }
        if done:
            self.outcome = "done"
            info.update(self._finish())
        elif self.steps >= self._max_steps:
            self.outcome = "out_of_steps"
        elif self.invalid > self.cfg.max_invalid:
            self.outcome = "too_many_invalid"
        over = self.outcome is not None
        info["outcome"] = self.outcome
        info["expert"] = self._expert_json()
        event = StepEvent(call, result, over, self.outcome)
        reward = float(self.cfg.reward(self, event)) if self.cfg.reward is not None else 0.0
        return StepResult(self._observe(result), reward, over, info)

    def _expert_json(self) -> list[dict[str, Any]] | None:
        found = self.expert()
        return None if found is None else [c.as_json() for c in found]

    def _finish(self) -> dict[str, Any]:
        """At `done`: the pieces the episode touched, and only those, are computed and checked."""
        box = self.box
        assert box is not None and self._start is not None
        touched = touched_pieces(self._start, box.session)
        geoms = box.session.pieces(touched)
        issues = box.session.piece_issues(touched)
        analysis = self.analysis()
        return {
            "pieces": {
                "touched": sorted(g.name for g in geoms.values()),
                "problems": [
                    {"code": i.code, "message": i.message, "severity": i.severity} for i in issues
                ],
            },
            "plan_complete": analysis.complete if analysis is not None else None,
            "errors": sum(1 for i in box.session.issues() if i.severity == "error"),
            "state_hash": box.session.state_hash(),
        }

    def pieces(self) -> dict[str, Any]:
        """The touched pieces' geometry now (computed on demand, only for touched pieces)."""
        box = self.box
        if box is None or self._start is None:
            raise EnvError("call reset first")
        return {
            g.name: g for g in box.session.pieces(touched_pieces(self._start, box.session)).values()
        }

    # -- the composite --------------------------------------------------------------------------
    def _apply_step(
        self, box: Toolbox, args: Mapping[str, Any], meta: ActionMeta
    ) -> dict[str, Any]:
        """`apply_step`: every op of the active step that is not done, in dependency order. If one
        cannot be made, none is kept."""
        teacher, plan = self.teacher, self.plan
        if teacher is None or plan is None:
            raise ToolError("no_plan", "this run has no plan to follow")
        number = cast(int, args["step"])
        analysis = teacher.analyse(box, plan)
        if analysis.problem:
            raise ToolError("no_plan", analysis.problem)
        if analysis.active != number:
            where = (
                "all steps are complete" if analysis.active is None else f"step {analysis.active}"
            )
            raise ToolError(
                "not_active", f"step {number} is not the active step ({where})", "step", None
            )
        if not analysis.step(number).covered:
            raise ToolError("no_recipe", f"no recipe covers step {number}", "step", None)
        landmarks = box.landmarks
        applied = 0
        merged: dict[str, Any] | None = None
        ops: list[str] = []
        for _ in range(len(analysis.step(number).ops) + 1):
            now = teacher.analyse(box, plan)
            status = now.step(number)
            if status.state == "done":
                break
            ready = next((o for o in status.ops if o.status == "ready" and o.call), None)
            if ready is None or ready.call is None:
                break
            result = box.call(
                ready.call.tool,
                ready.call.args,
                replace(meta, step=f"s{number}", op=ready.op.id, on_plan=True),
            )
            if not result["ok"]:
                self._roll_back(box, applied, landmarks)
                return result
            applied += 1
            ops.append(ready.op.id)
            merged = result if merged is None else _merge(merged, result)
        if merged is None or teacher.analyse(box, plan).step(number).state != "done":
            self._roll_back(box, applied, landmarks)
            raise ToolError(
                "step_incomplete", f"step {number} could not be completed", "step", None
            )
        merged["data"] = {"ops": ops}
        return merged

    @staticmethod
    def _roll_back(box: Toolbox, applied: int, landmarks: Any) -> None:
        for _ in range(applied):
            box.session.undo()
        box.landmarks = landmarks

    # -- looking --------------------------------------------------------------------------------
    def state(self) -> dict[str, Any]:
        """A compact picture of the pattern now."""
        box, _, _ = self._live()
        s = box.session
        ev = s.evaluation
        return {
            "objects": len(s.pattern.objects()),
            "points": len(ev.points),
            "curves": len(ev.curves),
            "pieces": _piece_names(s),
            "variables": len(s.pattern.variables),
            "errors": sum(1 for i in ev.issues if i.severity == "error"),
            "state_hash": s.state_hash()[:16],
        }

    def valid_actions(self) -> ValidActions:
        box, _, _ = self._live()
        analysis = self.analysis()
        return valid_actions(box, self.cfg.tools, step_open=self._step_open(analysis))

    def _step_open(self, analysis: Analysis | None) -> bool:
        if analysis is None or analysis.active is None or analysis.problem:
            return False
        if not self.cfg.composites or self.teacher is None:
            return False
        st = analysis.step(analysis.active)
        return st.covered and not st.error and any(o.status != "done" for o in st.ops)

    def _observe(self, last: dict[str, Any] | None, first: bool = False) -> Observation:
        analysis = self.analysis()
        card = status_card(self.plan, analysis)
        return Observation(
            step=self.steps,
            steps_left=max(self._max_steps - self.steps, 0),
            progress=analysis.active if analysis is not None else None,
            status_card=card,
            card_text=card_text(card),
            state=self.state(),
            last_result=last,
            valid_actions=self.valid_actions(),
            plan=self.plan if first else None,
        )

    # -- forking and replay ---------------------------------------------------------------------
    def fork(self) -> PatternEnv:
        """An independent copy at this point (tree search, grouped sampling)."""
        box, _, _ = self._live()
        child = PatternEnv(self.cfg)
        child.task, child.plan, child.teacher = self.task, self.plan, self.teacher
        child.rng = random.Random()
        child.rng.setstate(self.rng.getstate())
        child.episode, child.author = self.episode, self.author
        child.steps, child.invalid, child.outcome = self.steps, self.invalid, self.outcome
        child.history = list(self.history)
        child._start = self._start
        child._max_steps = self._max_steps
        child.box = child._toolbox(box.session.fork(), box.landmarks)
        return child

    def replay(self, task: Task, calls: Collection[Call], seed: int = 0, **kw: Any) -> Observation:
        """Start again and take the same actions: a killed worker's episode, restored exactly."""
        obs = self.reset(task, seed, **kw)
        for call in calls:
            obs = self.step(call).observation
        return obs


def _piece_names(session: PatternSession) -> list[str]:
    from yoko_engine.pieces_edit import pieces_of

    return [p.get("name") or "" for _, p, _ in pieces_of(session.pattern)]


def as_call(action: Call | Mapping[str, Any] | tuple[str, Mapping[str, Any]]) -> Call:
    if isinstance(action, Call):
        return action
    if isinstance(action, tuple):
        return Call(action[0], dict(action[1]))
    return Call.from_json(action)


def failed(code: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "created": [],
        "changed": [],
        "deleted": [],
        "warnings": [],
        "error": {"code": code, "field": None, "message": message, "hint": None},
        "diff": {},
    }


def _merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        **b,
        "created": [*a["created"], *b["created"]],
        "changed": [*a["changed"], *b["changed"]],
        "deleted": [*a["deleted"], *b["deleted"]],
        "warnings": b["warnings"],
    }
