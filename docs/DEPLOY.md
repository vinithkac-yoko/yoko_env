# Deploying to Railway

Phase 0 needs only the `web` service and one variable, `STUDIO_TOKEN`. No Postgres or bucket yet (Phase 6).

1. Sign in at railway.com with the GitHub account that owns `vinithkac-yoko/yoko_env`.
2. **New Project** > **Deploy from GitHub repo** > pick `yoko_env`. If Railway asks, install its GitHub app and allow this repository.
3. Name the service `web`.
4. Tell Railway where the Dockerfile is. Our Dockerfile is `docker/Dockerfile`, not at the repo root, so Railway will not find it on its own. Either set the service variable `RAILWAY_DOCKERFILE_PATH` = `docker/Dockerfile`, or set the Dockerfile path in the service's build settings. Leave the root directory as the repo root: the Dockerfile copies `packages/`, `fixtures/` and `studio/`.
5. Branch: Railway deploys the branch set under the service's source settings. Until `main` exists, set it to `claude/new-session-80etag`. Switch it to `main` once Kasi has created and merged into it.
6. Variables > add `STUDIO_TOKEN` = a long random string (for example the output of `openssl rand -hex 32`). Keep a copy in a password manager. It is the studio login.
7. Settings > Networking > **Generate Domain**. The app listens on Railway's `PORT`.
8. Settings > Deploy > healthcheck path `/api/health`.
9. Deploy and read the build log. When it finishes, open the URL.

Expected on the page: Health `ok`; Build = the commit's short sha; Seamly2D pin `v2026.10.5.154`; Formats read `0.6.8 to 0.7.5`; Fixtures hash starting `d3f89410dbcb`. Enter the token under "Library: fixtures" and press Load: four files, the basic set marked "locked base".

Menu names change over time; if one is not where this says, look for the same setting nearby.
