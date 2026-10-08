# 0001. Monorepo, tooling and layering

Status: accepted

- One monorepo, a `uv` workspace with eight Python packages under `packages/` plus `studio/` (React, Vite, TypeScript, Tailwind). Python 3.12 via `uv` (the dev machine's 3.11 is not used).
- Dependencies point one way: `engine <- io <- tools <- env <- agent | data | bench <- server`. Enforced by import-linter in CI (`[tool.importlinter]` in the root `pyproject.toml`).
- Model SDKs (`anthropic`, `openai`) may only be imported in `yoko_agent`. Enforced by a second import-linter contract.
- `ruff` for lint and format; `pyright` strict on `engine`, `tools`, `env`; `pytest` with Hypothesis; `vitest` for the studio. Coverage gates (90% engine and tools, 75% elsewhere) switch on when those packages have code (Phase 1 onwards); they are not enforced on empty skeletons.
- The `yoko` CLI lives in `yoko_server` because it is the only package allowed to depend on everything.
- `fixtures/MANIFEST.sha256` pins the hashes of the base set, measurement file and examples. A test fails if any change, so the locked base area is enforced, not just promised.
