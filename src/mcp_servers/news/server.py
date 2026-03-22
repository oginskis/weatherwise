import json
import logging
import sys

from mcp.server.fastmcp import FastMCP

from src.agent.config import GNEWS_API_KEY, GNEWS_DEFAULT_LANG, GNEWS_DEFAULT_MAX_RESULTS, NEWS_MCP_PORT
from .gnews_client import GNewsAPIError, GNewsClient
from .models import SearchResponse

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
        _client = GNewsClient(api_key=GNEWS_API_KEY)
    return _client


def _serialize_response(response: SearchResponse) -> str:
    """Serialize a SearchResponse to JSON string."""
    return json.dumps(
        [article.model_dump() for article in response.articles],
        ensure_ascii=False,
    )


@mcp.tool()
async def search_news(
    query: str,
    lang: str = GNEWS_DEFAULT_LANG,
    max_results: int = GNEWS_DEFAULT_MAX_RESULTS,
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
    return _serialize_response(response)


@mcp.tool()
async def get_top_headlines(
    category: str | None = None,
    country: str | None = None,
    lang: str = GNEWS_DEFAULT_LANG,
    max_results: int = GNEWS_DEFAULT_MAX_RESULTS,
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
    return _serialize_response(response)


def main() -> None:
    """Entry point for the news MCP server."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
