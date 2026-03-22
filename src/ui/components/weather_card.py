from __future__ import annotations

import streamlit as st

from src.agent.models import WeatherData

WEATHER_ICONS: dict[str, str] = {
    "sunny": "☀️",
    "clear": "☀️",
    "cloudy": "☁️",
    "overcast": "☁️",
    "rain": "🌧️",
    "drizzle": "🌦️",
    "snow": "❄️",
    "thunderstorm": "⛈️",
    "fog": "🌫️",
    "mist": "🌫️",
    "wind": "💨",
}

DEFAULT_ICON: str = "🌡️"


def _resolve_icon(conditions: str) -> str:
    """Match weather conditions to an icon."""
    conditions_lower = conditions.lower()
    for keyword, icon in WEATHER_ICONS.items():
        if keyword in conditions_lower:
            return icon
    return DEFAULT_ICON


def render_weather_card(weather: WeatherData) -> None:
    """Render an inline weather card in Streamlit."""
    icon = _resolve_icon(weather.conditions)
    html = f"""
    <div class="weather-card">
        <div class="weather-card-header">
            <span class="weather-icon">{icon}</span>
            <span class="weather-location">{weather.location}</span>
        </div>
        <div class="weather-card-temp">{weather.temperature:.1f}°C</div>
        <div class="weather-card-conditions">{weather.conditions}</div>
        <div class="weather-card-details">
    """
    if weather.humidity is not None:
        html += f'<span>💧 {weather.humidity:.0f}%</span>'
    if weather.wind_speed is not None:
        html += f'<span>💨 {weather.wind_speed:.1f} km/h</span>'
    html += "</div></div>"

    st.html(html)
