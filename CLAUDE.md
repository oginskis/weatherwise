# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start everything (weather MCP + news MCP + Streamlit) with one command
uv run python launcher.py

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_gnews_client.py -v

# Run a specific test
uv run pytest tests/test_gnews_client.py::test_search_returns_articles -v

# Install dependencies
uv sync

# Install with dev dependencies (pytest, respx)
uv sync --group dev
```

## Architecture

Three independent processes orchestrated by `launcher.py`:

```
Streamlit Chat UI (port 8501)
        │ async calls
        ▼
PydanticAI Agent (provider-agnostic, configured via .env)
   │                    │
   │ streamable-http    │ streamable-http
   ▼                    ▼
Weather MCP (8080)   News MCP (8081)
(pip: mcp-weather-   (custom FastMCP,
 server, no code)     wraps GNews.io)
   │                    │
   ▼                    ▼
Open-Meteo API       GNews.io API
(no key)             (free tier key)
```

**Key design decisions:**
- Weather MCP is an external pip package (`mcp-weather-server`) — no custom code, just start and use
- News MCP is custom-built following SRP: `server.py` (tool registration) → `gnews_client.py` (HTTP) → `models.py` (data contracts)
- Agent returns structured `AgentResponse` with optional `weather`/`articles` fields; UI renders them as styled cards
- LLM provider switched purely via `.env` — `pydantic-ai[google,openai,anthropic]` all installed

**Async in Streamlit:** `app.py` stores a persistent `asyncio` event loop in `st.session_state` and uses `loop.run_until_complete()`. Do NOT use `asyncio.run()` — it closes the loop after first use, breaking subsequent queries.

## Coding Standards (from agents.md)

- PEP 604 types: `str | None`, `list[str]` (not `Optional`, `List`)
- Type all function signatures
- Import order: stdlib → third-party → local (blank lines between)
- Never bare `except:` — catch specific types, always log context
- Single `httpx.AsyncClient` per service, reused across requests
- `pathlib.Path` for file paths, `is not None` for None checks
- All magic values as module-level constants in `config.py`

## Configuration

All config flows through `src/agent/config.py`. Environment variables loaded from `.env`:

```
LLM_MODEL=google-gla:gemini-3-flash-preview   # or openai:gpt-4o or anthropic:claude-sonnet-4-20250514
GOOGLE_API_KEY=...                              # matches the provider prefix above
GNEWS_API_KEY=...                               # GNews.io free tier key
```

## System Prompt

The agent prompt in `src/agent/agent.py` enforces strict topic confinement (weather + news only), prompt injection resistance, and a self-reflection check on news results for relevance/recency/quality before returning them. Changes to agent behavior start there.
