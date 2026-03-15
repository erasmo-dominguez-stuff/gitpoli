"""Application settings from environment variables."""

import os
from pathlib import Path

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
REPOL_DIR = Path(os.getenv("REPOL_DIR", ".repol"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
