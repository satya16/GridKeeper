from typing import Any, Literal

from pydantic import BaseModel


class PairingTokenCreate(BaseModel):
    label: str = ""
    group: str = ""


class PairingTokenOut(BaseModel):
    token: str
    label: str
    group: str


class EnrollRequest(BaseModel):
    pairing_token: str
    name: str
    os_name: str = "unknown"
    backends: list[str] = []


class EnrollResponse(BaseModel):
    worker_id: str
    bearer_token: str


class SchedulePolicy(BaseModel):
    """Hours/idle restrictions on when a machine should be donating cycles.
    BOINC enforces this itself once pushed as BOINC preferences (it has its
    own robust idle/hour engine); Folding@home has no such native
    mechanism, so the worker enforces it directly for FAH -- see
    worker/grid_worker/schedule.py."""

    enabled: bool = False
    restrict_hours: bool = False
    active_start_hour: int = 22
    active_end_hour: int = 6
    only_when_idle: bool = False
    idle_threshold_minutes: int = 3


class WorkerOut(BaseModel):
    id: str
    name: str
    os_name: str
    backends: list[str]
    group: str
    online: bool
    last_seen_at: str | None
    status: dict[str, Any] | None
    schedule: dict[str, Any] | None


class WorkerGroupUpdate(BaseModel):
    group: str = ""


class CommandRequest(BaseModel):
    backend: Literal["boinc", "fah"]
    action: str
    payload: dict[str, Any] = {}


class DiscoveredWorkerOut(BaseModel):
    discovery_id: str
    hostname: str
    backends: list[str]
    addresses: list[str]
    port: int


class DiscoveryPairRequest(BaseModel):
    code: str
    name: str = ""


class DiscoveryPairResponse(BaseModel):
    worker_id: str
    name: str


class CredentialCreate(BaseModel):
    name: str
    project_url: str
    account_key: str


class CredentialOut(BaseModel):
    id: str
    name: str
    project_url: str
    created_at: str
    last_used_at: str | None


class CredentialApplyRequest(BaseModel):
    worker_id: str


class CommandOut(BaseModel):
    id: str
    worker_id: str
    backend: str
    action: str
    payload: dict[str, Any]
    status: str
    result: dict[str, Any] | None
    created_at: str
    completed_at: str | None


# --- Wire protocol between worker <-> manager over the WebSocket ---
# Every frame is a small JSON envelope: {"type": ..., ...}
#
# worker -> manager:
#   {"type": "status", "backends": {"boinc": {...}, "fah": {...}}}
#   {"type": "command_result", "command_id": "...", "status": "ok"|"error", "result": {...}}
#
# manager -> worker:
#   {"type": "command", "command_id": "...", "backend": "boinc", "action": "...", "payload": {...}}
#   {"type": "schedule", "policy": {...SchedulePolicy fields...}}
