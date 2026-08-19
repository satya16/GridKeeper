import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import auth
from ..db import Node
from ..deps import get_db
from ..discovery import registry
from ..enrollment import create_node
from ..schemas import DiscoveredNodeOut, DiscoveryPairRequest, DiscoveryPairResponse

router = APIRouter(tags=["discovery"])

PAIR_HTTP_TIMEOUT_SECONDS = 10.0


def _public_hub_url(request: Request) -> str:
    """The URL a newly-paired node should use to reach this hub over
    the LAN. Usually the same host the admin's browser is hitting, but can
    be overridden if the dashboard is reached via a different address
    (e.g. a reverse proxy) than the one nodes should connect back to."""
    override = os.environ.get("GRIDKEEPER_PUBLIC_URL")
    return override.rstrip("/") if override else str(request.base_url).rstrip("/")


@router.get("/api/discovery", response_model=list[DiscoveredNodeOut])
def list_discovered(_admin: str = Depends(auth.require_session)) -> list[DiscoveredNodeOut]:
    return [DiscoveredNodeOut(**w) for w in registry.list_nodes()]


@router.post("/api/discovery/{discovery_id}/pair", response_model=DiscoveryPairResponse)
async def pair_discovered(
    discovery_id: str,
    body: DiscoveryPairRequest,
    request: Request,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_session),
) -> DiscoveryPairResponse:
    node = registry.get(discovery_id)
    if node is None:
        raise HTTPException(status_code=404, detail="node is no longer visible on the network -- try again")

    base_url = f"http://{node['addresses'][0]}:{node['port']}"

    async with httpx.AsyncClient(timeout=PAIR_HTTP_TIMEOUT_SECONDS) as client:
        try:
            verify_resp = await client.post(f"{base_url}/pair", json={"code": body.code})
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"could not reach node at {base_url}: {e}") from e

    if verify_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="pairing code was rejected by the node")

    verify_data = verify_resp.json()
    name = body.name or verify_data.get("name") or node["hostname"]

    if db.query(Node).filter(Node.name == name).one_or_none() is not None:
        raise HTTPException(status_code=400, detail=f"a node named '{name}' is already enrolled")

    node_id, bearer_token = create_node(
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
                    "node_id": node_id,
                    "bearer_token": bearer_token,
                    "hub_url": _public_hub_url(request),
                    "name": name,
                },
            )
        except httpx.HTTPError as e:
            db.rollback()
            raise HTTPException(status_code=502, detail=f"node verified the code but became unreachable: {e}") from e

    if complete_resp.status_code != 200:
        db.rollback()
        raise HTTPException(status_code=500, detail="node accepted the code but rejected the credential handoff")

    db.commit()
    return DiscoveryPairResponse(node_id=node_id, name=name)
