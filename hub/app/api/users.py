import json
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth
from ..audit import record_audit
from ..db import AuditLogEntry, User
from ..deps import get_db
from ..schemas import AuditLogEntryOut, UserCreate, UserOut, UserUpdate

router = APIRouter(tags=["users"])

AUDIT_LOG_LIMIT = 500


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, role=user.role, scope=user.scope, created_at=user.created_at.isoformat())


@router.get("/api/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(auth.require_admin_user)) -> list[UserOut]:
    return [_user_out(u) for u in db.query(User).order_by(User.username).all()]


@router.post("/api/users", response_model=UserOut)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(auth.require_admin_user),
) -> UserOut:
    if db.query(User).filter(User.username == body.username).first() is not None:
        raise HTTPException(status_code=409, detail=f"a user named '{body.username}' already exists")
    user = User(
        id=secrets.token_hex(16),
        username=body.username,
        password_hash=auth.hash_password(body.password),
        role=body.role,
        scope=body.scope,
    )
    db.add(user)
    db.commit()
    record_audit(db, admin, "create_user", target=user.username, detail={"role": user.role, "scope": user.scope})
    return _user_out(user)


@router.put("/api/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(auth.require_admin_user),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="no such user")
    changes = {}
    if body.role is not None:
        user.role = body.role
        changes["role"] = body.role
    if body.scope is not None:
        user.scope = body.scope
        changes["scope"] = body.scope
    if body.password:
        user.password_hash = auth.hash_password(body.password)
        changes["password"] = "changed"
    db.commit()
    record_audit(db, admin, "update_user", target=user.username, detail=changes)
    return _user_out(user)


@router.delete("/api/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(auth.require_admin_user),
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="cannot delete your own account")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="no such user")
    username = user.username
    db.delete(user)
    db.commit()
    record_audit(db, admin, "delete_user", target=username)


@router.get("/api/audit-log", response_model=list[AuditLogEntryOut])
def list_audit_log(db: Session = Depends(get_db), _admin: User = Depends(auth.require_admin_user)) -> list[AuditLogEntryOut]:
    entries = db.query(AuditLogEntry).order_by(AuditLogEntry.created_at.desc()).limit(AUDIT_LOG_LIMIT).all()
    return [
        AuditLogEntryOut(
            id=e.id,
            username=e.username,
            action=e.action,
            target=e.target,
            detail=json.loads(e.detail_json) if e.detail_json else None,
            created_at=e.created_at.isoformat(),
        )
        for e in entries
    ]
