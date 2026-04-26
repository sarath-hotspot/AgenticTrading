"""
Provider-agnostic LLM client abstraction.

Both AnthropicLLMClient and OpenAILLMClient expose the same two methods:
  complete(system, user, max_tokens)           — single-turn, no tools
  tool_loop(messages, system, tools, dispatch) — agentic tool-calling loop

All provider-specific message formats stay inside this module.
"""

import json
import time
from typing import Callable

from rich.console import Console

console = Console()


class AnthropicLLMClient:
    def __init__(self, client, model: str):
        import anthropic as _anthropic
        self._anthropic = _anthropic
        self.client = client
        self.model = model

    def _api_create(self, **kwargs):
        for attempt in range(5):
            try:
                return self.client.messages.create(**kwargs)
            except self._anthropic.RateLimitError:
                wait = 60 * (attempt + 1)
                console.print(f"[yellow]Rate limit — waiting {wait}s...[/yellow]")
                time.sleep(wait)
        return self.client.messages.create(**kwargs)

    def complete(self, system: str, user: str, max_tokens: int = 4096) -> str:
        response = self._api_create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def tool_loop(
        self,
        messages: list,
        system: str,
        tools: list,
        dispatch: Callable[[str, dict], str],
        max_tokens: int = 4096,
    ) -> str:
        # Work on a copy so we don't mutate the caller's list
        msgs = list(messages)
        while True:
            response = self._api_create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=msgs,
            )
            msgs.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    console.print(f"[dim]  -> {block.name}[/dim]")
                    result = dispatch(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            msgs.append({"role": "user", "content": tool_results})


class OpenAILLMClient:
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    @staticmethod
    def _to_oai_tools(tools: list) -> list:
        """Convert Anthropic-style tool defs to OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    def _api_create(self, **kwargs):
        import openai as _openai
        for attempt in range(5):
            try:
                return self.client.chat.completions.create(**kwargs)
            except _openai.RateLimitError:
                wait = 60 * (attempt + 1)
                console.print(f"[yellow]Rate limit — waiting {wait}s...[/yellow]")
                time.sleep(wait)
        return self.client.chat.completions.create(**kwargs)

    def complete(self, system: str, user: str, max_tokens: int = 4096) -> str:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user})
        response = self._api_create(model=self.model, max_tokens=max_tokens, messages=msgs)
        return response.choices[0].message.content or ""

    def tool_loop(
        self,
        messages: list,
        system: str,
        tools: list,
        dispatch: Callable[[str, dict], str],
        max_tokens: int = 4096,
    ) -> str:
        # OpenAI doesn't take system as a separate param — prepend as first message
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        oai_tools = self._to_oai_tools(tools)

        while True:
            response = self._api_create(
                model=self.model,
                max_tokens=max_tokens,
                tools=oai_tools,
                messages=msgs,
            )
            msg = response.choices[0].message

            # Append assistant turn as a plain dict for portability
            msg_dict: dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            msgs.append(msg_dict)

            if not msg.tool_calls:
                return msg.content or ""

            for tc in msg.tool_calls:
                console.print(f"[dim]  -> {tc.function.name}[/dim]")
                args = json.loads(tc.function.arguments)
                result = dispatch(tc.function.name, args)
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
