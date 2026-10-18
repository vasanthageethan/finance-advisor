"""
Password hashing and JWT session handling. See
docs/design-auth-and-customers.md for the full design, including why this
is a bootstrap-then-login flow rather than a registration form, and why
customer_id is a separate field from the row's own primary key.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Header, HTTPException

# Falls back to a random key generated at process start if unset -- fine
# for local dev, but tokens won't survive a restart; set JWT_SECRET_KEY in
# .env for persistent sessions.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or secrets.token_hex(32)
ALGORITHM = "HS256"
EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "168"))  # 7 days


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(customer_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=EXPIRY_HOURS)
    payload = {"customer_id": customer_id, "exp": expires_at}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the customer_id encoded in a valid token, or raises
    jwt.InvalidTokenError (expired, bad signature, malformed, ...)."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload["customer_id"]


def require_bearer_token(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: extracts and validates the Authorization header,
    returning the authenticated customer_id. Raises 401 otherwise."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return decode_access_token(token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "Invalid or expired session") from exc
