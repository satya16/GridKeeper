import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import auth
from ..audit import record_audit
from ..db import Node, User
from ..deps import get_db
from ..discovery import registry
from ..enrollment import create_node
from ..schemas import (
    DiscoveredNodeOut,
    DiscoveryPairBatchItemResult,
    DiscoveryPairBatchRequest,
    DiscoveryPairRequest,
    DiscoveryPairResponse,
)

router = APIRouter(tags=["discovery"])

PAIR_HTTP_TIMEOUT_SECONDS = 10.0


def _public_hub_url(request: Request) -> str:
    """The URL a newly-paired node should use to reach this hub over
    the LAN. Usually the same host the admin's browser is hitting, but can
    be overridden if the dashboard is reached via a different address
    (e.g. a reverse proxy) than the one nodes should connect back to."""
    override = os.environ.get("GRIDKEEPER_PUBLIC_URL")
    return override.rstrip("/") if override else str(request.base_url).rstrip("/")


def _require_discovery_access(user: User) -> None:
    """Discovery/pairing is admin or group_manager only -- a
    machine_manager already has their one machine, nothing new to find,
    and a viewer can't write at all."""
    if user.role not in ("admin", "group_manager"):
        raise HTTPException(status_code=403, detail="admin or group manager only")


@router.get("/api/discovery", response_model=list[DiscoveredNodeOut])
def list_discovered(user: User = Depends(auth.require_session)) -> list[DiscoveredNodeOut]:
    _require_discovery_access(user)
    return [DiscoveredNodeOut(**w) for w in registry.list_nodes()]


async def _pair_one(
    db: Session,
    hub_url: str,
    discovery_id: str,
    code: str,
    name: str,
    group: str,
) -> tuple[str, str]:
    """The actual code-verify -> create_node -> credential-handoff
    handshake (see _docs/REQUIREMENTS.md section 6), factored out of
    pair_discovered so pair_batch below can run it once per selected
    machine without duplicating the httpx calls. Raises HTTPException on
    any failure -- the caller (pair_batch) catches it per-item so one bad
    code doesn't abort the rest of the batch; pair_discovered lets it
    propagate directly since it's already single-item."""
    node = registry.get(discovery_id)
    if node is None:
        raise HTTPException(status_code=404, detail="node is no longer visible on the network -- try again")

    base_url = f"http://{node['addresses'][0]}:{node['port']}"

    async with httpx.AsyncClient(timeout=PAIR_HTTP_TIMEOUT_SECONDS) as client:
        try:
            verify_resp = await client.post(f"{base_url}/pair", json={"code": code})
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"could not reach node at {base_url}: {e}") from e

    if verify_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="pairing code was rejected by the node")

    verify_data = verify_resp.json()
    resolved_name = name or verify_data.get("name") or node["hostname"]

    if db.query(Node).filter(Node.name == resolved_name).one_or_none() is not None:
        raise HTTPException(status_code=400, detail=f"a node named '{resolved_name}' is already enrolled")

    node_id, bearer_token = create_node(
        db,
        name=resolved_name,
        os_name=verify_data.get("os_name", "unknown"),
        backends=verify_data.get("backends", []),
        group=group,
    )

    async with httpx.AsyncClient(timeout=PAIR_HTTP_TIMEOUT_SECONDS) as client:
        try:
            complete_resp = await client.post(
                f"{base_url}/pair-complete",
                json={"node_id": node_id, "bearer_token": bearer_token, "hub_url": hub_url, "name": resolved_name},
            )
        except httpx.HTTPError as e:
            db.rollback()
            raise HTTPException(status_code=502, detail=f"node verified the code but became unreachable: {e}") from e

    if complete_resp.status_code != 200:
        db.rollback()
        raise HTTPException(status_code=500, detail="node accepted the code but rejected the credential handoff")

    db.commit()
    return node_id, resolved_name


@router.post("/api/discovery/{discovery_id}/pair", response_model=DiscoveryPairResponse)
async def pair_discovered(
    discovery_id: str,
    body: DiscoveryPairRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_session),
) -> DiscoveryPairResponse:
    _require_discovery_access(user)
    if user.role == "group_manager":
        # Forced into their own scope, same reasoning as pairing tokens:
        # a group_manager shouldn't be able to enroll a node into a group
        # they don't manage, or leave it group-less (unmanageable by them
        # afterward).
        auth.require_group_access(user, body.group)

    node_id, name = await _pair_one(db, _public_hub_url(request), discovery_id, body.code, body.name, body.group)
    record_audit(db, user, "pair_discovered_node", target=name, detail={"group": body.group})
    return DiscoveryPairResponse(node_id=node_id, name=name)


@router.post("/api/discovery/pair-batch", response_model=list[DiscoveryPairBatchItemResult])
async def pair_discovered_batch(
    body: DiscoveryPairBatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_session),
) -> list[DiscoveryPairBatchItemResult]:
    """B1: walk through several discovered-but-unpaired machines in one
    dashboard sitting instead of one open/fill/close dialog per machine --
    the main friction point onboarding a whole lab. Each item's code is
    still read off that physical machine's own screen (inherent to the
    security model, see _docs/REQUIREMENTS.md section 6.5); this just
    collapses the dashboard side of pairing N machines into one submit.
    Tolerant per-item, same as credentials.py's apply-group/apply-all: one
    wrong code doesn't abort the rest of the batch."""
    _require_discovery_access(user)
    if user.role == "group_manager":
        for pair in body.pairs:
            auth.require_group_access(user, pair.group)

    hub_url = _public_hub_url(request)
    results: list[DiscoveryPairBatchItemResult] = []
    for pair in body.pairs:
        try:
            node_id, name = await _pair_one(db, hub_url, pair.discovery_id, pair.code, pair.name, pair.group)
            record_audit(db, user, "pair_discovered_node", target=name, detail={"group": pair.group, "batch": True})
            results.append(DiscoveryPairBatchItemResult(discovery_id=pair.discovery_id, ok=True, node_id=node_id, name=name))
        except HTTPException as e:
            results.append(DiscoveryPairBatchItemResult(discovery_id=pair.discovery_id, ok=False, error=str(e.detail)))
    return results
