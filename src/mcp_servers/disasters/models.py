from pydantic import BaseModel


class DisasterEvent(BaseModel):
    """A single disaster event row."""

    year: int
    country: str
    location: str | None
    disaster_type: str
    disaster_subtype: str | None
    total_deaths: int | None
    total_affected: int | None
    total_damages_usd_thousands: float | None
    event_name: str | None


class DisasterTypeCount(BaseModel):
    """Count of events for a single disaster type — used in summary top_types."""

    disaster_type: str
    count: int


class LocationSummary(BaseModel):
    """Narrative-shaped summary returned by location_disaster_summary."""

    country: str
    location_filter: str | None
    total_events: int
    time_span: str | None
    top_types: list[DisasterTypeCount]
    deadliest_event: DisasterEvent | None


class StatsRow(BaseModel):
    """One row of an aggregated statistics response."""

    group_value: str
    metric_value: float
    event_count: int


class QueryResponse(BaseModel):
    """Paginated event listing returned by query_disasters."""

    total_matched: int
    events: list[DisasterEvent]


class StatsResponse(BaseModel):
    """Aggregated metric returned by disaster_stats."""

    group_by: str
    metric: str
    rows: list[StatsRow]
