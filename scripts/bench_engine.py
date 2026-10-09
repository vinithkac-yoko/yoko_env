"""Engine benchmarks on the real basic set (425 objects). Run without coverage for true numbers:

    uv run python scripts/bench_engine.py

Targets from the spec: fork under 1 ms; one edit re-evaluated under 5 ms (an edit near the start
of the pattern legitimately re-evaluates much of it, so both a late and an early edit are shown).
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from yoko_engine.evaluator import evaluate
from yoko_engine.session import PatternSession, SetAttrs
from yoko_io.seamly import read_measurements, read_pattern

ROOT = Path(__file__).resolve().parents[1]


def timed(fn, n: int = 30) -> float:  # type: ignore[no-untyped-def]
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def main() -> None:
    pattern = read_pattern(ROOT / "fixtures/patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d")
    table = read_measurements(ROOT / "fixtures/measurements/Aldrich-Womens-MultiSize-06-14.smms")
    values = table.values()
    session = PatternSession(pattern, table)
    objs = pattern.objects()
    late = next(o for o in reversed(objs) if o.kind == "alongLine" and o.get("length"))
    early = next(o for o in objs if o.label == "A1")

    print(f"objects: {len(objs)}")
    print(f"full evaluation:        {timed(lambda: evaluate(pattern, values)):8.2f} ms")
    print(f"fork:                   {timed(session.fork, 300):8.3f} ms   (target < 1)")
    hashed = PatternSession(pattern, table)
    print(f"state hash:             {timed(hashed.state_hash, 30):8.2f} ms")

    def edit(obj, value):  # type: ignore[no-untyped-def]
        s = session.fork()
        start = time.perf_counter()
        res = s.apply(SetAttrs(obj.id, (("length", value),)))
        ms = (time.perf_counter() - start) * 1000
        return ms, res.reevaluated

    for name, obj, value in (("late edit", late, "1.5*#CM"), ("early edit", early, "6*#CM")):
        runs = [edit(obj, value) for _ in range(30)]
        ms = statistics.median(r[0] for r in runs)
        print(f"{name:<22}  {ms:8.2f} ms   ({runs[0][1]} objects re-evaluated)")


if __name__ == "__main__":
    main()
