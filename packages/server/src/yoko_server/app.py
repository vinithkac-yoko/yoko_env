"""FastAPI app. Phase 0: health, build info, fixture inventory, static studio."""

from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from yoko_server import __version__
from yoko_server.buildinfo import build_info, fixture_manifest, repo_root
from yoko_server.library import base_summary, base_svg


def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
    """Single-user auth: one bearer token from STUDIO_TOKEN.

    If STUDIO_TOKEN is unset the protected routes are closed (503), never open.
    """
    expected = os.environ.get("STUDIO_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="STUDIO_TOKEN is not configured")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="invalid token")


def studio_dist() -> Path | None:
    override = os.environ.get("YOKO_STUDIO_DIST")
    path = Path(override) if override else repo_root() / "studio" / "dist"
    return path if (path / "index.html").is_file() else None


def create_app() -> FastAPI:
    app = FastAPI(title="yoko-env", version=__version__)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/build")
    def build() -> dict[str, Any]:
        return build_info()

    @app.get("/api/fixtures", dependencies=[Depends(require_token)])
    def fixtures() -> dict[str, Any]:
        return {"files": fixture_manifest()}

    @app.get("/api/library/base", dependencies=[Depends(require_token)])
    def library_base() -> dict[str, Any]:
        return base_summary()

    @app.get("/api/library/base/render.svg", dependencies=[Depends(require_token)])
    def library_base_svg() -> Response:
        return Response(base_svg(), media_type="image/svg+xml")

    dist = studio_dist()
    if dist is not None:
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(dist / "index.html")

    return app


app = create_app()
