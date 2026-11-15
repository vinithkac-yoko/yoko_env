"""Logins: email and password, accounts made only by the owner, no emails sent.

Passwords are stored as scrypt hashes. A login is a cookie holding the user id, the user's session
version and when it was issued, signed with `SESSION_SECRET`. Resetting or changing a password bumps
the session version, so every older cookie stops working. Bearer `STUDIO_TOKEN` still opens the API
for scripts and the CI smoke test, and makes the owner account the first time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

COOKIE = "yoko_session"
MAX_AGE_S = 30 * 24 * 3600
_N, _R, _P = 2**14, 8, 1  # scrypt cost: about 50 ms a hash


@dataclass(frozen=True, slots=True)
class User:
    id: int
    email: str
    name: str
    role: str  # owner | maker
    session_version: int = 1

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, n, r, p, salt, digest = stored.split("$")
    except ValueError:
        return False
    if kind != "scrypt":
        return False
    got = hashlib.scrypt(
        password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32
    )
    return hmac.compare_digest(got, _unb64(digest))


def password_problem(password: str) -> str | None:
    """Why a new password is refused, or None."""
    if len(password) < 10:
        return "a password needs at least 10 characters"
    if len(password) > 200:
        return "a password may have at most 200 characters"
    return None


def session_secret() -> bytes | None:
    secret = os.environ.get("SESSION_SECRET")
    return secret.encode() if secret else None


def make_cookie(user: User, secret: bytes, issued: float | None = None) -> str:
    body = f"{user.id}.{user.session_version}.{int(issued if issued is not None else time.time())}"
    sig = hmac.new(secret, body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(sig)}"


def read_cookie(value: str, secret: bytes, now: float | None = None) -> tuple[int, int] | None:
    """(user id, session version) from a cookie that is ours and not too old; else None."""
    try:
        uid, version, issued, sig = value.split(".")
        body = f"{uid}.{version}.{issued}"
        want = hmac.new(secret, body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(want, _unb64(sig)):
            return None
        if (now if now is not None else time.time()) - int(issued) > MAX_AGE_S:
            return None
        return int(uid), int(version)
    except (ValueError, TypeError):
        return None


def token_matches(supplied: str | None) -> bool:
    expected = os.environ.get("STUDIO_TOKEN")
    if not expected or not supplied:
        return False
    return hmac.compare_digest(supplied.encode(), expected.encode())
