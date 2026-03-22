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
