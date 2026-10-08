# 0009. Held-out rules and seed ranges

Status: **proposed**. Needs Kasi's go-ahead; the pairings need the recipe list and the pattern makers.

**Seed ranges** (disjoint, so data generation, DAgger, tests, RL and calibration never share a seed):

| Use | Range |
| --- | --- |
| Teacher data generation | 0 to 999,999 |
| DAgger | 1,000,000 to 1,999,999 |
| Test suites | 2,000,000 to 2,099,999 |
| RL | 3,000,000 to 3,999,999 |
| Calibration | 4,000,000 to 4,099,999 |

**Difficulty levels** (Addendum 1 §12): training L1 = 1 step, L2 = 2, L3 = 3 to 5; held out of training L4 = 6 to 7, L5 = 8 to 9, L6 = 10 to 12.

**Held-out pairings:** 2 to 3 recipe pairs excluded from training by `heldout_rule(plan)`. **Not chosen yet.** I will propose candidates when the first 8 recipes are written (Phase 4), and pattern makers confirm. A pair that never occurs together in real designs is a poor choice; one that does is a strong test.
