"""Minimal experiment tracking: one JSON line per run (parameters, metrics, code version)."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import PROJECT_ROOT

RUNS_FILE = PROJECT_ROOT / "data" / "evaluation" / "runs.jsonl"


def git_sha() -> str:
    if os.environ.get("GIT_SHA"):
        return os.environ["GIT_SHA"]
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def log_run(name: str, params: dict, metrics: dict, artifacts: list[str] | None = None,
            path: Path | None = None) -> str:
    """Append a run record and return its id."""
    run_id = uuid.uuid4().hex[:8]
    record = {
        "run_id": run_id, "name": name, "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(), "params": params, "metrics": metrics, "artifacts": artifacts or [],
    }
    target = path or RUNS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return run_id
