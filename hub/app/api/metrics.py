from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth
from ..db import Node
from ..deps import get_db
from ..metrics_store import store

router = APIRouter(tags=["metrics"])


@router.get("/api/metrics")
def get_metrics(db: Session = Depends(get_db), _admin: str = Depends(auth.require_admin)) -> dict:
    """Per-node rolling window of {t, cpu_percent, ram_percent,
    temperature_c} points, keyed by node id, for the dashboard's live
    graphs. Nodes with no metrics recorded yet are simply absent."""
    names = {a.id: a.name for a in db.query(Node).all()}
    return {
        node_id: {"name": names.get(node_id, node_id), "points": points}
        for node_id, points in store.all_history().items()
    }
