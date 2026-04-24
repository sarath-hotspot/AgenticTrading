"""
Persistent per-agent memory. Each agent gets a markdown file in memory/.
Agents can read their memory (injected into system prompt) and write new
entries after discovering an error/fix or a useful pattern.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path("memory")


def _path(agent_name: str) -> Path:
    MEMORY_DIR.mkdir(exist_ok=True)
    return MEMORY_DIR / f"{agent_name}.md"


def read_memory(agent_name: str) -> str:
    """Return the full memory file content, or empty string if none exists."""
    p = _path(agent_name)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def append_entry(agent_name: str, title: str, body: str) -> None:
    """Append a dated entry to the agent's memory file."""
    p = _path(agent_name)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = f"\n\n## {ts} — {title}\n{body.strip()}\n"
    with open(p, "a", encoding="utf-8") as f:
        f.write(entry)


def ensure_header(agent_name: str, header: str) -> None:
    """Write the file header if the file doesn't exist yet."""
    p = _path(agent_name)
    if not p.exists():
        p.write_text(f"# {header}\n", encoding="utf-8")


# --- Tool definitions ---

TOOL_MEMORY_READ = {
    "name": "memory_read",
    "description": (
        "Read your persistent memory — past learnings, error fixes, and patterns "
        "discovered in previous runs. Call this at the start of each task."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_MEMORY_WRITE = {
    "name": "memory_write",
    "description": (
        "Save a learning to your persistent memory so it is available in future runs. "
        "Call this whenever you discover a new error pattern, a fix that worked, "
        "or a useful QC-specific insight."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title for this learning (e.g. 'SetWarmUp method name')",
            },
            "body": {
                "type": "string",
                "description": (
                    "The learning content. Include: what the error/pattern was, "
                    "what fix worked, and any caveats."
                ),
            },
        },
        "required": ["title", "body"],
    },
}
