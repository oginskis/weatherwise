# Weather & News Chat App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit chat app that answers weather and news questions using PydanticAI with MCP servers for real-time data access.

**Architecture:** Two MCP servers (weather: existing pip package, news: custom FastMCP) communicate over streamable-http with a PydanticAI agent. Streamlit renders a chat UI with inline weather/news cards. A launcher script starts all three processes.

**Tech Stack:** Python 3.10+, PydanticAI, FastMCP, Streamlit, httpx, uv

**Spec:** `docs/superpowers/specs/2026-03-22-weather-news-chat-app-design.md`
**Coding Standards:** `agents.md`

---

## File Map

| File | Responsibility |
| --- | --- |
| `pyproject.toml` | Project metadata, dependencies |
| `.env.example` | Template for required env vars |
| `.gitignore` | Git ignore patterns |
| `src/agent/__init__.py` | Package init |
| `src/agent/config.py` | Centralized config — env-driven, module-level constants |
| `src/agent/models.py` | Pydantic models for agent structured output (AgentResponse, WeatherData, ArticleData) |
| `src/agent/agent.py` | PydanticAI agent definition, MCP toolset wiring |
| `src/mcp_servers/__init__.py` | Package init |
| `src/mcp_servers/news/__init__.py` | Package init |
| `src/mcp_servers/news/models.py` | Pydantic models for GNews API response |
| `src/mcp_servers/news/gnews_client.py` | GNews.io HTTP client (single httpx.AsyncClient) |
| `src/mcp_servers/news/server.py` | FastMCP server with tool registration, delegates to client |
| `src/ui/__init__.py` | Package init |
| `src/ui/app.py` | Streamlit entry point, chat loop, response rendering |
| `src/ui/components/__init__.py` | Package init |
| `src/ui/components/weather_card.py` | Weather card HTML renderer |
| `src/ui/components/news_card.py` | News article card HTML renderer |
| `src/ui/styles/custom.css` | Custom card styling |
| `launcher.py` | Single entry point — spawns MCP servers + Streamlit |
| `tests/test_gnews_client.py` | Unit tests for GNews client |
| `tests/test_news_models.py` | Unit tests for news models |
| `tests/test_agent_models.py` | Unit tests for agent response models |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: all `__init__.py` files

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "ai-training-weather"
version = "0.1.0"
description = "Streamlit chat app for weather and news powered by PydanticAI + MCP"
requires-python = ">=3.10"
dependencies = [
    "pydantic-ai[google,openai,anthropic]",
    "mcp-weather-server",
    "mcp",
    "httpx",
    "streamlit",
    "python-dotenv",
    "pydantic",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "respx",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
```

- [ ] **Step 2: Create `.env.example`**

```
# LLM — switch provider by changing these two values
LLM_MODEL=google-gla:gemini-3-flash-preview
GOOGLE_API_KEY=your_gemini_key_here

# Alternatively:
# LLM_MODEL=openai:gpt-4o
# OPENAI_API_KEY=your_key
#
# LLM_MODEL=anthropic:claude-sonnet-4-20250514
# ANTHROPIC_API_KEY=your_key

# News
GNEWS_API_KEY=your_key_here
```

- [ ] **Step 3: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
.venv/
*.egg-info/
dist/
.pytest_cache/
.mypy_cache/
```

- [ ] **Step 4: Create all `__init__.py` files**

Create empty `__init__.py` in:
- `src/agent/__init__.py`
- `src/mcp_servers/__init__.py`
- `src/mcp_servers/news/__init__.py`
- `src/ui/__init__.py`
- `src/ui/components/__init__.py`

- [ ] **Step 5: Run `uv sync`**

Run: `uv sync`
Expected: Dependencies installed, `uv.lock` created.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .env.example .gitignore src/
git commit -m "feat: scaffold project with pyproject.toml and package structure"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `src/agent/config.py`

- [ ] **Step 1: Create `src/agent/config.py`**

```python
import os

from dotenv import load_dotenv

load_dotenv()

# MCP server endpoints
WEATHER_MCP_URL: str = "http://localhost:8080/mcp"
NEWS_MCP_URL: str = "http://localhost:8081/mcp"

# MCP server ports
WEATHER_MCP_PORT: int = 8080
NEWS_MCP_PORT: int = 8081

# Streamlit
STREAMLIT_PORT: int = 8501

# LLM — provider resolved automatically by PydanticAI from the string prefix
LLM_MODEL: str = os.environ["LLM_MODEL"]

# News API
GNEWS_API_KEY: str = os.environ["GNEWS_API_KEY"]
GNEWS_BASE_URL: str = "https://gnews.io/api/v4"
GNEWS_DEFAULT_LANG: str = "en"
GNEWS_DEFAULT_MAX_RESULTS: int = 5
GNEWS_REQUEST_TIMEOUT_SECONDS: float = 10.0
```

- [ ] **Step 2: Commit**

```bash
git add src/agent/config.py
git commit -m "feat: add centralized env-driven config module"
```

---

### Task 3: News MCP Server — Pydantic Models

**Files:**
- Create: `src/mcp_servers/news/models.py`
- Create: `tests/test_news_models.py`

- [ ] **Step 1: Write failing test for news models**

Create `tests/test_news_models.py`:

```python
from src.mcp_servers.news.models import Article, SearchResponse


def test_article_from_gnews_payload() -> None:
    payload = {
        "title": "Test headline",
        "description": "A test article",
        "content": "Full content here",
        "url": "https://example.com/article",
        "image": "https://example.com/image.jpg",
        "publishedAt": "2026-03-22T10:00:00Z",
        "source": {"name": "Test Source", "url": "https://example.com"},
    }
    article = Article.from_gnews(payload)
    assert article.title == "Test headline"
    assert article.description == "A test article"
    assert article.source_name == "Test Source"
    assert article.url == "https://example.com/article"
    assert article.image_url == "https://example.com/image.jpg"


def test_article_from_gnews_missing_image() -> None:
    payload = {
        "title": "No image",
        "description": "Desc",
        "content": "Content",
        "url": "https://example.com",
        "image": None,
        "publishedAt": "2026-03-22T10:00:00Z",
        "source": {"name": "Src", "url": "https://example.com"},
    }
    article = Article.from_gnews(payload)
    assert article.image_url is None


def test_search_response_parses_articles() -> None:
    payload = {
        "totalArticles": 1,
        "articles": [
            {
                "title": "One",
                "description": "Desc",
                "content": "Content",
                "url": "https://example.com",
                "image": None,
                "publishedAt": "2026-03-22T10:00:00Z",
                "source": {"name": "Src", "url": "https://example.com"},
            }
        ],
    }
    response = SearchResponse.from_gnews(payload)
    assert response.total_articles == 1
    assert len(response.articles) == 1
    assert response.articles[0].title == "One"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_news_models.py -v`
Expected: FAIL — `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement news models**

Create `src/mcp_servers/news/models.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Article(BaseModel):
    title: str
    description: str
    source_name: str
    url: str
    image_url: str | None
    published_at: str

    @classmethod
    def from_gnews(cls, data: dict[str, Any]) -> Article:
        source = data.get("source", {})
        return cls(
            title=data["title"],
            description=data.get("description", ""),
            source_name=source.get("name", "Unknown"),
            url=data["url"],
            image_url=data.get("image"),
            published_at=data.get("publishedAt", ""),
        )


class SearchResponse(BaseModel):
    total_articles: int
    articles: list[Article]

    @classmethod
    def from_gnews(cls, data: dict[str, Any]) -> SearchResponse:
        articles = [
            Article.from_gnews(article)
            for article in data.get("articles", [])
        ]
        return cls(
            total_articles=data.get("totalArticles", 0),
            articles=articles,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_news_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/news/models.py tests/test_news_models.py
git commit -m "feat: add Pydantic models for GNews API response"
```

---

### Task 4: News MCP Server — GNews HTTP Client

**Files:**
- Create: `src/mcp_servers/news/gnews_client.py`
- Create: `tests/test_gnews_client.py`

- [ ] **Step 1: Write failing test for GNews client**

Create `tests/test_gnews_client.py`:

```python
import httpx
import pytest
import respx

from src.mcp_servers.news.gnews_client import GNewsClient, GNewsAPIError

GNEWS_BASE_URL = "https://gnews.io/api/v4"


@pytest.fixture
def client() -> GNewsClient:
    return GNewsClient(api_key="test-key", base_url=GNEWS_BASE_URL)


@respx.mock
@pytest.mark.asyncio
async def test_search_returns_articles(client: GNewsClient) -> None:
    respx.get(f"{GNEWS_BASE_URL}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "totalArticles": 1,
                "articles": [
                    {
                        "title": "Test",
                        "description": "Desc",
                        "content": "Content",
                        "url": "https://example.com",
                        "image": None,
                        "publishedAt": "2026-03-22T10:00:00Z",
                        "source": {"name": "Src", "url": "https://example.com"},
                    }
                ],
            },
        )
    )
    response = await client.search("test query")
    assert response.total_articles == 1
    assert response.articles[0].title == "Test"


@respx.mock
@pytest.mark.asyncio
async def test_search_raises_on_api_error(client: GNewsClient) -> None:
    respx.get(f"{GNEWS_BASE_URL}/search").mock(
        return_value=httpx.Response(403, json={"errors": ["Forbidden"]})
    )
    with pytest.raises(GNewsAPIError, match="403"):
        await client.search("test query")


@respx.mock
@pytest.mark.asyncio
async def test_top_headlines_returns_articles(client: GNewsClient) -> None:
    respx.get(f"{GNEWS_BASE_URL}/top-headlines").mock(
        return_value=httpx.Response(
            200,
            json={
                "totalArticles": 1,
                "articles": [
                    {
                        "title": "Headline",
                        "description": "Desc",
                        "content": "Content",
                        "url": "https://example.com",
                        "image": "https://example.com/img.jpg",
                        "publishedAt": "2026-03-22T10:00:00Z",
                        "source": {"name": "Src", "url": "https://example.com"},
                    }
                ],
            },
        )
    )
    response = await client.top_headlines()
    assert response.articles[0].title == "Headline"
    assert response.articles[0].image_url == "https://example.com/img.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gnews_client.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement GNews client**

Create `src/mcp_servers/news/gnews_client.py`:

```python
from __future__ import annotations

import logging

import httpx

from .models import SearchResponse

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS: float = 10.0
DEFAULT_LANG: str = "en"
DEFAULT_MAX_RESULTS: int = 5


class GNewsAPIError(Exception):
    """Raised when the GNews API returns a non-success status code."""


class GNewsClient:
    """HTTP client for the GNews.io API. Reuses a single httpx.AsyncClient."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://gnews.io/api/v4",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._http = httpx.AsyncClient(timeout=timeout)

    async def search(
        self,
        query: str,
        lang: str = DEFAULT_LANG,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> SearchResponse:
        """Search for news articles by keyword."""
        params = {
            "q": query,
            "lang": lang,
            "max": max_results,
            "apikey": self._api_key,
        }
        return await self._request("/search", params)

    async def top_headlines(
        self,
        category: str | None = None,
        country: str | None = None,
        lang: str = DEFAULT_LANG,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> SearchResponse:
        """Get top headlines, optionally filtered by category or country."""
        params: dict[str, str | int] = {
            "lang": lang,
            "max": max_results,
            "apikey": self._api_key,
        }
        if category is not None:
            params["category"] = category
        if country is not None:
            params["country"] = country
        return await self._request("/top-headlines", params)

    async def _request(
        self, endpoint: str, params: dict[str, str | int]
    ) -> SearchResponse:
        """Make a GET request and parse the response."""
        url = f"{self._base_url}{endpoint}"
        try:
            response = await self._http.get(url, params=params)
        except httpx.HTTPError as exc:
            logger.error("HTTP request failed for %s: %s", url, exc)
            raise GNewsAPIError(f"Request failed: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "GNews API error %d for %s: %s",
                response.status_code,
                url,
                response.text,
            )
            raise GNewsAPIError(
                f"GNews API returned {response.status_code}: {response.text}"
            )

        return SearchResponse.from_gnews(response.json())

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_gnews_client.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/news/gnews_client.py tests/test_gnews_client.py
git commit -m "feat: add GNews.io HTTP client with error handling"
```

---

### Task 5: News MCP Server — FastMCP Server

**Files:**
- Create: `src/mcp_servers/news/server.py`

- [ ] **Step 1: Implement the FastMCP news server**

Create `src/mcp_servers/news/server.py`:

```python
from __future__ import annotations

import json
import logging
import os
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.agent.config import NEWS_MCP_PORT
from .gnews_client import GNewsAPIError, GNewsClient

load_dotenv()

logger = logging.getLogger(__name__)

NEWS_MCP_HOST: str = "127.0.0.1"

mcp = FastMCP("news-server", stateless_http=True, json_response=True)

_client: GNewsClient | None = None


def _get_client() -> GNewsClient:
    """Lazily initialize the GNews client."""
    global _client
    if _client is None:
        api_key = os.environ.get("GNEWS_API_KEY", "")
        if not api_key:
            logger.error("GNEWS_API_KEY environment variable is not set")
            raise RuntimeError("GNEWS_API_KEY is required")
        _client = GNewsClient(api_key=api_key)
    return _client


@mcp.tool()
async def search_news(
    query: str, lang: str = "en", max_results: int = 5
) -> str:
    """Search for news articles by keyword.

    Args:
        query: Search term (e.g. "artificial intelligence", "climate change")
        lang: Language code (default: "en")
        max_results: Number of articles to return, 1-10 (default: 5)
    """
    client = _get_client()
    try:
        response = await client.search(query, lang=lang, max_results=max_results)
    except GNewsAPIError as exc:
        logger.error("search_news failed for query=%s: %s", query, exc)
        return json.dumps({"error": str(exc)})

    return json.dumps(
        [article.model_dump() for article in response.articles],
        ensure_ascii=False,
    )


@mcp.tool()
async def get_top_headlines(
    category: str | None = None,
    country: str | None = None,
    lang: str = "en",
    max_results: int = 5,
) -> str:
    """Get top news headlines, optionally filtered by category or country.

    Args:
        category: News category (e.g. "technology", "sports", "business")
        country: Country code (e.g. "us", "gb", "de")
        lang: Language code (default: "en")
        max_results: Number of articles to return, 1-10 (default: 5)
    """
    client = _get_client()
    try:
        response = await client.top_headlines(
            category=category, country=country, lang=lang, max_results=max_results
        )
    except GNewsAPIError as exc:
        logger.error("get_top_headlines failed: %s", exc)
        return json.dumps({"error": str(exc)})

    return json.dumps(
        [article.model_dump() for article in response.articles],
        ensure_ascii=False,
    )


def main() -> None:
    """Entry point for the news MCP server."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    mcp.run(transport="streamable-http", host=NEWS_MCP_HOST, port=NEWS_MCP_PORT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test the server starts**

Create a `.env` file with your real `GNEWS_API_KEY` first, then:

Run: `timeout 5 uv run python -m src.mcp_servers.news.server || true`
Expected: Server starts listening on port 8081 (then times out after 5s — that's fine).

- [ ] **Step 3: Commit**

```bash
git add src/mcp_servers/news/server.py
git commit -m "feat: add FastMCP news server with search and headlines tools"
```

---

### Task 6: Agent Response Models

**Files:**
- Create: `src/agent/models.py`
- Create: `tests/test_agent_models.py`

- [ ] **Step 1: Write failing test for agent models**

Create `tests/test_agent_models.py`:

```python
from src.agent.models import AgentResponse, ArticleData, WeatherData


def test_agent_response_weather_only() -> None:
    response = AgentResponse(
        message="It's sunny in Riga.",
        weather=WeatherData(
            location="Riga",
            temperature=22.5,
            conditions="Sunny",
        ),
    )
    assert response.weather is not None
    assert response.weather.temperature == 22.5
    assert response.articles is None


def test_agent_response_news_only() -> None:
    response = AgentResponse(
        message="Here are the latest headlines.",
        articles=[
            ArticleData(
                title="Big News",
                description="Something happened",
                source="Reuters",
                url="https://example.com",
            )
        ],
    )
    assert response.weather is None
    assert response.articles is not None
    assert len(response.articles) == 1


def test_agent_response_both() -> None:
    response = AgentResponse(
        message="Weather and news for you.",
        weather=WeatherData(
            location="Riga",
            temperature=15.0,
            conditions="Cloudy",
            humidity=80.0,
            wind_speed=5.2,
        ),
        articles=[
            ArticleData(
                title="Tech News",
                description="AI update",
                source="TechCrunch",
                url="https://example.com",
                image_url="https://example.com/img.jpg",
            )
        ],
    )
    assert response.weather is not None
    assert response.articles is not None
    assert response.weather.humidity == 80.0
    assert response.articles[0].image_url == "https://example.com/img.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agent_models.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement agent models**

Create `src/agent/models.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


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
    message: str
    weather: WeatherData | None = None
    articles: list[ArticleData] | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_agent_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent/models.py tests/test_agent_models.py
git commit -m "feat: add agent response models (WeatherData, ArticleData, AgentResponse)"
```

---

### Task 7: PydanticAI Agent Definition

**Files:**
- Create: `src/agent/agent.py`

- [ ] **Step 1: Implement the agent module**

Create `src/agent/agent.py`:

```python
from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

from .config import LLM_MODEL, NEWS_MCP_URL, WEATHER_MCP_URL
from .models import AgentResponse

SYSTEM_PROMPT: str = (
    "You are a helpful assistant that answers questions about current weather "
    "and latest news. Always use the available tools to fetch real-time data — "
    "never guess or make up weather conditions or news articles. When the user "
    "asks about weather, use weather tools. When they ask about news, use news "
    "tools. You may use both in a single response when appropriate. Return "
    "structured data so the UI can render rich cards."
)

weather_mcp = MCPServerStreamableHTTP(WEATHER_MCP_URL)
news_mcp = MCPServerStreamableHTTP(NEWS_MCP_URL)

agent = Agent(
    LLM_MODEL,
    output_type=AgentResponse,
    system_prompt=SYSTEM_PROMPT,
    toolsets=[weather_mcp, news_mcp],
)
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from src.agent.agent import agent; print(type(agent))"`
Expected: `<class 'pydantic_ai.agent.Agent'>`

(This requires `.env` with `LLM_MODEL` and `GNEWS_API_KEY` set.)

- [ ] **Step 3: Commit**

```bash
git add src/agent/agent.py
git commit -m "feat: add PydanticAI agent with MCP toolsets and structured output"
```

---

### Task 8: UI — Weather Card Component

**Files:**
- Create: `src/ui/components/weather_card.py`

- [ ] **Step 1: Implement weather card renderer**

Create `src/ui/components/weather_card.py`:

```python
from __future__ import annotations

import streamlit as st

from src.agent.models import WeatherData

WEATHER_ICONS: dict[str, str] = {
    "sunny": "☀️",
    "clear": "☀️",
    "cloudy": "☁️",
    "overcast": "☁️",
    "rain": "🌧️",
    "drizzle": "🌦️",
    "snow": "❄️",
    "thunderstorm": "⛈️",
    "fog": "🌫️",
    "mist": "🌫️",
    "wind": "💨",
}

DEFAULT_ICON: str = "🌡️"


def _resolve_icon(conditions: str) -> str:
    """Match weather conditions to an icon."""
    conditions_lower = conditions.lower()
    for keyword, icon in WEATHER_ICONS.items():
        if keyword in conditions_lower:
            return icon
    return DEFAULT_ICON


def render_weather_card(weather: WeatherData) -> None:
    """Render an inline weather card in Streamlit."""
    icon = _resolve_icon(weather.conditions)
    html = f"""
    <div class="weather-card">
        <div class="weather-card-header">
            <span class="weather-icon">{icon}</span>
            <span class="weather-location">{weather.location}</span>
        </div>
        <div class="weather-card-temp">{weather.temperature:.1f}°C</div>
        <div class="weather-card-conditions">{weather.conditions}</div>
        <div class="weather-card-details">
    """
    if weather.humidity is not None:
        html += f'<span>💧 {weather.humidity:.0f}%</span>'
    if weather.wind_speed is not None:
        html += f'<span>💨 {weather.wind_speed:.1f} km/h</span>'
    html += "</div></div>"

    st.html(html)
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/components/weather_card.py
git commit -m "feat: add weather card UI component"
```

---

### Task 9: UI — News Card Component

**Files:**
- Create: `src/ui/components/news_card.py`

- [ ] **Step 1: Implement news card renderer**

Create `src/ui/components/news_card.py`:

```python
from __future__ import annotations

import streamlit as st

from src.agent.models import ArticleData


def render_news_card(article: ArticleData) -> None:
    """Render an inline news article card in Streamlit."""
    image_html = ""
    if article.image_url is not None:
        image_html = (
            f'<img class="news-card-image" src="{article.image_url}" '
            f'alt="{article.title}" />'
        )

    html = f"""
    <div class="news-card">
        {image_html}
        <div class="news-card-body">
            <a class="news-card-title" href="{article.url}" target="_blank">
                {article.title}
            </a>
            <div class="news-card-description">{article.description}</div>
            <div class="news-card-source">{article.source}</div>
        </div>
    </div>
    """
    st.html(html)


def render_news_cards(articles: list[ArticleData]) -> None:
    """Render a list of news article cards."""
    for article in articles:
        render_news_card(article)
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/components/news_card.py
git commit -m "feat: add news card UI component"
```

---

### Task 10: UI — Custom CSS

**Files:**
- Create: `src/ui/styles/custom.css`

- [ ] **Step 1: Create custom CSS for cards**

Create `src/ui/styles/custom.css`:

```css
/* Weather Card */
.weather-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    padding: 1.2rem;
    color: white;
    margin: 0.5rem 0;
    max-width: 320px;
}

.weather-card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}

.weather-icon {
    font-size: 1.5rem;
}

.weather-location {
    font-size: 1.1rem;
    font-weight: 600;
}

.weather-card-temp {
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1.1;
}

.weather-card-conditions {
    font-size: 0.95rem;
    opacity: 0.9;
    margin-bottom: 0.5rem;
}

.weather-card-details {
    display: flex;
    gap: 1rem;
    font-size: 0.85rem;
    opacity: 0.85;
}

/* News Card */
.news-card {
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    overflow: hidden;
    margin: 0.5rem 0;
    background: white;
    max-width: 480px;
}

.news-card-image {
    width: 100%;
    height: 160px;
    object-fit: cover;
}

.news-card-body {
    padding: 0.8rem 1rem;
}

.news-card-title {
    font-size: 1rem;
    font-weight: 600;
    color: #1a1a2e;
    text-decoration: none;
    display: block;
    margin-bottom: 0.3rem;
}

.news-card-title:hover {
    color: #667eea;
}

.news-card-description {
    font-size: 0.85rem;
    color: #555;
    margin-bottom: 0.4rem;
    line-height: 1.4;
}

.news-card-source {
    font-size: 0.75rem;
    color: #999;
    font-weight: 500;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/styles/custom.css
git commit -m "feat: add custom CSS for weather and news cards"
```

---

### Task 11: UI — Streamlit Chat App

**Files:**
- Create: `src/ui/app.py`

- [ ] **Step 1: Implement the Streamlit chat app**

Create `src/ui/app.py`:

```python
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import streamlit as st

from src.agent.agent import agent
from src.agent.models import AgentResponse
from src.ui.components.news_card import render_news_cards
from src.ui.components.weather_card import render_weather_card

logger = logging.getLogger(__name__)

STYLES_PATH: Path = Path(__file__).parent / "styles" / "custom.css"
APP_TITLE: str = "Weather & News Assistant"
CHAT_PLACEHOLDER: str = "Ask about weather or news..."
ASSISTANT_AVATAR: str = "🤖"
USER_AVATAR: str = "👤"


def _load_css() -> None:
    """Load custom CSS into the Streamlit app."""
    css = STYLES_PATH.read_text()
    st.html(f"<style>{css}</style>")


async def _ask_agent(user_message: str) -> AgentResponse:
    """Send a message to the PydanticAI agent and return structured output."""
    async with agent:
        result = await agent.run(user_message)
    return result.output


def _render_response(response: AgentResponse) -> None:
    """Render the agent response with text and optional cards."""
    if response.message:
        st.markdown(response.message)
    if response.weather is not None:
        render_weather_card(response.weather)
    if response.articles is not None:
        render_news_cards(response.articles)


def main() -> None:
    """Streamlit chat application entry point."""
    st.set_page_config(page_title=APP_TITLE, page_icon="🌤️", layout="centered")
    _load_css()
    st.title(APP_TITLE)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        avatar = USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["role"] == "assistant" and "response" in msg:
                _render_response(msg["response"])
            else:
                st.markdown(msg["content"])

    # Accept user input
    if prompt := st.chat_input(CHAT_PLACEHOLDER):
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)

        # Get agent response
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            with st.spinner("Thinking..."):
                try:
                    response = asyncio.run(_ask_agent(prompt))
                    _render_response(response)
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": response.message,
                            "response": response,
                        }
                    )
                except Exception as exc:
                    logger.error("Agent call failed: %s", exc)
                    error_msg = f"Sorry, something went wrong: {exc}"
                    st.error(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify Streamlit can import the app**

Run: `uv run python -c "from src.ui.app import main; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ui/app.py
git commit -m "feat: add Streamlit chat app with agent integration and card rendering"
```

---

### Task 12: Launcher

**Files:**
- Create: `launcher.py`

- [ ] **Step 1: Implement the launcher**

Create `launcher.py`:

```python
"""Single entry point to start Weather MCP, News MCP, and Streamlit."""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time
from types import FrameType

import httpx
from dotenv import load_dotenv

from src.agent.config import NEWS_MCP_PORT, STREAMLIT_PORT, WEATHER_MCP_PORT

load_dotenv()

logger = logging.getLogger(__name__)

HEALTH_CHECK_TIMEOUT_SECONDS: float = 30.0
HEALTH_CHECK_INTERVAL_SECONDS: float = 1.0


def _start_weather_mcp() -> subprocess.Popen[bytes]:
    """Start the weather MCP server."""
    logger.info("Starting weather MCP server on port %d...", WEATHER_MCP_PORT)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "mcp_weather_server",
            "--mode",
            "streamable-http",
            "--port",
            str(WEATHER_MCP_PORT),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _start_news_mcp() -> subprocess.Popen[bytes]:
    """Start the news MCP server."""
    logger.info("Starting news MCP server on port %d...", NEWS_MCP_PORT)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "src.mcp_servers.news.server",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _start_streamlit() -> subprocess.Popen[bytes]:
    """Start the Streamlit app."""
    logger.info("Starting Streamlit on port %d...", STREAMLIT_PORT)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "src/ui/app.py",
            "--server.port",
            str(STREAMLIT_PORT),
            "--server.headless",
            "true",
        ],
    )


def _wait_for_server(port: int, name: str) -> bool:
    """Wait until a server responds on the given port."""
    url = f"http://localhost:{port}/mcp"
    deadline = time.monotonic() + HEALTH_CHECK_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            response = httpx.post(
                url,
                json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
                timeout=2.0,
            )
            if response.status_code in (200, 405, 400):
                logger.info("%s is ready on port %d", name, port)
                return True
        except httpx.HTTPError:
            pass
        time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
    logger.error("%s failed to start on port %d", name, port)
    return False


def main() -> None:
    """Start all services and manage their lifecycle."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    processes: list[subprocess.Popen[bytes]] = []

    def _shutdown(signum: int | None = None, frame: FrameType | None = None) -> None:
        logger.info("Shutting down...")
        for proc in reversed(processes):
            proc.terminate()
        for proc in reversed(processes):
            proc.wait(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Start MCP servers
    weather_proc = _start_weather_mcp()
    processes.append(weather_proc)

    news_proc = _start_news_mcp()
    processes.append(news_proc)

    # Wait for MCP servers to be ready
    if not _wait_for_server(WEATHER_MCP_PORT, "Weather MCP"):
        _shutdown()
        return
    if not _wait_for_server(NEWS_MCP_PORT, "News MCP"):
        _shutdown()
        return

    # Start Streamlit
    streamlit_proc = _start_streamlit()
    processes.append(streamlit_proc)

    logger.info("All services running. Press Ctrl+C to stop.")

    try:
        streamlit_proc.wait()
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify launcher imports**

Run: `uv run python -c "from launcher import main; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add launcher.py
git commit -m "feat: add launcher to start all services with health checks"
```

---

### Task 13: End-to-End Integration Test

**Files:** None new — tests existing code together.

- [ ] **Step 1: Set up `.env` with real keys**

Copy `.env.example` to `.env` and fill in real values:
- `LLM_MODEL=google-gla:gemini-3-flash-preview`
- `GOOGLE_API_KEY=<your real key>`
- `GNEWS_API_KEY=<your real key>`

- [ ] **Step 2: Start the full stack**

Run: `uv run python launcher.py`
Expected: All three services start, health checks pass, Streamlit opens on `http://localhost:8501`.

- [ ] **Step 3: Test weather query**

In the chat, type: "What's the weather in Riga?"
Expected: Agent responds with a weather card showing temperature, conditions, and location.

- [ ] **Step 4: Test news query**

In the chat, type: "What are the latest tech news?"
Expected: Agent responds with news article cards with titles, sources, and links.

- [ ] **Step 5: Test combined query**

In the chat, type: "Weather in London and today's business news"
Expected: Agent responds with both a weather card and news cards.

- [ ] **Step 6: Run all unit tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: complete weather & news chat app — all integration tests passing"
```
