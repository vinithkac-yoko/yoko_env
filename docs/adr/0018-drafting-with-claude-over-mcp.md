# 0018. Drafting real patterns with Claude over MCP; training parked

Status: accepted (Kasi, 2026-11-21). The tool list and details are in `docs/mcp-plan.md`, for review.

**Change of direction.** YokoStyles is no longer training a drafting model. The goal now: Kasi drafts
real patterns from the basic blocks with Claude (claude.ai, as a custom connector) through an MCP server
on our engine, and watches the pattern change live in the studio.

**Kept and extended**
- `packages/engine`, `packages/io`: the parametric engine, Seamly2D files, rendering.
- `packages/tools`: the tool layer (YAML tools in `config/tools/`, the runtime, adapters, section
  references). The MCP server drives it.
- `packages/server`: the studio (stage A as built) and, new, the MCP server on the same `web` service.

**Parked** (kept in the repo, their tests still run so they do not rot, not extended)
- `packages/env`, `packages/data`, `packages/agent`, `packages/bench`.
- In `packages/tools`: the teacher (`teacher.py`), the recipe framework (`recipes.py`), plan
  validation (`plan.py`); in `packages/data`: the records.
- The training phases of BUILD_SPEC section 14: 5 (recipes and teacher), 6 (environment, throughput),
  7 (drafter runner and planner), 8 (data), 9 (bench).
- The studio v0 plan's stages B2 to E (`docs/studio-v0-plan.md`). Stage B's tool forms and picking on
  the canvas may come back as step d of the MCP plan.
- ADRs 0007, 0009, 0015 and 0016 stay as records of the parked work; ADR 0017's phase order is replaced
  by this one.

**What stays true**
- Seamly2D compatibility and the oracle: every pattern Claude makes is a Seamly2D pattern, and CI
  checks an exported one in the pinned Seamly2D.
- Proposed landmark names stay proposals: shown to Claude only marked unconfirmed.
- Never invent drafting rules; seam allowance, notches and grainline come later (finishing), with seam
  allowance widths as settings per order.

**Why MCP.** Claude already drafts well when it can see and change the pattern; what it needs is our
engine's exact geometry, checks at every size, and Seamly2D-compatible output. An MCP server gives
that inside claude.ai without a model of our own, and Kasi's prompts become the place to teach it.
Every call is logged so Kasi can tune those prompts.
