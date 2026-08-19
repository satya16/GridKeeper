import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, crypto
from ..db import CredentialKey, Worker, utcnow
from ..deps import get_db
from ..schemas import CommandOut, CredentialApplyRequest, CredentialApplyResult, CredentialCreate, CredentialOut
from ..ws_manager import manager
from .workers import dispatch_command

router = APIRouter(tags=["credentials"])


def _credential_out(cred: CredentialKey) -> CredentialOut:
    return CredentialOut(
        id=cred.id,
        name=cred.name,
        project_url=cred.project_url,
        created_at=cred.created_at.isoformat(),
        last_used_at=cred.last_used_at.isoformat() if cred.last_used_at else None,
    )


@router.post("/api/credentials", response_model=CredentialOut)
def create_credential(
    body: CredentialCreate,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> CredentialOut:
    if db.query(CredentialKey).filter(CredentialKey.name == body.name).first() is not None:
        raise HTTPException(status_code=409, detail=f"a credential named '{body.name}' already exists")
    try:
        encrypted = crypto.encrypt(body.account_key)
    except crypto.SecretKeyNotConfigured as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    cred = CredentialKey(
        id=str(uuid.uuid4()),
        name=body.name,
        project_url=body.project_url,
        encrypted_account_key=encrypted,
    )
    db.add(cred)
    db.commit()
    return _credential_out(cred)


@router.get("/api/credentials", response_model=list[CredentialOut])
def list_credentials(db: Session = Depends(get_db), _admin: str = Depends(auth.require_admin)) -> list[CredentialOut]:
    return [_credential_out(c) for c in db.query(CredentialKey).order_by(CredentialKey.name).all()]


@router.delete("/api/credentials/{credential_id}", status_code=204)
def delete_credential(
    credential_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> None:
    cred = db.get(CredentialKey, credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="no such credential")
    db.delete(cred)
    db.commit()


@router.post("/api/credentials/{credential_id}/apply", response_model=CommandOut)
async def apply_credential(
    credential_id: str,
    body: CredentialApplyRequest,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> CommandOut:
    """Single-worker apply -- attaches the saved key's project to one
    worker. Fleet-wide/group apply is a deliberate follow-up, not this
    endpoint's job (see knowledge-graph/credentials.md)."""
    cred = db.get(CredentialKey, credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="no such credential")
    worker = db.get(Worker, body.worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="no such worker")

    try:
        account_key = crypto.decrypt(cred.encrypted_account_key)
    except crypto.SecretKeyNotConfigured as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    result = await dispatch_command(
        db,
        worker,
        "boinc",
        "attach_project",
        {"project_url": cred.project_url, "account_key": account_key},
    )
    cred.last_used_at = utcnow()
    db.commit()
    return result


async def _apply_to_workers(db: Session, cred: CredentialKey, workers: list[Worker]) -> list[CredentialApplyResult]:
    """Bulk fan-out, one attach_project dispatch per online worker.

    Unlike a schedule policy (persisted state that a worker picks up the
    next time it connects, see schedule.py's apply-group/apply-all),
    attach_project is a one-shot command -- a worker that's offline right
    now simply can't receive it, there's no "queue it for later" here. So
    offline workers are reported as skipped rather than causing the whole
    batch to fail, matching the tolerant style of apply-group/apply-all
    for schedules rather than the single-worker apply endpoint's strict
    404/409 (that one is a deliberate single-target action, this one
    expects a mixed-availability fleet)."""
    online_workers = [w for w in workers if manager.is_online(w.id)]
    account_key = None
    if online_workers:
        try:
            account_key = crypto.decrypt(cred.encrypted_account_key)
        except crypto.SecretKeyNotConfigured as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    results: list[CredentialApplyResult] = []
    for worker in workers:
        if worker not in online_workers:
            results.append(
                CredentialApplyResult(worker_id=worker.id, worker_name=worker.name, online=False, status="skipped", result=None)
            )
            continue
        cmd = await dispatch_command(
            db, worker, "boinc", "attach_project", {"project_url": cred.project_url, "account_key": account_key}
        )
        results.append(
            CredentialApplyResult(worker_id=worker.id, worker_name=worker.name, online=True, status=cmd.status, result=cmd.result)
        )

    if online_workers:
        cred.last_used_at = utcnow()
        db.commit()
    return results


@router.post("/api/credentials/{credential_id}/apply-group/{group}", response_model=list[CredentialApplyResult])
async def apply_credential_to_group(
    credential_id: str,
    group: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> list[CredentialApplyResult]:
    """An unknown or empty group simply matches no workers rather than
    erroring, same as schedule.py's apply-group."""
    cred = db.get(CredentialKey, credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="no such credential")
    workers = db.query(Worker).filter(Worker.group == group).all()
    return await _apply_to_workers(db, cred, workers)


@router.post("/api/credentials/{credential_id}/apply-all", response_model=list[CredentialApplyResult])
async def apply_credential_to_all(
    credential_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> list[CredentialApplyResult]:
    cred = db.get(CredentialKey, credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="no such credential")
    workers = db.query(Worker).all()
    return await _apply_to_workers(db, cred, workers)
