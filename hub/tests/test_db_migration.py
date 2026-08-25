"""Unit tests for the hand-written, idempotent migrations in app/db.py
(see _migrate_credential_keys/_migrate_pairing_tokens) -- this project has
no migration tooling (see _docs/knowledge-graph/data-model.md), so these
are the only thing standing between an existing deployed grid.db (with
saved BOINC credentials already in it) and data loss when the
CredentialKey/PairingToken schema generalizes. Runs against a throwaway
SQLite file of its own, not the shared app.db engine the rest of the
suite uses (that one's schema is already current by the time any test
runs), so this is a true "old schema in, new schema + preserved data out"
check.
"""

import os
import tempfile

from sqlalchemy import create_engine, inspect, text

from app.db import _migrate_credential_keys


def _fresh_engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    return engine, path


def test_migrate_credential_keys_backfills_existing_row_and_preserves_secret():
    engine, path = _fresh_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE credential_keys ("
                    "id VARCHAR PRIMARY KEY, name VARCHAR, project_url VARCHAR, "
                    "encrypted_account_key VARCHAR, created_at DATETIME, last_used_at DATETIME)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO credential_keys (id, name, project_url, encrypted_account_key, created_at) "
                    "VALUES ('id-1', 'wcg-lab', 'https://www.worldcommunitygrid.org/', 'gAAAA-fake-ciphertext', '2026-08-19T00:00:00')"
                )
            )

        with engine.begin() as conn:
            _migrate_credential_keys(conn)

        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT backend, static_fields_json, encrypted_secret FROM credential_keys WHERE id = 'id-1'")
            ).one()
        assert row[0] == "boinc"
        assert row[1] == '{"project_url": "https://www.worldcommunitygrid.org/"}'
        assert row[2] == "gAAAA-fake-ciphertext"

        # Old columns are left in place, never dropped (see the function's docstring).
        columns = {c["name"] for c in inspect(engine).get_columns("credential_keys")}
        assert {"project_url", "encrypted_account_key", "backend", "static_fields_json", "encrypted_secret"} <= columns
    finally:
        engine.dispose()
        os.unlink(path)


def test_migrate_credential_keys_is_idempotent():
    engine, path = _fresh_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE credential_keys ("
                    "id VARCHAR PRIMARY KEY, name VARCHAR, project_url VARCHAR, "
                    "encrypted_account_key VARCHAR, created_at DATETIME, last_used_at DATETIME)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO credential_keys (id, name, project_url, encrypted_account_key, created_at) "
                    "VALUES ('id-1', 'wcg-lab', 'https://example.org/', 'secret', '2026-08-19T00:00:00')"
                )
            )
        with engine.begin() as conn:
            _migrate_credential_keys(conn)
        with engine.begin() as conn:
            _migrate_credential_keys(conn)  # must not raise or duplicate/corrupt data

        with engine.begin() as conn:
            rows = conn.execute(text("SELECT backend FROM credential_keys")).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "boinc"
    finally:
        engine.dispose()
        os.unlink(path)


def test_migrate_credential_keys_noop_on_already_current_schema():
    engine, path = _fresh_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE credential_keys ("
                    "id VARCHAR PRIMARY KEY, name VARCHAR, backend VARCHAR, "
                    "static_fields_json VARCHAR, encrypted_secret VARCHAR, created_at DATETIME, last_used_at DATETIME)"
                )
            )
        with engine.begin() as conn:
            _migrate_credential_keys(conn)  # should return immediately, no error

        columns = {c["name"] for c in inspect(engine).get_columns("credential_keys")}
        assert "project_url" not in columns  # never added when not migrating from the old shape
    finally:
        engine.dispose()
        os.unlink(path)
