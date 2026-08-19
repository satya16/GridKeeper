import hashlib
import hmac
import secrets
import threading
import time

from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .db import Node

# Very small v1 auth story: a single admin password protects the dashboard
# and REST API, nodes authenticate with a bearer token that was minted
# during enrollment. Nothing here is meant to survive contact with a
# multi-user future -- see _docs/REQUIREMENTS.md section 6/9.
#
# Session-cookie login (not HTTP Basic): switched 2026-08-19 after a real
# report that Firefox Focus never shows Basic Auth's native credential
# prompt at all (just renders as "unauthenticated", no way in) --
# browser-native Basic Auth UI turned out to not be reliable enough across
# real mobile browsers to depend on. In-memory session store, not
# persisted -- a hub restart logging everyone out is an acceptable
# tradeoff for this app's size (unlike node bearer tokens, which *are*
# persisted, since nodes need to reconnect unattended).

ADMIN_PASSWORD_ENV = "GRIDKEEPER_ADMIN_PASSWORD"
DEFAULT_ADMIN_PASSWORD = "changeme"
SESSION_COOKIE_NAME = "gridkeeper_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days

_sessions_lock = threading.Lock()
_sessions: dict[str, float] = {}  # token -> expires_at (unix time)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_pairing_token() -> str:
    return secrets.token_urlsafe(16)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def get_admin_password() -> str:
    import os

    return os.environ.get(ADMIN_PASSWORD_ENV, DEFAULT_ADMIN_PASSWORD)


def create_session(response: Response) -> None:
    token = new_token()
    with _sessions_lock:
        _sessions[token] = time.time() + SESSION_TTL_SECONDS
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        # No `secure=True`: this app is deliberately served over plain LAN
        # HTTP by default (see README) -- requiring HTTPS here would just
        # break the cookie silently. Real TLS deployments are a documented
        # open item (_docs/REQUIREMENTS.md), not solved by this flag alone.
    )


def destroy_session(token: str | None, response: Response) -> None:
    if token:
        with _sessions_lock:
            _sessions.pop(token, None)
    response.delete_cookie(SESSION_COOKIE_NAME)


def _session_valid(token: str) -> bool:
    with _sessions_lock:
        expires_at = _sessions.get(token)
        if expires_at is None:
            return False
        if expires_at < time.time():
            del _sessions[token]
            return False
        return True


def require_session(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)) -> str:
    if not session_token or not _session_valid(session_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not logged in")
    return session_token


def authenticate_node(db: Session, node_id: str, token: str) -> Node:
    node = db.get(Node, node_id)
    if node is None or not verify_token(token, node.token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown node or bad token")
    return node
