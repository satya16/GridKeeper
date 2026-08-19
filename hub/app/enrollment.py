import uuid

from sqlalchemy.orm import Session

from . import auth
from .db import Node


def create_node(db: Session, name: str, os_name: str, backends: list[str], group: str = "") -> tuple[str, str]:
    """Creates a Node row and returns (node_id, bearer_token). Caller is
    responsible for checking the name isn't already taken and for
    committing/rolling back the session."""
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
        )
    )
    return node_id, bearer_token
