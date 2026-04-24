import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENTS_DIR = Path("experiments")
INDEX_FILE = EXPERIMENTS_DIR / "index.json"


def generate_experiment_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"exp_{ts}_{suffix}"


def load_index() -> dict:
    if not INDEX_FILE.exists():
        return {"schema_version": 1, "experiments": []}
    with open(INDEX_FILE) as f:
        return json.load(f)


def save_index(index: dict) -> None:
    EXPERIMENTS_DIR.mkdir(exist_ok=True)
    tmp = INDEX_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(index, f, indent=2)
    os.replace(tmp, INDEX_FILE)


def load_experiment(exp_id: str) -> dict:
    path = EXPERIMENTS_DIR / f"{exp_id}.json"
    with open(path) as f:
        return json.load(f)


def save_experiment(exp_id: str, data: dict) -> None:
    EXPERIMENTS_DIR.mkdir(exist_ok=True)
    path = EXPERIMENTS_DIR / f"{exp_id}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    index = load_index()
    results = data.get("results", {})
    if not isinstance(results, dict):
        results = {}
    hyp = data.get("hypothesis", {})
    if isinstance(hyp, dict):
        hyp_summary = hyp.get("summary", "")
    else:
        hyp_summary = str(hyp)[:120]
    summary = {
        "id": exp_id,
        "timestamp": data.get("timestamp", ""),
        "hypothesis_summary": hyp_summary,
        "status": data.get("status", "completed"),
        "goal_reached": data.get("goal_reached", False),
        "accuracy_pct": results.get("accuracy_pct"),
        "sharpe": results.get("sharpe"),
    }
    existing_ids = [e["id"] for e in index["experiments"]]
    if exp_id in existing_ids:
        index["experiments"] = [
            summary if e["id"] == exp_id else e for e in index["experiments"]
        ]
    else:
        index["experiments"].append(summary)
    save_index(index)


def list_experiments(limit: int = 20) -> list:
    index = load_index()
    experiments = sorted(
        index["experiments"], key=lambda e: e.get("timestamp", ""), reverse=True
    )
    return experiments[:limit]


def get_past_results_summary(limit: int = 5) -> str:
    experiments = list_experiments(limit)
    if not experiments:
        return "No past experiments found."
    lines = []
    for i, exp in enumerate(experiments, 1):
        acc = f"{exp['accuracy_pct']:.1f}%" if exp.get("accuracy_pct") is not None else "N/A"
        reached = "GOAL REACHED" if exp.get("goal_reached") else "goal not reached"
        lines.append(
            f"{i}. [{exp['id']}] {exp['hypothesis_summary']} - accuracy: {acc}, {reached}"
        )
    return "\n".join(lines)


# --- Anthropic tool definitions ---

TOOL_STORAGE_READ = {
    "name": "storage_read_past_results",
    "description": "Read a summary of past experiment results to inform hypothesis generation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of past experiments to retrieve (default 5)",
            }
        },
        "required": [],
    },
}

TOOL_STORAGE_WRITE = {
    "name": "storage_write_experiment",
    "description": "Save a completed experiment record to persistent storage.",
    "input_schema": {
        "type": "object",
        "properties": {
            "exp_id": {"type": "string", "description": "Experiment ID"},
            "data": {"type": "object", "description": "Full experiment record dict"},
        },
        "required": ["exp_id", "data"],
    },
}
