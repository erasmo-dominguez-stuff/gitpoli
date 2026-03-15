"""Application settings from environment variables."""

import os
from pathlib import Path

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
REPOL_DIR = Path(os.getenv("REPOL_DIR", ".repol"))

# ── GitHub App authentication ─────────────────────────────────────────────────
# The server authenticates as a GitHub App.  Set APP_ID + PRIVATE_KEY_PATH.
# The installation_id is extracted from each webhook payload automatically.

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY_PATH = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "")
