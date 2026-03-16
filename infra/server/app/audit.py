"""Audit trail — records every policy evaluation for traceability.

Every call to the webhook and evaluate endpoints writes an audit event to a
SQLite database.  This gives operators a searchable history of all policy
decisions with the inputs and outcomes that produced them.

The database path is read from config.AUDIT_DB so it can be pointed at a
persistent volume in production without any code change.
"""

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, Optional

from .config import AUDIT_DB as _AUDIT_DB_STR

from pathlib import Path

# Resolve the audit DB path once at import time.  The value comes from the
# AUDIT_DB environment variable (set in config.py) so it is fully configurable
# without touching this module.
AUDIT_DB: Path = Path(_AUDIT_DB_STR)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id          TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    policy      TEXT NOT NULL,
    decision    TEXT NOT NULL,
    violations  TEXT NOT NULL DEFAULT '[]',
    input_hash  TEXT,
    actor       TEXT,
    source      TEXT,
    environment TEXT,
    ref         TEXT,
    meta        TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_ts       ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_policy   ON audit_events(policy);
CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_events(decision);
"""


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields an open SQLite connection and auto-commits.

    Creates the parent directory on first use so the server does not need a
    pre-existing /data directory in the container image.
    """
    AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(AUDIT_DB))
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def _deserialize_row(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict with JSON fields parsed."""
    d = dict(row)
    d["violations"] = json.loads(d["violations"])
    d["meta"] = json.loads(d["meta"])
    return d


def init_db() -> None:
    """Create the audit_events table and indexes if they do not yet exist."""
    with _conn() as db:
        db.executescript(_SCHEMA)


def record(
    *,
    policy: str,
    decision: bool,
    violations: list[dict],
    input_data: dict,
    actor: str = "",
    source: str = "",
) -> dict:
    """Write a policy evaluation audit event and return it as a dict.

    ``input_data`` is hashed (not stored) to keep the audit log compact while
    still allowing verification that the same input was used twice.
    """
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    environment = input_data.get("environment", "")
    ref = input_data.get("ref", "") or input_data.get("base_ref", "")

    input_hash = hashlib.sha256(
        json.dumps(input_data, sort_keys=True).encode()
    ).hexdigest()[:16]

    meta = {
        "head_ref": input_data.get("head_ref", ""),
        "approvers": (input_data.get("workflow_meta") or {}).get("approvers", []),
    }

    row = {
        "id": event_id,
        "timestamp": now,
        "policy": policy,
        "decision": "allow" if decision else "deny",
        "violations": json.dumps(violations),
        "input_hash": input_hash,
        "actor": actor,
        "source": source,
        "environment": environment,
        "ref": ref,
        "meta": json.dumps(meta),
    }

    with _conn() as db:
        db.execute(
            """INSERT INTO audit_events
               (id, timestamp, policy, decision, violations, input_hash,
                actor, source, environment, ref, meta)
               VALUES (:id, :timestamp, :policy, :decision, :violations,
                       :input_hash, :actor, :source, :environment, :ref, :meta)""",
            row,
        )

    row["violations"] = violations
    row["meta"] = meta
    return row


def update_callback(event_id: str, *, status_code: int, state: str) -> None:
    """Record the GitHub callback result on an existing audit event."""
    with _conn() as db:
        row = db.execute(
            "SELECT meta FROM audit_events WHERE id = :id", {"id": event_id}
        ).fetchone()
        if not row:
            return
        meta = json.loads(row["meta"])
        meta["callback"] = {
            "status_code": status_code,
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        db.execute(
            "UPDATE audit_events SET meta = :meta WHERE id = :id",
            {"meta": json.dumps(meta), "id": event_id},
        )


def get_by_id(event_id: str) -> Optional[dict]:
    """Retrieve a single audit event by ID."""
    with _conn() as db:
        row = db.execute(
            "SELECT * FROM audit_events WHERE id = :id", {"id": event_id}
        ).fetchone()
    if not row:
        return None
    return _deserialize_row(row)


def query(
    *,
    limit: int = 50,
    policy: Optional[str] = None,
    decision: Optional[str] = None,
    since: Optional[str] = None,
    environment: Optional[str] = None,
) -> list[dict]:
    """Return audit events matching the given filters, newest first.

    All filters are optional and are combined with AND.  Only column *names*
    are interpolated into the SQL — never user-supplied values — so this is
    safe from SQL injection despite the f-string.  All filter values go
    through named parameters (`:policy`, `:decision`, etc.).
    """
    clauses = []
    params: dict = {}

    if policy:
        clauses.append("policy = :policy")
        params["policy"] = policy
    if decision:
        clauses.append("decision = :decision")
        params["decision"] = decision
    if since:
        clauses.append("timestamp >= :since")
        params["since"] = since
    if environment:
        clauses.append("environment = :environment")
        params["environment"] = environment

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params["limit"] = min(limit, 500)

    with _conn() as db:
        rows = db.execute(
            f"SELECT * FROM audit_events {where} ORDER BY timestamp DESC LIMIT :limit",
            params,
        ).fetchall()

    return [_deserialize_row(r) for r in rows]


def summary() -> dict:
    """Return aggregate counts broken down by decision, policy, and environment."""
    with _conn() as db:
        total = db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        by_decision = dict(
            db.execute(
                "SELECT decision, COUNT(*) FROM audit_events GROUP BY decision"
            ).fetchall()
        )
        by_policy = dict(
            db.execute(
                "SELECT policy, COUNT(*) FROM audit_events GROUP BY policy"
            ).fetchall()
        )
        by_environment = dict(
            db.execute(
                "SELECT environment, COUNT(*) FROM audit_events "
                "WHERE environment != '' GROUP BY environment"
            ).fetchall()
        )
    return {
        "total": total,
        "by_decision": by_decision,
        "by_policy": by_policy,
        "by_environment": by_environment,
    }
