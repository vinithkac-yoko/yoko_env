from fastapi.testclient import TestClient
from yoko_server.app import create_app
from yoko_server.cli import build_parser, main


def client() -> TestClient:
    return TestClient(create_app())


def test_health() -> None:
    r = client().get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_build_reports_pin_and_fixtures_hash() -> None:
    body = client().get("/api/build").json()
    assert body["seamly2d_pin"] == "v2026.10.5.154"
    assert body["pattern_formats_read"] == ["0.6.8", "0.7.5"]
    assert body["fixtures_hash"]
    assert body["git_sha"]


def test_fixtures_closed_without_configured_token(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("STUDIO_TOKEN", raising=False)
    assert client().get("/api/fixtures").status_code == 503


def test_fixtures_requires_matching_token(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("STUDIO_TOKEN", "s3cret")
    c = client()
    assert c.get("/api/fixtures").status_code == 401
    assert c.get("/api/fixtures", headers={"Authorization": "Bearer nope"}).status_code == 401
    ok = c.get("/api/fixtures", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
    files = {f["path"]: f["area"] for f in ok.json()["files"]}
    assert files["patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d"] == "base"


def test_cli_placeholders_exit_nonzero(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["bench"]) == 2
    assert "Phase 9" in capsys.readouterr().err
    assert build_parser().parse_args(["serve", "--port", "1234"]).port == 1234


def test_library_base_needs_the_token_and_describes_the_locked_basic_set(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("STUDIO_TOKEN", "s3cret")
    c = client()
    assert c.get("/api/library/base").status_code == 401
    assert c.get("/api/library/base/render.svg").status_code == 401
    auth = {"Authorization": "Bearer s3cret"}
    body = c.get("/api/library/base", headers=auth).json()
    assert body["locked"] is True
    assert body["objects"] == 425
    assert body["points"] == 302
    assert body["curves"] == 37
    assert body["issues"] == 0
    assert len(body["state_hash"]) == 64
    svg = c.get("/api/library/base/render.svg", headers=auth)
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert svg.text.startswith("<svg")
