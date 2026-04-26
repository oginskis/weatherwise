"""Shared fixtures for the agent eval suite.

The :func:`agent_runner` fixture is session-scoped: it builds one event loop,
caches `(response, all_messages, disaster_card)` per prompt, and probes the
three MCP servers once at startup. If they are unreachable, all eval tests
in this directory skip cleanly rather than failing.

The disaster card is built deterministically from the run's tool returns
by :func:`src.agent.disaster_card.build_disaster_card` — the LLM is NOT in
this loop, so structured-data hallucination is impossible by construction.
Grounding assertions inspect this built card, not a model-emitted field.
"""
import asyncio
from collections.abc import Callable, Iterator

import httpx
import pytest
from pydantic_ai.messages import ModelMessage

from src.agent.config import (
    DISASTERS_MCP_URL,
    NEWS_MCP_URL,
    WEATHER_MCP_URL,
)
from src.agent.disaster_card import build_disaster_card
from src.agent.models import AgentResponse, DisasterSummaryView

AgentRunResult = tuple[
    AgentResponse, list[ModelMessage], DisasterSummaryView | None
]


def _mcp_servers_reachable() -> bool:
    """Quick JSON-RPC initialize probe of all three MCP server endpoints."""
    init_body = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "eval-probe", "version": "0.1.0"},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    for url in (WEATHER_MCP_URL, NEWS_MCP_URL, DISASTERS_MCP_URL):
        try:
            response = httpx.post(url, headers=headers, json=init_body, timeout=3.0)
        except httpx.HTTPError:
            return False
        if response.status_code not in (200, 400, 405, 406):
            return False
    return True


@pytest.fixture(scope="session")
def eval_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Session-scoped event loop reused across all eval tests.

    Sharing the loop avoids "Event loop is closed" errors that arise when
    a per-test ``asyncio.run`` tries to clean up HTTP clients that were
    opened on a different loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def agent_runner(
    eval_loop: asyncio.AbstractEventLoop,
) -> Callable[[str], AgentRunResult]:
    """Returns a callable that runs a prompt and returns (response, messages).

    Caches results by prompt across the entire eval session so the four
    grounding and trajectory tests for one case share a single LLM call.
    """
    if not _mcp_servers_reachable():
        pytest.skip(
            "MCP servers not reachable on 8080/8081/8082 — start the "
            "launcher (`uv run python launcher.py`) before running evals."
        )

    from src.agent.agent import agent  # imported lazily to avoid early MCP wiring

    cache: dict[str, AgentRunResult] = {}

    def run(prompt: str) -> AgentRunResult:
        if prompt in cache:
            return cache[prompt]

        async def _go() -> AgentRunResult:
            async with agent:
                result = await agent.run(prompt)
            # Use new_messages (this turn only) consistently for both card
            # construction and trajectory assertions. all_messages would
            # also include prior-turn tool calls if the agent were ever
            # run in a multi-turn context — which would inflate
            # max_tool_calls budgets unexpectedly.
            new_messages = result.new_messages()
            return (
                result.output,
                new_messages,
                build_disaster_card(new_messages),
            )

        cache[prompt] = eval_loop.run_until_complete(_go())
        return cache[prompt]

    return run
