import logging

import click
from datetime import datetime, timezone
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from engine.config_loader import ConfigLoader
from engine.agents.hypothesis_agent import HypothesisAgent
from engine.agents.experiment_agent import ExperimentAgent
from engine.agents.reviewer_agent import ReviewerAgent
from engine.tools import storage
from engine import run_state

console = Console()
logger = logging.getLogger(__name__)


class ControlLoop:
    def __init__(
        self,
        config_loader: ConfigLoader,
        hypothesis_agent: HypothesisAgent,
        experiment_agent: ExperimentAgent,
        reviewer_agent: ReviewerAgent,
        max_iterations: int = 10,
        auto: bool = False,
        run_id: str | None = None,
        engine_config: dict | None = None,
    ):
        engine = engine_config or {}
        self.config_loader = config_loader
        self.hypothesis_agent = hypothesis_agent
        self.experiment_agent = experiment_agent
        self.reviewer_agent = reviewer_agent
        self.max_iterations = max_iterations
        self.auto = auto
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.goal_accuracy_threshold = float(engine.get("goal_accuracy_threshold", 70.0))
        self.max_hypothesis_attempts = int(engine.get("max_hypothesis_attempts", 3))

    def run(self) -> None:
        console.rule("[bold blue]AgenticTrading Engine Starting[/bold blue]")
        config = self.config_loader.load()
        engine = config.get("engine", {})
        console.print(f"[dim]Goal:[/dim] {config['goal'].splitlines()[0]}")
        console.print(
            f"[dim]Config:[/dim] "
            f"max_iterations={self.max_iterations}  "
            f"goal_threshold={self.goal_accuracy_threshold}%  "
            f"max_fix_attempts={engine.get('max_fix_attempts')}  "
            f"max_hypothesis_attempts={self.max_hypothesis_attempts}  "
            f"model={engine.get('model')}"
        )
        console.print()

        # Load or create checkpoint state
        state = run_state.load()
        if state and state.get("run_id") == self.run_id:
            start_iter = state["next_iteration"]
            console.print(
                f"[yellow]Resuming run {self.run_id} from iteration {start_iter}[/yellow]"
            )
            logger.info("Resuming run %s from iteration %d", self.run_id, start_iter)
        else:
            state = run_state.new_state(self.run_id, self.max_iterations, self.auto)
            start_iter = 1
            run_state.save(state)
            logger.info("Starting new run %s (max_iterations=%d)", self.run_id, self.max_iterations)

        for iteration in range(start_iter, self.max_iterations + 1):
            console.rule(f"[bold]Iteration {iteration} / {self.max_iterations}[/bold]")
            logger.info("=== Iteration %d / %d ===", iteration, self.max_iterations)

            # Check if a hypothesis was already generated (interrupted mid-experiment)
            resume_hypothesis = None
            resume_exp_id = None
            if (
                state.get("phase") == "running_experiment"
                and state.get("hypothesis")
                and state.get("exp_id")
                and state.get("next_iteration") == iteration
            ):
                resume_hypothesis = state["hypothesis"]
                resume_exp_id = state["exp_id"]
                console.print(
                    f"[yellow]Resuming experiment {resume_exp_id} from checkpoint.[/yellow]"
                )
                logger.info("Resuming experiment %s from checkpoint", resume_exp_id)

            # --- Hypothesis generation ---
            if resume_hypothesis is None:
                past_results = storage.get_past_results_summary()
                logger.debug("Past results context: %s", past_results[:200])

                hypothesis = None
                for regen in range(1, self.max_hypothesis_attempts + 1):
                    console.print(f"[cyan]Generating hypothesis (attempt {regen}/{self.max_hypothesis_attempts})...[/cyan]")
                    candidate = self.hypothesis_agent.generate(past_results)
                    logger.info(
                        "Hypothesis generated: %s", candidate.get("summary", "")[:120]
                    )
                    self._print_hypothesis(candidate)

                    decision = self._human_or_agent_decision(candidate)
                    if decision != "skip":
                        hypothesis = candidate
                        break
                    console.print("[yellow]Hypothesis skipped. Regenerating...[/yellow]")
                    logger.info("Hypothesis skipped (attempt %d/3).", regen)

                if hypothesis is None:
                    console.print(f"[yellow]All {self.max_hypothesis_attempts} hypothesis attempts skipped. Advancing iteration.[/yellow]")
                    logger.warning("All %d hypothesis attempts skipped for iteration %d.", self.max_hypothesis_attempts, iteration)
                    state.update({"next_iteration": iteration + 1, "phase": "generating_hypothesis",
                                  "hypothesis": None, "exp_id": None})
                    run_state.save(state)
                    continue
            else:
                hypothesis = resume_hypothesis
                self._print_hypothesis(hypothesis)

            # --- Checkpoint: hypothesis ready, about to run experiment ---
            exp_id = resume_exp_id or storage.generate_experiment_id()
            state.update({
                "next_iteration": iteration,
                "phase": "running_experiment",
                "hypothesis": hypothesis,
                "exp_id": exp_id,
            })
            run_state.save(state)

            # Check if experiment was already completed (mid-loop crash after write)
            results = {}
            goal_reached = False
            already_done = False
            try:
                record = storage.load_experiment(exp_id)
                raw_results = record.get("results", {})
                if not isinstance(raw_results, dict):
                    raw_results = {}
                if record.get("status") == "completed" and raw_results:
                    results = raw_results
                    goal_reached = record.get("goal_reached", self._evaluate_goal(results))
                    already_done = True
                    logger.info(
                        "Experiment %s already completed (loaded from disk). accuracy_pct=%s",
                        exp_id, results.get("accuracy_pct"),
                    )
                    console.print(
                        f"[dim]Experiment {exp_id} already completed, loading stored results.[/dim]"
                    )
            except FileNotFoundError:
                pass

            if not already_done:
                console.print(f"\n[cyan]Running experiment[/cyan] [dim]{exp_id}[/dim]")
                logger.info("Starting experiment %s", exp_id)
                try:
                    run_meta = self.experiment_agent.run(hypothesis, exp_id)
                    logger.info(
                        "Experiment %s finished. project_id=%s backtest_id=%s compile_attempts=%d",
                        exp_id,
                        run_meta.get("project_id"),
                        run_meta.get("backtest_id"),
                        run_meta.get("compile_attempts", 0),
                    )
                except Exception as e:
                    logger.exception("Experiment %s failed: %s", exp_id, e)
                    console.print(f"[red]Experiment failed:[/red] {e}")
                    _save_failed_experiment(exp_id, hypothesis, str(e))
                    state.update({"next_iteration": iteration + 1, "phase": "generating_hypothesis",
                                  "hypothesis": None, "exp_id": None})
                    run_state.save(state)
                    continue

                try:
                    record = storage.load_experiment(exp_id)
                    results = record.get("results", {})
                    if not isinstance(results, dict):
                        results = {}
                except Exception:
                    results = {}

                goal_reached = self._evaluate_goal(results)

                try:
                    record = storage.load_experiment(exp_id)
                    record["goal_reached"] = goal_reached
                    record["status"] = "completed"
                    storage.save_experiment(exp_id, record)
                except Exception:
                    pass

            self._print_results(iteration, hypothesis, results, goal_reached)
            logger.info(
                "Iteration %d result: accuracy_pct=%s goal_reached=%s",
                iteration, results.get("accuracy_pct"), goal_reached,
            )

            # --- Checkpoint: iteration done ---
            completed_entry = {
                "iteration": iteration,
                "exp_id": exp_id,
                "accuracy_pct": results.get("accuracy_pct"),
                "goal_reached": goal_reached,
            }
            state["completed"].append(completed_entry)
            state.update({
                "next_iteration": iteration + 1,
                "phase": "generating_hypothesis",
                "hypothesis": None,
                "exp_id": None,
            })
            run_state.save(state)

            if goal_reached:
                console.print(
                    f"\n[bold green]GOAL REACHED![/bold green] "
                    f"Accuracy: {results.get('accuracy_pct', 'N/A')}%"
                )
                logger.info("Goal reached on iteration %d!", iteration)
                state["phase"] = "done"
                run_state.save(state)
                return

        state["phase"] = "done"
        run_state.save(state)
        console.print(
            f"\n[yellow]Max iterations ({self.max_iterations}) reached without achieving goal.[/yellow]"
        )
        logger.info("Run complete. Max iterations reached without achieving goal.")

    def _human_or_agent_decision(self, hypothesis: dict) -> str:
        past_results = storage.get_past_results_summary()
        if self.auto:
            decision = self.reviewer_agent.review(hypothesis, past_results)
            return decision

        console.print()
        choice = click.prompt(
            "Run this hypothesis? [[bold]Y[/bold]]es / [bold]n[/bold]o (skip) / [bold]s[/bold]kip",
            default="Y",
            show_default=False,
        ).strip().lower()

        if choice in ("n", "no", "s", "skip"):
            return "skip"
        return "agent"

    def _evaluate_goal(self, results: dict) -> bool:
        acc = results.get("accuracy_pct")
        if acc is None:
            return False
        return acc >= self.goal_accuracy_threshold

    def _print_hypothesis(self, hypothesis: dict) -> None:
        def s(text: str, limit: int = 0) -> str:
            out = (text or "").encode("ascii", errors="replace").decode("ascii")
            return out[:limit] if limit else out

        body = (
            f"[bold]Summary:[/bold] {s(hypothesis.get('summary', ''))}\n\n"
            f"[bold]Rationale:[/bold] {s(hypothesis.get('rationale', ''))}\n\n"
            f"[bold]Approach:[/bold] {s(hypothesis.get('suggested_algorithm_approach', ''), 300)}"
        )
        console.print(Panel(body, title="New Hypothesis", border_style="blue"))

    def _print_results(
        self, iteration: int, hypothesis: dict, results: dict, goal_reached: bool
    ) -> None:
        acc = results.get("accuracy_pct")
        acc_str = f"{acc:.1f}%" if acc is not None else "N/A"
        sharpe = results.get("sharpe")
        sharpe_str = f"{sharpe:.2f}" if sharpe is not None else "N/A"

        status = "[green]GOAL REACHED[/green]" if goal_reached else "[red]goal not reached[/red]"
        console.print(
            f"\nIteration {iteration} complete - "
            f"accuracy: [bold]{acc_str}[/bold], sharpe: {sharpe_str}, {status}"
        )


def _save_failed_experiment(exp_id: str, hypothesis: dict, error: str) -> None:
    storage.save_experiment(exp_id, {
        "id": exp_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": hypothesis,
        "status": "failed",
        "goal_reached": False,
        "error": error,
        "results": {},
    })
