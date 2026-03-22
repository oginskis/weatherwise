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

mcp = FastMCP(
    "news-server",
    host=NEWS_MCP_HOST,
    port=NEWS_MCP_PORT,
    stateless_http=True,
    json_response=True,
)

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
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
