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
    message: str
    weather: WeatherData | None = None
    articles: list[ArticleData] | None = None
    disasters: DisasterSummaryView | None = None
