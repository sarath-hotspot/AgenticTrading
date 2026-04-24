from pathlib import Path

import yaml

ENGINE_DEFAULTS = {
    "model": "claude-haiku-4-5",
    "backtest_start_date": "2021-01-01",
    "backtest_end_date": "2024-06-30",
    "max_iterations": 10,
    "goal_accuracy_threshold": 70.0,
    "max_fix_attempts": 3,
    "max_hypothesis_attempts": 3,
    "min_signals_per_year": 15,
    "max_signal_conditions": 2,
}


_REPO_ROOT = Path(__file__).resolve().parent.parent


class ConfigLoader:
    MD_FILES = ("goal", "instructions", "domain_knowledge", "qc_instructions", "qc_python_spec")

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = Path(config_dir) if config_dir else _REPO_ROOT / "config"

    def load(self) -> dict:
        config = {name: self._read_md(name) for name in self.MD_FILES}
        config["engine"] = self._load_engine()
        return config

    def get_system_context(self) -> str:
        config = self.load()
        return (
            f"## GOAL\n{config['goal']}\n\n"
            f"## DOMAIN INSTRUCTIONS\n{config['instructions']}\n\n"
            f"## DOMAIN KNOWLEDGE\n{config['domain_knowledge']}"
        )

    def _load_engine(self) -> dict:
        path = self.config_dir / "engine.yaml"
        engine = dict(ENGINE_DEFAULTS)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            engine.update({k: v for k, v in loaded.items() if v is not None})
        return engine

    def _read_md(self, name: str) -> str:
        path = self.config_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(
                f"Config file not found: {path}\n"
                f"Please create it — see the existing config/*.md files for examples."
            )
        return path.read_text(encoding="utf-8").strip()
