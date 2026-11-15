"""The studio's database: people, shared measurement files, work items.

Postgres in production (`DATABASE_URL`, set on Railway), SQLite in tests and on a laptop. The
schema is SQLAlchemy Core tables; `migrate` creates what is missing and records the schema version,
so later stages add migrations here, in order, never by hand.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    insert,
    select,
)
from sqlalchemy.pool import StaticPool

SCHEMA_VERSION = 1

metadata = MetaData()

schema_version = Table(
    "schema_version",
    metadata,
    Column("version", Integer, primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False),
)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("name", String(120), nullable=False),
    Column("role", String(16), nullable=False),  # owner | maker
    Column("password_hash", String(255), nullable=False),
    # bumped when the password changes or is reset: every older login cookie stops working
    Column("session_version", Integer, nullable=False, default=1),
    Column("disabled", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

measurement_files = Table(
    "measurement_files",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(120), nullable=False, unique=True),
    Column("unit", String(8), nullable=False),
    Column("content", Text, nullable=False),  # the .smis file as uploaded (lossless)
    Column("created_by", Integer, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

items = Table(
    "items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("kind", String(20), nullable=False),  # recipe_example | design
    Column("recipe", String(64)),  # recipe examples: the recipe's name (new ones too)
    Column("example_no", Integer),  # recipe examples: 1, 2 or 3
    Column("title", String(200), nullable=False),
    Column("brief", Text, nullable=False, default=""),
    Column("start_pattern", String(64), nullable=False),  # a library pattern id
    Column("pieces", JSON, nullable=False, default=list),  # the pieces the item is about
    # the measurements the item is drafted at: {"kind": "table", "size", "height"} or
    # {"kind": "person", "id"}
    Column("measurements", JSON, nullable=False),
    Column("author_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("status", String(16), nullable=False, default="open"),  # open | finished
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    UniqueConstraint("kind", "recipe", "example_no", "author_id", name="one_version_per_maker"),
)


def now() -> datetime:
    return datetime.now(UTC)


def database_url() -> str | None:
    """`DATABASE_URL` as SQLAlchemy wants it (Railway gives `postgresql://`, we use psycopg 3)."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite") and ":memory:" in url:
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


def migrate(engine: Engine) -> int:
    """Create the tables that are missing and record the schema version. Safe to run at every
    start."""
    metadata.create_all(engine)
    with engine.begin() as conn:
        have = conn.execute(select(schema_version.c.version)).scalars().all()
        if SCHEMA_VERSION not in have:
            conn.execute(insert(schema_version).values(version=SCHEMA_VERSION, applied_at=now()))
    return SCHEMA_VERSION
