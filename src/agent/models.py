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


class DisasterSummaryView(BaseModel):
    """Compact disaster summary rendered as a UI card for direct questions."""

    total_events: int
    time_span: str | None
    top_types: list[tuple[str, int]]
    deadliest_event_summary: str | None


class AgentResponse(BaseModel):
    """Conversational response returned by the agent.

    Note: there is no ``disasters`` field here. The disaster UI card is
    built deterministically from the agent's tool returns by
    :mod:`src.agent.disaster_card` after the run completes. Keeping the
    LLM out of structured-data construction prevents hallucinated
    numbers in the card.
    """

    message: str
    weather: WeatherData | None = None
    articles: list[ArticleData] | None = None
