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
"""
