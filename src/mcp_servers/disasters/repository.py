"""DisasterRepository — pandas DataFrame query layer for the disasters MCP.

Holds a singleton DataFrame loaded once at startup. All public methods
(:meth:`query`, :meth:`stats`, :meth:`location_summary`) build their masks
through the shared :meth:`_apply_filters` helper to keep filtering semantics
consistent.
"""
import logging

import pandas as pd

from src.agent.config import (
    DISASTERS_CSV_PATH,
    DISASTERS_MIN_YEAR_FOR_LOCATION_SUMMARY,
)
from .loader import load_disasters
from .models import DisasterEvent, QueryResponse

logger = logging.getLogger(__name__)


class DisasterRepositoryError(Exception):
    """Raised when an MCP tool passes invalid arguments to the repository."""


class DisasterRepository:
    """Query layer over a loaded disaster DataFrame."""

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def _apply_filters(
        self,
        *,
        country: str | None = None,
        disaster_type: str | None = None,
        location_contains: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> pd.DataFrame:
        """Build a boolean mask from the supplied filters and return matching rows."""
        if start_year is not None and end_year is not None and start_year > end_year:
            raise DisasterRepositoryError(
                f"start_year ({start_year}) must be <= end_year ({end_year})"
            )

        df = self._df
        mask = pd.Series(True, index=df.index)

        if country is not None:
            country_lc = country.strip().lower()
            country_upper = country.strip().upper()
            mask &= (
                (df["country_lc"] == country_lc)
                | (df["ISO"].astype("string") == country_upper)
            )

        if disaster_type is not None:
            mask &= df["Disaster Type"].astype("string") == disaster_type

        if location_contains is not None:
            substring = location_contains.strip().lower()
            mask &= df["location_lc"].fillna("").str.contains(
                substring, regex=False, na=False
            )

        if start_year is not None:
            mask &= df["Year"] >= start_year
        if end_year is not None:
            mask &= df["Year"] <= end_year

        return df[mask]

    def query(
        self,
        *,
        country: str | None,
        disaster_type: str | None,
        location_contains: str | None,
        start_year: int | None,
        end_year: int | None,
        limit: int,
    ) -> QueryResponse:
        """Return matching events sorted newest-first, capped at ``limit``."""
        matched = self._apply_filters(
            country=country,
            disaster_type=disaster_type,
            location_contains=location_contains,
            start_year=start_year,
            end_year=end_year,
        )
        sort_cols = ["Year", "Start Month", "Start Day"]
        matched = matched.sort_values(sort_cols, ascending=False, na_position="last")
        head = matched.head(limit)
        events = [_row_to_event(row) for row in head.to_dict(orient="records")]
        return QueryResponse(total_matched=int(len(matched)), events=events)


def _row_to_event(row: dict) -> DisasterEvent:
    """Convert a DataFrame row dict into a DisasterEvent."""
    return DisasterEvent(
        year=int(row["Year"]),
        country=str(row["Country"]),
        location=_optional_str(row.get("Location")),
        disaster_type=str(row["Disaster Type"]),
        disaster_subtype=_optional_str(row.get("Disaster Subtype")),
        total_deaths=_optional_int(row.get("Total Deaths")),
        total_affected=_optional_int(row.get("Total Affected")),
        total_damages_usd_thousands=_optional_float(row.get("Total Damages ('000 US$)")),
        event_name=_optional_str(row.get("Event Name")),
    )


def _optional_str(value: object) -> str | None:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return int(value)


def _optional_float(value: object) -> float | None:
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return float(value)


_repo: DisasterRepository | None = None


def get_repository() -> DisasterRepository:
    """Return the singleton repository, loading the CSV on first call."""
    global _repo
    if _repo is None:
        _repo = DisasterRepository(load_disasters(DISASTERS_CSV_PATH))
    return _repo
