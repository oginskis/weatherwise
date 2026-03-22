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
