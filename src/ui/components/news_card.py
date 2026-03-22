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
