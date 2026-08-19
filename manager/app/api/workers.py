import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth
from ..db import Worker, Command, utcnow
from ..deps import get_db
from ..schemas import WorkerOut, CommandOut, CommandRequest, WorkerGroupUpdate
from ..ws_manager import manager

router = APIRouter(tags=["workers"])

COMMAND_TIMEOUT_SECONDS = 15.0

# Payload fields that are long-lived credentials, not one-time tokens --
# must never land in the commands table (or its audit-log GET response) in
# plaintext. Keyed by (backend, action). The *unredacted* payload is still
# what actually gets sent to the worker, which needs the real value; only
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


def _worker_out(worker: Worker) -> WorkerOut:
    return WorkerOut(
        id=worker.id,
        name=worker.name,
        os_name=worker.os_name,
        backends=[b for b in worker.backends.split(",") if b],
        group=worker.group,
        online=manager.is_online(worker.id),
        last_seen_at=worker.last_seen_at.isoformat() if worker.last_seen_at else None,
        status=json.loads(worker.last_status_json) if worker.last_status_json else None,
        schedule=json.loads(worker.schedule_json) if worker.schedule_json else None,
    )


def _command_out(cmd: Command) -> CommandOut:
    return CommandOut(
        id=cmd.id,
        worker_id=cmd.worker_id,
        backend=cmd.backend,
        action=cmd.action,
        payload=json.loads(cmd.payload_json),
        status=cmd.status,
        result=json.loads(cmd.result_json) if cmd.result_json else None,
        created_at=cmd.created_at.isoformat(),
        completed_at=cmd.completed_at.isoformat() if cmd.completed_at else None,
    )


@router.get("/api/workers", response_model=list[WorkerOut])
def list_workers(db: Session = Depends(get_db), _admin: str = Depends(auth.require_admin)) -> list[WorkerOut]:
    workers = db.query(Worker).order_by(Worker.name).all()
    return [_worker_out(a) for a in workers]


@router.get("/api/workers/{worker_id}", response_model=WorkerOut)
def get_worker(worker_id: str, db: Session = Depends(get_db), _admin: str = Depends(auth.require_admin)) -> WorkerOut:
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="no such worker")
    return _worker_out(worker)


@router.get("/api/groups", response_model=list[str])
def list_groups(db: Session = Depends(get_db), _admin: str = Depends(auth.require_admin)) -> list[str]:
    """Distinct, non-empty group names currently in use -- lets the
    dashboard offer a picker instead of everyone free-typing "Lab 1" vs
    "lab1" vs "Lab One" for the same room."""
    rows = db.query(Worker.group).filter(Worker.group != "").distinct().order_by(Worker.group).all()
    return [r[0] for r in rows]


@router.put("/api/workers/{worker_id}/group", response_model=WorkerGroupUpdate)
def set_worker_group(
    worker_id: str,
    body: WorkerGroupUpdate,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> WorkerGroupUpdate:
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="no such worker")
    worker.group = body.group
    db.commit()
    return body


async def dispatch_command(db: Session, worker: Worker, backend: str, action: str, payload: dict) -> CommandOut:
    """Shared by the direct issue_command route below and
    credentials.py's apply endpoint, which dispatches the same
    attach_project command but with a saved (decrypted) account key
    instead of one typed inline in the dashboard's attach form."""
    if not manager.is_online(worker.id):
        raise HTTPException(status_code=409, detail=f"worker '{worker.name}' is not connected right now")

    command_id = str(uuid.uuid4())
    cmd = Command(
        id=command_id,
        worker_id=worker.id,
        backend=backend,
        action=action,
        payload_json=json.dumps(_redact_payload(backend, action, payload)),
        status="sent",
    )
    db.add(cmd)
    db.commit()

    future = manager.register_pending(command_id)
    sent = await manager.send_frame(
        worker.id,
        {
            "type": "command",
            "command_id": command_id,
            "backend": backend,
            "action": action,
            "payload": payload,
        },
    )
    if not sent:
        manager.drop_pending(command_id)
        cmd.status = "error"
        cmd.result_json = json.dumps({"error": "worker disconnected before command could be sent"})
        cmd.completed_at = utcnow()
        db.commit()
        return _command_out(cmd)

    try:
        result = await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT_SECONDS)
        cmd.status = result.get("status", "ok")
        cmd.result_json = json.dumps(result.get("result", {}))
    except TimeoutError:
        manager.drop_pending(command_id)
        cmd.status = "timeout"
        cmd.result_json = json.dumps({"error": f"no response from worker within {COMMAND_TIMEOUT_SECONDS}s"})
    cmd.completed_at = utcnow()
    db.commit()
    return _command_out(cmd)


@router.post("/api/workers/{worker_id}/commands", response_model=CommandOut)
async def issue_command(
    worker_id: str,
    body: CommandRequest,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> CommandOut:
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="no such worker")
    return await dispatch_command(db, worker, body.backend, body.action, body.payload)


@router.get("/api/workers/{worker_id}/commands/{command_id}", response_model=CommandOut)
def get_command(
    worker_id: str,
    command_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> CommandOut:
    cmd = db.get(Command, command_id)
    if cmd is None or cmd.worker_id != worker_id:
        raise HTTPException(status_code=404, detail="no such command")
    return _command_out(cmd)
