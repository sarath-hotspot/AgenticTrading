"""
Checkpoints the control loop so an interrupted run can be resumed.

State file: .engine_run_state.json (excluded from git)

Schema:
{
  "run_id":          str,            # e.g. "20260424_054936"
  "max_iterations":  int,
  "auto":            bool,
  "next_iteration":  int,            # 1-based; start here on resume
  "phase":           str,            # "generating_hypothesis" | "running_experiment" | "done"
  "hypothesis":      dict | null,    # set when phase == "running_experiment"
  "exp_id":          str | null,     # set when experiment started
  "completed": [
    {"iteration": int, "exp_id": str, "accuracy_pct": float|null, "goal_reached": bool}
  ]
}
"""

import json
import os
from pathlib import Path

STATE_FILE = Path(".engine_run_state.json")


def load() -> dict | None:
    """Return saved state dict, or None if no state file exists."""
    if not STATE_FILE.exists():
        return None
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def clear() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def new_state(run_id: str, max_iterations: int, auto: bool) -> dict:
    return {
        "run_id": run_id,
        "max_iterations": max_iterations,
        "auto": auto,
        "next_iteration": 1,
        "phase": "generating_hypothesis",
        "hypothesis": None,
        "exp_id": None,
        "completed": [],
    }
