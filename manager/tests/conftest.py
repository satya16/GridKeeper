import os
import tempfile

# Must happen before any `app.*` import, since app/db.py reads these at
# import time to build its SQLAlchemy engine.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["GRIDKEEPER_DB"] = _db_path
os.environ["GRIDKEEPER_ADMIN_PASSWORD"] = "test-admin-password"

import pytest
from fastapi.testclient import TestClient

from app import discovery as discovery_module
from app.db import Base, engine, init_db
from app.main import app

ADMIN_PASSWORD = "test-admin-password"
AUTH = ("admin", ADMIN_PASSWORD)


async def _noop() -> None:
    return None


# Real mDNS browsing has no place in a unit test -- it's slow, needs a
# real network, and is already covered by manual/integration testing.
discovery_module.registry.start = _noop
discovery_module.registry.stop = _noop


@pytest.fixture()
def client():
    init_db()
    with TestClient(app) as c:
        yield c
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
