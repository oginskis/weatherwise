from typing import Any, Self

from pydantic import BaseModel


class Article(BaseModel):
    title: str
    description: str
    source_name: str
    url: str
    image_url: str | None
    published_at: str

    @classmethod
    def from_gnews(cls, data: dict[str, Any]) -> Self:
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
    def from_gnews(cls, data: dict[str, Any]) -> Self:
        articles = [
            Article.from_gnews(article)
            for article in data.get("articles", [])
        ]
        return cls(
            total_articles=data.get("totalArticles", 0),
            articles=articles,
        )
