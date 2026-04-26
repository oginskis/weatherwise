import pytest

from src.mcp_servers.disasters.loader import load_disasters
from src.mcp_servers.disasters.repository import (
    DisasterRepository,
    DisasterRepositoryError,
)


@pytest.fixture
def repo(disasters_fixture_path) -> DisasterRepository:
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
    rows = repo._apply_filters(start_year=2010, end_year=2015)
    years = sorted(rows["Year"].tolist())
    assert all(2010 <= y <= 2015 for y in years)


def test_apply_filters_invalid_year_range_raises(repo) -> None:
    with pytest.raises(DisasterRepositoryError):
        repo._apply_filters(start_year=2020, end_year=2010)


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
    # sorted descending by count
    counts = [(row.group_value, int(row.metric_value)) for row in response.rows]
    assert counts[0][1] >= counts[-1][1]
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
