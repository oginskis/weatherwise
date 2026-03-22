from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

from .config import LLM_MODEL, NEWS_MCP_URL, WEATHER_MCP_URL
from .models import AgentResponse

SYSTEM_PROMPT: str = (
    "You are a helpful assistant that answers questions about current weather "
    "and latest news. Always use the available tools to fetch real-time data — "
    "never guess or make up weather conditions or news articles. When the user "
    "asks about weather, use weather tools. When they ask about news, use news "
    "tools. You may use both in a single response when appropriate. Return "
    "structured data so the UI can render rich cards."
)

weather_mcp = MCPServerStreamableHTTP(WEATHER_MCP_URL)
news_mcp = MCPServerStreamableHTTP(NEWS_MCP_URL)

agent = Agent(
    LLM_MODEL,
    output_type=AgentResponse,
    system_prompt=SYSTEM_PROMPT,
    toolsets=[weather_mcp, news_mcp],
)
