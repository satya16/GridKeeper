import os
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DB_PATH = os.environ.get("GRIDKEEPER_DB", os.path.join(os.path.dirname(__file__), "..", "grid.db"))
DB_URL = f"sqlite:///{os.path.abspath(DB_PATH)}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Worker(Base):
    __tablename__ = "workers"

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
    group: Mapped[str] = mapped_column(default="")  # inherited by the worker that redeems this token
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(default=None)
    used_by_worker_id: Mapped[str | None] = mapped_column(default=None)


class CredentialKey(Base):
    """A saved BOINC project account key, so an admin enrolling many
    machines with the same institutional account doesn't have to paste the
    raw key into each worker's attach form separately. encrypted_account_key
    is Fernet-encrypted at rest (see crypto.py) -- the plaintext key only
    ever exists in memory, decrypted just before dispatching an
    attach_project command."""

    __tablename__ = "credential_keys"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    project_url: Mapped[str]
    encrypted_account_key: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)


class Command(Base):
    __tablename__ = "commands"

    id: Mapped[str] = mapped_column(primary_key=True)
    worker_id: Mapped[str]
    backend: Mapped[str]
    action: Mapped[str]
    payload_json: Mapped[str] = mapped_column(default="{}")
    status: Mapped[str] = mapped_column(default="pending")  # pending|sent|ok|error|timeout
    result_json: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)


def init_db() -> None:
    Base.metadata.create_all(engine)
