"""A task: where an episode starts and what it is to make."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from yoko_engine.landmarks import Landmarks
from yoko_engine.model import MeasurementSet, Pattern


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
