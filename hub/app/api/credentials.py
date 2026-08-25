import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, crypto
from ..audit import record_audit
from ..db import BackendCapability, CredentialKey, Node, User, utcnow
from ..deps import get_db
from ..schemas import CommandOut, CommandResult, CredentialApplyRequest, CredentialCreate, CredentialOut
from ..connections import connections
from .nodes import dispatch_command, dispatch_command_to_nodes

router = APIRouter(tags=["credentials"])


def _credential_out(cred: CredentialKey) -> CredentialOut:
    return CredentialOut(
        id=cred.id,
        name=cred.name,
        backend=cred.backend,
        static_fields=json.loads(cred.static_fields_json),
        created_at=cred.created_at.isoformat(),
        last_used_at=cred.last_used_at.isoformat() if cred.last_used_at else None,
    )


def _credential_action_for(db: Session, backend: str) -> dict:
    """Looks up the backend's declared CREDENTIAL_ACTION (see
    node/grid_node/backends/base.py) from the hub's BackendCapability
    registry, populated from a node's status frame -- not hardcoded to
    BOINC's attach_project, so any backend that declares one works here.
    404s the same way an unknown backend name would practically behave: no
    node has ever reported it, so there's nothing to apply a credential
    through."""
    cap = db.get(BackendCapability, backend)
    credential_action = json.loads(cap.credential_action_json) if cap and cap.credential_action_json else None
    if credential_action is None:
        raise HTTPException(
            status_code=400,
            detail=f"backend '{backend}' has no known saved-credential action -- either the hub hasn't seen a "
            "node running it yet, or that backend doesn't support saved credentials",
        )
    return credential_action


@router.post("/api/credentials", response_model=CredentialOut)
def create_credential(
    body: CredentialCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(auth.require_admin_user),
) -> CredentialOut:
    if db.query(CredentialKey).filter(CredentialKey.name == body.name).first() is not None:
        raise HTTPException(status_code=409, detail=f"a credential named '{body.name}' already exists")
    credential_action = _credential_action_for(db, body.backend)
    expected_fields = set(credential_action.get("static_fields", []))
    if set(body.static_fields) != expected_fields:
        raise HTTPException(
            status_code=400,
            detail=f"backend '{body.backend}' credentials require exactly these static fields: {sorted(expected_fields)}",
        )
    try:
        encrypted = crypto.encrypt(body.secret)
    except crypto.SecretKeyNotConfigured as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    cred = CredentialKey(
        id=str(uuid.uuid4()),
        name=body.name,
        backend=body.backend,
        static_fields_json=json.dumps(body.static_fields),
        encrypted_secret=encrypted,
    )
    db.add(cred)
    db.commit()
    record_audit(db, admin, "create_credential", target=cred.name, detail={"backend": cred.backend})
    return _credential_out(cred)


@router.get("/api/credentials", response_model=list[CredentialOut])
def list_credentials(db: Session = Depends(get_db), _user: User = Depends(auth.require_session)) -> list[CredentialOut]:
    """Available to everyone, not just admins -- metadata only (name/
    backend/static fields), no secret material, so a group/machine manager
    can see what's available to apply within their own scope."""
    return [_credential_out(c) for c in db.query(CredentialKey).order_by(CredentialKey.name).all()]


@router.delete("/api/credentials/{credential_id}", status_code=204)
def delete_credential(
    credential_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(auth.require_admin_user),
) -> None:
    cred = db.get(CredentialKey, credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="no such credential")
    name = cred.name
    db.delete(cred)
    db.commit()
    record_audit(db, admin, "delete_credential", target=name)


@router.post("/api/credentials/{credential_id}/apply", response_model=CommandOut)
async def apply_credential(
    credential_id: str,
    body: CredentialApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_session),
) -> CommandOut:
    """Single-node apply -- applies the saved credential to one node.
    Fleet-wide/group apply is a deliberate follow-up, not this endpoint's
    job (see _docs/knowledge-graph/credentials.md)."""
    cred = db.get(CredentialKey, credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="no such credential")
    node = auth.get_node_or_403(db, user, body.node_id, write=True)
    credential_action = _credential_action_for(db, cred.backend)

    try:
        secret = crypto.decrypt(cred.encrypted_secret)
    except crypto.SecretKeyNotConfigured as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    payload = {**json.loads(cred.static_fields_json), credential_action["key_field"]: secret}
    result = await dispatch_command(db, user, node, cred.backend, credential_action["action"], payload)
    cred.last_used_at = utcnow()
    db.commit()
    return result


async def _apply_to_nodes(db: Session, user: User, cred: CredentialKey, nodes: list[Node]) -> list[CommandResult]:
    """Bulk fan-out, reusing nodes.py::dispatch_command_to_nodes -- the
    secret is only ever decrypted if at least one target node is actually
    online (an all-offline batch is a no-op: no decrypt, no last_used_at
    bump, same as before this was generalized)."""
    online_nodes = [n for n in nodes if connections.is_online(n.id)]
    if not online_nodes:
        return [CommandResult(node_id=n.id, node_name=n.name, online=False, status="skipped", result=None) for n in nodes]

    credential_action = _credential_action_for(db, cred.backend)
    try:
        secret = crypto.decrypt(cred.encrypted_secret)
    except crypto.SecretKeyNotConfigured as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    payload = {**json.loads(cred.static_fields_json), credential_action["key_field"]: secret}
    results = await dispatch_command_to_nodes(db, user, nodes, cred.backend, credential_action["action"], payload)
    cred.last_used_at = utcnow()
    db.commit()
    return results


@router.post("/api/credentials/{credential_id}/apply-group/{group}", response_model=list[CommandResult])
async def apply_credential_to_group(
    credential_id: str,
    group: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_session),
) -> list[CommandResult]:
    """An unknown or empty group simply matches no nodes rather than
    erroring, same as schedule.py's apply-group. group_manager only,
    scoped to their own group -- a machine_manager has no group-wide
    action to take."""
    auth.require_group_access(user, group)
    cred = db.get(CredentialKey, credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="no such credential")
    nodes = db.query(Node).filter(Node.group == group).all()
    return await _apply_to_nodes(db, user, cred, nodes)


@router.post("/api/credentials/{credential_id}/apply-all", response_model=list[CommandResult])
async def apply_credential_to_all(
    credential_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(auth.require_admin_user),
) -> list[CommandResult]:
    cred = db.get(CredentialKey, credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="no such credential")
    nodes = db.query(Node).all()
    return await _apply_to_nodes(db, admin, cred, nodes)
