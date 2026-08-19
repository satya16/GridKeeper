import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth
from ..audit import record_audit
from ..db import Node, Command, User, utcnow
from ..deps import get_db
from ..schemas import NodeOut, CommandOut, CommandRequest, NodeGroupUpdate
from ..connections import connections

router = APIRouter(tags=["nodes"])

COMMAND_TIMEOUT_SECONDS = 15.0

# Payload fields that are long-lived credentials, not one-time tokens --
# must never land in the commands table (or its audit-log GET response) in
# plaintext. Keyed by (backend, action). The *unredacted* payload is still
# what actually gets sent to the node, which needs the real value; only
# what's persisted/returned via the API is masked.
_SENSITIVE_PAYLOAD_FIELDS: dict[tuple[str, str], set[str]] = {
    ("boinc", "attach_project"): {"account_key"},
    ("fah", "set_config"): {"passkey"},
}


def _redact_payload(backend: str, action: str, payload: dict) -> dict:
    sensitive = _SENSITIVE_PAYLOAD_FIELDS.get((backend, action))
    if not sensitive:
        return payload
    return {k: ("***redacted***" if k in sensitive else v) for k, v in payload.items()}


def _node_out(node: Node) -> NodeOut:
    return NodeOut(
        id=node.id,
        name=node.name,
        os_name=node.os_name,
        backends=[b for b in node.backends.split(",") if b],
        group=node.group,
        online=connections.is_online(node.id),
        last_seen_at=node.last_seen_at.isoformat() if node.last_seen_at else None,
        status=json.loads(node.last_status_json) if node.last_status_json else None,
        schedule=json.loads(node.schedule_json) if node.schedule_json else None,
    )


def _command_out(cmd: Command) -> CommandOut:
    return CommandOut(
        id=cmd.id,
        node_id=cmd.node_id,
        backend=cmd.backend,
        action=cmd.action,
        payload=json.loads(cmd.payload_json),
        status=cmd.status,
        result=json.loads(cmd.result_json) if cmd.result_json else None,
        created_at=cmd.created_at.isoformat(),
        completed_at=cmd.completed_at.isoformat() if cmd.completed_at else None,
    )


def scoped_nodes_query(db: Session, user: User):
    """admin/viewer: every node. group_manager/machine_manager: only
    nodes within their own scope -- confirmed with the user this should
    restrict *visibility*, not just editing (a manager shouldn't see
    other groups'/machines' nodes at all, matching viewer's inverse:
    unrestricted visibility, zero edit rights)."""
    query = db.query(Node)
    if user.role == "group_manager":
        return query.filter(Node.group.in_(auth.scope_list(user)))
    if user.role == "machine_manager":
        return query.filter(Node.id.in_(auth.scope_list(user)))
    return query


@router.get("/api/nodes", response_model=list[NodeOut])
def list_nodes(db: Session = Depends(get_db), user: User = Depends(auth.require_session)) -> list[NodeOut]:
    nodes = scoped_nodes_query(db, user).order_by(Node.name).all()
    return [_node_out(a) for a in nodes]


@router.get("/api/nodes/{node_id}", response_model=NodeOut)
def get_node(node_id: str, db: Session = Depends(get_db), user: User = Depends(auth.require_session)) -> NodeOut:
    node = auth.get_node_or_403(db, user, node_id, write=False)
    return _node_out(node)


@router.get("/api/groups", response_model=list[str])
def list_groups(db: Session = Depends(get_db), user: User = Depends(auth.require_session)) -> list[str]:
    """Distinct, non-empty group names currently in use -- lets the
    dashboard offer a picker instead of everyone free-typing "Lab 1" vs
    "lab1" vs "Lab One" for the same room. Scoped the same way the node
    list is: a group_manager only sees their own group(s) in this picker,
    a machine_manager sees whatever group(s) their scoped node(s) happen
    to be in (usually zero or one)."""
    rows = scoped_nodes_query(db, user).filter(Node.group != "").with_entities(Node.group).distinct().order_by(Node.group).all()
    return [r[0] for r in rows]


@router.put("/api/nodes/{node_id}/group", response_model=NodeGroupUpdate)
def set_node_group(
    node_id: str,
    body: NodeGroupUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_session),
) -> NodeGroupUpdate:
    node = auth.get_node_or_403(db, user, node_id, write=True)
    node.group = body.group
    db.commit()
    record_audit(db, user, "set_node_group", target=node.name, detail={"group": body.group})
    return body


async def dispatch_command(db: Session, user: User, node: Node, backend: str, action: str, payload: dict) -> CommandOut:
    """Shared by the direct issue_command route below and
    credentials.py's apply endpoints, which dispatch the same
    attach_project command but with a saved (decrypted) account key
    instead of one typed inline in the dashboard's attach form. `user` is
    required (not optional) so every command that ever reaches a node,
    from any caller, gets one consistent audit-log entry here rather than
    each caller needing to remember to log it separately."""
    if not connections.is_online(node.id):
        raise HTTPException(status_code=409, detail=f"node '{node.name}' is not connected right now")

    command_id = str(uuid.uuid4())
    cmd = Command(
        id=command_id,
        node_id=node.id,
        backend=backend,
        action=action,
        payload_json=json.dumps(_redact_payload(backend, action, payload)),
        status="sent",
    )
    db.add(cmd)
    db.commit()

    future = connections.register_pending(command_id)
    sent = await connections.send_frame(
        node.id,
        {
            "type": "command",
            "command_id": command_id,
            "backend": backend,
            "action": action,
            "payload": payload,
        },
    )
    if not sent:
        connections.drop_pending(command_id)
        cmd.status = "error"
        cmd.result_json = json.dumps({"error": "node disconnected before command could be sent"})
        cmd.completed_at = utcnow()
        db.commit()
        record_audit(db, user, f"{backend}.{action}", target=node.name, detail={"status": cmd.status})
        return _command_out(cmd)

    try:
        result = await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT_SECONDS)
        cmd.status = result.get("status", "ok")
        cmd.result_json = json.dumps(result.get("result", {}))
    except TimeoutError:
        connections.drop_pending(command_id)
        cmd.status = "timeout"
        cmd.result_json = json.dumps({"error": f"no response from node within {COMMAND_TIMEOUT_SECONDS}s"})
    cmd.completed_at = utcnow()
    db.commit()
    record_audit(db, user, f"{backend}.{action}", target=node.name, detail={"status": cmd.status})
    return _command_out(cmd)


@router.post("/api/nodes/{node_id}/commands", response_model=CommandOut)
async def issue_command(
    node_id: str,
    body: CommandRequest,
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_session),
) -> CommandOut:
    node = auth.get_node_or_403(db, user, node_id, write=True)
    return await dispatch_command(db, user, node, body.backend, body.action, body.payload)


@router.get("/api/nodes/{node_id}/commands/{command_id}", response_model=CommandOut)
def get_command(
    node_id: str,
    command_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_session),
) -> CommandOut:
    auth.get_node_or_403(db, user, node_id, write=False)
    cmd = db.get(Command, command_id)
    if cmd is None or cmd.node_id != node_id:
        raise HTTPException(status_code=404, detail="no such command")
    return _command_out(cmd)
