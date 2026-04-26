"""Live agent evals — runs prompts through the real PydanticAI agent and
verifies the response shape and grounding.

These tests are slow (each call is a real LLM round-trip plus MCP tool calls)
and consume model API quota. They are deselected by default. Run them
explicitly with::

    uv run pytest tests/evals/ -v -m eval

Prerequisites:
- Launcher running locally (``uv run python launcher.py``) so the three MCP
  servers are reachable on ports 8080/8081/8082.
- ``LLM_MODEL``, ``GOOGLE_API_KEY`` (or other provider) and ``GNEWS_API_KEY``
  set in ``.env``.

The eval will skip — not fail — if the MCP servers aren't reachable, so
running it without the launcher up just emits skips.
"""
import asyncio

import httpx
import pytest

from src.agent.config import (
    DISASTERS_CSV_PATH,
    DISASTERS_MCP_URL,
    NEWS_MCP_URL,
    WEATHER_MCP_URL,
)
from src.agent.models import AgentResponse
from .golden_dataset import DATASET, EvalCase
from .validators import find_hallucinations

pytestmark = pytest.mark.eval


def _mcp_servers_reachable() -> bool:
    """Quick TCP+HTTP probe of all three MCP server endpoints."""
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
def agent_runner():
    """Session-scoped fixture that returns a callable to run agent prompts."""
    if not _mcp_servers_reachable():
        pytest.skip(
            "MCP servers not reachable on 8080/8081/8082 — start the "
            "launcher (`uv run python launcher.py`) before running evals."
        )

    from src.agent.agent import agent  # imported lazily to avoid early MCP wiring

    loop = asyncio.new_event_loop()
    cache: dict[str, AgentResponse] = {}

    def run(prompt: str) -> AgentResponse:
        if prompt in cache:
            return cache[prompt]

        async def _go() -> AgentResponse:
            async with agent:
                result = await agent.run(prompt)
            return result.output

        cache[prompt] = loop.run_until_complete(_go())
        return cache[prompt]

    yield run
    loop.close()


@pytest.mark.parametrize(
    "case",
    DATASET,
    ids=[case.name for case in DATASET],
)
def test_eval_case_structure(case: EvalCase, agent_runner) -> None:
    """Hybrid-rule structural assertions: which response fields are populated."""
    response = agent_runner(case.prompt)

    if case.expect_weather:
        assert response.weather is not None, (
            f"{case.name}: weather field must be populated"
        )
    else:
        assert response.weather is None, (
            f"{case.name}: weather field must be null for non-weather prompts"
        )

    if case.expect_disasters_field:
        assert response.disasters is not None, (
            f"{case.name}: disasters field must be populated for direct "
            "disaster questions"
        )
        assert response.disasters.total_events > 0, (
            f"{case.name}: disasters.total_events must be > 0"
        )
    else:
        assert response.disasters is None, (
            f"{case.name}: disasters field must be null on weather-flow "
            "responses (hybrid rule)"
        )

    if case.expect_articles:
        assert response.articles is not None, (
            f"{case.name}: articles field must be populated"
        )

    for forbidden in case.forbidden_substrings_in_message:
        assert forbidden.lower() not in (response.message or "").lower(), (
            f"{case.name}: forbidden substring {forbidden!r} appeared in message"
        )


@pytest.mark.parametrize(
    "case",
    [c for c in DATASET if c.expect_disasters_field],
    ids=[c.name for c in DATASET if c.expect_disasters_field],
)
def test_eval_case_no_hallucinations(case: EvalCase, agent_runner) -> None:
    """Every dataset-range year referenced must correspond to a real EM-DAT event."""
    response = agent_runner(case.prompt)
    findings = find_hallucinations(
        response,
        csv_path=DISASTERS_CSV_PATH,
        grounded_country=case.grounded_country,
        grounded_disaster_type=case.grounded_disaster_type,
    )
    assert findings == [], (
        f"{case.name}: agent stated facts not present in EM-DAT:\n  "
        + "\n  ".join(f.model_dump_json() for f in findings)
    )


@pytest.mark.parametrize(
    "case",
    [c for c in DATASET if c.require_deadliest_event],
    ids=[c.name for c in DATASET if c.require_deadliest_event],
)
def test_eval_case_deadliest_event_populated(
    case: EvalCase, agent_runner
) -> None:
    """For 'deadliest'/'costliest' cases the deadliest_event_summary must be set."""
    response = agent_runner(case.prompt)
    assert response.disasters is not None, f"{case.name}: disasters field is null"
    assert response.disasters.deadliest_event_summary, (
        f"{case.name}: disasters.deadliest_event_summary must be a non-empty "
        "string for ranking-style prompts (the system prompt requires the "
        "agent to chain disaster_stats + query_disasters)."
    )
