import json

from src.mcp_servers.disasters.models import (
    DisasterEvent,
    DisasterTypeCount,
    LocationSummary,
    QueryResponse,
    StatsResponse,
    StatsRow,
)


def test_disaster_event_minimal_fields() -> None:
    event = DisasterEvent(
        year=2011, country="Japan", location="Tohoku",
        disaster_type="Earthquake", disaster_subtype=None,
        total_deaths=19846, total_affected=469000,
        total_damages_usd_thousands=210_000_000.0, event_name="Tohoku",
    )
    assert event.year == 2011
    assert event.country == "Japan"
    assert event.total_deaths == 19846


def test_disaster_event_optional_nullable() -> None:
    event = DisasterEvent(
        year=1900, country="India", location=None,
        disaster_type="Drought", disaster_subtype=None,
        total_deaths=None, total_affected=None,
        total_damages_usd_thousands=None, event_name=None,
    )
    assert event.total_deaths is None
    assert event.total_damages_usd_thousands is None


def test_location_summary_empty_serializes_cleanly() -> None:
    summary = LocationSummary(
        country="Latvia", location_filter="Riga",
        total_events=0, time_span=None,
        top_types=[], deadliest_event=None,
    )
    payload = json.loads(summary.model_dump_json())
    assert payload["total_events"] == 0
    assert payload["time_span"] is None
    assert payload["top_types"] == []
    assert payload["deadliest_event"] is None


def test_location_summary_populated_round_trip() -> None:
    deadliest = DisasterEvent(
        year=2011, country="Japan", location="Tohoku",
        disaster_type="Earthquake", disaster_subtype=None,
        total_deaths=19846, total_affected=469000,
        total_damages_usd_thousands=210_000_000.0, event_name="Tohoku",
    )
    summary = LocationSummary(
        country="Japan", location_filter=None,
        total_events=3, time_span="1995–2019",
        top_types=[
            DisasterTypeCount(disaster_type="Earthquake", count=2),
            DisasterTypeCount(disaster_type="Storm", count=1),
        ],
        deadliest_event=deadliest,
    )
    rehydrated = LocationSummary.model_validate_json(summary.model_dump_json())
    assert rehydrated.total_events == 3
    assert rehydrated.deadliest_event is not None
    assert rehydrated.deadliest_event.year == 2011
    assert len(rehydrated.top_types) == 2


def test_query_response_serializes_event_list() -> None:
    response = QueryResponse(total_matched=2, events=[])
    assert response.total_matched == 2
    assert response.events == []


def test_stats_response_carries_metric_metadata() -> None:
    response = StatsResponse(
        group_by="type",
        metric="count",
        rows=[StatsRow(group_value="Flood", metric_value=2.0, event_count=2)],
    )
    payload = json.loads(response.model_dump_json())
    assert payload["group_by"] == "type"
    assert payload["rows"][0]["group_value"] == "Flood"
