import json

import pytest

from src.mcp_servers.disasters import server as srv
from src.mcp_servers.disasters.loader import load_disasters
from src.mcp_servers.disasters.repository import DisasterRepository


@pytest.fixture(autouse=True)
def _swap_repository(monkeypatch, disasters_fixture_path) -> None:
    """Replace the singleton with one backed by the test fixture."""
    repo = DisasterRepository(load_disasters(disasters_fixture_path))
    monkeypatch.setattr(srv, "_get_repository", lambda: repo)


@pytest.mark.asyncio
async def test_query_disasters_tool_returns_json() -> None:
    payload = await srv.query_disasters(country="Japan")
    parsed = json.loads(payload)
    assert parsed["total_matched"] == 3
    assert len(parsed["events"]) == 3


@pytest.mark.asyncio
async def test_disaster_stats_tool_returns_json() -> None:
    payload = await srv.disaster_stats(group_by="type", metric="count")
    parsed = json.loads(payload)
    assert parsed["group_by"] == "type"
    assert parsed["metric"] == "count"
    assert any(row["group_value"] == "Storm" for row in parsed["rows"])


@pytest.mark.asyncio
async def test_location_disaster_summary_quiet_returns_zero() -> None:
    payload = await srv.location_disaster_summary(country="Latvia")
    parsed = json.loads(payload)
    assert parsed["total_events"] == 0
    assert parsed["time_span"] is None


@pytest.mark.asyncio
async def test_location_disaster_summary_populated() -> None:
    payload = await srv.location_disaster_summary(country="Japan")
    parsed = json.loads(payload)
    assert parsed["total_events"] == 3
    assert parsed["deadliest_event"]["year"] == 2011


@pytest.mark.asyncio
async def test_disaster_stats_invalid_group_by_returns_error_json() -> None:
    payload = await srv.disaster_stats(group_by="quarter", metric="count")
    parsed = json.loads(payload)
    assert "error" in parsed


@pytest.mark.asyncio
async def test_query_disasters_unknown_country_returns_empty_response() -> None:
    payload = await srv.query_disasters(country="Atlantis")
    parsed = json.loads(payload)
    assert parsed["total_matched"] == 0
    assert parsed["events"] == []
