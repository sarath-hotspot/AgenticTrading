import json
import logging
import re
import time

import anthropic
from rich.console import Console

from engine.tools.storage import TOOL_STORAGE_READ, get_past_results_summary
from engine.tools.websearch import TOOL_WEB_SEARCH, web_search, format_search_results
from engine.tools.agent_memory import (
    read_memory, append_entry, ensure_header,
    TOOL_MEMORY_READ, TOOL_MEMORY_WRITE,
)

AGENT_NAME = "hypothesis_agent"
logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
You are a quantitative research hypothesis generator specialising in energy futures trading.
Your role is to propose novel, testable hypotheses for predicting large price moves (>=1%) \
in Crude Oil (CL) or Natural Gas (NG) futures.

Use the web_search tool to find recent academic or industry research on the topic.
Use the storage_read_past_results tool to review what has already been tried.

CRITICAL — The hypothesis MUST be implementable with LEAN built-in indicators ONLY:
  self.sma(symbol, period)          — simple moving average
  self.rsi(symbol, period)          — relative strength index
  self.bb(symbol, period, 2)        — Bollinger Bands
  self.atr(symbol, period)          — average true range
  self.macd(symbol, fast, slow, sig)— MACD

CRITICAL — The signal MUST use at most {max_conditions} condition(s):
  Good examples:
    - RSI < 30 → predict upward move (single condition, very tradeable)
    - SMA10 crosses above SMA30 → predict upward move (single condition)
    - Price closes above upper Bollinger Band → predict continuation
    - ATR expands above 20-day average → predict large move either direction
  Bad examples (do NOT propose these):
    - Wavelet decomposition (requires scipy, not in LEAN)
    - Order flow imbalance (requires tick data, not in LEAN)
    - 3+ simultaneous conditions (fires too rarely)
    - GARCH models (no built-in, complex to implement manually)
    - EIA calendar + volatility + divergence + volume all at once

The hypothesis should generate at least {min_signals} signals per year on daily or hourly bars.

After using the tools, output a JSON object (no markdown fences, no extra text) \
with exactly these keys:
  "summary"                      — one sentence describing the hypothesis
  "full_text"                    — detailed description of the signal and logic
  "rationale"                    — why this is novel compared to past attempts
  "suggested_algorithm_approach" — pseudocode or step-by-step description for implementation
"""

USER_TEMPLATE = """\
== USER CONFIG ==
{config_context}

Generate the next hypothesis to move us toward the goal.

Past experiment results:
{past_results}

Requirements:
- Must be meaningfully different from what has already been tried.
- Must be implementable with LEAN built-in indicators (SMA, RSI, BB, ATR, MACD) only.
- Must use at most TWO entry conditions so it actually fires frequently.
- Must include a way to measure out-of-sample prediction accuracy.
"""

console = Console()


class HypothesisAgent:
    def __init__(self, client: anthropic.Anthropic, config_context: str, engine_config: dict | None = None):
        engine = engine_config or {}
        self.client = client
        self.config_context = config_context
        self.model = engine.get("model", "claude-haiku-4-5")
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            min_signals=engine.get("min_signals_per_year", 15),
            max_conditions=engine.get("max_signal_conditions", 2),
        )
        self.tools = [TOOL_WEB_SEARCH, TOOL_STORAGE_READ, TOOL_MEMORY_READ, TOOL_MEMORY_WRITE]
        ensure_header(AGENT_NAME, "Hypothesis Agent Learnings")

    def generate(self, past_results_summary: str) -> dict:
        memory = read_memory(AGENT_NAME)
        system = self.system_prompt
        if memory:
            system = self.system_prompt + f"\n\n== PAST LEARNINGS (from memory) ==\n{memory}\n"

        user_msg = USER_TEMPLATE.format(
            config_context=self.config_context,
            past_results=past_results_summary,
        )
        messages = [{"role": "user", "content": user_msg}]
        raw = self._run_tool_loop(messages, system)
        return self._parse_hypothesis(raw)

    def _api_create(self, **kwargs):
        for attempt in range(5):
            try:
                return self.client.messages.create(**kwargs)
            except anthropic.RateLimitError:
                wait = 60 * (attempt + 1)
                console.print(f"[yellow]Rate limit hit - waiting {wait}s...[/yellow]")
                time.sleep(wait)
        return self.client.messages.create(**kwargs)

    def _run_tool_loop(self, messages: list, system: str = "") -> str:
        while True:
            response = self._api_create(
                model=self.model,
                max_tokens=4096,
                system=system,
                tools=self.tools,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    console.print(f"[dim]  -> {block.name}[/dim]")
                    logger.debug("Tool call: %s  args=%s", block.name, str(block.input)[:200])
                    result = self._dispatch(block.name, block.input)
                    logger.debug("Tool result: %s  -> %s", block.name, str(result)[:200])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "user", "content": tool_results})

    def _dispatch(self, name: str, args: dict) -> str:
        if name == "web_search":
            results = web_search(args.get("query", ""), args.get("num_results", 5))
            return format_search_results(results)
        if name == "storage_read_past_results":
            return get_past_results_summary(args.get("limit", 5))
        if name == "memory_read":
            return read_memory(AGENT_NAME) or "No memory entries yet."
        if name == "memory_write":
            title = args.get("title", "untitled")
            body = args.get("body", "")
            append_entry(AGENT_NAME, title, body)
            logger.info("Memory entry written: %s", title)
            return f"Learning saved: {title}"
        return f"Unknown tool: {name}"

    def _parse_hypothesis(self, raw: str) -> dict:
        raw = raw.strip()
        # Try direct parse first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Strip markdown fences
        fenced = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        fenced = re.sub(r"```\s*$", "", fenced, flags=re.MULTILINE).strip()
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass
        # Extract first {...} block from prose
        match = re.search(r"\{[\s\S]*\}", fenced)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {
            "summary": raw[:120],
            "full_text": raw,
            "rationale": "Could not parse structured output.",
            "suggested_algorithm_approach": "",
        }
