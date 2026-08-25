import uuid

from sqlalchemy.orm import Session

from . import auth
from .db import Node


def create_node(
    db: Session, name: str, os_name: str, backends: list[str], group: str = "", schedule_json: str | None = None
) -> tuple[str, str]:
    """Creates a Node row and returns (node_id, bearer_token). Caller is
    responsible for checking the name isn't already taken and for
    committing/rolling back the session. `schedule_json`, if given, seeds
    the node's schedule policy at creation time (see the pairing-token
    default-schedule flow in api/pairing.py) -- the node's very first
    WebSocket connect already sends whatever's in Node.schedule_json (see
    main.py's node_ws), so nothing further is needed to deliver it once the
    node actually shows up."""
    node_id = str(uuid.uuid4())
    bearer_token = auth.new_token()
    db.add(
        Node(
            id=node_id,
            name=name,
            token_hash=auth.hash_token(bearer_token),
            os_name=os_name,
            backends=",".join(backends),
            group=group,
            schedule_json=schedule_json,
        )
    )
    return node_id, bearer_token
