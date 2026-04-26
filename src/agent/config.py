import os
from pathlib import Path

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

# Disasters MCP
DISASTERS_MCP_PORT: int = 8082
DISASTERS_MCP_URL: str = f"http://localhost:{DISASTERS_MCP_PORT}/mcp"
DISASTERS_CSV_PATH: Path = Path("data/emdat_disasters_1900_2021.csv")
DISASTERS_MIN_YEAR_FOR_LOCATION_SUMMARY: int = 1980
DISASTERS_DEFAULT_QUERY_LIMIT: int = 20
DISASTERS_DEFAULT_TOP_N: int = 10
