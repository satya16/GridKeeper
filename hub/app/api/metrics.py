from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth
from ..db import User
from ..deps import get_db
from ..metrics_store import store
from .nodes import scoped_nodes_query

router = APIRouter(tags=["metrics"])


@router.get("/api/metrics")
def get_metrics(db: Session = Depends(get_db), user: User = Depends(auth.require_session)) -> dict:
    """Per-node rolling window of {t, cpu_percent, ram_percent,
    temperature_c} points, keyed by node id, for the dashboard's live
    graphs. Nodes with no metrics recorded yet are simply absent. Scoped
    the same way the node list is -- names come only from nodes the
    requesting user can see, which also acts as the filter: a node id
    absent from `names` is simply dropped from the response."""
    names = {a.id: a.name for a in scoped_nodes_query(db, user).all()}
    return {
        node_id: {"name": names[node_id], "points": points}
        for node_id, points in store.all_history().items()
        if node_id in names
    }
