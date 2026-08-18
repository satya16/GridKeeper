import uuid

from sqlalchemy.orm import Session

from . import auth
from .db import Worker


def create_worker(db: Session, name: str, os_name: str, backends: list[str], group: str = "") -> tuple[str, str]:
    """Creates a Worker row and returns (worker_id, bearer_token). Caller is
    responsible for checking the name isn't already taken and for
    committing/rolling back the session."""
    worker_id = str(uuid.uuid4())
    bearer_token = auth.new_token()
    db.add(
        Worker(
            id=worker_id,
            name=name,
            token_hash=auth.hash_token(bearer_token),
            os_name=os_name,
            backends=",".join(backends),
            group=group,
        )
    )
    return worker_id, bearer_token
