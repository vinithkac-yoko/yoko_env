"""The record format for teacher data (Addendum 1 section 12): gzip JSONL.

One file holds many episodes. Each episode is written as one gzip member, in one write, when it
ends, so a worker killed in the middle of an episode damages at most the last member; everything
before it is intact. The loader keeps every complete line before a truncation.

Lines, in order, per episode:

    {"kind": "plan", "episode", "plan_id", "level", "source", "seed", "noise_rate", "plan"}
    {"kind": "step", "episode", "plan_id", "level", "step", "observation", "valid_actions",
     "acceptable", "noise", "progress"}                                       (one per step)
    {"kind": "end", "episode", "outcome", "steps", ...}

The plan is written once per episode, not in every step. `acceptable` is the teacher's label for the
state the observation shows (None: no recipe covers the step). `noise` says that the action
executed after this state was a random valid action; the action itself is not stored, only the
teacher's label. A source other than the teacher (`derivation_diff`, ...) uses the same lines.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import zlib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

NOISE_RATES = (0.0, 0.0, 0.1, 0.2, 0.3)  # an episode draws one of these
LEVEL_STEPS = ((1, 1), (2, 2), (3, 5), (4, 7), (5, 9), (6, 12))  # level -> most steps
TRAINING_LEVELS = (1, 2, 3)  # L4 to L6 are held out of training

# docs/adr/0009-heldout-and-seeds.md: disjoint, so no two uses ever share a seed
SEED_RANGES: Mapping[str, tuple[int, int]] = {
    "teacher": (0, 999_999),
    "dagger": (1_000_000, 1_999_999),
    "test": (2_000_000, 2_099_999),
    "rl": (3_000_000, 3_999_999),
    "calibration": (4_000_000, 4_099_999),
}


def check_seed(use: str, seed: int) -> int:
    """The seed, if it is in the range reserved for `use`; ValueError otherwise."""
    low, high = SEED_RANGES[use]
    if not low <= seed <= high:
        raise ValueError(f"seed {seed} is outside the {use} range {low} to {high}")
    return seed


def level_for(plan: Mapping[str, Any]) -> int:
    """The difficulty level of a plan from its number of steps (0 for more than 12)."""
    n = len(cast("Sequence[Any]", plan["steps"]))
    for level, most in LEVEL_STEPS:
        if n <= most:
            return level
    return 0


def plan_family(plan: Mapping[str, Any]) -> str:
    """Plans with the same recipes in the same order are one family: they must not be split between
    training and test, whatever their amounts are."""
    steps = cast("Sequence[Mapping[str, Any]]", plan["steps"])
    return "+".join(cast(str, s["transformation"]) for s in steps)


def split_of(key: str, fractions: Mapping[str, float], salt: str = "") -> str:
    """The split (`train`, `val`, `test`) a key belongs to, the same every time. Use a plan family
    as the key to split by family, or an episode id to split by episode."""
    digest = hashlib.sha256(f"{salt}|{key}".encode()).digest()
    point = int.from_bytes(digest[:8], "big") / 2**64
    total = sum(fractions.values())
    edge = 0.0
    for name, share in fractions.items():
        edge += share / total
        if point < edge:
            return name
    return list(fractions)[-1]


def _line(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(record, separators=(",", ":"), sort_keys=True, allow_nan=False) + "\n"
    ).encode()


@dataclass(slots=True)
class EpisodeRecord:
    """One episode as read back."""

    episode: str
    header: dict[str, Any]
    steps: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    end: dict[str, Any] | None = None

    @property
    def complete(self) -> bool:
        return self.end is not None

    @property
    def plan(self) -> dict[str, Any]:
        return cast("dict[str, Any]", self.header["plan"])


class RecordWriter:
    """Appends episodes to one file. Each `write_episode` is a single write of one gzip member and
    is flushed to disk before it returns."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write_episode(
        self,
        header: Mapping[str, Any],
        steps: Iterable[Mapping[str, Any]],
        end: Mapping[str, Any],
    ) -> None:
        episode = cast(str, header["episode"])
        lines = [_line({**header, "kind": "plan"})]
        lines += [_line({**s, "kind": "step", "episode": episode}) for s in steps]
        lines.append(_line({**end, "kind": "end", "episode": episode}))
        member = gzip.compress(b"".join(lines), compresslevel=6)
        with self.path.open("ab") as f:
            f.write(member)
            f.flush()
            os.fsync(f.fileno())


def read_lines(path: Path | str) -> Iterator[dict[str, Any]]:
    """Every complete record in the file, in order. A file that stops in the middle of a gzip
    member (a killed writer, a full disk) yields the records before the break; a line cut in half
    is dropped. Lines that are not JSON objects are skipped."""
    pending = b""
    decomp = zlib.decompressobj(wbits=31)
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(1 << 16)
            if not chunk:
                break
            data = chunk
            while data:
                try:
                    out = decomp.decompress(data)
                except zlib.error:
                    return  # damaged: what came before is all we can trust
                pending += out
                *lines, pending = pending.split(b"\n")
                yield from _parse(lines)
                if decomp.eof:
                    data = decomp.unused_data
                    decomp = zlib.decompressobj(wbits=31)
                else:
                    data = b""


def _parse(lines: Sequence[bytes]) -> Iterator[dict[str, Any]]:
    for raw in lines:
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        if isinstance(value, dict):
            yield cast("dict[str, Any]", value)


def load_episodes(path: Path | str) -> list[EpisodeRecord]:
    """The episodes in a file, grouped. An episode cut off before its `end` line is returned with
    `complete` False."""
    episodes: dict[str, EpisodeRecord] = {}
    for rec in read_lines(path):
        kind = rec.get("kind")
        name = cast("str | None", rec.get("episode"))
        if name is None:
            continue
        if kind == "plan":
            episodes[name] = EpisodeRecord(name, rec)
        elif kind == "step" and name in episodes:
            episodes[name].steps.append(rec)
        elif kind == "end" and name in episodes:
            episodes[name].end = rec
    return list(episodes.values())
