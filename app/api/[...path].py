import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

default_db_name = os.environ.get("DB_NAME") or "sacramento"
os.environ.setdefault(
    "HEALTHSCOUT_DB_PATH",
    str(Path(__file__).parent.parent / "database" / f"{default_db_name}.db"),
)
os.environ.setdefault("LOG_FILE", "/tmp/app.log")

from src.presentation.core_api import app  # noqa: E402, F401
