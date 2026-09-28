"""Password hashing, JWT access tokens, and legacy-hash verification.

ARCHITECTURE.md §9: argon2id for new hashes. The prototype used PBKDF2 (`pbkdf2_sha256$...`); we verify
those transparently and re-hash to argon2 on successful login so the migration is invisible to students.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

ALGORITHM = "HS256"
_hasher = PasswordHasher()

_LEGACY_PBKDF2_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _verify_legacy_pbkdf2(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def verify_password(password: str, encoded: str) -> tuple[bool, bool]:
    """Returns (is_valid, needs_rehash)."""
    if encoded.startswith("pbkdf2_sha256$"):
        valid = _verify_legacy_pbkdf2(password, encoded)
        return valid, valid  # a valid legacy hash always needs upgrading to argon2
    try:
        _hasher.verify(encoded, password)
    except VerifyMismatchError:
        return False, False
    except Exception:
        return False, False
    return True, _hasher.check_needs_rehash(encoded)


def generate_password(length: int = 10) -> str:
    """Readable random password: no look-alike characters (0/O/1/l/I) — ARCHITECTURE.md A4."""
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_access_token(subject: str, role: str, session_id: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "sid": session_id, "exp": expires}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
