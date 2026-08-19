from typing import Any, Literal

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResult(BaseModel):
    ok: bool
    role: str | None = None


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    scope: str
    created_at: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: Literal["admin", "group_manager", "machine_manager", "viewer"]
    scope: str = ""


class UserUpdate(BaseModel):
    role: Literal["admin", "group_manager", "machine_manager", "viewer"] | None = None
    scope: str | None = None
    password: str | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class AuditLogEntryOut(BaseModel):
    id: str
    username: str
    action: str
    target: str
    detail: dict[str, Any] | None
    created_at: str


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
    node_id: str
    bearer_token: str


class SchedulePolicy(BaseModel):
    """Hours/idle restrictions on when a machine should be donating cycles.
    BOINC enforces this itself once pushed as BOINC preferences (it has its
    own robust idle/hour engine); Folding@home has no such native
    mechanism, so the node enforces it directly for FAH -- see
    node/grid_node/schedule.py."""

    enabled: bool = False
    restrict_hours: bool = False
    active_start_hour: int = 22
    active_end_hour: int = 6
    only_when_idle: bool = False
    idle_threshold_minutes: int = 3


class NodeOut(BaseModel):
    id: str
    name: str
    os_name: str
    backends: list[str]
    group: str
    online: bool
    last_seen_at: str | None
    status: dict[str, Any] | None
    schedule: dict[str, Any] | None


class NodeGroupUpdate(BaseModel):
    group: str = ""


class CommandRequest(BaseModel):
    backend: Literal["boinc", "fah"]
    action: str
    payload: dict[str, Any] = {}


class DiscoveredNodeOut(BaseModel):
    discovery_id: str
    hostname: str
    backends: list[str]
    addresses: list[str]
    port: int


class DiscoveryPairRequest(BaseModel):
    code: str
    name: str = ""
    group: str = ""


class DiscoveryPairResponse(BaseModel):
    node_id: str
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
    node_id: str


class CredentialApplyResult(BaseModel):
    node_id: str
    node_name: str
    online: bool
    status: str
    result: dict[str, Any] | None


class CommandOut(BaseModel):
    id: str
    node_id: str
    backend: str
    action: str
    payload: dict[str, Any]
    status: str
    result: dict[str, Any] | None
    created_at: str
    completed_at: str | None


# --- Wire protocol between node <-> hub over the WebSocket ---
# Every frame is a small JSON envelope: {"type": ..., ...}
#
# node -> hub:
#   {"type": "status", "backends": {"boinc": {...}, "fah": {...}}}
#   {"type": "command_result", "command_id": "...", "status": "ok"|"error", "result": {...}}
#
# hub -> node:
#   {"type": "command", "command_id": "...", "backend": "boinc", "action": "...", "payload": {...}}
#   {"type": "schedule", "policy": {...SchedulePolicy fields...}}
