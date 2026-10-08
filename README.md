# yoko-env

An environment for AI agents that turn a design idea into a garment pattern by manipulating a basic pattern in a parametric pattern engine (YokoStyles).

Start with `docs/BUILD_SPEC.md` and `docs/BUILD_SPEC_ADDENDUM_1.md` (the addendum wins), then `docs/ARCHITECTURE.md` and `docs/PROGRESS.md`.

```bash
uv sync --all-packages
(cd studio && npm ci && npm run build)
STUDIO_TOKEN=devtoken uv run yoko serve      # http://localhost:8000
uv run ruff check . && uv run pyright && uv run lint-imports && uv run pytest
```
