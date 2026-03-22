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
    {"label": "Weather in New York", "icon": "🌤️", "prompt": "What's the weather like in New York right now?"},
    {"label": "Today's tech news", "icon": "💻", "prompt": "What are the latest technology news headlines?"},
    {"label": "Weather in Tokyo", "icon": "🗼", "prompt": "What's the current weather in Tokyo?"},
    {"label": "World business news", "icon": "📈", "prompt": "What's happening in business news today?"},
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


@st.cache_resource
def _get_agent():
    """Lazy-load the PydanticAI agent on first use (not at import time)."""
    from src.agent.agent import agent
    return agent


def _render_response(response) -> None:
    """Render the agent response with text and optional cards."""
    from src.ui.components.news_card import render_news_cards
    from src.ui.components.weather_card import render_weather_card

    if response.message:
        st.markdown(response.message)
    if response.weather is not None:
        render_weather_card(response.weather)
    if response.articles is not None:
        render_news_cards(response.articles)


def _handle_prompt(prompt: str) -> None:
    """Display user message, call agent with spinner, render response."""
    import httpx
    from pydantic_ai import exceptions as pydantic_ai_exceptions
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
                    async with agent:
                        result = await agent.run(
                            prompt, message_history=st.session_state.agent_history
                        )
                    return result.output, result.all_messages()

                response, updated_history = loop.run_until_complete(_run())
                st.session_state.agent_history = updated_history
                _render_response(response)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response.message,
                        "response": response,
                    }
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
                _render_response(msg["response"])
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
