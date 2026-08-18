import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import auth
from ..db import Worker
from ..deps import get_db
from ..discovery import registry
from ..enrollment import create_worker
from ..schemas import DiscoveredWorkerOut, DiscoveryPairRequest, DiscoveryPairResponse

router = APIRouter(tags=["discovery"])

PAIR_HTTP_TIMEOUT_SECONDS = 10.0


def _public_manager_url(request: Request) -> str:
    """The URL a newly-paired worker should use to reach this manager over
    the LAN. Usually the same host the admin's browser is hitting, but can
    be overridden if the dashboard is reached via a different address
    (e.g. a reverse proxy) than the one workers should connect back to."""
    override = os.environ.get("GRID_MANAGER_PUBLIC_URL")
    return override.rstrip("/") if override else str(request.base_url).rstrip("/")


@router.get("/api/discovery", response_model=list[DiscoveredWorkerOut])
def list_discovered(_admin: str = Depends(auth.require_admin)) -> list[DiscoveredWorkerOut]:
    return [DiscoveredWorkerOut(**w) for w in registry.list_workers()]


@router.post("/api/discovery/{discovery_id}/pair", response_model=DiscoveryPairResponse)
async def pair_discovered(
    discovery_id: str,
    body: DiscoveryPairRequest,
    request: Request,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin),
) -> DiscoveryPairResponse:
    worker = registry.get(discovery_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="worker is no longer visible on the network -- try again")

    base_url = f"http://{worker['addresses'][0]}:{worker['port']}"

    async with httpx.AsyncClient(timeout=PAIR_HTTP_TIMEOUT_SECONDS) as client:
        try:
            verify_resp = await client.post(f"{base_url}/pair", json={"code": body.code})
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"could not reach worker at {base_url}: {e}") from e

    if verify_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="pairing code was rejected by the worker")

    verify_data = verify_resp.json()
    name = body.name or verify_data.get("name") or worker["hostname"]

    if db.query(Worker).filter(Worker.name == name).one_or_none() is not None:
        raise HTTPException(status_code=400, detail=f"a worker named '{name}' is already enrolled")

    worker_id, bearer_token = create_worker(
        db,
        name=name,
        os_name=verify_data.get("os_name", "unknown"),
        backends=verify_data.get("backends", []),
    )

    async with httpx.AsyncClient(timeout=PAIR_HTTP_TIMEOUT_SECONDS) as client:
        try:
            complete_resp = await client.post(
                f"{base_url}/pair-complete",
                json={
                    "worker_id": worker_id,
                    "bearer_token": bearer_token,
                    "manager_url": _public_manager_url(request),
                    "name": name,
                },
            )
        except httpx.HTTPError as e:
            db.rollback()
            raise HTTPException(status_code=502, detail=f"worker verified the code but became unreachable: {e}") from e

    if complete_resp.status_code != 200:
        db.rollback()
        raise HTTPException(status_code=500, detail="worker accepted the code but rejected the credential handoff")

    db.commit()
    return DiscoveryPairResponse(worker_id=worker_id, name=name)
