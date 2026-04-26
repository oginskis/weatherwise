from src.agent.models import AgentResponse, ArticleData, DisasterSummaryView, WeatherData


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


def test_disaster_summary_view_round_trip() -> None:
    view = DisasterSummaryView(
        total_events=3,
        time_span="1995–2019",
        top_types=[("Earthquake", 2), ("Storm", 1)],
        deadliest_event_summary="2011 Earthquake (Tohoku, 19,846 deaths)",
    )
    rehydrated = DisasterSummaryView.model_validate_json(view.model_dump_json())
    assert rehydrated.total_events == 3
    assert rehydrated.top_types == [("Earthquake", 2), ("Storm", 1)]


def test_agent_response_disasters_field_optional() -> None:
    response = AgentResponse(message="hello")
    assert response.disasters is None


def test_agent_response_with_disaster_summary() -> None:
    summary = DisasterSummaryView(
        total_events=1,
        time_span="2010",
        top_types=[("Earthquake", 1)],
        deadliest_event_summary="2010 Earthquake (Port-au-Prince, 222,570 deaths)",
    )
    response = AgentResponse(message="Haiti has had one major disaster.", disasters=summary)
    assert response.disasters is not None
    assert response.disasters.total_events == 1
