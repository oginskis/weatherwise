# Weather & News Chat App — Design Spec

## Overview

A Streamlit chat application that answers questions about current weather and latest news. It uses PydanticAI as the agent orchestrator with Gemini 3 Flash as the LLM. Real-time data access happens through two MCP servers communicating over streamable-http transport.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit Chat UI                   │
│         (st.chat_message / inline cards)             │
└──────────────────────┬──────────────────────────────┘
                       │ async calls
                       ▼
┌─────────────────────────────────────────────────────┐
│              PydanticAI Agent                        │
│   model: google-gla:gemini-3-flash-preview          │
│   toolsets: [weather_mcp, news_mcp]                 │
└──────────┬──────────────────────┬───────────────────┘
           │ streamable-http      │ streamable-http
           ▼                      ▼
┌─────────────────────┐  ┌────────────────────────────┐
│  Weather MCP Server │  │   News MCP Server          │
│  isdaniel/          │  │   (custom, FastMCP)         │
│  mcp_weather_server │  │   wraps GNews.io API       │
│  port 8080          │  │   port 8081                 │
└─────────┬───────────┘  └──────────┬─────────────────┘
          │ HTTP                     │ HTTP
          ▼                          ▼
   Open-Meteo API              GNews.io API
   (no key needed)          (free tier, API key)
```

## Technology Stack

| Component        | Technology                           | Notes                                      |
| ---------------- | ------------------------------------ | ------------------------------------------ |
| Weather MCP      | `mcp-weather-server` (pip)           | streamable-http, port 8080, no API key     |
| News MCP         | Custom FastMCP server (Python)       | streamable-http, port 8081, GNews.io       |
| Agent            | PydanticAI                           | `google-gla:gemini-3-flash-preview`        |
| UI               | Streamlit                            | Chat interface with inline cards           |
| Launcher         | `launcher.py`                        | Spawns all 3 processes, health checks      |
| Package manager  | `uv`                                 | Single `pyproject.toml`                    |
| Coding standards | `agents.md`                          | SOLID, typing, error handling conventions  |

## Project Structure

```
ai-training-weather/
├── pyproject.toml                  # uv project, all dependencies
├── launcher.py                     # Single entry point — starts all 3 processes
├── agents.md                       # Coding standards and conventions
├── .env                            # API keys (GNEWS_API_KEY, GOOGLE_API_KEY)
├── .env.example                    # Template for required env vars
├── .gitignore
│
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent.py                # PydanticAI agent definition + MCP toolset wiring
│   │   └── config.py               # Agent config (model, MCP server URLs, etc.)
│   │
│   ├── mcp_servers/
│   │   └── news/
│   │       ├── __init__.py
│   │       ├── server.py           # FastMCP server + tool registration
│   │       ├── gnews_client.py     # GNews.io API client (single responsibility)
│   │       └── models.py           # Pydantic models for API responses
│   │
│   └── ui/
│       ├── __init__.py
│       ├── app.py                  # Streamlit entry point + chat loop
│       ├── components/
│       │   ├── __init__.py
│       │   ├── weather_card.py     # Inline weather card renderer
│       │   └── news_card.py        # Inline news article card renderer
│       └── styles/
│           └── custom.css          # Custom Streamlit styling
│
└── docs/
    └── superpowers/
        └── specs/
```

## Components

### 1. Weather MCP Server

External dependency: `mcp-weather-server` (pip package by isdaniel).

- Started via `python -m mcp_weather_server --mode streamable-http --port 8080`
- Exposes tools: `get_current_weather`, `get_weather_forecast`, `get_air_quality`, `get_weather_details`, `get_weather_by_datetime_range`, `get_current_datetime`, `get_timezone_info`, `convert_time`
- Calls Open-Meteo API (free, no API key)
- No custom code needed — install and run

**Trustworthiness audit passed**: clean code, no data exfiltration, mainstream dependencies only, credible maintainer (11+ year GitHub account, 45 stars, Apache 2.0 license).

### 2. News MCP Server (Custom)

Custom-built FastMCP server wrapping GNews.io API.

**Tools:**

| Tool               | Description                          | Parameters                                                        |
| ------------------- | ------------------------------------ | ----------------------------------------------------------------- |
| `search_news`       | Search for news articles by keyword  | `query` (str), `lang` (str, default "en"), `max_results` (int, default 5) |
| `get_top_headlines`  | Get top headlines by category/country | `category` (str, optional), `country` (str, optional), `max_results` (int, default 5) |

**Internal structure (SRP):**

- `models.py` — Pydantic models: `Article`, `SearchResponse`. Data contracts only.
- `gnews_client.py` — `GNewsClient` class wrapping `httpx.AsyncClient`. Handles HTTP calls, returns typed models. Reads `GNEWS_API_KEY` from env. Only module that knows about GNews API details.
- `server.py` — FastMCP server definition. Registers tools, delegates to `GNewsClient`. Knows nothing about HTTP calls or API structure.

**Transport:** streamable-http on port 8081.

**GNews.io free tier:** 100 requests/day, 10 articles/request, 12-hour delay, registration via email or Google OAuth, no credit card.

### 3. PydanticAI Agent

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

weather_mcp = MCPServerStreamableHTTP(WEATHER_MCP_URL)
news_mcp = MCPServerStreamableHTTP(NEWS_MCP_URL)

agent = Agent(
    LLM_MODEL,
    toolsets=[weather_mcp, news_mcp],
    result_type=AgentResponse,
    system_prompt="..."
)
```

**Structured output model:**

```python
class WeatherData(BaseModel):
    location: str
    temperature: float
    conditions: str
    humidity: float | None = None
    wind_speed: float | None = None

class ArticleData(BaseModel):
    title: str
    description: str
    source: str
    url: str
    image_url: str | None = None

class AgentResponse(BaseModel):
    message: str                              # Natural language response
    weather: WeatherData | None = None        # Populated when weather was queried
    articles: list[ArticleData] | None = None # Populated when news was queried
```

The agent returns structured output so the UI can render weather and news as styled cards while keeping the conversational message as text.

### 4. Streamlit Chat UI

- `st.chat_input` for user input, `st.chat_message` for message display
- Message history persisted in `st.session_state`
- Async agent calls via `asyncio.run()`
- Parses `AgentResponse`:
  - `message` rendered as markdown text
  - `weather` rendered via `weather_card.py` (temperature, conditions, icon)
  - `articles` rendered via `news_card.py` (title, source, clickable link, image)
- Custom CSS for clean, sleek card styling
- Cards displayed inline within the chat thread

### 5. Launcher

`launcher.py` — single entry point to start everything:

- Uses `subprocess.Popen` to manage 3 child processes
- Startup order: Weather MCP (port 8080) → News MCP (port 8081) → Streamlit (port 8501)
- Health check: pings MCP server endpoints before starting Streamlit
- Graceful shutdown: catches `SIGINT`/`SIGTERM`, terminates children in reverse order
- Loads config from `.env` via `python-dotenv`

**Run command:** `uv run python launcher.py`

### 6. Configuration

**`config.py`** — centralized, no scattered magic values:

```python
WEATHER_MCP_URL: str = "http://localhost:8080/mcp"
NEWS_MCP_URL: str = "http://localhost:8081/mcp"
WEATHER_MCP_PORT: int = 8080
NEWS_MCP_PORT: int = 8081
STREAMLIT_PORT: int = 8501
LLM_MODEL: str = "google-gla:gemini-3-flash-preview"
```

**`.env`:**

```
GNEWS_API_KEY=your_key_here
GOOGLE_API_KEY=your_gemini_key_here
```

## Data Flow

User types: "What's the weather in Riga and today's tech news?"

1. `app.py` sends message to PydanticAI agent (async)
2. Agent (Gemini) decides it needs both weather + news tools
3. Agent calls weather MCP tool → streamable-http → `localhost:8080/mcp` → Open-Meteo API → returns weather data
4. Agent calls news MCP tool → streamable-http → `localhost:8081/mcp` → GNews.io API → returns articles
5. Agent composes a unified `AgentResponse` with structured weather, articles, and a natural language message
6. `app.py` parses the response:
   - Renders `message` as markdown
   - Renders `weather` as a styled weather card (temperature, conditions, icon)
   - Renders `articles` as clickable news cards (title, source, link)
7. Cards appear inline in the chat thread

## Error Handling

- MCP server unreachable: agent gracefully reports which data source is unavailable
- GNews API rate limit (100/day): `gnews_client.py` raises a typed exception, tool returns a user-friendly message
- Invalid API key: caught at startup by the launcher health check
- Network timeouts: `httpx.AsyncClient` configured with sensible timeouts, specific exceptions caught and logged

## Dependencies

```toml
[project]
name = "ai-training-weather"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "pydantic-ai[google]",
    "mcp-weather-server",
    "mcp",
    "httpx",
    "streamlit",
    "python-dotenv",
    "pydantic",
]
```
