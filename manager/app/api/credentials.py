import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, crypto
from ..db import CredentialKey, Worker, utcnow
from ..deps import get_db
from ..schemas import CommandOut, CredentialApplyRequest, CredentialCreate, CredentialOut
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
