import asyncio
import logging
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

STYLES_PATH: Path = Path(__file__).parent / "styles" / "custom.css"
APP_TITLE: str = "Weather & News Assistant"
CHAT_PLACEHOLDER: str = "Ask about weather or news..."
ASSISTANT_AVATAR: str = "🤖"
USER_AVATAR: str = "👤"

CONVERSATION_STARTERS: list[dict[str, str]] = [
    # Weather — single-place lookups (hybrid rule may add a one-sentence
    # disaster mention for places with rich post-1980 history).
    {"label": "Weather in New York", "icon": "🌤️", "prompt": "What's the weather like in New York right now?"},
    {"label": "Weather in Tokyo", "icon": "🗼", "prompt": "What's the current weather in Tokyo?"},
    # News — two distinct categories.
    {"label": "Today's tech news", "icon": "💻", "prompt": "What are the latest technology news headlines?"},
    {"label": "Business news", "icon": "📈", "prompt": "What's happening in business news today?"},
    # Disasters — aggregate / ranking queries.
    {"label": "Deadliest earthquakes", "icon": "🪨", "prompt": "What were the deadliest earthquakes ever recorded?"},
    {"label": "Floods by decade", "icon": "🌊", "prompt": "Which decade had the most floods worldwide?"},
    # Disasters — scoped queries (country + type, country + year).
    {"label": "Costliest US storms", "icon": "🌪️", "prompt": "What were the costliest storms in the United States?"},
    {"label": "Disasters in Haiti", "icon": "🌎", "prompt": "What disasters happened in Haiti?"},
]


def _load_css() -> None:
    """Load custom CSS into the Streamlit app."""
    css = STYLES_PATH.read_text()
    st.html(f"<style>{css}</style>")


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a persistent event loop for async agent calls."""
    if "event_loop" not in st.session_state:
        st.session_state.event_loop = asyncio.new_event_loop()
    return st.session_state.event_loop


def _get_agent():
    """Lazy-load the PydanticAI agent on first use (not at import time)."""
    from src.agent.agent import agent
    return agent


def _render_response(response, disaster_card) -> None:
    """Render the agent response with text and optional cards.

    ``disaster_card`` is a :class:`DisasterSummaryView` built deterministically
    from this turn's tool returns by ``build_disaster_card``, or None when the
    turn was a weather/news response or returned no usable disaster data.
    """
    from src.ui.components.disaster_card import render_disaster_card
    from src.ui.components.news_card import render_news_cards
    from src.ui.components.weather_card import render_weather_card

    if response.message:
        st.markdown(response.message)
    if response.weather is not None:
        render_weather_card(response.weather)
    if response.articles is not None:
        render_news_cards(response.articles)
    if disaster_card is not None:
        render_disaster_card(disaster_card)


def _handle_prompt(prompt: str) -> None:
    """Display user message, call agent with spinner, render response."""
    import asyncio

    import httpx
    from pydantic_ai import exceptions as pydantic_ai_exceptions
    from src.agent.config import (
        AGENT_MAX_RETRIES,
        AGENT_RETRY_BASE_DELAY_SECONDS,
        AGENT_RETRYABLE_STATUS_CODES,
    )
    from src.agent.disaster_card import build_disaster_card
    from src.mcp_servers.news.gnews_client import GNewsAPIError

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner("Thinking..."):
            try:
                agent = _get_agent()
                loop = _get_event_loop()

                async def _run():
                    for attempt in range(AGENT_MAX_RETRIES + 1):
                        try:
                            async with agent:
                                result = await agent.run(
                                    prompt, message_history=st.session_state.agent_history
                                )
                            # all_messages → next-turn history; new_messages → this
                            # turn's tool calls (used to build the disaster card).
                            return (
                                result.output,
                                result.all_messages(),
                                result.new_messages(),
                            )
                        except pydantic_ai_exceptions.ModelHTTPError as exc:
                            if (
                                exc.status_code not in AGENT_RETRYABLE_STATUS_CODES
                                or attempt == AGENT_MAX_RETRIES
                            ):
                                raise
                            delay = AGENT_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                            logger.warning(
                                "Model returned %d; retrying in %.1fs (attempt %d/%d)",
                                exc.status_code,
                                delay,
                                attempt + 1,
                                AGENT_MAX_RETRIES,
                            )
                            await asyncio.sleep(delay)

                response, updated_history, new_messages = loop.run_until_complete(_run())
                disaster_card = build_disaster_card(new_messages)
                st.session_state.agent_history = updated_history
                _render_response(response, disaster_card)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response.message,
                        "response": response,
                        "disaster_card": disaster_card,
                    }
                )
            except pydantic_ai_exceptions.ModelHTTPError as exc:
                logger.error("Agent model unavailable after retries: %s", exc)
                error_msg = (
                    "The AI model is currently overloaded and didn't respond after a "
                    "few retries. Please try again in a moment."
                )
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
            except (httpx.HTTPError, GNewsAPIError, pydantic_ai_exceptions.UserError, OSError) as exc:
                logger.error("Agent call failed: %s", exc)
                error_msg = f"Sorry, something went wrong: {exc}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )


def main() -> None:
    """Streamlit chat application entry point."""
    st.set_page_config(page_title=APP_TITLE, page_icon="🌤️", layout="centered")
    _load_css()

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_history" not in st.session_state:
        st.session_state.agent_history = []

    # Header
    st.markdown(
        '<h1 class="app-header">🌤️ Weather & News Assistant</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Real-time weather and news powered by AI")

    # Display chat history
    for msg in st.session_state.messages:
        avatar = USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["role"] == "assistant" and "response" in msg:
                _render_response(msg["response"], msg.get("disaster_card"))
            else:
                st.markdown(msg["content"])

    # Show conversation starters only when chat is empty
    if not st.session_state.messages and "pending_prompt" not in st.session_state:
        cols = st.columns(2)
        for i, starter in enumerate(CONVERSATION_STARTERS):
            with cols[i % 2]:
                if st.button(
                    f"{starter['icon']}  {starter['label']}",
                    key=f"starter_{i}",
                    use_container_width=True,
                ):
                    st.session_state["pending_prompt"] = starter["prompt"]
                    st.rerun()

    # Handle pending prompt from conversation starter
    if "pending_prompt" in st.session_state:
        prompt = st.session_state.pop("pending_prompt")
        _handle_prompt(prompt)

    # Accept user input
    if prompt := st.chat_input(CHAT_PLACEHOLDER):
        _handle_prompt(prompt)


if __name__ == "__main__":
    main()
