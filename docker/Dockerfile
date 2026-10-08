# App image: FastAPI + built studio + engine. Railway builds this (no Nixpacks).
FROM node:22-slim AS studio
WORKDIR /studio
COPY studio/package.json studio/package-lock.json ./
RUN npm ci
COPY studio/ ./
RUN npm run build

FROM python:3.12-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv sync --frozen --all-packages --no-dev
COPY fixtures ./fixtures
COPY docs ./docs
COPY --from=studio /studio/dist ./studio/dist
ENV YOKO_FIXTURES_DIR=/app/fixtures YOKO_STUDIO_DIST=/app/studio/dist PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# Railway sets PORT; `yoko serve` reads it.
CMD ["yoko", "serve"]
