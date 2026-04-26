"""FastMCP server exposing the three disasters tools.

Mirrors the structure of ``src/mcp_servers/news/server.py``: tool registration
only, no business logic. The repository owns querying; this module owns transport
and serialization.
"""
import json
import logging
import sys
from typing import Literal

from mcp.server.fastmcp import FastMCP

from src.agent.config import (
    DISASTERS_DEFAULT_QUERY_LIMIT,
    DISASTERS_DEFAULT_TOP_N,
    DISASTERS_MCP_PORT,
)
from .repository import (
    DisasterRepository,
    DisasterRepositoryError,
    get_repository,
)

logger = logging.getLogger(__name__)

DISASTERS_MCP_HOST: str = "127.0.0.1"

mcp = FastMCP(
    "disasters-server",
    host=DISASTERS_MCP_HOST,
    port=DISASTERS_MCP_PORT,
    stateless_http=True,
    json_response=True,
)


def _get_repository() -> DisasterRepository:
    """Indirect accessor so tests can monkey-patch the repository."""
    return get_repository()


@mcp.tool()
async def query_disasters(
    country: str | None = None,
    disaster_type: str | None = None,
    location_contains: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    limit: int = DISASTERS_DEFAULT_QUERY_LIMIT,
) -> str:
    """List historical disaster events matching the given filters.

    Use this for direct questions about specific events ("what happened in
    Haiti in 2010", "all wildfires in Australia 2010-2020"). Returns up to
    ``limit`` events sorted newest first.

    Do NOT use this for ranking or counting questions ("deadliest", "how
    many", "which decade") — use ``disaster_stats`` instead. Do NOT use this
    when answering a weather question — use ``location_disaster_summary``.

    Args:
        country: Country name (case-insensitive) or ISO-3 code (e.g. "Japan",
            "JPN", "United States of America (the)").
        disaster_type: Exact match on disaster type — "Flood", "Earthquake",
            "Storm", "Drought", "Wildfire", "Landslide", "Epidemic", etc.
        location_contains: Case-insensitive substring of the free-text Location
            field (e.g. "tokyo", "florida", "bengal"). Many rows have a null
            Location, so substring matches are best-effort.
        start_year: Lower bound (inclusive) on Year.
        end_year: Upper bound (inclusive) on Year.
        limit: Maximum events to return (default 20).
    """
    repo = _get_repository()
    try:
        response = repo.query(
            country=country,
            disaster_type=disaster_type,
            location_contains=location_contains,
            start_year=start_year,
            end_year=end_year,
            limit=limit,
        )
    except DisasterRepositoryError as exc:
        logger.error("query_disasters invalid input: %s", exc)
        return json.dumps({"error": str(exc)})
    return response.model_dump_json()


@mcp.tool()
async def disaster_stats(
    group_by: Literal["year", "decade", "type", "country", "continent"],
    metric: Literal["count", "total_deaths", "total_damages_usd"] = "count",
    country: str | None = None,
    disaster_type: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    top_n: int = DISASTERS_DEFAULT_TOP_N,
) -> str:
    """Aggregate disasters and return top-N ranked groups.

    Use this for ranking and counting questions ("deadliest earthquakes",
    "which decade had the most floods", "costliest storms in the US",
    "how many wildfires in 2018").

    Do NOT use this when the user wants raw events listed — use
    ``query_disasters`` instead. Do NOT use this for weather-flow context —
    use ``location_disaster_summary``.

    Args:
        group_by: How to group rows — "year", "decade", "type", "country",
            "continent".
        metric: How to rank groups — "count" (default), "total_deaths",
            or "total_damages_usd" (sum of the 'Total Damages (000 US$)'
            column; values are in thousands of USD).
        country: Optional country filter (case-insensitive name or ISO-3).
        disaster_type: Optional disaster type filter.
        start_year: Optional inclusive lower bound on Year.
        end_year: Optional inclusive upper bound on Year.
        top_n: Maximum number of groups to return (default 10).
    """
    repo = _get_repository()
    try:
        response = repo.stats(
            group_by=group_by,
            metric=metric,
            country=country,
            disaster_type=disaster_type,
            start_year=start_year,
            end_year=end_year,
            top_n=top_n,
        )
    except DisasterRepositoryError as exc:
        logger.error("disaster_stats invalid input: %s", exc)
        return json.dumps({"error": str(exc)})
    return response.model_dump_json()


@mcp.tool()
async def location_disaster_summary(
    country: str,
    location_contains: str | None = None,
) -> str:
    """Return a narrative-shaped disaster summary for a location since 1980.

    Use this WHENEVER the user asks about weather in a specific place. Run it
    alongside the weather lookup so you can mention notable historical
    disasters (one short sentence) when total_events > 0. When total_events
    == 0 you MUST stay silent about disasters in your reply.

    Do NOT use this for direct disaster questions — use ``query_disasters``
    or ``disaster_stats`` instead.

    Args:
        country: Country name (case-insensitive) or ISO-3 code; required.
        location_contains: Case-insensitive substring on Location to narrow
            to a city or sub-region (e.g. "tokyo", "florida"). Optional.
    """
    repo = _get_repository()
    try:
        response = repo.location_summary(
            country=country,
            location_contains=location_contains,
        )
    except DisasterRepositoryError as exc:
        logger.error("location_disaster_summary invalid input: %s", exc)
        return json.dumps({"error": str(exc)})
    return response.model_dump_json()


def main() -> None:
    """Entry point for the disasters MCP server."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
