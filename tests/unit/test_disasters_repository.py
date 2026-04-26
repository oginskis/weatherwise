from pathlib import Path

import pytest

from src.mcp_servers.disasters.loader import load_disasters
from src.mcp_servers.disasters.repository import (
    DisasterRepository,
    DisasterRepositoryError,
)


@pytest.fixture
def repo(disasters_fixture_path: Path) -> DisasterRepository:
    return DisasterRepository(load_disasters(disasters_fixture_path))


def test_apply_filters_by_country_name_case_insensitive(repo) -> None:
    rows = repo._apply_filters(country="japan")
    assert len(rows) == 3  # Tohoku, Kobe, Hagibis
    rows = repo._apply_filters(country="JAPAN")
    assert len(rows) == 3


def test_apply_filters_by_iso_fallback(repo) -> None:
    rows = repo._apply_filters(country="USA")
    assert len(rows) == 3  # Katrina, Harvey, Camp Fire


def test_apply_filters_full_country_string(repo) -> None:
    rows = repo._apply_filters(country="United States of America (the)")
    assert len(rows) == 3


def test_apply_filters_country_substring_short_form(repo) -> None:
    """'United States' must match the EM-DAT 'United States of America (the)'."""
    rows = repo._apply_filters(country="United States")
    assert len(rows) == 3


def test_apply_filters_unknown_country_returns_empty(repo) -> None:
    rows = repo._apply_filters(country="Atlantis")
    assert len(rows) == 0


def test_apply_filters_by_disaster_type(repo) -> None:
    rows = repo._apply_filters(disaster_type="Earthquake")
    assert len(rows) == 3  # Tohoku, Kobe, Haiti


def test_apply_filters_country_and_type_anded(repo) -> None:
    rows = repo._apply_filters(country="Japan", disaster_type="Earthquake")
    assert len(rows) == 2  # Tohoku + Kobe


def test_apply_filters_location_substring(repo) -> None:
    rows = repo._apply_filters(country="USA", location_contains="florida")
    assert len(rows) == 1  # Katrina (location includes Florida)


def test_apply_filters_location_substring_without_country(repo) -> None:
    rows = repo._apply_filters(location_contains="bengal")
    assert len(rows) == 2  # India 1900 drought + 2019 flood


def test_apply_filters_year_range(repo) -> None:
    """Inclusive range; off-by-one boundaries would fail this exact-count assertion."""
    rows = repo._apply_filters(start_year=2010, end_year=2015)
    years = sorted(rows["Year"].tolist())
    # Fixture matches: Haiti 2010, Tohoku 2011, Australia flood 2011 (year=2011).
    assert len(rows) == 3, f"expected 3 rows in 2010-2015, got {len(rows)}: years={years}"
    assert years == [2010, 2011, 2011]


def test_apply_filters_invalid_year_range_raises(repo) -> None:
    with pytest.raises(DisasterRepositoryError):
        repo._apply_filters(start_year=2020, end_year=2010)


def test_apply_filters_three_way_combination(repo) -> None:
    """Country + location_contains + start_year all AND together."""
    rows = repo._apply_filters(
        country="India", location_contains="bengal", start_year=2000
    )
    # Fixture: India 1900 Bengal drought (excluded by start_year),
    # India 2019 Bengal flood (included).
    assert len(rows) == 1
    assert int(rows.iloc[0]["Year"]) == 2019


def test_query_returns_query_response(repo) -> None:
    response = repo.query(
        country="Japan", disaster_type=None, location_contains=None,
        start_year=None, end_year=None, limit=10,
    )
    assert response.total_matched == 3
    assert len(response.events) == 3
    # Sorted descending by Year, Start Month, Start Day
    assert response.events[0].year == 2019
    assert response.events[1].year == 2011
    assert response.events[2].year == 1995


def test_query_respects_limit(repo) -> None:
    response = repo.query(
        country=None, disaster_type=None, location_contains=None,
        start_year=None, end_year=None, limit=2,
    )
    assert response.total_matched == 12
    assert len(response.events) == 2


def test_query_event_payload_shape(repo) -> None:
    response = repo.query(
        country="Haiti", disaster_type=None, location_contains=None,
        start_year=None, end_year=None, limit=10,
    )
    haiti = response.events[0]
    assert haiti.year == 2010
    assert haiti.country == "Haiti"
    assert haiti.location == "Port-au-Prince"
    assert haiti.disaster_type == "Earthquake"
    assert haiti.total_deaths == 222570
    assert haiti.total_damages_usd_thousands == 8_000_000.0


def test_query_handles_null_optional_fields(repo) -> None:
    response = repo.query(
        country="Latvia", disaster_type=None, location_contains=None,
        start_year=None, end_year=None, limit=10,
    )
    riga = response.events[0]
    assert riga.event_name is None  # blank in fixture
    assert riga.total_damages_usd_thousands is None


def test_query_empty_result(repo) -> None:
    response = repo.query(
        country="Atlantis", disaster_type=None, location_contains=None,
        start_year=None, end_year=None, limit=10,
    )
    assert response.total_matched == 0
    assert response.events == []


def test_stats_count_by_type_descending(repo) -> None:
    response = repo.stats(
        group_by="type", metric="count",
        country=None, disaster_type=None,
        start_year=None, end_year=None, top_n=10,
    )
    # Strict descending invariant — every row's metric must be >= the next.
    values = [row.metric_value for row in response.rows]
    assert values == sorted(values, reverse=True), (
        f"rows must be sorted descending by metric_value; got {values}"
    )
    storm_row = next(r for r in response.rows if r.group_value == "Storm")
    assert storm_row.metric_value == 4.0  # Hagibis, Katrina, Harvey, Latvia 1969


def test_stats_top_n_caps_results(repo) -> None:
    response = repo.stats(
        group_by="type", metric="count",
        country=None, disaster_type=None,
        start_year=None, end_year=None, top_n=2,
    )
    assert len(response.rows) == 2


def test_stats_total_deaths_by_country(repo) -> None:
    response = repo.stats(
        group_by="country", metric="total_deaths",
        country=None, disaster_type=None,
        start_year=None, end_year=None, top_n=10,
    )
    haiti_row = next(r for r in response.rows if r.group_value == "Haiti")
    assert haiti_row.metric_value == 222570.0
    # India should be top — 1,253,000 combined
    india_row = next(r for r in response.rows if r.group_value == "India")
    assert india_row.metric_value == 1253000.0


def test_stats_total_damages_returns_thousands_usd(repo) -> None:
    response = repo.stats(
        group_by="country", metric="total_damages_usd",
        country=None, disaster_type=None,
        start_year=None, end_year=None, top_n=10,
    )
    japan_row = next(r for r in response.rows if r.group_value == "Japan")
    # Tohoku 210M + Kobe 100M + Hagibis 17M = 327M (thousands USD)
    assert japan_row.metric_value == 327_000_000.0


def test_stats_by_continent(repo) -> None:
    """The 'continent' group_by is in _VALID_GROUP_BY; verify it groups correctly."""
    response = repo.stats(
        group_by="continent", metric="count",
        country=None, disaster_type=None,
        start_year=None, end_year=None, top_n=10,
    )
    rows_by_continent = {row.group_value: int(row.metric_value) for row in response.rows}
    # Fixture: 5 events in Asia (3 Japan + 2 India), 4 in Americas (3 USA + 1 Haiti),
    # 2 in Oceania (Australia), 1 in Europe (Latvia).
    assert rows_by_continent == {
        "Asia": 5,
        "Americas": 4,
        "Oceania": 2,
        "Europe": 1,
    }


def test_stats_by_decade(repo) -> None:
    response = repo.stats(
        group_by="decade", metric="count",
        country=None, disaster_type=None,
        start_year=None, end_year=None, top_n=10,
    )
    decade_values = {row.group_value for row in response.rows}
    assert "2010" in decade_values
    assert "2000" in decade_values


def test_stats_invalid_group_by_raises(repo) -> None:
    with pytest.raises(DisasterRepositoryError):
        repo.stats(
            group_by="quarter", metric="count",
            country=None, disaster_type=None,
            start_year=None, end_year=None, top_n=10,
        )


def test_stats_invalid_metric_raises(repo) -> None:
    with pytest.raises(DisasterRepositoryError):
        repo.stats(
            group_by="type", metric="median_deaths",
            country=None, disaster_type=None,
            start_year=None, end_year=None, top_n=10,
        )


def test_stats_with_country_filter(repo) -> None:
    response = repo.stats(
        group_by="type", metric="count",
        country="USA", disaster_type=None,
        start_year=None, end_year=None, top_n=10,
    )
    types = {row.group_value for row in response.rows}
    assert types == {"Storm", "Wildfire"}


def test_location_summary_japan_populated(repo) -> None:
    summary = repo.location_summary(country="Japan", location_contains=None)
    assert summary.country == "Japan"
    assert summary.location_filter is None
    assert summary.total_events == 3
    assert summary.time_span == "1995–2019"
    assert summary.deadliest_event is not None
    assert summary.deadliest_event.year == 2011
    assert summary.deadliest_event.disaster_type == "Earthquake"


def test_location_summary_top_types_for_usa(repo) -> None:
    """USA has 2 distinct disaster types post-1980 (Storm, Wildfire); both must appear."""
    summary = repo.location_summary(country="USA", location_contains=None)
    types = {item.disaster_type for item in summary.top_types}
    assert types == {"Storm", "Wildfire"}
    storm = next(item for item in summary.top_types if item.disaster_type == "Storm")
    wildfire = next(item for item in summary.top_types if item.disaster_type == "Wildfire")
    assert storm.count == 2  # Katrina + Harvey
    assert wildfire.count == 1  # Camp Fire
    # The 3-cap itself is exercised by disaster_stats top_n in
    # test_stats_top_n_caps_results — the fixture has no country with 4+
    # post-1980 disaster types, so it can't be exercised through
    # location_summary.


def test_location_summary_quiet_country_returns_empty(repo) -> None:
    """Latvia's only event is 1969 — outside the 1980+ default window."""
    summary = repo.location_summary(country="Latvia", location_contains=None)
    assert summary.total_events == 0
    assert summary.time_span is None
    assert summary.top_types == []
    assert summary.deadliest_event is None


def test_location_summary_unknown_country_returns_empty(repo) -> None:
    summary = repo.location_summary(country="Atlantis", location_contains=None)
    assert summary.total_events == 0


def test_location_summary_location_substring_narrows_results(repo) -> None:
    summary = repo.location_summary(country="USA", location_contains="florida")
    assert summary.total_events == 1
    assert summary.location_filter == "florida"


def test_location_summary_overrides_min_year_for_tests(repo) -> None:
    """Repository method allows min_year override even though MCP tool does not."""
    summary = repo.location_summary(
        country="Latvia", location_contains=None, min_year=1900,
    )
    assert summary.total_events == 1  # 1969 storm now in window
