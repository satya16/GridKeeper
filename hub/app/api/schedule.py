import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth
from ..audit import record_audit
from ..db import Node, User
from ..deps import get_db
from ..schemas import SchedulePolicy
from ..connections import connections

router = APIRouter(tags=["schedule"])


async def _push_schedule(node_id: str, policy: SchedulePolicy) -> None:
    await connections.send_frame(node_id, {"type": "schedule", "policy": policy.model_dump()})


@router.put("/api/nodes/{node_id}/schedule", response_model=SchedulePolicy)
async def set_node_schedule(
    node_id: str,
    policy: SchedulePolicy,
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_session),
) -> SchedulePolicy:
    node = auth.get_node_or_403(db, user, node_id, write=True)

    node.schedule_json = json.dumps(policy.model_dump())
    db.commit()
    record_audit(db, user, "set_node_schedule", target=node.name, detail=policy.model_dump())

    if connections.is_online(node_id):
        await _push_schedule(node_id, policy)
    return policy


@router.post("/api/schedule/apply-all", response_model=list[str])
async def apply_schedule_to_all(
    policy: SchedulePolicy,
    db: Session = Depends(get_db),
    admin: User = Depends(auth.require_admin_user),
) -> list[str]:
    """Sets the same schedule policy on every currently-known node --
    the common case for a school lab of identical machines. Nodes that
    are offline right now still get it: it's persisted to their row and
    pushed the moment they next connect (see main.py's node_ws). Fleet-
    wide, so admin only."""
    nodes = db.query(Node).all()
    for node in nodes:
        node.schedule_json = json.dumps(policy.model_dump())
    db.commit()
    record_audit(db, admin, "apply_schedule_to_all", detail=policy.model_dump())

    for node in nodes:
        if connections.is_online(node.id):
            await _push_schedule(node.id, policy)
    return [a.id for a in nodes]


@router.post("/api/schedule/apply-group/{group}", response_model=list[str])
async def apply_schedule_to_group(
    group: str,
    policy: SchedulePolicy,
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_session),
) -> list[str]:
    """Same as apply-all, scoped to one group -- the motivating case is a
    deployment with multiple physically distinct rooms that need different
    hours (e.g. a library open later than classrooms). An unknown or empty
    group simply matches no nodes rather than erroring, same as apply-all
    on an empty fleet. group_manager only, scoped to their own group."""
    auth.require_group_access(user, group)
    nodes = db.query(Node).filter(Node.group == group).all()
    for node in nodes:
        node.schedule_json = json.dumps(policy.model_dump())
    db.commit()
    record_audit(db, user, "apply_schedule_to_group", target=group, detail=policy.model_dump())

    for node in nodes:
        if connections.is_online(node.id):
            await _push_schedule(node.id, policy)
    return [a.id for a in nodes]
