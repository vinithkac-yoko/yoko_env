"""Show which fields differ between two JSON-lines files (committed real-Qt vectors vs a fresh run).

    python3 scripts/jsonl_diff.py committed.jsonl fresh.jsonl [--max-ulps N] [--show N]

Prints, for each differing line, the keys whose values differ, with both values, and how far apart
the numbers are in ulps (units in the last place). Exit status 1 if any difference is larger than
`--max-ulps` (default 0: exact), or is not a number.
"""

import argparse
import json
import math
import struct
from itertools import zip_longest
from typing import Any


def ulps(a: float, b: float) -> int:
    def key(x: float) -> int:
        n = struct.unpack("<q", struct.pack("<d", x))[0]
        return n if n >= 0 else -(n & 0x7FFFFFFFFFFFFFFF)

    return abs(key(a) - key(b))


def distance(a: Any, b: Any) -> float:
    """Largest ulp distance between two JSON values; infinity when they differ otherwise."""
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return max((distance(x, y) for x, y in zip(a, b, strict=True)), default=0)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b:
            return 0
        return ulps(float(a), float(b))
    return 0 if a == b else math.inf


parser = argparse.ArgumentParser()
parser.add_argument("committed")
parser.add_argument("fresh")
parser.add_argument("--max-ulps", type=int, default=0)
parser.add_argument("--show", type=int, default=5)
args = parser.parse_args()

bad = differing = shown = 0
worst: float = 0
with open(args.committed) as fa, open(args.fresh) as fb:
    for n, (la, lb) in enumerate(zip_longest(fa, fb), 1):
        if la == lb:
            continue
        differing += 1
        if la is None or lb is None:
            print(f"line {n}: only in {'fresh' if la is None else 'committed'} file")
            bad += 1
            continue
        ja, jb = json.loads(la), json.loads(lb)
        line_worst: float = 0
        for k in ja.keys() | jb.keys():
            d = distance(ja.get(k), jb.get(k))
            if d:
                line_worst = max(line_worst, d)
                if shown < args.show:
                    print(
                        f"line {n} i={ja.get('i')} {k}: committed {ja.get(k)!r} "
                        f"fresh {jb.get(k)!r} ({d} ulp)"
                    )
        shown += 1
        worst = max(worst, line_worst)
        if line_worst > args.max_ulps:
            bad += 1
print(f"{differing} differing lines, largest {worst} ulp, {bad} beyond {args.max_ulps} ulp")
raise SystemExit(1 if bad else 0)
