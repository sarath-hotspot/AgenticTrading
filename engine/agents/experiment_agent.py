import json
import logging
import re
import time
from datetime import datetime, timezone

import anthropic
import click
from rich.console import Console
from rich.panel import Panel

from engine.tools.quantconnect import QuantConnectClient, QuantConnectError
from engine.tools.storage import save_experiment
from engine.tools.agent_memory import (
    read_memory, append_entry, ensure_header, TOOL_MEMORY_WRITE,
)

AGENT_NAME = "experiment_agent"

logger = logging.getLogger(__name__)
console = Console()

# ── Prompt: write the initial algorithm ──────────────────────────────────────

WRITE_SYSTEM = """\
You are an expert QuantConnect LEAN developer implementing a trading hypothesis as a Python backtest.

Output ONLY the complete Python source code. No explanation, no markdown fences, no extra text.

STYLE RULE — CRITICAL: Use snake_case for ALL method names, overrides, and properties.
LEAN Python fully supports snake_case aliases. Never use PascalCase method names.
  Wrong: SetStartDate, AddFuture, IsWarmingUp, OnData, Initialize, Securities, IsReady
  Right: set_start_date, add_future, is_warming_up, on_data, initialize, securities, is_ready
Enums and constants keep their casing: Resolution.Daily, Futures.Energy.CrudeOilWTI

Algorithm requirements:
- Class inherits from QCAlgorithm with initialize() and on_data() methods.
- Futures setup:
    cl = self.add_future(Futures.Energy.CrudeOilWTI)
    cl.set_filter(0, 90)
    self.cl_sym = cl.symbol
- Backtest period: self.set_start_date({backtest_start}) / self.set_end_date({backtest_end})
- Split data: first 70% in-sample, last 30% out-of-sample. Use timedelta for the split date.
- Warm-up: self.set_warm_up(50)   ← use set_warm_up, NOT set_warm_up_period

Accuracy reporting — REQUIRED in on_end_of_algorithm:
    self.set_runtime_statistic("accuracy_pct", str(round(accuracy_pct, 2)))
    self.set_runtime_statistic("total_predictions", str(total_predictions))
    self.log(f'{{"metric": "out_of_sample_accuracy", "accuracy_pct": {{accuracy_pct}}, "total_predictions": {{total_predictions}}}}')

Signal rules (CRITICAL — follow exactly):
- Use at most TWO conditions for entry.
- LEAN built-in indicators only: sma, ema, rsi, bb, atr, macd, mom, roc, sto (NOT stoch/stochastic)
- Attach indicators to cl.symbol: self.rsi(self.cl_sym, 14, Resolution.Daily)
- Aim for ≥20 signals per year in out-of-sample. Single-condition signals are fine.
- Record each signal: self.predictions.append({{"time": self.time, "direction": 1, "price": price}})
- Evaluate at on_end_of_algorithm: did price move ≥1% in predicted direction within 60 bars?

Data access pattern:
    def on_data(self, data):
        if self.is_warming_up: return
        if not self.my_indicator.is_ready: return
        if self.cl_sym not in data or data[self.cl_sym] is None: return
        price = self.securities[self.cl_sym].price
        if price == 0: return

Known LEAN pitfalls (avoid these):
- set_warm_up_period does not exist — use set_warm_up(n)
- data[symbol] can be None — always guard with `if symbol not in data or data[symbol] is None`
- QuoteBar has no .volume — use self.securities[sym].volume or use Resolution.Daily
- Consolidator callbacks: def on_bar(self, consolidator, bar) — takes TWO args after self
- Do NOT use Futures.Energy.CrudeOilWTI as a symbol — use cl.symbol from add_future()
- from datetime import timedelta — required for date arithmetic
"""

WRITE_USER = """\
== PAST LEARNINGS (errors seen and fixes that worked) ==
{memory}

== TRADING GOAL ==
{goal}

== DOMAIN KNOWLEDGE (QuantConnect patterns, known signals, setup instructions) ==
{domain_knowledge}

== QC CODE INSTRUCTIONS (templates, indicator reference, common errors) ==
{qc_instructions}

== HYPOTHESIS TO IMPLEMENT ==
Summary: {summary}
Detail: {full_text}
Suggested approach: {approach}

Experiment ID: {exp_id}

Write the complete Python algorithm now.
"""

# ── Prompt: fix an error ─────────────────────────────────────────────────────

FIX_SYSTEM = """\
You are an expert QuantConnect LEAN developer fixing a Python backtest that failed.

Output ONLY the complete corrected Python source code. No explanation, no markdown fences.

Apply the fix described in the error. Keep everything else unchanged.
Refer to your past learnings for common QC mistakes and their fixes.
"""

FIX_USER = """\
== PAST LEARNINGS (errors seen and fixes that worked) ==
{memory}

== DOMAIN KNOWLEDGE (QuantConnect patterns and known pitfalls) ==
{domain_knowledge}

== QC CODE INSTRUCTIONS (templates and indicator reference) ==
{qc_instructions}

== ERROR (fix attempt {attempt}/{max_attempts}) ==
Type: {error_type}
Message:
{error}

== CURRENT CODE ==
{code}

Output the complete fixed Python code.
"""


class ExperimentAgent:
    def __init__(
        self,
        client: anthropic.Anthropic,
        qc: QuantConnectClient,
        config: dict,
        pause_on_error: bool = False,
    ):
        self.client = client
        self.qc = qc
        engine = config.get("engine", {})
        self.model = engine.get("model", "claude-haiku-4-5")
        self.max_fix_attempts = int(engine.get("max_fix_attempts", 3))
        self.backtest_start = engine.get("backtest_start_date", "2021-01-01").replace("-", ",").lstrip("0")
        self.backtest_end = engine.get("backtest_end_date", "2024-06-30").replace("-", ",").lstrip("0")
        self.goal = config.get("goal", "")
        self.domain_knowledge = config.get("domain_knowledge", "")
        self.instructions = config.get("instructions", "")
        self.qc_instructions = config.get("qc_instructions", "")
        self.qc_python_spec = config.get("qc_python_spec", "")
        self.pause_on_error = pause_on_error
        ensure_header(AGENT_NAME, "QC Experiment Agent Learnings")

    # ── Public entry point ───────────────────────────────────────────────────

    def run(self, hypothesis: dict, exp_id: str) -> dict:
        memory = read_memory(AGENT_NAME)
        summary = hypothesis.get("summary", "")

        # Step 1 — create QC project
        project_id = self._create_project(exp_id, summary)

        # Step 2 — generate initial algorithm code
        console.print("[cyan]  Generating algorithm code...[/cyan]")
        code = self._generate_code(hypothesis, exp_id, memory)
        logger.info("Initial code generated (%d chars) for %s", len(code), exp_id)

        # Step 3 — compile-fix inner loop
        backtest_id = None
        final_result: dict = {}
        compile_attempts = 0

        for attempt in range(1, self.max_fix_attempts + 1):
            compile_attempts = attempt
            console.rule(f"[dim]  Fix attempt {attempt}/{self.max_fix_attempts}[/dim]", style="dim")

            # Upload code
            self._upload_code(project_id, code, is_update=(attempt > 1))

            # Compile
            console.print(f"[dim]  Compiling (attempt {attempt}/{self.max_fix_attempts})...[/dim]")
            compile_ok, compile_id, compile_error_logs = self._compile(project_id)

            if not compile_ok:
                error_text = "\n".join(compile_error_logs)
                self._show_error("Compile Error", error_text)
                if self.pause_on_error:
                    click.pause(info="\nVerify compile error above matches QC, then press any key to attempt fix...")
                if attempt == self.max_fix_attempts:
                    logger.warning("Max fix attempts reached on compile error for %s", exp_id)
                    break
                console.print(f"[yellow]  Fixing compile error...[/yellow]")
                code = self._fix_code(code, "Compile Error", error_text, attempt, self.max_fix_attempts, memory)
                continue

            # Run backtest using the compile_id already obtained above
            console.print("[dim]  Running backtest...[/dim]")
            backtest_id = self._run_backtest(project_id, compile_id, summary, attempt)
            result = self._read_results(project_id, backtest_id)
            final_result = result

            if result.get("runtime_error"):
                error_text = result.get("error") or result.get("stacktrace") or "Unknown runtime error"
                self._show_error("Runtime Error", error_text, result)
                if self.pause_on_error:
                    click.pause(info="\nVerify runtime error above matches QC, then press any key to attempt fix...")
                if attempt == self.max_fix_attempts:
                    logger.warning("Max fix attempts reached on runtime error for %s", exp_id)
                    break
                console.print(f"[yellow]  Fixing runtime error...[/yellow]")
                code = self._fix_code(code, "Runtime Error", error_text, attempt, self.max_fix_attempts, memory)
                continue

            # Success
            logger.info("Backtest %s completed. accuracy=%s", backtest_id, result.get("accuracy_pct"))
            console.print(
                f"  [green]Backtest complete.[/green] "
                f"accuracy={result.get('accuracy_pct')}  "
                f"total_predictions={result.get('total_trades')}"
            )
            break

        # Step 4 — save experiment
        self._save_experiment(exp_id, hypothesis, code, project_id, backtest_id, compile_attempts, final_result)

        return {
            "project_id": project_id,
            "backtest_id": backtest_id,
            "compile_attempts": compile_attempts,
        }

    # ── Inner steps (Python-controlled) ─────────────────────────────────────

    def _create_project(self, exp_id: str, summary: str = "") -> int:
        short_id = exp_id[-8:] if len(exp_id) >= 8 else exp_id
        slug = summary[:50].strip() if summary else exp_id
        project_name = f"{slug} [{short_id}]"
        console.print("[dim]  -> qc_create_project[/dim]")
        for attempt in range(3):
            try:
                pid = self.qc.create_project(project_name)
                logger.info("Created QC project %d (%s) for %s", pid, project_name, exp_id)
                return pid
            except QuantConnectError as e:
                if attempt == 2:
                    raise
                time.sleep(2)
        raise QuantConnectError("Failed to create project after 3 attempts")

    def _upload_code(self, project_id: int, code: str, is_update: bool) -> None:
        console.print("[dim]  -> qc_upload_code[/dim]")
        try:
            if is_update:
                self.qc.update_file(project_id, "main.py", code)
            else:
                try:
                    self.qc.create_file(project_id, "main.py", code)
                except QuantConnectError as e:
                    if "already exist" in str(e).lower():
                        self.qc.update_file(project_id, "main.py", code)
                    else:
                        raise
        except QuantConnectError as e:
            logger.error("Upload failed: %s", e)
            raise

    def _compile(self, project_id: int) -> tuple[bool, str, list[str]]:
        compile_id = self.qc.compile(project_id)
        result = self.qc.wait_for_compile(project_id, compile_id)
        return result["success"], compile_id, result.get("logs", [])

    def _run_backtest(self, project_id: int, compile_id: str, summary: str, attempt: int) -> str:
        slug = summary[:40].strip() if summary else "backtest"
        bt_name = f"{slug} (a{attempt})"
        console.print("[dim]  -> qc_compile_and_run[/dim]")
        return self.qc.run_backtest(project_id, compile_id, bt_name)

    def _read_results(self, project_id: int, backtest_id: str) -> dict:
        console.print("[dim]  -> qc_read_results[/dim]")
        backtest = self.qc.wait_for_backtest(project_id, backtest_id)
        log_lines = self.qc.read_backtest_logs(project_id, backtest_id, start=0, count=500)
        backtest["_fetched_logs"] = log_lines
        return self._parse_results(backtest)

    def _save_experiment(
        self,
        exp_id: str,
        hypothesis: dict,
        code: str,
        project_id: int,
        backtest_id: str | None,
        compile_attempts: int,
        result: dict,
    ) -> None:
        console.print("[dim]  -> storage_write_experiment[/dim]")
        data = {
            "id": exp_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hypothesis": hypothesis,
            "algorithm_code": code,
            "compile_attempts": compile_attempts,
            "qc_project_id": project_id,
            "qc_backtest_id": backtest_id,
            "status": "completed" if (result and not result.get("runtime_error")) else "failed",
            "goal_reached": False,
            "results": result,
        }
        save_experiment(exp_id, data)
        logger.info("Experiment %s saved.", exp_id)

    # ── LLM calls (focused, single-purpose) ─────────────────────────────────

    def _generate_code(self, hypothesis: dict, exp_id: str, memory: str) -> str:
        user_msg = WRITE_USER.format(
            memory=memory or "None yet.",
            goal=self.goal,
            domain_knowledge=self.domain_knowledge,
            qc_instructions=self.qc_instructions or "None.",
            summary=hypothesis.get("summary", ""),
            full_text=hypothesis.get("full_text", ""),
            approach=hypothesis.get("suggested_algorithm_approach", "")[:1000],
            exp_id=exp_id,
        )
        system = WRITE_SYSTEM.format(
            backtest_start=self.backtest_start,
            backtest_end=self.backtest_end,
        )
        if self.qc_python_spec:
            system += (
                "\n\n== LEAN PYTHON API REFERENCE"
                " (authoritative — use ONLY these exact method names) ==\n"
                + self.qc_python_spec
            )
        response = self._api_call(system=system, user=user_msg, max_tokens=8192)
        code = self._extract_code(response)
        logger.debug("Generated code (%d chars)", len(code))
        return code

    def _fix_code(
        self,
        code: str,
        error_type: str,
        error_text: str,
        attempt: int,
        max_attempts: int,
        memory: str,
    ) -> str:
        # HTML-decode common QC entities before sending to LLM
        for ent, ch in [("&#039;", "'"), ("&gt;", ">"), ("&lt;", "<"), ("&amp;", "&")]:
            error_text = error_text.replace(ent, ch)

        user_msg = FIX_USER.format(
            memory=memory or "None yet.",
            domain_knowledge=self.domain_knowledge,
            qc_instructions=self.qc_instructions or "None.",
            attempt=attempt,
            max_attempts=max_attempts,
            error_type=error_type,
            error=error_text,
            code=code,
        )
        response = self._api_call(system=FIX_SYSTEM, user=user_msg, max_tokens=8192)
        fixed = self._extract_code(response)

        # Write a memory entry for this fix
        append_entry(
            AGENT_NAME,
            f"{error_type} fix (attempt {attempt})",
            f"Error: {error_text[:300]}\n\nFix applied (see code diff).",
        )
        console.print(f"  [dim cyan]Memory saved:[/dim cyan] {error_type} fix (attempt {attempt})")
        logger.debug("Fixed code (%d chars)", len(fixed))
        return fixed

    def _api_call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        for attempt in range(5):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""
            except anthropic.RateLimitError:
                wait = 60 * (attempt + 1)
                console.print(f"[yellow]Rate limit — waiting {wait}s...[/yellow]")
                time.sleep(wait)
        return ""

    # ── Display helpers ──────────────────────────────────────────────────────

    def _show_error(self, title: str, error: str, result: dict | None = None) -> None:
        for ent, ch in [("&#039;", "'"), ("&gt;", ">"), ("&lt;", "<"), ("&amp;", "&")]:
            error = error.replace(ent, ch)

        body = f"[bold red]{error}[/bold red]"

        if result:
            stacktrace = result.get("stacktrace") or ""
            for ent, ch in [("&#039;", "'"), ("&gt;", ">"), ("&lt;", "<"), ("&amp;", "&")]:
                stacktrace = stacktrace.replace(ent, ch)
            if stacktrace and stacktrace.strip() != error.strip():
                body += f"\n\n[yellow]Stacktrace:[/yellow]\n{stacktrace}"
            logs = result.get("logs") or ""
            if logs:
                last = "\n".join(logs.strip().splitlines()[-15:])
                body += f"\n\n[dim]Last log lines:[/dim]\n{last}"

        console.print(Panel(body, title=f"[red]{title}[/red]", border_style="red"))
        logger.error("%s: %s", title, error[:200])

    # ── Utilities ────────────────────────────────────────────────────────────

    def _extract_code(self, raw: str) -> str:
        raw = raw.strip()
        # Strip markdown code fences if present
        fenced = re.sub(r"^```(?:python)?\s*\n?", "", raw, flags=re.IGNORECASE)
        fenced = re.sub(r"\n?```\s*$", "", fenced).strip()
        # If it starts with 'from' or 'import', it's likely raw code
        if fenced.startswith(("from ", "import ", "class ")):
            return fenced
        return fenced or raw

    def _parse_results(self, backtest: dict) -> dict:
        status = backtest.get("status", "")
        error = backtest.get("error") or ""
        stacktrace = backtest.get("stacktrace") or ""
        has_error = bool(error) or backtest.get("hasInitializeError", False)

        fetched = backtest.get("_fetched_logs", [])
        inline = backtest.get("logs", "") or ""
        if isinstance(inline, list):
            inline = "\n".join(inline)
        fetched_text = "\n".join(fetched) if isinstance(fetched, list) else str(fetched)
        log_lines = (fetched_text + "\n" + inline).strip()

        stats = backtest.get("statistics") or {}
        rt_stats = backtest.get("runtimeStatistics") or {}

        result = {
            "status": status,
            "runtime_error": has_error,
            "error": error[:2000] if error else None,
            "stacktrace": stacktrace[:2000] if stacktrace else None,
            "logs": log_lines[-3000:] if log_lines else None,
            "sharpe": self._parse_float(stats.get("Sharpe Ratio")),
            "max_drawdown_pct": self._parse_float(stats.get("Drawdown")),
            "net_profit_pct": self._parse_float(stats.get("Net Profit")),
            "total_trades": self._parse_int(stats.get("Total Orders")),
            "win_rate_pct": self._parse_float(stats.get("Win Rate")),
            "accuracy_pct": None,
        }

        # 1. runtimeStatistics (via self.SetRuntimeStatistic)
        if "accuracy_pct" in rt_stats:
            result["accuracy_pct"] = self._parse_float(rt_stats["accuracy_pct"])
        # 2. log line extraction
        if result["accuracy_pct"] is None:
            result["accuracy_pct"] = self._extract_accuracy(log_lines)
        # 3. scan runtimeStatistics JSON
        if result["accuracy_pct"] is None:
            result["accuracy_pct"] = self._extract_accuracy(json.dumps(rt_stats))

        return result

    def _extract_accuracy(self, text: str) -> float | None:
        m = re.search(r'"metric"\s*:\s*"out_of_sample_accuracy".*?"accuracy_pct"\s*:\s*([0-9.]+)', text)
        return float(m.group(1)) if m else None

    def _parse_float(self, value) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace("%", "").strip())
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).replace(",", "").strip())
        except (ValueError, TypeError):
            return None
