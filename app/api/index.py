"""Vercel serverless entry point for the Talk Box FastAPI backend.

Vercel looks for an `app` variable (ASGI) in this file.
The backend source lives under `backend/` (bundled via includeFiles in vercel.json).
"""

import os
import sys
from pathlib import Path

# Make `src.*` imports work — backend/ is bundled alongside this file.
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Point the Healthscout lookup at the same bundled SQLite asset Vercel ships
# alongside this function unless an explicit override is already configured.
default_db_name = os.environ.get("DB_NAME") or "sacramento"
os.environ.setdefault(
    "HEALTHSCOUT_DB_PATH",
    str(Path(__file__).parent.parent / "database" / f"{default_db_name}.db"),
)

# Serverless functions have no persistent filesystem; redirect the log file to
# the writable /tmp directory so RotatingFileHandler doesn't crash at startup.
# Note: /tmp is ephemeral and reset between cold-start invocations. For
# persistent logs, configure a cloud logging service (e.g. Datadog, Logtail).
os.environ.setdefault("LOG_FILE", "/tmp/app.log")

from src.presentation.api import app  # noqa: E402, F401
