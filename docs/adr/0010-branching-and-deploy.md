# 0010. Branching and deploy workflow

Status: accepted (Addendum 1 §1 Q12, Q13)

- Work on the session branch and keep one draft PR open. Kasi merges into `main` at each checkpoint. Railway deploys `main`, so `main` always builds.
- Before every push: ruff, pyright, import-linter, pytest, studio typecheck and tests, Docker build.
- Railway service `web`, Dockerfile build (no Nixpacks), generated URL. Environment variables are listed per phase in `docs/PROGRESS.md`. Phase 0 needs only `STUDIO_TOKEN`.
- Risky changes go behind a flag until they work.
