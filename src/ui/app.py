from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import streamlit as st

from src.agent.agent import agent
from src.agent.models import AgentResponse
from src.ui.components.news_card import render_news_cards
from src.ui.components.weather_card import render_weather_card

logger = logging.getLogger(__name__)

STYLES_PATH: Path = Path(__file__).parent / "styles" / "custom.css"
APP_TITLE: str = "Weather & News Assistant"
CHAT_PLACEHOLDER: str = "Ask about weather or news..."
ASSISTANT_AVATAR: str = "🤖"
USER_AVATAR: str = "👤"


def _load_css() -> None:
    """Load custom CSS into the Streamlit app."""
    css = STYLES_PATH.read_text()
    st.html(f"<style>{css}</style>")


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a persistent event loop for async agent calls."""
    if "event_loop" not in st.session_state:
        st.session_state.event_loop = asyncio.new_event_loop()
    return st.session_state.event_loop


async def _ask_agent(user_message: str) -> AgentResponse:
    """Send a message to the PydanticAI agent and return structured output."""
    async with agent:
        result = await agent.run(user_message)
    return result.output


def _render_response(response: AgentResponse) -> None:
    """Render the agent response with text and optional cards."""
    if response.message:
        st.markdown(response.message)
    if response.weather is not None:
        render_weather_card(response.weather)
    if response.articles is not None:
        render_news_cards(response.articles)


def main() -> None:
    """Streamlit chat application entry point."""
    st.set_page_config(page_title=APP_TITLE, page_icon="🌤️", layout="centered")
    _load_css()
    st.title(APP_TITLE)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        avatar = USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["role"] == "assistant" and "response" in msg:
                _render_response(msg["response"])
            else:
                st.markdown(msg["content"])

    # Accept user input
    if prompt := st.chat_input(CHAT_PLACEHOLDER):
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)

        # Get agent response
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            with st.spinner("Thinking..."):
                try:
                    loop = _get_event_loop()
                    response = loop.run_until_complete(_ask_agent(prompt))
                    _render_response(response)
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": response.message,
                            "response": response,
                        }
                    )
                except Exception as exc:
                    logger.error("Agent call failed: %s", exc)
                    error_msg = f"Sorry, something went wrong: {exc}"
                    st.error(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )


if __name__ == "__main__":
    main()
