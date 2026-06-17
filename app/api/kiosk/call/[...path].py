import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
os.environ.setdefault("LOG_FILE", "/tmp/app.log")

from src.presentation.kiosk_call_api import app  # noqa: E402, F401
