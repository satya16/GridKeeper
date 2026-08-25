import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth
from ..db import BackendCapability, User, utcnow
from ..deps import get_db
from ..schemas import BackendCapabilityOut

router = APIRouter(tags=["backends"])


def _out(cap: BackendCapability) -> BackendCapabilityOut:
    return BackendCapabilityOut(
        name=cap.name,
        label=cap.label,
        sensitive_fields=json.loads(cap.sensitive_fields_json),
        credential_action=json.loads(cap.credential_action_json) if cap.credential_action_json else None,
        actions=json.loads(cap.actions_json),
    )


def upsert_capabilities(db: Session, capabilities: dict) -> None:
    """Called from main.py's node_ws for every status frame's `capabilities`
    block (see node/grid_node/daemon.py::collect_capabilities). Last-writer-
    wins: capability shape is a property of the backend package/version a
    node happens to be running, not of that individual machine, so any node
    reporting a given backend name is an equally valid source of truth for
    it."""
    for name, caps in capabilities.items():
        cap = db.get(BackendCapability, name)
        if cap is None:
            cap = BackendCapability(name=name)
            db.add(cap)
        cap.label = caps.get("label", name)
        cap.sensitive_fields_json = json.dumps(caps.get("sensitive_fields", {}))
        credential_action = caps.get("credential_action")
        cap.credential_action_json = json.dumps(credential_action) if credential_action else None
        cap.actions_json = json.dumps(caps.get("actions", []))
        cap.updated_at = utcnow()
    db.commit()


@router.get("/api/backends", response_model=list[BackendCapabilityOut])
def list_backends(db: Session = Depends(get_db), _user: User = Depends(auth.require_session)) -> list[BackendCapabilityOut]:
    """Every backend this hub has ever seen a node report -- lets the
    dashboard build a generic credential-create form and a generic per-
    backend action UI without hardcoding BOINC/FAH."""
    return [_out(c) for c in db.query(BackendCapability).order_by(BackendCapability.name).all()]
