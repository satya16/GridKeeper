import json
import secrets

from sqlalchemy.orm import Session

from .db import AuditLogEntry, User, utcnow


def record_audit(db: Session, user: User, action: str, target: str = "", detail: dict | None = None) -> None:
    """Durable "who did what" record, admin-visible via GET /api/audit-log.
    Plain synchronous write in the caller's own transaction -- no separate
    queue, matching this project's existing "keep v1 simple" pattern (see
    auth.py's in-memory sessions, User.scope's comma-separated fields).
    Call this *after* the action has actually succeeded, not before, so a
    failed action doesn't get logged as if it happened."""
    db.add(
        AuditLogEntry(
            id=secrets.token_hex(16),
            user_id=user.id,
            username=user.username,
            action=action,
            target=target,
            detail_json=json.dumps(detail) if detail is not None else None,
            created_at=utcnow(),
        )
    )
    db.commit()
