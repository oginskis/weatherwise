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
