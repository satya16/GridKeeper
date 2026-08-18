import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from .db import Worker

_basic = HTTPBasic()

# Very small v1 auth story: a single admin password protects the dashboard
# and REST API (HTTP Basic), workers authenticate with a bearer token that
# was minted during enrollment. Nothing here is meant to survive contact
# with a multi-user future -- see docs/REQUIREMENTS.md section 6/9.

ADMIN_PASSWORD_ENV = "GRID_MANAGER_ADMIN_PASSWORD"
DEFAULT_ADMIN_PASSWORD = "changeme"


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


def require_admin(credentials: HTTPBasicCredentials = Depends(_basic)) -> str:
    """HTTP Basic auth for the dashboard + REST API. Username can be anything
    (e.g. 'admin'); only the password is checked against GRID_MANAGER_ADMIN_PASSWORD."""
    if not hmac.compare_digest(credentials.password, get_admin_password()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad admin password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def authenticate_worker(db: Session, worker_id: str, token: str) -> Worker:
    worker = db.get(Worker, worker_id)
    if worker is None or not verify_token(token, worker.token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown worker or bad token")
    return worker
