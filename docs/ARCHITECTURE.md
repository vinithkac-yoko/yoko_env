# Architecture

Kept current as the build proceeds. State: **Phase 0** (scaffold only; no engine yet).

## Layers

```text
engine  <-  io  <-  tools  <-  env  <-  agent | data | bench  <-  server  <-  studio (TS, over HTTP)
```

Imports point one way only; import-linter enforces it (`pyproject.toml`). No model SDK outside `yoko_agent`.

| Package | Role | Phase |
| --- | --- | --- |
| `yoko_engine` | Construction graph, formulas, geometry, pieces, validation, library | 1 |
| `yoko_io` | Seamly2D import/export, SVG/PNG render | 2 |
| `yoko_tools` | Action schemas, dispatcher, errors, adapters, recipes, teacher | 4 to 5 |
| `yoko_env` | reset/step/state, observations, valid actions, status card | 6 |
| `yoko_agent` | Policies, drafter loop, planner agent, flat sketch | 7 |
| `yoko_data` | Trajectories, importers, plan sampler, exports | 8 |
| `yoko_bench` | Tasks, scorers, reward specs, runner | 9 |
| `yoko_server` | FastAPI app and the `yoko` CLI (health and build live now) | 0 onwards |
| `studio/` | React app served by `yoko_server` | 0 onwards |

## Running today

- `uv sync --all-packages`
- `uv run yoko serve` serves `/api/health`, `/api/build`, `/api/fixtures` (bearer token) and the built studio.
- `cd studio && npm ci && npm run build`

## Key decisions

See `docs/adr/`. The engine is the source of truth: typed actions, validated, atomic. Deterministic and replayable. Everything versioned and hashed.
