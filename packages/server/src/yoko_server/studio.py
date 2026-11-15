"""The studio's API for manual drafting, stage A (docs/studio-v0-plan.md).

People: Kasi (the owner) makes every account; no self sign-up, no emails. The first owner account
is made once with `STUDIO_TOKEN`. Makers see each other's items read-only, except that the
cross-check is blind: a maker sees another maker's version of a recipe example only when both
versions are finished.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import Engine, Row, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from yoko_engine.library import LibraryError
from yoko_engine.model import MeasurementSet
from yoko_engine.pieces_edit import pieces_of

from yoko_server import auth, drafting
from yoko_server.auth import User
from yoko_server.db import items, measurement_files, now, users
from yoko_server.library import library

RECIPE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Store:
    """What the studio routes share: the database and the evaluated patterns."""

    engine: Engine | None
    problem: str = ""
    sessions: drafting.Sessions = field(default_factory=drafting.Sessions)


def store(request: Request) -> Store:
    found = cast("Store | None", getattr(request.app.state, "store", None))
    if found is None or found.engine is None:
        detail = found.problem if found is not None and found.problem else "DATABASE_URL is not set"
        raise HTTPException(status_code=503, detail=detail)
    return found


StoreDep = Annotated[Store, Depends(store)]


def _engine(s: Store) -> Engine:
    assert s.engine is not None
    return s.engine


def _new_id(result: Any) -> int:
    key = result.inserted_primary_key
    assert key is not None
    return int(key[0])


def _user(row: Row[Any]) -> User:
    return User(row.id, row.email, row.name, row.role, row.session_version)


def current_user(request: Request, s: StoreDep) -> User:
    """The person behind a request: the login cookie, or the owner for bearer `STUDIO_TOKEN`."""
    engine = _engine(s)
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer ") and auth.token_matches(header.removeprefix("Bearer ").strip()):
        with engine.connect() as conn:
            row = conn.execute(
                select(users).where(users.c.role == "owner").order_by(users.c.id)
            ).first()
        if row is None:
            raise HTTPException(status_code=401, detail="there is no owner account yet")
        return _user(row)
    secret = auth.session_secret()
    if secret is None:
        raise HTTPException(status_code=503, detail="SESSION_SECRET is not set")
    cookie = request.cookies.get(auth.COOKIE)
    found = auth.read_cookie(cookie, secret) if cookie else None
    if found is None:
        raise HTTPException(status_code=401, detail="sign in first")
    uid, version = found
    with engine.connect() as conn:
        row = conn.execute(select(users).where(users.c.id == uid)).first()
    if row is None or row.disabled or row.session_version != version:
        raise HTTPException(status_code=401, detail="sign in again")
    return _user(row)


UserDep = Annotated[User, Depends(current_user)]


def owner(user: UserDep) -> User:
    if not user.is_owner:
        raise HTTPException(status_code=403, detail="only the owner can do this")
    return user


OwnerDep = Annotated[User, Depends(owner)]


def _set_cookie(request: Request, response: Response, user: User) -> None:
    secret = auth.session_secret()
    if secret is None:
        raise HTTPException(status_code=503, detail="SESSION_SECRET is not set")
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        auth.COOKIE,
        auth.make_cookie(user, secret),
        max_age=auth.MAX_AGE_S,
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def _person(row: Row[Any]) -> dict[str, Any]:
    return {
        "id": row.id,
        "email": row.email,
        "name": row.name,
        "role": row.role,
        "disabled": row.disabled,
    }


def _check_password(password: str) -> None:
    problem = auth.password_problem(password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)


# -- request bodies -------------------------------------------------------------------------------
class SetupBody(BaseModel):
    token: str
    email: str
    name: str = Field(min_length=1, max_length=120)
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class PasswordBody(BaseModel):
    old_password: str
    new_password: str


class NewPersonBody(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=120)
    password: str


class ResetBody(BaseModel):
    password: str


class DisabledBody(BaseModel):
    disabled: bool


class MeasurementBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=2_000_000)


class TableSize(BaseModel):
    kind: Literal["table"] = "table"
    size: float | None = None
    height: float | None = None


class PersonSize(BaseModel):
    kind: Literal["person"]
    id: int


class NewItemBody(BaseModel):
    kind: Literal["recipe_example", "design"]
    recipe: str | None = None
    example_no: int | None = Field(default=None, ge=1, le=9)
    title: str = Field(min_length=1, max_length=200)
    brief: str = Field(default="", max_length=5000)
    start_pattern: str
    pieces: list[str] = Field(default_factory=list[str], max_length=20)
    measurements: TableSize | PersonSize = Field(default_factory=TableSize)


router = APIRouter(prefix="/api")


# -- signing in -----------------------------------------------------------------------------------
@router.get("/auth/status")
def auth_status(request: Request) -> dict[str, Any]:
    """What the sign-in screen needs to know (no login required)."""
    found = cast("Store | None", getattr(request.app.state, "store", None))
    engine = found.engine if found is not None else None
    owner_exists = False
    if engine is not None:
        with engine.connect() as conn:
            owner_exists = (
                conn.execute(select(func.count()).where(users.c.role == "owner")).scalar_one() > 0
            )
    return {
        "database": engine is not None,
        "database_problem": found.problem if found is not None else "",
        "session_secret": auth.session_secret() is not None,
        "owner_exists": owner_exists,
    }


@router.post("/auth/setup")
def setup(body: SetupBody, request: Request, response: Response, s: StoreDep) -> dict[str, Any]:
    """Make the owner account, once, with `STUDIO_TOKEN`."""
    if not auth.token_matches(body.token):
        raise HTTPException(status_code=401, detail="that is not the studio token")
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="that is not an email address")
    _check_password(body.password)
    with _engine(s).begin() as conn:
        if conn.execute(select(func.count()).where(users.c.role == "owner")).scalar_one():
            raise HTTPException(status_code=409, detail="the owner account exists already")
        uid = _new_id(
            conn.execute(
                insert(users).values(
                    email=email,
                    name=body.name.strip(),
                    role="owner",
                    password_hash=auth.hash_password(body.password),
                    session_version=1,
                    disabled=False,
                    created_at=now(),
                )
            )
        )
    user = User(int(uid), email, body.name.strip(), "owner", 1)
    _set_cookie(request, response, user)
    return {"user": _person_dict(user)}


def _person_dict(user: User) -> dict[str, Any]:
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}


@router.post("/auth/login")
def login(body: LoginBody, request: Request, response: Response, s: StoreDep) -> dict[str, Any]:
    email = body.email.strip().lower()
    with _engine(s).connect() as conn:
        row = conn.execute(select(users).where(users.c.email == email)).first()
    if row is None or row.disabled or not auth.verify_password(body.password, row.password_hash):
        raise HTTPException(status_code=401, detail="wrong email or password")
    user = _user(row)
    _set_cookie(request, response, user)
    return {"user": _person_dict(user)}


@router.post("/auth/logout")
def logout(response: Response) -> dict[str, Any]:
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@router.get("/auth/me")
def me(user: UserDep) -> dict[str, Any]:
    return {"user": _person_dict(user)}


@router.post("/auth/password")
def change_password(
    body: PasswordBody, request: Request, response: Response, user: UserDep, s: StoreDep
) -> dict[str, Any]:
    _check_password(body.new_password)
    with _engine(s).begin() as conn:
        row = conn.execute(select(users).where(users.c.id == user.id)).one()
        if not auth.verify_password(body.old_password, row.password_hash):
            raise HTTPException(status_code=401, detail="the old password is wrong")
        conn.execute(
            update(users)
            .where(users.c.id == user.id)
            .values(
                password_hash=auth.hash_password(body.new_password),
                session_version=row.session_version + 1,
            )
        )
    fresh = User(user.id, user.email, user.name, user.role, row.session_version + 1)
    _set_cookie(request, response, fresh)  # this browser stays signed in; others are signed out
    return {"ok": True}


# -- people (the owner) ---------------------------------------------------------------------------
@router.get("/people")
def people(_: OwnerDep, s: StoreDep) -> dict[str, Any]:
    with _engine(s).connect() as conn:
        rows = conn.execute(select(users).order_by(users.c.id)).all()
    return {"people": [_person(r) for r in rows]}


@router.post("/people")
def add_person(body: NewPersonBody, _: OwnerDep, s: StoreDep) -> dict[str, Any]:
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="that is not an email address")
    _check_password(body.password)
    try:
        with _engine(s).begin() as conn:
            uid = _new_id(
                conn.execute(
                    insert(users).values(
                        email=email,
                        name=body.name.strip(),
                        role="maker",
                        password_hash=auth.hash_password(body.password),
                        session_version=1,
                        disabled=False,
                        created_at=now(),
                    )
                )
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"{email} has an account already") from None
    return {"id": int(uid)}


def _set_person(s: Store, person_id: int, **values: Any) -> None:
    with _engine(s).begin() as conn:
        row = conn.execute(select(users).where(users.c.id == person_id)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="there is no such person")
        if row.role == "owner" and values.get("disabled"):
            raise HTTPException(status_code=422, detail="the owner account cannot be disabled")
        conn.execute(
            update(users)
            .where(users.c.id == person_id)
            .values(**values, session_version=row.session_version + 1)
        )


@router.post("/people/{person_id}/password")
def reset_password(person_id: int, body: ResetBody, _: OwnerDep, s: StoreDep) -> dict[str, Any]:
    """The owner sets a new password for someone; their old logins stop working."""
    _check_password(body.password)
    _set_person(s, person_id, password_hash=auth.hash_password(body.password))
    return {"ok": True}


@router.post("/people/{person_id}/disabled")
def set_disabled(person_id: int, body: DisabledBody, _: OwnerDep, s: StoreDep) -> dict[str, Any]:
    _set_person(s, person_id, disabled=body.disabled)
    return {"ok": True}


# -- measurements: a shared list of people's own files --------------------------------------------
def _people_tables(s: Store) -> dict[int, tuple[str, MeasurementSet]]:
    with _engine(s).connect() as conn:
        rows = conn.execute(select(measurement_files)).all()
    return {r.id: (r.name, drafting.person_table(r.content)) for r in rows}


@router.get("/measurements")
def measurements(_: UserDep, s: StoreDep) -> dict[str, Any]:
    with _engine(s).connect() as conn:
        rows = conn.execute(
            select(
                measurement_files.c.id,
                measurement_files.c.name,
                measurement_files.c.unit,
                measurement_files.c.created_at,
                users.c.name.label("by"),
            )
            .join(users, users.c.id == measurement_files.c.created_by)
            .order_by(measurement_files.c.name)
        ).all()
    return {
        "files": [
            {
                "id": r.id,
                "name": r.name,
                "unit": r.unit,
                "by": r.by,
                "created_at": str(r.created_at),
            }
            for r in rows
        ]
    }


@router.post("/measurements")
def add_measurements(body: MeasurementBody, user: UserDep, s: StoreDep) -> dict[str, Any]:
    try:
        table = drafting.person_table(body.content)
    except drafting.DraftingError as err:
        raise HTTPException(status_code=422, detail=str(err)) from None
    try:
        with _engine(s).begin() as conn:
            fid = _new_id(
                conn.execute(
                    insert(measurement_files).values(
                        name=body.name.strip(),
                        unit=table.unit,
                        content=body.content,
                        created_by=user.id,
                        created_at=now(),
                    )
                )
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"{body.name!r} exists already") from None
    return {"id": int(fid), "measurements": len(table.measurements)}


# -- starting points ------------------------------------------------------------------------------
@router.get("/patterns")
def patterns(user: UserDep) -> dict[str, Any]:
    """The patterns an item can start from: the locked blocks and the saved styles."""
    del user  # any signed-in person may look
    lib = library()
    out: list[dict[str, Any]] = []
    for meta in lib.metas().values():
        pattern = drafting.start(meta.id)[0]
        out.append(
            {
                "id": meta.id,
                "name": meta.name,
                "area": meta.area,
                "locked": meta.locked,
                "pieces": [p.get("name") or "" for _, p, _ in pieces_of(pattern)],
            }
        )
    return {"patterns": out}


@router.get("/patterns/{pattern_id}/sizes")
def pattern_sizes(pattern_id: str, user: UserDep, s: StoreDep) -> dict[str, Any]:
    """The sizes a new item can be drafted at: the table's, and every person's file."""
    del user
    try:
        options = drafting.size_options(pattern_id, _people_tables(s))
    except LibraryError as err:
        raise HTTPException(status_code=404, detail=str(err)) from None
    return {
        "sizes": [{"key": o.key, "label": o.label} for o in options],
        "default": drafting.default_key({"kind": "table"}, pattern_id),
    }


@router.get("/recipes")
def recipes(user: UserDep) -> dict[str, Any]:
    """The recipes that have a procedure (or a draft of one) in docs/manipulations, and the two
    Kasi is writing. A new name can be typed in too."""
    del user
    return {"recipes": drafting.known_recipes()}


# -- work items -----------------------------------------------------------------------------------
def _item(row: Row[Any], authors: dict[int, str], user: User) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "recipe": row.recipe,
        "example_no": row.example_no,
        "title": row.title,
        "brief": row.brief,
        "start_pattern": row.start_pattern,
        "pieces": row.pieces,
        "measurements": row.measurements,
        "author_id": row.author_id,
        "author": authors.get(row.author_id, "?"),
        "status": row.status,
        "created_at": str(row.created_at),
        "finished_at": str(row.finished_at) if row.finished_at else None,
        "can_edit": row.author_id == user.id and row.status == "open",
    }


def visible(user: User, row: Row[Any], all_rows: Sequence[Row[Any]]) -> bool:
    """Who may see an item. Your own: always. Others' designs: read-only. Others' recipe examples
    follow the blind cross-check: only when that version is finished and your own version of the
    same example is finished too. The owner sees everything, except other versions of an example
    the owner is drafting and has not finished (the owner is a maker there too)."""
    if row.author_id == user.id:
        return True
    if row.kind != "recipe_example":
        return True
    mine = [
        r
        for r in all_rows
        if r.author_id == user.id
        and r.kind == "recipe_example"
        and r.recipe == row.recipe
        and r.example_no == row.example_no
    ]
    if user.is_owner and not mine:
        return True
    return row.status == "finished" and any(r.status == "finished" for r in mine)


def _authors(conn: Any) -> dict[int, str]:
    return {r.id: r.name for r in conn.execute(select(users.c.id, users.c.name)).all()}


@router.get("/items")
def list_items(user: UserDep, s: StoreDep) -> dict[str, Any]:
    with _engine(s).connect() as conn:
        rows = conn.execute(select(items).order_by(items.c.id.desc())).all()
        authors = _authors(conn)
    shown = [r for r in rows if visible(user, r, rows)]
    return {
        "items": [_item(r, authors, user) for r in shown],
        "hidden": len(rows) - len(shown),  # versions kept blind until both are finished
    }


@router.post("/items")
def new_item(body: NewItemBody, user: UserDep, s: StoreDep) -> dict[str, Any]:
    if body.kind == "recipe_example":
        if not body.recipe or not RECIPE_RE.match(body.recipe):
            raise HTTPException(
                status_code=422,
                detail="a recipe example needs the recipe's name: lower case, digits and _",
            )
        if body.example_no is None:
            raise HTTPException(status_code=422, detail="a recipe example needs its number")
    try:
        pattern, table, _ = drafting.start(body.start_pattern)
    except LibraryError as err:
        raise HTTPException(status_code=422, detail=str(err)) from None
    names = {p.get("name") or "" for _, p, _ in pieces_of(pattern)}
    unknown = [n for n in body.pieces if n not in names]
    if unknown:
        raise HTTPException(status_code=422, detail=f"no such piece: {', '.join(unknown)}")
    meas = body.measurements.model_dump()
    people = _people_tables(s)
    key = drafting.default_key(meas, body.start_pattern)
    try:
        drafting.option_for(key, body.start_pattern, people)
    except drafting.DraftingError as err:
        raise HTTPException(status_code=422, detail=str(err)) from None
    if meas["kind"] == "table":
        meas["size"] = meas["size"] if meas["size"] is not None else table.base_size
        meas["height"] = meas["height"] if meas["height"] is not None else table.base_height
    try:
        with _engine(s).begin() as conn:
            iid = _new_id(
                conn.execute(
                    insert(items).values(
                        kind=body.kind,
                        recipe=body.recipe if body.kind == "recipe_example" else None,
                        example_no=body.example_no if body.kind == "recipe_example" else None,
                        title=body.title.strip(),
                        brief=body.brief,
                        start_pattern=body.start_pattern,
                        pieces=body.pieces,
                        measurements=meas,
                        author_id=user.id,
                        status="open",
                        created_at=now(),
                    )
                )
            )
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"you have a version of {body.recipe} example {body.example_no} already",
        ) from None
    return {"id": int(iid)}


def _load(s: Store, user: User, item_id: int) -> Row[Any]:
    with _engine(s).connect() as conn:
        rows = conn.execute(select(items)).all()
    row = next((r for r in rows if r.id == item_id), None)
    if row is None or not visible(user, row, rows):
        # a blind version is reported as missing, not as forbidden: its existence is not shown
        raise HTTPException(status_code=404, detail="there is no such item")
    return row


@router.get("/items/{item_id}")
def get_item(item_id: int, user: UserDep, s: StoreDep) -> dict[str, Any]:
    row = _load(s, user, item_id)
    with _engine(s).connect() as conn:
        authors = _authors(conn)
    return {"item": _item(row, authors, user)}


@router.post("/items/{item_id}/finish")
def finish_item(item_id: int, user: UserDep, s: StoreDep) -> dict[str, Any]:
    row = _load(s, user, item_id)
    if row.author_id != user.id:
        raise HTTPException(status_code=403, detail="only its author can finish an item")
    with _engine(s).begin() as conn:
        conn.execute(
            update(items).where(items.c.id == item_id).values(status="finished", finished_at=now())
        )
    return {"ok": True}


@router.post("/items/{item_id}/reopen")
def reopen_item(item_id: int, _: OwnerDep, s: StoreDep) -> dict[str, Any]:
    with _engine(s).begin() as conn:
        conn.execute(
            update(items).where(items.c.id == item_id).values(status="open", finished_at=None)
        )
    return {"ok": True}


def _box(s: Store, row: Row[Any], size: str | None) -> tuple[Any, drafting.SizeOption]:
    people = _people_tables(s)
    key = size or drafting.default_key(row.measurements, row.start_pattern)
    try:
        option = drafting.option_for(key, row.start_pattern, people)
    except drafting.DraftingError as err:
        raise HTTPException(status_code=422, detail=str(err)) from None
    pattern, _, _ = drafting.start(row.start_pattern)
    return s.sessions.get(row.id, "start", pattern, option), option


@router.get("/items/{item_id}/sizes")
def item_sizes(item_id: int, user: UserDep, s: StoreDep) -> dict[str, Any]:
    row = _load(s, user, item_id)
    options = drafting.size_options(row.start_pattern, _people_tables(s))
    return {
        "sizes": [{"key": o.key, "label": o.label} for o in options],
        "default": drafting.default_key(row.measurements, row.start_pattern),
    }


@router.get("/items/{item_id}/scene")
def item_scene(item_id: int, user: UserDep, s: StoreDep, size: str | None = None) -> dict[str, Any]:
    row = _load(s, user, item_id)
    box, option = _box(s, row, size)
    data = drafting.scene(box)
    data["size"] = {"key": option.key, "label": option.label}
    data["pieces"] = row.pieces
    return data


@router.get("/items/{item_id}/objects/{object_id}")
def item_object(
    item_id: int, object_id: int, user: UserDep, s: StoreDep, size: str | None = None
) -> dict[str, Any]:
    row = _load(s, user, item_id)
    box, _ = _box(s, row, size)
    try:
        drafting.check_object(box, object_id)
        return {"object": drafting.inspect(box, object_id)}
    except drafting.DraftingError as err:
        raise HTTPException(status_code=404, detail=str(err)) from None
