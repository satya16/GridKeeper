import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth
from ..db import Worker
from ..deps import get_db
from ..schemas import SchedulePolicy
from ..ws_manager import manager

router = APIRouter(tags=["schedule"])


async def _push_schedule(worker_id: str, policy: SchedulePolicy) -> None:
    await manager.send_frame(worker_id, {"type": "schedule", "policy": policy.model_dump()})


@router.put("/api/workers/{worker_id}/schedule", response_model=SchedulePolicy)
async def set_worker_schedule(
    worker_id: str,
    policy: SchedulePolicy,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> SchedulePolicy:
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="no such worker")

    worker.schedule_json = json.dumps(policy.model_dump())
    db.commit()

    if manager.is_online(worker_id):
        await _push_schedule(worker_id, policy)
    return policy


@router.post("/api/schedule/apply-all", response_model=list[str])
async def apply_schedule_to_all(
    policy: SchedulePolicy,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> list[str]:
    """Sets the same schedule policy on every currently-known worker --
    the common case for a school lab of identical machines. Workers that
    are offline right now still get it: it's persisted to their row and
    pushed the moment they next connect (see main.py's worker_ws)."""
    workers = db.query(Worker).all()
    for worker in workers:
        worker.schedule_json = json.dumps(policy.model_dump())
    db.commit()

    for worker in workers:
        if manager.is_online(worker.id):
            await _push_schedule(worker.id, policy)
    return [a.id for a in workers]


@router.post("/api/schedule/apply-group/{group}", response_model=list[str])
async def apply_schedule_to_group(
    group: str,
    policy: SchedulePolicy,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> list[str]:
    """Same as apply-all, scoped to one group -- the motivating case is a
    deployment with multiple physically distinct rooms that need different
    hours (e.g. a library open later than classrooms). An unknown or empty
    group simply matches no workers rather than erroring, same as apply-all
    on an empty fleet."""
    workers = db.query(Worker).filter(Worker.group == group).all()
    for worker in workers:
        worker.schedule_json = json.dumps(policy.model_dump())
    db.commit()

    for worker in workers:
        if manager.is_online(worker.id):
            await _push_schedule(worker.id, policy)
    return [a.id for a in workers]
