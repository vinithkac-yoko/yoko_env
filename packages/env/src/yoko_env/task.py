"""A task: where an episode starts and what it is to make."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from yoko_engine.landmarks import Landmarks
from yoko_engine.model import MeasurementSet, Pattern

if TYPE_CHECKING:
    from yoko_env.invariants import SeamPair


@dataclass(frozen=True, slots=True)
class Task:
    """A starting pattern, the measurements it is evaluated with (a multisize table, or a person's
    own file), and a plan (or a brief when there is no plan)."""

    pattern: Pattern
    measurements: MeasurementSet
    plan: Mapping[str, Any] | None = None
    landmarks: Landmarks | None = None
    brief: str = ""
    plan_id: str = ""
    level: int | None = None  # difficulty level of the plan (Addendum 1 section 12)
    size: float | None = None  # a size of the table; the table's base size when None
    height: float | None = None
    max_steps: int | None = None  # overrides the env's limit
    seam_pairs: tuple[SeamPair, ...] = ()  # edges sewn together, checked at done
    # the multisize table the pattern was drafted from: how a person's own file is nudged
    grading: MeasurementSet | None = None
