from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth
from ..db import Worker, PairingToken, utcnow
from ..deps import get_db
from ..enrollment import create_worker
from ..schemas import EnrollRequest, EnrollResponse, PairingTokenCreate, PairingTokenOut

router = APIRouter(tags=["pairing"])


@router.post("/api/pairing-tokens", response_model=PairingTokenOut)
def create_pairing_token(
    body: PairingTokenCreate,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> PairingTokenOut:
    """A token's `group`, if set, carries over to whichever worker redeems
    it (see enroll() below) -- so an admin onboarding a whole lab can mint
    one token per room and every machine paired with it lands in that
    group automatically, no per-machine follow-up edit needed."""
    token = auth.new_pairing_token()
    db.add(PairingToken(token=token, label=body.label, group=body.group))
    db.commit()
    return PairingTokenOut(token=token, label=body.label, group=body.group)


@router.post("/api/enroll", response_model=EnrollResponse)
def enroll(body: EnrollRequest, db: Session = Depends(get_db)) -> EnrollResponse:
    """Called by a fresh grid-worker with the one-time pairing token an admin
    generated on the dashboard. Exchanges it for a long-lived bearer token."""
    pt = db.get(PairingToken, body.pairing_token)
    if pt is None or pt.used_at is not None:
        raise HTTPException(status_code=400, detail="invalid or already-used pairing token")

    if db.query(Worker).filter(Worker.name == body.name).one_or_none() is not None:
        raise HTTPException(status_code=400, detail=f"a worker named '{body.name}' is already enrolled")

    worker_id, bearer_token = create_worker(
        db, name=body.name, os_name=body.os_name, backends=body.backends, group=pt.group
    )

    pt.used_at = utcnow()
    pt.used_by_worker_id = worker_id
    db.commit()

    return EnrollResponse(worker_id=worker_id, bearer_token=bearer_token)
