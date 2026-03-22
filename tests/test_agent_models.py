from src.agent.models import AgentResponse, ArticleData, WeatherData


def test_agent_response_weather_only() -> None:
    response = AgentResponse(
        message="It's sunny in Riga.",
        weather=WeatherData(
            location="Riga",
            temperature=22.5,
            conditions="Sunny",
        ),
    )
    assert response.weather is not None
    assert response.weather.temperature == 22.5
    assert response.articles is None


def test_agent_response_news_only() -> None:
    response = AgentResponse(
        message="Here are the latest headlines.",
        articles=[
            ArticleData(
                title="Big News",
                description="Something happened",
                source="Reuters",
                url="https://example.com",
            )
        ],
    )
    assert response.weather is None
    assert response.articles is not None
    assert len(response.articles) == 1


def test_agent_response_both() -> None:
    response = AgentResponse(
        message="Weather and news for you.",
        weather=WeatherData(
            location="Riga",
            temperature=15.0,
            conditions="Cloudy",
            humidity=80.0,
            wind_speed=5.2,
        ),
        articles=[
            ArticleData(
                title="Tech News",
                description="AI update",
                source="TechCrunch",
                url="https://example.com",
                image_url="https://example.com/img.jpg",
            )
        ],
    )
    assert response.weather is not None
    assert response.articles is not None
    assert response.weather.humidity == 80.0
    assert response.articles[0].image_url == "https://example.com/img.jpg"
