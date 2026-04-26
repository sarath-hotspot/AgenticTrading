import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# On Windows the legacy console uses the system code page (usually cp1252).
# Wrap stdout/stderr with UTF-8 + replace so LLM-generated Unicode never crashes.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", newline="")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", newline="")

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box

from engine.config_loader import ConfigLoader
from engine.llm_client import AnthropicLLMClient, OpenAILLMClient
from engine.tools.quantconnect import QuantConnectClient
from engine.tools import storage
from engine.agents.hypothesis_agent import HypothesisAgent
from engine.agents.experiment_agent import ExperimentAgent
from engine.agents.reviewer_agent import ReviewerAgent
from engine.loop import ControlLoop
from engine import run_logger, run_state

console = Console()

REQUIRED_ENV = ["QC_USER_ID", "QC_API_TOKEN"]


def _safe(text: str, max_len: int = 0) -> str:
    """Replace non-ASCII chars so the Windows legacy console renderer doesn't crash."""
    out = text.encode("ascii", errors="replace").decode("ascii")
    return out[:max_len] if max_len else out


def _load_env() -> None:
    load_dotenv()


def _check_env() -> None:
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        console.print(f"[red]Missing required environment variables:[/red] {', '.join(missing)}")
        console.print("[dim]Copy .env.example to .env and fill in your QC credentials.[/dim]")
        sys.exit(1)


def _check_config(config_loader: ConfigLoader) -> None:
    try:
        config_loader.load()
    except FileNotFoundError as e:
        console.print(f"[red]Config error:[/red] {e}")
        sys.exit(1)


def _create_llm_client(provider: str, engine_config: dict):
    """Create the appropriate LLM client based on the selected provider."""
    if provider == "openai":
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            console.print("[red]No OpenAI API key found.[/red] Set OPENAI_API_KEY in your .env file.")
            sys.exit(1)
        model = engine_config.get("openai_model", "gpt-4o")
        console.print(f"[dim]Provider: OpenAI  model: {model}[/dim]")
        return OpenAILLMClient(openai.OpenAI(api_key=api_key), model)
    else:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            config_path = Path.home() / ".claude" / "config.json"
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        api_key = json.load(f).get("primaryApiKey")
                except Exception:
                    pass
        if not api_key:
            console.print(
                "[red]No Anthropic API key found.[/red] "
                "Set ANTHROPIC_API_KEY or log in via Claude Code."
            )
            sys.exit(1)
        model = engine_config.get("model", "claude-haiku-4-5")
        console.print(f"[dim]Provider: Anthropic  model: {model}[/dim]")
        return AnthropicLLMClient(anthropic.Anthropic(api_key=api_key), model)


@click.group()
def cli():
    """AgenticTrading — agentic research engine for energy futures."""
    _load_env()


@cli.command()
@click.option("--max-iterations", default=None, type=int,
              help="Maximum number of hypothesis/experiment cycles (overrides engine.yaml).")
@click.option("--auto", is_flag=True, default=False,
              help="Skip human decision prompts (fully autonomous mode).")
@click.option("--resume", is_flag=True, default=False,
              help="Resume the last interrupted run from its checkpoint.")
@click.option("--pause-on-error", is_flag=True, default=False,
              help="Pause after each QC runtime error so you can verify it in the QC dashboard.")
@click.option("--provider", default="anthropic", type=click.Choice(["anthropic", "openai"]),
              show_default=True, help="LLM provider to use.")
def run(max_iterations: int | None, auto: bool, resume: bool, pause_on_error: bool, provider: str) -> None:
    """Start the agentic research loop."""
    _check_env()

    config_loader = ConfigLoader()
    _check_config(config_loader)

    config = config_loader.load()
    engine_config = config["engine"]

    # Determine run_id: reuse from checkpoint or generate fresh
    existing_state = run_state.load()
    if resume and existing_state and existing_state.get("phase") != "done":
        run_id = existing_state["run_id"]
        max_iterations = existing_state["max_iterations"]
        auto = existing_state["auto"]
        console.print(f"[yellow]Resuming run {run_id}[/yellow]")
    else:
        if resume and (not existing_state or existing_state.get("phase") == "done"):
            console.print("[dim]No interrupted run found — starting fresh.[/dim]")
        run_id = None  # loop.py will generate one
        # CLI flag takes precedence; fall back to engine.yaml value
        if max_iterations is None:
            max_iterations = int(engine_config.get("max_iterations", 10))

    log_run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_logger.setup(log_run_id)

    client = _create_llm_client(provider, engine_config)
    qc_client = QuantConnectClient(
        user_id=os.environ["QC_USER_ID"],
        api_token=os.environ["QC_API_TOKEN"],
    )

    config_context = config_loader.get_system_context()
    hypothesis_agent = HypothesisAgent(client, config_context, engine_config)
    experiment_agent = ExperimentAgent(client, qc_client, config, pause_on_error=pause_on_error)
    reviewer_agent = ReviewerAgent(client, engine_config)

    loop = ControlLoop(
        config_loader=config_loader,
        hypothesis_agent=hypothesis_agent,
        experiment_agent=experiment_agent,
        reviewer_agent=reviewer_agent,
        max_iterations=max_iterations,
        auto=auto,
        run_id=run_id,
        engine_config=engine_config,
    )
    loop.run()


@cli.command()
def status() -> None:
    """Show the experiment index table."""
    experiments = storage.list_experiments()
    if not experiments:
        console.print("[dim]No experiments found. Run [bold]engine run[/bold] to start.[/dim]")
        return

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Timestamp", no_wrap=True)
    table.add_column("Hypothesis")
    table.add_column("Accuracy", justify="right")
    table.add_column("Goal", justify="center")
    table.add_column("Status")

    for exp in experiments:
        acc = exp.get("accuracy_pct")
        acc_str = f"{acc:.1f}%" if acc is not None else "N/A"
        goal_str = "[green]YES[/green]" if exp.get("goal_reached") else "[red]no[/red]"
        table.add_row(
            _safe(exp.get("id", "")),
            exp.get("timestamp", "")[:19].replace("T", " "),
            _safe(exp.get("hypothesis_summary") or "", 60),
            acc_str,
            goal_str,
            _safe(exp.get("status", "")),
        )

    console.print(table)


@cli.command()
@click.option("--force", is_flag=True, default=False,
              help="Skip confirmation prompt.")
@click.option("--keep-logs", is_flag=True, default=False,
              help="Keep run log files in logs/.")
def clear(force: bool, keep_logs: bool) -> None:
    """Remove all experiments, agent memory, and the resume checkpoint."""
    experiments_dir = Path("experiments")
    memory_dir = Path("memory")
    checkpoint = Path(".engine_run_state.json")
    logs_dir = Path("logs")

    # Collect what will be deleted so we can show a preview
    to_delete: list[Path] = []

    if experiments_dir.exists():
        to_delete.extend(p for p in sorted(experiments_dir.iterdir()) if p.name != ".gitkeep")
    if memory_dir.exists():
        to_delete.extend(
            p for p in sorted(memory_dir.iterdir())
            if p.suffix == ".md" and p.name != ".gitkeep"
        )
    if checkpoint.exists():
        to_delete.append(checkpoint)
    if not keep_logs and logs_dir.exists():
        to_delete.extend(sorted(logs_dir.iterdir()))

    if not to_delete:
        console.print("[dim]Nothing to clear.[/dim]")
        return

    console.print("[bold]The following files will be deleted:[/bold]")
    for p in to_delete:
        console.print(f"  [dim]{p}[/dim]")

    if not force:
        click.confirm("\nProceed?", abort=True)

    deleted = 0
    for p in to_delete:
        try:
            p.unlink()
            deleted += 1
        except Exception as exc:
            console.print(f"[red]Could not delete {p}:[/red] {exc}")

    console.print(f"[green]Cleared {deleted} file(s).[/green]")


@cli.command()
@click.argument("exp_id", required=False)
def results(exp_id: str | None) -> None:
    """Show detailed results for an experiment (or list all)."""
    if not exp_id:
        experiments = storage.list_experiments()
        if not experiments:
            console.print("[dim]No experiments found.[/dim]")
            return
        for exp in experiments:
            acc = exp.get("accuracy_pct")
            acc_str = f"{acc:.1f}%" if acc is not None else "N/A"
            goal_str = "GOAL REACHED" if exp.get("goal_reached") else "not reached"
            console.print(f"[bold]{_safe(exp['id'])}[/bold]  {acc_str}  {goal_str}")
            console.print(f"  {_safe(exp.get('hypothesis_summary', ''))}")
        return

    try:
        record = storage.load_experiment(exp_id)
    except FileNotFoundError:
        console.print(f"[red]Experiment not found:[/red] {exp_id}")
        sys.exit(1)

    console.print_json(__import__("json").dumps(record, indent=2))


if __name__ == "__main__":
    cli()
