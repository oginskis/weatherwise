import os

from dotenv import load_dotenv

load_dotenv()

# MCP server ports
WEATHER_MCP_PORT: int = 8080
NEWS_MCP_PORT: int = 8081

# MCP server endpoints (derived from ports)
WEATHER_MCP_URL: str = f"http://localhost:{WEATHER_MCP_PORT}/mcp"
NEWS_MCP_URL: str = f"http://localhost:{NEWS_MCP_PORT}/mcp"

# Streamlit
STREAMLIT_PORT: int = 8501

# LLM — provider resolved automatically by PydanticAI from the string prefix
LLM_MODEL: str = os.environ["LLM_MODEL"]

# News API
GNEWS_API_KEY: str = os.environ["GNEWS_API_KEY"]
GNEWS_BASE_URL: str = "https://gnews.io/api/v4"
GNEWS_DEFAULT_LANG: str = "en"
GNEWS_DEFAULT_MAX_RESULTS: int = 5
GNEWS_REQUEST_TIMEOUT_SECONDS: float = 10.0
