"""The studio's stage A API: accounts, people, measurements, work items and the blind cross-check,
sizes, the canvas scene and the inspector.

Run on SQLite; also on Postgres when YOKO_TEST_DATABASE_URL is set (CI does).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from yoko_io.seamly import individual_measurements_file
from yoko_server import auth
from yoko_server.app import create_app
from yoko_server.db import make_engine
from yoko_server.drafting import start

TOKEN = "studio-token-for-tests"
OWNER = {"email": "kasi@example.com", "name": "Kasi", "password": "owner-password-1"}
BASE = "aldrich-womens-6th-basic"
REPO = Path(__file__).resolve().parents[3]
URLS = ["sqlite:///:memory:"] + (
    [os.environ["YOKO_TEST_DATABASE_URL"]] if os.environ.get("YOKO_TEST_DATABASE_URL") else []
)


@pytest.fixture(params=URLS, ids=lambda u: u.split(":")[0])
def app_url(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("STUDIO_TOKEN", TOKEN)
    monkeypatch.setenv("SESSION_SECRET", "a-secret-for-signing-cookies")
    url = str(request.param)
    if not url.startswith("sqlite"):
        engine = make_engine(url)
        with engine.begin() as conn:  # a clean database for every test
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    yield url


def client(url: str) -> TestClient:
    return TestClient(create_app(database_url=url))


def owner(url: str) -> TestClient:
    c = client(url)
    r = c.post("/api/auth/setup", json={"token": TOKEN, **OWNER})
    assert r.status_code == 200, r.text
    return c


def maker(
    c_owner: TestClient, url: str, email: str, password: str = "maker-password-1"
) -> TestClient:
    r = c_owner.post(
        "/api/people", json={"email": email, "name": email.split("@")[0], "password": password}
    )
    assert r.status_code == 200, r.text
    c = TestClient(c_owner.app)
    assert c.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    del url
    return c


def new_item(c: TestClient, **kw: Any) -> int:
    body = {
        "kind": "recipe_example",
        "recipe": "lengthen_or_shorten",
        "example_no": 1,
        "title": "longer skirt",
        "start_pattern": BASE,
        "pieces": ["A - Skirt Back"],
        **kw,
    }
    r = c.post("/api/items", json=body)
    assert r.status_code == 200, r.text
    return int(r.json()["id"])


# -- accounts -------------------------------------------------------------------------------------
def test_the_owner_account_is_made_once_with_the_studio_token(app_url: str) -> None:
    c = client(app_url)
    status = c.get("/api/auth/status").json()
    assert status == {
        "database": True,
        "database_problem": "",
        "session_secret": True,
        "owner_exists": False,
    }
    bad = c.post("/api/auth/setup", json={"token": "wrong", **OWNER})
    assert bad.status_code == 401
    short = c.post("/api/auth/setup", json={"token": TOKEN, **OWNER, "password": "short"})
    assert short.status_code == 422 and "10 characters" in short.json()["detail"]
    ok = c.post("/api/auth/setup", json={"token": TOKEN, **OWNER})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "owner"
    assert c.get("/api/auth/me").json()["user"]["email"] == "kasi@example.com"  # signed in
    again = client(app_url).post("/api/auth/setup", json={"token": TOKEN, **OWNER})
    # a second app on the same SQLite memory database is a new database; on Postgres it is not
    if not app_url.startswith("sqlite"):
        assert again.status_code == 409
    assert c.post("/api/auth/setup", json={"token": TOKEN, **OWNER}).status_code == 409


def test_signing_in_and_out(app_url: str) -> None:
    c = owner(app_url)
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401
    assert (
        c.post(
            "/api/auth/login", json={"email": "KASI@example.com", "password": "nope-nope-nope"}
        ).status_code
        == 401
    )
    r = c.post("/api/auth/login", json={"email": "KASI@example.com", "password": OWNER["password"]})
    assert r.status_code == 200 and c.get("/api/auth/me").status_code == 200


def test_a_forged_or_stale_cookie_is_refused(app_url: str) -> None:
    c = owner(app_url)
    cookie = c.cookies.get(auth.COOKIE)
    assert cookie
    c.cookies.set(auth.COOKIE, cookie[:-2] + "xx")
    assert c.get("/api/auth/me").status_code == 401
    secret = b"a-secret-for-signing-cookies"
    old = auth.make_cookie(auth.User(1, "kasi@example.com", "Kasi", "owner", 1), secret, issued=0)
    c.cookies.set(auth.COOKIE, old)
    assert c.get("/api/auth/me").status_code == 401  # too old


def test_only_the_owner_adds_people_and_resets_their_passwords(app_url: str) -> None:
    c = owner(app_url)
    m = maker(c, app_url, "rani@example.com")
    assert m.get("/api/people").status_code == 403
    assert (
        m.post(
            "/api/people", json={"email": "x@example.com", "name": "x", "password": "x" * 12}
        ).status_code
        == 403
    )
    people = c.get("/api/people").json()["people"]
    assert [(p["email"], p["role"]) for p in people] == [
        ("kasi@example.com", "owner"),
        ("rani@example.com", "maker"),
    ]
    dup = c.post(
        "/api/people", json={"email": "rani@example.com", "name": "r", "password": "y" * 12}
    )
    assert dup.status_code == 409
    # a reset signs the maker out everywhere; the new password works
    rid = people[1]["id"]
    assert (
        c.post(f"/api/people/{rid}/password", json={"password": "a-new-password"}).status_code
        == 200
    )
    assert m.get("/api/auth/me").status_code == 401
    assert (
        m.post(
            "/api/auth/login", json={"email": "rani@example.com", "password": "maker-password-1"}
        ).status_code
        == 401
    )
    assert (
        m.post(
            "/api/auth/login", json={"email": "rani@example.com", "password": "a-new-password"}
        ).status_code
        == 200
    )
    # disabled: cannot sign in; the owner cannot be disabled
    assert c.post(f"/api/people/{rid}/disabled", json={"disabled": True}).status_code == 200
    assert m.get("/api/auth/me").status_code == 401
    assert (
        m.post(
            "/api/auth/login", json={"email": "rani@example.com", "password": "a-new-password"}
        ).status_code
        == 401
    )
    assert (
        c.post(f"/api/people/{people[0]['id']}/disabled", json={"disabled": True}).status_code
        == 422
    )


def test_a_person_changes_their_own_password(app_url: str) -> None:
    c = owner(app_url)
    m = maker(c, app_url, "rani@example.com")
    wrong = m.post("/api/auth/password", json={"old_password": "nope", "new_password": "z" * 12})
    assert wrong.status_code == 401
    ok = m.post(
        "/api/auth/password", json={"old_password": "maker-password-1", "new_password": "z" * 12}
    )
    assert (
        ok.status_code == 200 and m.get("/api/auth/me").status_code == 200
    )  # this browser stays in


def test_without_a_database_the_studio_says_why_and_the_rest_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    c = TestClient(create_app())
    assert c.get("/api/health").status_code == 200
    r = c.get("/api/items")
    assert r.status_code == 503 and r.json()["detail"] == "DATABASE_URL is not set"
    assert c.get("/api/auth/status").json()["database"] is False


def test_the_studio_token_works_as_the_owner_for_scripts(app_url: str) -> None:
    owner(app_url)
    c = client(app_url) if not app_url.startswith("sqlite") else None
    if c is None:
        return  # a new SQLite memory database has no owner
    r = c.get("/api/people", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


# -- measurements ---------------------------------------------------------------------------------
def person_file() -> str:
    _, table, _ = start(BASE)
    return individual_measurements_file(table.values(36, 164)).decode()


def test_a_persons_file_goes_in_a_shared_list(app_url: str) -> None:
    c = owner(app_url)
    m = maker(c, app_url, "rani@example.com")
    r = m.post("/api/measurements", json={"name": "Asha", "content": person_file()})
    assert r.status_code == 200, r.text
    listed = c.get("/api/measurements").json()["files"]
    assert [(f["name"], f["by"]) for f in listed] == [("Asha", "rani")]  # shared: the owner sees it
    assert (
        m.post("/api/measurements", json={"name": "Asha", "content": person_file()}).status_code
        == 409
    )
    bad = m.post("/api/measurements", json={"name": "junk", "content": "<not xml"})
    assert bad.status_code == 422
    multisize = (REPO / "fixtures/measurements/Aldrich-Womens-MultiSize-06-14.smms").read_text()
    refused = m.post("/api/measurements", json={"name": "table", "content": multisize})
    assert refused.status_code == 422 and "multisize" in refused.json()["detail"]


# -- items and the blind cross-check --------------------------------------------------------------
def test_a_work_item_starts_from_a_block_at_a_size(app_url: str) -> None:
    c = owner(app_url)
    iid = new_item(c, measurements={"kind": "table", "size": 40, "height": 164})
    item = c.get(f"/api/items/{iid}").json()["item"]
    assert item["status"] == "open" and item["can_edit"] and item["author"] == "Kasi"
    assert item["measurements"] == {"kind": "table", "size": 40, "height": 164}
    bad = c.post(
        "/api/items",
        json={
            "kind": "recipe_example",
            "recipe": "Bad Name",
            "example_no": 1,
            "title": "x",
            "start_pattern": BASE,
        },
    )
    assert bad.status_code == 422
    no_piece = c.post(
        "/api/items",
        json={"kind": "design", "title": "x", "start_pattern": BASE, "pieces": ["Nope"]},
    )
    assert no_piece.status_code == 422
    no_size = c.post(
        "/api/items",
        json={
            "kind": "design",
            "title": "x",
            "start_pattern": BASE,
            "measurements": {"kind": "table", "size": 99},
        },
    )
    assert no_size.status_code == 422
    twice = c.post(
        "/api/items",
        json={
            "kind": "recipe_example",
            "recipe": "lengthen_or_shorten",
            "example_no": 1,
            "title": "again",
            "start_pattern": BASE,
        },
    )
    assert twice.status_code == 409


def test_an_item_can_be_drafted_at_a_persons_own_measurements(app_url: str) -> None:
    c = owner(app_url)
    fid = c.post("/api/measurements", json={"name": "Asha", "content": person_file()}).json()["id"]
    iid = new_item(
        c, kind="design", recipe=None, example_no=None, measurements={"kind": "person", "id": fid}
    )
    sizes = c.get(f"/api/items/{iid}/sizes").json()
    assert sizes["default"] == f"person:{fid}"
    assert f"person:{fid}" in [s["key"] for s in sizes["sizes"]]


def test_makers_see_designs_but_recipe_examples_stay_blind_until_both_are_finished(
    app_url: str,
) -> None:
    c = owner(app_url)
    a = maker(c, app_url, "a@example.com")
    b = maker(c, app_url, "b@example.com")
    design = new_item(a, kind="design", recipe=None, example_no=None, title="a wrap skirt")
    ex_a = new_item(a)
    assert {i["id"] for i in b.get("/api/items").json()["items"]} == {design}
    assert b.get("/api/items").json()["hidden"] == 1
    assert b.get(f"/api/items/{ex_a}").status_code == 404  # not even its existence
    assert not b.get(f"/api/items/{design}").json()["item"]["can_edit"]
    ex_b = new_item(b)
    assert a.post(f"/api/items/{ex_a}/finish").status_code == 200
    assert b.get(f"/api/items/{ex_a}").status_code == 404  # b has not finished
    assert a.get(f"/api/items/{ex_b}").status_code == 404  # b's is not finished
    assert b.post(f"/api/items/{ex_a}/finish").status_code == 404  # cannot touch what it cannot see
    assert b.post(f"/api/items/{ex_b}/finish").status_code == 200
    assert b.get(f"/api/items/{ex_a}").status_code == 200
    assert a.get(f"/api/items/{ex_b}").status_code == 200
    # a third maker who has not drafted the example cannot look either
    m3 = maker(c, app_url, "c@example.com")
    assert m3.get(f"/api/items/{ex_a}").status_code == 404
    # the owner, not drafting this example, sees both; a finished item cannot be edited
    assert c.get(f"/api/items/{ex_a}").status_code == 200
    assert not a.get(f"/api/items/{ex_a}").json()["item"]["can_edit"]


def test_the_owner_drafting_an_example_is_blind_like_a_maker(app_url: str) -> None:
    c = owner(app_url)
    a = maker(c, app_url, "a@example.com")
    ex_a = new_item(a)
    assert c.get(f"/api/items/{ex_a}").status_code == 200  # not drafting it: sees it
    mine = new_item(c)
    assert c.get(f"/api/items/{ex_a}").status_code == 404  # drafting it now: blind
    a.post(f"/api/items/{ex_a}/finish")
    c.post(f"/api/items/{mine}/finish")
    assert c.get(f"/api/items/{ex_a}").status_code == 200
    assert c.post(f"/api/items/{mine}/reopen").status_code == 200  # the owner may reopen
    assert a.post(f"/api/items/{ex_a}/reopen").status_code == 403


# -- sizes, the canvas, the inspector -------------------------------------------------------------
def test_the_size_switcher_names_the_tables_sizes_once_each(app_url: str) -> None:
    c = owner(app_url)
    iid = new_item(c)
    sizes = c.get(f"/api/items/{iid}/sizes").json()
    labels = [s["label"] for s in sizes["sizes"]]
    # the basic set's table does not grade by height: one entry per size, named in UK sizes
    assert labels == [
        "UK 6 (size 34)",
        "UK 8 (size 36)",
        "UK 10 (size 38)",
        "UK 12 (size 40)",
        "UK 14 (size 42)",
    ]
    assert sizes["default"] == "table:34:164"


def test_the_scene_has_every_line_curve_and_point_with_its_object(app_url: str) -> None:
    c = owner(app_url)
    iid = new_item(c)
    small = c.get(f"/api/items/{iid}/scene", params={"size": "table:34:164"}).json()
    large = c.get(f"/api/items/{iid}/scene", params={"size": "table:42:164"}).json()
    assert small["size"]["label"] == "UK 6 (size 34)" and small["errors"] == []
    labels = {p["label"] for p in small["points"]}
    assert {"A1", "A3", "C32", "D7"} <= labels
    assert len(small["lines"]) > 100 and len(small["curves"]) > 20
    a7_small = next(p for p in small["points"] if p["label"] == "A7")
    a7_large = next(p for p in large["points"] if p["label"] == "A7")
    assert a7_large["x"] > a7_small["x"]  # the hip is wider at UK 14
    assert all(isinstance(line["id"], int) for line in small["lines"])
    # proposed landmark names are marked as proposals, by object
    a7 = small["proposed_landmarks"][str(a7_small["id"])]
    assert "skirt_back.side_hip" in a7 and "skirt_front.side_hip" in a7
    assert c.get(f"/api/items/{iid}/scene", params={"size": "table:99:1"}).status_code == 422
    # the canvas opens on the item's pieces: the skirt back, not the whole drafting area
    f, b = small["focus"], small["bounds"]
    assert f["max_x"] - f["min_x"] < (b["max_x"] - b["min_x"]) / 2


def test_the_inspector_shows_formulas_dependencies_and_dependents(app_url: str) -> None:
    c = owner(app_url)
    iid = new_item(c)
    scene = c.get(f"/api/items/{iid}/scene").json()
    a7 = next(p for p in scene["points"] if p["label"] == "A7")
    obj = c.get(f"/api/items/{iid}/objects/{a7['id']}").json()["object"]
    assert obj["name"] == "A7" and obj["kind"] == "point"
    assert obj["attributes"]["length"] == "(hip_circ/4)+1.5*#CM"
    assert obj["attributes"]["firstPoint"] == "A5"  # references by label
    assert "mx" not in obj["attributes"] and "lineColor" not in obj["attributes"]
    assert obj["built_from"] and obj["used_by"]
    assert obj["tool"] == "point_along_line" and obj["edit_with"] == "edit_point_along_line"
    assert "skirt_back.side_hip" in obj["proposed_landmarks"]
    at_14 = c.get(f"/api/items/{iid}/objects/{a7['id']}", params={"size": "table:42:164"}).json()
    assert at_14["object"]["x_mm"] > obj["x_mm"]
    assert c.get(f"/api/items/{iid}/objects/999999").status_code == 404


def test_the_new_item_form_gets_recipes_and_sizes(app_url: str) -> None:
    c = owner(app_url)
    names = c.get("/api/recipes").json()["recipes"]
    assert {"slash_and_spread", "remove_dart", "reshape_neckline", "hem_shaping"} <= set(names)
    assert "snake_case_name" not in names  # the template is not a recipe
    sizes = c.get(f"/api/patterns/{BASE}/sizes").json()
    assert sizes["default"] == "table:34:164" and len(sizes["sizes"]) == 5
    assert c.get("/api/patterns/nope/sizes").status_code == 404
    pats = c.get("/api/patterns").json()["patterns"]
    assert pats[0]["id"] == BASE and pats[0]["locked"] and "A - Skirt Back" in pats[0]["pieces"]
