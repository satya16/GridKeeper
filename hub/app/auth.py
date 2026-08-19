import hashlib
import hmac
import os
import secrets
import threading
import time

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .db import Node, User
from .deps import get_db

# v2 auth: real per-user accounts + roles, replacing the earlier single
# shared admin password (see _docs/REQUIREMENTS.md section 6/9 for why
# that was originally considered enough for v1). Nodes still authenticate
# their WebSocket with a per-node bearer token minted at enrollment --
# unrelated to admin/user auth, unchanged by this.
#
# Session-cookie login (not HTTP Basic): switched 2026-08-19 after a real
# report that Firefox Focus never shows Basic Auth's native credential
# prompt at all -- browser-native Basic Auth UI turned out to not be
# reliable enough across real mobile browsers to depend on. In-memory
# session store, not persisted -- a hub restart logging everyone out is
# an acceptable tradeoff for this app's size (unlike node bearer tokens,
# which *are* persisted, since nodes reconnect unattended and can't
# re-enter a password themselves).

ADMIN_PASSWORD_ENV = "GRIDKEEPER_ADMIN_PASSWORD"
DEFAULT_ADMIN_PASSWORD = "changeme"
SESSION_COOKIE_NAME = "gridkeeper_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
ROLES = ("admin", "group_manager", "machine_manager", "viewer")

_sessions_lock = threading.Lock()
_sessions: dict[str, dict] = {}  # token -> {"user_id": str, "expires_at": float}


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_pairing_token() -> str:
    return secrets.token_urlsafe(16)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash (shouldn't happen outside test fixtures/manual DB
        # edits) -- fail closed, not a 500.
        return False


def get_admin_password() -> str:
    return os.environ.get(ADMIN_PASSWORD_ENV, DEFAULT_ADMIN_PASSWORD)


def bootstrap_admin_user(db: Session) -> None:
    """Seeds a single 'admin' user from GRIDKEEPER_ADMIN_PASSWORD the first
    time the hub ever boots (users table empty) -- keeps the existing
    `docker run -e GRIDKEEPER_ADMIN_PASSWORD=...` quickstart working
    unchanged; that env var becomes the *first* admin's password instead
    of the only one. Called once from main.py's lifespan, after init_db()."""
    if db.query(User).count() > 0:
        return
    db.add(
        User(
            id=secrets.token_hex(16),
            username="admin",
            password_hash=hash_password(get_admin_password()),
            role="admin",
            scope="",
        )
    )
    db.commit()


def scope_list(user: User) -> list[str]:
    return [s for s in user.scope.split(",") if s]


def create_session(response: Response, user_id: str) -> None:
    token = new_token()
    with _sessions_lock:
        _sessions[token] = {"user_id": user_id, "expires_at": time.time() + SESSION_TTL_SECONDS}
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


def _session_user_id(token: str) -> str | None:
    with _sessions_lock:
        entry = _sessions.get(token)
        if entry is None:
            return None
        if entry["expires_at"] < time.time():
            del _sessions[token]
            return None
        return entry["user_id"]


def require_session(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    user_id = _session_user_id(session_token) if session_token else None
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not logged in")
    user = db.get(User, user_id)
    if user is None:
        # Account was deleted while this session was still live.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not logged in")
    return user


def require_admin_user(user: User = Depends(require_session)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user


def can_access_node(user: User, node: Node, *, write: bool) -> bool:
    """admin: unrestricted. viewer: read anything, write nothing.
    group_manager/machine_manager: read AND write restricted to scope --
    confirmed with the user this should be a genuinely restricted view,
    not just a restricted edit (unlike viewer, which does see everything,
    read-only)."""
    if user.role == "admin":
        return True
    if user.role == "viewer":
        return not write
    if user.role == "group_manager":
        return node.group != "" and node.group in scope_list(user)
    if user.role == "machine_manager":
        return node.id in scope_list(user)
    return False


def get_node_or_403(db: Session, user: User, node_id: str, *, write: bool) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="no such node")
    if not can_access_node(user, node, write=write):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not permitted for this node")
    return node


def require_group_access(user: User, group: str) -> None:
    """Gate for group-wide write operations -- credential apply-group,
    schedule apply-group, pairing-token minting, discovery pairing.
    admin: any group, including "" (fleet-wide). group_manager: only a
    non-empty group that's in their own scope. Everyone else
    (machine_manager, viewer) is blocked outright: a machine_manager has
    nothing fleet-wide to do (they manage exactly one machine, already
    in a group or not), and a viewer can't write at all."""
    if user.role == "admin":
        return
    if user.role == "group_manager" and group and group in scope_list(user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not permitted for this group")


def authenticate_node(db: Session, node_id: str, token: str) -> Node:
    node = db.get(Node, node_id)
    if node is None or not verify_token(token, node.token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown node or bad token")
    return node
