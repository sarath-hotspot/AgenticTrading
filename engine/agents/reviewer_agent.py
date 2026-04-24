import json
import logging
import time

import anthropic
from rich.console import Console

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
You are a quantitative research reviewer for an energy futures trading engine.
Your job is to evaluate whether a proposed trading hypothesis is worth backtesting.

Given a hypothesis, output a JSON object with exactly these keys:
  "decision"    — "approve" or "skip"
  "confidence"  — float 0.0 to 1.0 (how confident you are in this decision)
  "reason"      — one sentence explaining the decision
  "concerns"    — list of strings describing issues (empty list if approving cleanly)

Approve the hypothesis if ALL of:
- It describes a measurable, binary signal (something that either fires or doesn't)
- It can be implemented with standard LEAN indicators (SMA, RSI, BB, ATR, MACD)
- It is likely to generate at least {min_signals} signals per year on daily/hourly/minute bars
- It is meaningfully different from past experiments listed
- It is ok if hypothesis is tweaking the final results, it  hypothesis should not do blind parameter search.

Skip the hypothesis if ANY of:
- It requires more than {max_conditions} simultaneous conditions to all be true (rarely fires)
- It depends on data not available in QuantConnect (bid-ask spreads, order flow imbalance)
- It is nearly identical to a past failed experiment
- It is too vague to implement unambiguously
"""

USER_TEMPLATE = """\
== Past experiments ==
{past_results}

== Proposed hypothesis ==
Summary: {summary}
Rationale: {rationale}
Approach: {approach}

Evaluate and return your JSON decision.
"""

console = Console()


class ReviewerAgent:
    def __init__(self, client: anthropic.Anthropic, engine_config: dict | None = None):
        engine = engine_config or {}
        self.client = client
        self.model = engine.get("model", "claude-haiku-4-5")
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            min_signals=engine.get("min_signals_per_year", 15),
            max_conditions=engine.get("max_signal_conditions", 2),
        )

    def review(self, hypothesis: dict, past_results: str) -> str:
        """Returns 'approve' or 'skip'."""
        user_msg = USER_TEMPLATE.format(
            past_results=past_results or "None",
            summary=hypothesis.get("summary", ""),
            rationale=hypothesis.get("rationale", ""),
            approach=hypothesis.get("suggested_algorithm_approach", "")[:800],
        )
        messages = [{"role": "user", "content": user_msg}]

        for attempt in range(5):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=512,
                    system=self.system_prompt,
                    messages=messages,
                )
                break
            except anthropic.RateLimitError:
                wait = 60 * (attempt + 1)
                console.print(f"[yellow]Reviewer rate limit - waiting {wait}s...[/yellow]")
                time.sleep(wait)
        else:
            logger.warning("Reviewer: all rate limit retries exhausted, defaulting to approve")
            return "approve"

        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw = block.text.strip()
                break

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            import re
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError:
                    parsed = {}
            else:
                parsed = {}

        decision = parsed.get("decision", "approve").lower()
        reason = parsed.get("reason", "")
        concerns = parsed.get("concerns", [])
        confidence = parsed.get("confidence", 1.0)

        logger.info(
            "Reviewer decision=%s confidence=%.2f reason=%s",
            decision, confidence, reason,
        )

        marker = "[green]APPROVE[/green]" if decision == "approve" else "[yellow]SKIP[/yellow]"
        console.print(f"  [dim]Reviewer:[/dim] {marker}  {reason}")
        if concerns:
            for c in concerns:
                console.print(f"  [dim]  - {c}[/dim]")

        return "skip" if decision == "skip" else "approve"
