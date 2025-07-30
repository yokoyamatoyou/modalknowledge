from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

LOG_FILE = Path("operation_history.log")


def log_operation(action: str, detail: Dict[str, Any]) -> None:
    """Append an operation record to the log file."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "detail": detail,
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

