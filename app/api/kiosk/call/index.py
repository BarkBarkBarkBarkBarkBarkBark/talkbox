"""Vercel compatibility entry point for the kiosk call function.

Some Vercel deployments in the wild still resolve this legacy path. Keep it
pointing at the same FastAPI app as the primary `api/index.py` entry point so
either project root can build successfully.
"""

import os
import sys
from pathlib import Path

# Make `src.*` imports work when this file is deployed as a nested Vercel
# function under `api/kiosk/call`.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

# Serverless functions have no persistent filesystem; redirect the log file to
# the writable /tmp directory so RotatingFileHandler doesn't crash at startup.
os.environ.setdefault("LOG_FILE", "/tmp/app.log")

from src.presentation.api import app  # noqa: E402, F401