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
