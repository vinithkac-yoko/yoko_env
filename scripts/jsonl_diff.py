"""Show which fields differ between two JSON-lines files (committed real-Qt vectors vs a fresh run).

    python3 scripts/jsonl_diff.py committed.jsonl fresh.jsonl [max_lines]

Prints, for each differing line, the keys whose values differ, with both values. Exit status 1 if
anything differs.
"""

import json
import sys
from itertools import zip_longest

a_path, b_path = sys.argv[1], sys.argv[2]
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
bad = shown = 0
with open(a_path) as fa, open(b_path) as fb:
    for n, (la, lb) in enumerate(zip_longest(fa, fb), 1):
        if la == lb:
            continue
        bad += 1
        if shown >= limit:
            continue
        shown += 1
        if la is None or lb is None:
            print(f"line {n}: only in {'fresh' if la is None else 'committed'} file")
            continue
        ja, jb = json.loads(la), json.loads(lb)
        for k in ja.keys() | jb.keys():
            if ja.get(k) != jb.get(k):
                print(f"line {n} i={ja.get('i')} {k}: committed {ja.get(k)!r} fresh {jb.get(k)!r}")
print(f"{bad} differing lines")
sys.exit(1 if bad else 0)
