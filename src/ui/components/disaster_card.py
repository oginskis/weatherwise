import html

import streamlit as st

from src.agent.models import DisasterSummaryView

DISASTER_TYPE_ICONS: dict[str, str] = {
    "earthquake": "🪨",
    "flood": "🌊",
    "storm": "🌪️",
    "wildfire": "🔥",
    "drought": "🏜️",
    "landslide": "⛰️",
    "epidemic": "🦠",
    "extreme temperature": "🌡️",
    "volcanic": "🌋",
}

DEFAULT_DISASTER_ICON: str = "⚠️"


def _resolve_icon(disaster_type: str) -> str:
    """Match a disaster type string to an emoji icon."""
    key = disaster_type.lower()
    for fragment, icon in DISASTER_TYPE_ICONS.items():
        if fragment in key:
            return icon
    return DEFAULT_DISASTER_ICON


def render_disaster_card(summary: DisasterSummaryView) -> None:
    """Render a compact disaster summary card."""
    time_span = html.escape(summary.time_span or "")
    chips = "".join(
        f'<span class="disaster-chip">{_resolve_icon(t)} '
        f'{html.escape(t)} <strong>{c}</strong></span>'
        for t, c in summary.top_types
    )
    deadliest_html = ""
    if summary.deadliest_event_summary:
        deadliest_html = (
            f'<div class="disaster-card-deadliest">'
            f'Deadliest: {html.escape(summary.deadliest_event_summary)}'
            f'</div>'
        )

    markup = f"""
    <div class="disaster-card">
        <div class="disaster-card-header">
            <span class="disaster-icon">⚠️</span>
            <span class="disaster-card-title">
                {summary.total_events} historical events
                <span class="disaster-card-span"> · {time_span}</span>
            </span>
        </div>
        <div class="disaster-card-chips">{chips}</div>
        {deadliest_html}
    </div>
    """
    st.html(markup)
