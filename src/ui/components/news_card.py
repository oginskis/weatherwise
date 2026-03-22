import html

import streamlit as st

from src.agent.models import ArticleData


def render_news_card(article: ArticleData) -> None:
    """Render an inline news article card in Streamlit."""
    title = html.escape(article.title)
    description = html.escape(article.description)
    source = html.escape(article.source)
    url = html.escape(article.url)

    image_block = ""
    if article.image_url is not None:
        image_url = html.escape(article.image_url)
        image_block = (
            f'<img class="news-card-image" src="{image_url}" alt="{title}" />'
        )

    markup = f"""
    <div class="news-card">
        {image_block}
        <div class="news-card-body">
            <a class="news-card-title" href="{url}" target="_blank">{title}</a>
            <div class="news-card-description">{description}</div>
            <div class="news-card-source">{source}</div>
        </div>
    </div>
    """
    st.html(markup)


def render_news_cards(articles: list[ArticleData]) -> None:
    """Render a list of news article cards."""
    for article in articles:
        render_news_card(article)
