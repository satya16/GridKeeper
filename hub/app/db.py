import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DB_PATH = os.environ.get("GRIDKEEPER_DB", os.path.join(os.path.dirname(__file__), "..", "grid.db"))
DB_URL = f"sqlite:///{os.path.abspath(DB_PATH)}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    token_hash: Mapped[str]
    os_name: Mapped[str] = mapped_column(default="unknown")
    backends: Mapped[str] = mapped_column(default="")  # comma-separated: boinc,fah
    group: Mapped[str] = mapped_column(default="")  # e.g. "Lab 1", "Library" -- "" = ungrouped
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(default=None)
    last_status_json: Mapped[str | None] = mapped_column(default=None)
    schedule_json: Mapped[str | None] = mapped_column(default=None)


class PairingToken(Base):
    __tablename__ = "pairing_tokens"

    token: Mapped[str] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(default="")
    group: Mapped[str] = mapped_column(default="")  # inherited by the node that redeems this token
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(default=None)
    used_by_node_id: Mapped[str | None] = mapped_column(default=None)


class CredentialKey(Base):
    """A saved backend credential (e.g. a BOINC project account key), so an
    admin enrolling many machines with the same institutional account
    doesn't have to paste the raw key into each node's attach form
    separately. `backend` + the backend's declared CREDENTIAL_ACTION (see
    node/grid_node/backends/base.py, BackendCapability below) determine
    which command this gets applied via and which field is the secret;
    `static_fields_json` holds the non-secret fields that command also
    needs (e.g. BOINC's project_url). encrypted_secret is Fernet-encrypted
    at rest (see crypto.py) -- the plaintext secret only ever exists in
    memory, decrypted just before dispatching the credential's command."""

    __tablename__ = "credential_keys"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    backend: Mapped[str] = mapped_column(default="boinc")
    static_fields_json: Mapped[str] = mapped_column(default="{}")
    encrypted_secret: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)


class BackendCapability(Base):
    """The hub's registry of every backend it's ever seen a node report
    (see daemon.py::collect_capabilities / backends/base.py::capabilities).
    Populated from the `capabilities` block of each node's status frame
    (main.py's node_ws) -- last-writer-wins, since capability shape is a
    property of the backend package/version, not of any one machine.
    Exists independent of any currently-paired node so a credential for a
    backend can be created even if that backend's only node is offline."""

    __tablename__ = "backend_capabilities"

    name: Mapped[str] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(default="")
    sensitive_fields_json: Mapped[str] = mapped_column(default="{}")
    credential_action_json: Mapped[str | None] = mapped_column(default=None)
    actions_json: Mapped[str] = mapped_column(default="[]")
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class User(Base):
    """An admin-managed account, replacing the earlier single shared
    GRIDKEEPER_ADMIN_PASSWORD model. `scope` is a comma-separated list,
    same lightweight convention as Node.backends -- group names for
    role="group_manager", node ids for role="machine_manager", unused
    (empty) for "admin"/"viewer"."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    role: Mapped[str]  # "admin" | "group_manager" | "machine_manager" | "viewer"
    scope: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AuditLogEntry(Base):
    """Durable record of who did what -- see audit.py::record_audit().
    username is denormalized (not just user_id) so a log entry still
    reads correctly after the user who made it is deleted."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str]
    username: Mapped[str]
    action: Mapped[str]
    target: Mapped[str] = mapped_column(default="")
    detail_json: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Command(Base):
    __tablename__ = "commands"

    id: Mapped[str] = mapped_column(primary_key=True)
    node_id: Mapped[str]
    backend: Mapped[str]
    action: Mapped[str]
    payload_json: Mapped[str] = mapped_column(default="{}")
    status: Mapped[str] = mapped_column(default="pending")  # pending|sent|ok|error|timeout
    result_json: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)


def _add_column_if_missing(conn, table: str, column: str, ddl_type: str, default_sql: str | None = None) -> None:
    existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
    if column in existing:
        return
    default_clause = f" DEFAULT {default_sql}" if default_sql else ""
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}{default_clause}"))


def _migrate_credential_keys(conn) -> None:
    """Generalizes CredentialKey from BOINC-specific {project_url,
    encrypted_account_key} to backend-agnostic {backend, static_fields_json,
    encrypted_secret} (see BackendCapability/CredentialKey docstrings). No
    migration tooling exists in this project (see _docs/knowledge-graph/
    data-model.md) -- this is a hand-written, idempotent, additive-only
    migration: existing columns are never dropped (SQLite DROP COLUMN
    support varies by version), old data is copied forward into the new
    shape so a saved credential from before this change keeps working."""
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(credential_keys)"))}
    if "backend" in columns:
        return  # already migrated
    _add_column_if_missing(conn, "credential_keys", "backend", "VARCHAR", "'boinc'")
    _add_column_if_missing(conn, "credential_keys", "static_fields_json", "VARCHAR", "'{}'")
    _add_column_if_missing(conn, "credential_keys", "encrypted_secret", "VARCHAR", "''")
    if "project_url" in columns and "encrypted_account_key" in columns:
        import json as _json

        rows = conn.execute(text("SELECT id, project_url, encrypted_account_key FROM credential_keys")).fetchall()
        for row_id, project_url, encrypted_account_key in rows:
            conn.execute(
                text(
                    "UPDATE credential_keys SET static_fields_json = :fields, encrypted_secret = :secret "
                    "WHERE id = :id"
                ),
                {
                    "fields": _json.dumps({"project_url": project_url} if project_url else {}),
                    "secret": encrypted_account_key or "",
                    "id": row_id,
                },
            )


def init_db() -> None:
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    with engine.begin() as conn:
        if "credential_keys" in inspector.get_table_names():
            _migrate_credential_keys(conn)
