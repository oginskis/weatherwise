# Disasters MCP Server & Agent Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third MCP server backed by the local EM-DAT natural disasters CSV (`data/emdat_disasters_1900_2021.csv`), expose three focused tools (`query_disasters`, `disaster_stats`, `location_disaster_summary`), and extend the existing PydanticAI agent so it answers direct disaster questions and adds historical-disaster context to weather questions.

**Architecture:** New Python package `src/mcp_servers/disasters/` with four modules — `loader.py` (CSV → DataFrame at startup), `repository.py` (singleton query layer), `models.py` (Pydantic response contracts), `server.py` (FastMCP tool registration). Agent gets a third toolset and a small system-prompt addition; UI gets a new disaster card; launcher gains a third subprocess.

**Tech Stack:** Python 3.10+, Pandas 2.x with PyArrow string backend and categorical dtypes, FastMCP (already used by news server), PydanticAI, Streamlit, pytest.

**Spec reference:** `docs/superpowers/specs/2026-04-26-disasters-mcp-design.md`.

---

## File Map

**Create:**
- `src/mcp_servers/disasters/__init__.py`
- `src/mcp_servers/disasters/models.py`
- `src/mcp_servers/disasters/loader.py`
- `src/mcp_servers/disasters/repository.py`
- `src/mcp_servers/disasters/server.py`
- `src/ui/components/disaster_card.py`
- `tests/conftest.py` (if absent — provides shared fixture)
- `tests/test_disasters_models.py`
- `tests/test_disasters_loader.py`
- `tests/test_disasters_repository.py`
- `tests/test_disasters_server.py`

**Modify:**
- `pyproject.toml` (add `pandas`, `pyarrow` to `[project].dependencies`)
- `src/agent/config.py` (disaster constants)
- `src/agent/models.py` (`DisasterSummaryView`, extend `AgentResponse`)
- `src/agent/agent.py` (add `disasters_mcp` toolset, extend `SYSTEM_PROMPT`)
- `src/ui/app.py` (render disaster card branch)
- `launcher.py` (start disasters MCP, health check)

---

## Task 1: Add dependencies and configuration constants

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/agent/config.py`

- [ ] **Step 1: Add `pandas` and `pyarrow` to runtime dependencies**

Edit `pyproject.toml`. Replace the `dependencies` list with:

```toml
dependencies = [
    "pydantic-ai[google,openai,anthropic]",
    "mcp-weather-server",
    "mcp",
    "httpx",
    "streamlit",
    "python-dotenv",
    "pydantic",
    "pandas>=2.2",
    "pyarrow>=15",
]
```

- [ ] **Step 2: Sync the lockfile**

Run: `uv sync`
Expected: completes successfully, installs `pandas` and `pyarrow` into `.venv`.

- [ ] **Step 3: Add disaster config constants**

Edit `src/agent/config.py`. Add these lines after the GNews section (keep all existing content intact):

```python
from pathlib import Path  # add to imports if not already present

# Disasters MCP
DISASTERS_MCP_PORT: int = 8082
DISASTERS_MCP_URL: str = f"http://localhost:{DISASTERS_MCP_PORT}/mcp"
DISASTERS_CSV_PATH: Path = Path("data/emdat_disasters_1900_2021.csv")
DISASTERS_MIN_YEAR_FOR_LOCATION_SUMMARY: int = 1980
DISASTERS_DEFAULT_QUERY_LIMIT: int = 20
DISASTERS_DEFAULT_TOP_N: int = 10
```

- [ ] **Step 4: Verify config still loads**

Run: `uv run python -c "from src.agent.config import DISASTERS_MCP_PORT, DISASTERS_CSV_PATH; print(DISASTERS_MCP_PORT, DISASTERS_CSV_PATH)"`
Expected output: `8082 data/emdat_disasters_1900_2021.csv`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/agent/config.py
git commit -m "chore: add pandas/pyarrow deps and disasters config constants"
```

---

## Task 2: Create disasters package skeleton + shared test fixture

**Files:**
- Create: `src/mcp_servers/disasters/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create empty package init**

Create `src/mcp_servers/disasters/__init__.py` with empty content (a single newline is fine).

- [ ] **Step 2: Create the shared test fixture**

Create `tests/conftest.py`:

```python
"""Shared pytest fixtures for the test suite."""
from pathlib import Path

import pandas as pd
import pytest

DISASTER_FIXTURE_ROWS: list[dict] = [
    # Japan — multiple events for top-N and location_summary tests
    {"Year": 2011, "Seq": 9001, "Disaster Group": "Natural", "Disaster Subgroup": "Geophysical",
     "Disaster Type": "Earthquake", "Disaster Subtype": "Earthquake", "Event Name": "Tohoku",
     "Country": "Japan", "ISO": "JPN", "Region": "Eastern Asia", "Continent": "Asia",
     "Location": "Tohoku region", "Latitude": "38.32", "Longitude": "142.37",
     "Start Year": 2011, "Start Month": 3, "Start Day": 11,
     "End Year": 2011, "End Month": 3, "End Day": 11,
     "Total Deaths": 19846, "Total Affected": 469000,
     "Total Damages ('000 US$)": 210000000, "CPI": 87.5},
    {"Year": 1995, "Seq": 9002, "Disaster Group": "Natural", "Disaster Subgroup": "Geophysical",
     "Disaster Type": "Earthquake", "Disaster Subtype": "Earthquake", "Event Name": "Kobe",
     "Country": "Japan", "ISO": "JPN", "Region": "Eastern Asia", "Continent": "Asia",
     "Location": "Kobe", "Latitude": "34.7", "Longitude": "135.2",
     "Start Year": 1995, "Start Month": 1, "Start Day": 17,
     "End Year": 1995, "End Month": 1, "End Day": 17,
     "Total Deaths": 6434, "Total Damages ('000 US$)": 100000000, "CPI": 72.3},
    {"Year": 2019, "Seq": 9003, "Disaster Group": "Natural", "Disaster Subgroup": "Meteorological",
     "Disaster Type": "Storm", "Disaster Subtype": "Tropical cyclone", "Event Name": "Hagibis",
     "Country": "Japan", "ISO": "JPN", "Region": "Eastern Asia", "Continent": "Asia",
     "Location": "Tokyo, Chiba", "Latitude": "35.69 N", "Longitude": "139.69 E",
     "Start Year": 2019, "Start Month": 10, "Start Day": 11,
     "End Year": 2019, "End Month": 10, "End Day": 13,
     "Total Deaths": 90, "Total Damages ('000 US$)": 17000000, "CPI": 99.0},
    # USA — multiple types, lat/lon with N/W suffix
    {"Year": 2005, "Seq": 9101, "Disaster Group": "Natural", "Disaster Subgroup": "Meteorological",
     "Disaster Type": "Storm", "Disaster Subtype": "Tropical cyclone", "Event Name": "Katrina",
     "Country": "United States of America (the)", "ISO": "USA",
     "Region": "Northern America", "Continent": "Americas",
     "Location": "Louisiana, Mississippi, Florida", "Latitude": "29.95",
     "Longitude": "-90.07",
     "Start Year": 2005, "Start Month": 8, "Start Day": 23,
     "End Year": 2005, "End Month": 8, "End Day": 31,
     "Total Deaths": 1833, "Total Damages ('000 US$)": 125000000, "CPI": 80.6},
    {"Year": 2017, "Seq": 9102, "Disaster Group": "Natural", "Disaster Subgroup": "Meteorological",
     "Disaster Type": "Storm", "Disaster Subtype": "Tropical cyclone", "Event Name": "Harvey",
     "Country": "United States of America (the)", "ISO": "USA",
     "Region": "Northern America", "Continent": "Americas",
     "Location": "Texas, Houston", "Latitude": "29.38 N", "Longitude": "95.16 W ",
     "Start Year": 2017, "Start Month": 8, "Start Day": 17,
     "End Year": 2017, "End Month": 9, "End Day": 2,
     "Total Deaths": 88, "Total Damages ('000 US$)": 95000000, "CPI": 96.1},
    {"Year": 2018, "Seq": 9103, "Disaster Group": "Natural", "Disaster Subgroup": "Climatological",
     "Disaster Type": "Wildfire", "Disaster Subtype": "Forest fire", "Event Name": "Camp Fire",
     "Country": "United States of America (the)", "ISO": "USA",
     "Region": "Northern America", "Continent": "Americas",
     "Location": "California, Butte County", "Latitude": "39.79", "Longitude": "-121.61",
     "Start Year": 2018, "Start Month": 11, "Start Day": 8,
     "End Year": 2018, "End Month": 11, "End Day": 25,
     "Total Deaths": 85, "Total Damages ('000 US$)": 16500000, "CPI": 98.0},
    # India — pre-1980 high-deaths event for top-N
    {"Year": 1900, "Seq": 9201, "Disaster Group": "Natural", "Disaster Subgroup": "Climatological",
     "Disaster Type": "Drought", "Disaster Subtype": "Drought",
     "Country": "India", "ISO": "IND", "Region": "Southern Asia", "Continent": "Asia",
     "Location": "Bengal",
     "Start Year": 1900, "End Year": 1900,
     "Total Deaths": 1250000, "CPI": 3.22},
    {"Year": 2019, "Seq": 9202, "Disaster Group": "Natural", "Disaster Subgroup": "Hydrological",
     "Disaster Type": "Flood", "Disaster Subtype": "Riverine flood",
     "Country": "India", "ISO": "IND", "Region": "Southern Asia", "Continent": "Asia",
     "Location": "Bengal, Odisha", "Latitude": "22.57", "Longitude": "88.36",
     "Start Year": 2019, "Start Month": 7, "Start Day": 1,
     "End Year": 2019, "End Month": 8, "End Day": 31,
     "Total Deaths": 3000, "Total Damages ('000 US$)": 5000000, "CPI": 99.0},
    # Australia — wildfires + flood
    {"Year": 2009, "Seq": 9301, "Disaster Group": "Natural", "Disaster Subgroup": "Climatological",
     "Disaster Type": "Wildfire", "Disaster Subtype": "Forest fire", "Event Name": "Black Saturday",
     "Country": "Australia", "ISO": "AUS", "Region": "Australia and New Zealand", "Continent": "Oceania",
     "Location": "Victoria", "Latitude": "-37.81", "Longitude": "144.96",
     "Start Year": 2009, "Start Month": 2, "Start Day": 7,
     "End Year": 2009, "End Month": 3, "End Day": 14,
     "Total Deaths": 173, "Total Damages ('000 US$)": 1300000, "CPI": 82.4},
    {"Year": 2011, "Seq": 9302, "Disaster Group": "Natural", "Disaster Subgroup": "Hydrological",
     "Disaster Type": "Flood", "Disaster Subtype": "Riverine flood",
     "Country": "Australia", "ISO": "AUS", "Region": "Australia and New Zealand", "Continent": "Oceania",
     "Location": "Queensland, Brisbane",
     "Start Year": 2010, "Start Month": 12, "Start Day": 25,
     "End Year": 2011, "End Month": 1, "End Day": 14,
     "Total Deaths": 35, "Total Damages ('000 US$)": 7300000, "CPI": 87.5},
    # Haiti — single deadliest event for ranking tests
    {"Year": 2010, "Seq": 9401, "Disaster Group": "Natural", "Disaster Subgroup": "Geophysical",
     "Disaster Type": "Earthquake", "Disaster Subtype": "Earthquake",
     "Country": "Haiti", "ISO": "HTI", "Region": "Caribbean", "Continent": "Americas",
     "Location": "Port-au-Prince", "Latitude": "18.54", "Longitude": "-72.34",
     "Start Year": 2010, "Start Month": 1, "Start Day": 12,
     "End Year": 2010, "End Month": 1, "End Day": 12,
     "Total Deaths": 222570, "Total Damages ('000 US$)": 8000000, "CPI": 84.0},
    # Latvia — only event, pre-1980 (used to test silence in location_disaster_summary)
    {"Year": 1969, "Seq": 9501, "Disaster Group": "Natural", "Disaster Subgroup": "Meteorological",
     "Disaster Type": "Storm", "Disaster Subtype": "Convective storm",
     "Country": "Latvia", "ISO": "LVA", "Region": "Northern Europe", "Continent": "Europe",
     "Location": "Riga",
     "Start Year": 1969, "End Year": 1969,
     "Total Deaths": 3, "CPI": 12.0},
]

ALL_FIXTURE_COLUMNS: list[str] = [
    "Year", "Seq", "Glide", "Disaster Group", "Disaster Subgroup", "Disaster Type",
    "Disaster Subtype", "Disaster Subsubtype", "Event Name", "Country", "ISO",
    "Region", "Continent", "Location", "Origin", "Associated Dis", "Associated Dis2",
    "OFDA Response", "Appeal", "Declaration", "Aid Contribution", "Dis Mag Value",
    "Dis Mag Scale", "Latitude", "Longitude", "Local Time", "River Basin",
    "Start Year", "Start Month", "Start Day", "End Year", "End Month", "End Day",
    "Total Deaths", "No Injured", "No Affected", "No Homeless", "Total Affected",
    "Insured Damages ('000 US$)", "Total Damages ('000 US$)", "CPI",
    "Adm Level", "Admin1 Code", "Admin2 Code", "Geo Locations",
]


@pytest.fixture
def disasters_fixture_path(tmp_path: Path) -> Path:
    """Write the disaster fixture rows to a temp CSV and return its path."""
    df = pd.DataFrame(DISASTER_FIXTURE_ROWS)
    # Ensure every column exists in the right order, even if blank
    for col in ALL_FIXTURE_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[ALL_FIXTURE_COLUMNS]
    csv_path = tmp_path / "fixture.csv"
    df.to_csv(csv_path, index=False)
    return csv_path
```

- [ ] **Step 3: Verify the fixture writes correctly**

Run: `uv run python -c "
import tempfile, pathlib
from tests.conftest import DISASTER_FIXTURE_ROWS, ALL_FIXTURE_COLUMNS
print('rows:', len(DISASTER_FIXTURE_ROWS), 'cols:', len(ALL_FIXTURE_COLUMNS))"`

Expected output: `rows: 12 cols: 45`

- [ ] **Step 4: Commit**

```bash
git add src/mcp_servers/disasters/__init__.py tests/conftest.py
git commit -m "test: add disasters fixture data and package skeleton"
```

---

## Task 3: Disasters server-side Pydantic models

**Files:**
- Create: `src/mcp_servers/disasters/models.py`
- Create: `tests/test_disasters_models.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_disasters_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_disasters_models.py -v`
Expected: import errors / ModuleNotFoundError for `src.mcp_servers.disasters.models`.

- [ ] **Step 3: Implement the models**

Create `src/mcp_servers/disasters/models.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_disasters_models.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/disasters/models.py tests/test_disasters_models.py
git commit -m "feat: add disasters MCP pydantic response models"
```

---

## Task 4: CSV loader with PyArrow + categorical dtypes and coordinate parsing

**Files:**
- Create: `src/mcp_servers/disasters/loader.py`
- Create: `tests/test_disasters_loader.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_disasters_loader.py`:

```python
import math

import pandas as pd

from src.mcp_servers.disasters.loader import _parse_coord, load_disasters


def test_load_disasters_reads_all_rows(disasters_fixture_path) -> None:
    df = load_disasters(disasters_fixture_path)
    assert len(df) == 12


def test_load_disasters_applies_categorical_dtypes(disasters_fixture_path) -> None:
    df = load_disasters(disasters_fixture_path)
    for col in ["Disaster Type", "Disaster Subgroup", "Continent", "ISO", "Country"]:
        assert isinstance(df[col].dtype, pd.CategoricalDtype), (
            f"column {col!r} should be categorical, got {df[col].dtype}"
        )


def test_load_disasters_adds_lowercase_helpers(disasters_fixture_path) -> None:
    df = load_disasters(disasters_fixture_path)
    assert "country_lc" in df.columns
    assert "location_lc" in df.columns
    # Japan rows should all be lowercase "japan" in country_lc
    japan_rows = df[df["ISO"] == "JPN"]
    assert (japan_rows["country_lc"] == "japan").all()
    # Tokyo row should match a "tokyo" substring
    tokyo_mask = df["location_lc"].str.contains("tokyo", na=False)
    assert tokyo_mask.sum() == 1


def test_load_disasters_parses_lat_lon_floats(disasters_fixture_path) -> None:
    df = load_disasters(disasters_fixture_path)
    # Plain decimal: row with Latitude="38.32" (Tohoku)
    tohoku = df[df["Event Name"] == "Tohoku"].iloc[0]
    assert tohoku["latitude"] == 38.32
    assert tohoku["longitude"] == 142.37
    # N/W suffix: row with Latitude="29.38 N", Longitude="95.16 W "
    harvey = df[df["Event Name"] == "Harvey"].iloc[0]
    assert harvey["latitude"] == 29.38
    assert harvey["longitude"] == -95.16
    # Already-negative decimal: Australia "-37.81"
    bs = df[df["Event Name"] == "Black Saturday"].iloc[0]
    assert bs["latitude"] == -37.81
    # Missing lat/lon (1900 Bengal drought) -> NaN
    drought_1900 = df[(df["Year"] == 1900) & (df["Country"] == "India")].iloc[0]
    assert math.isnan(drought_1900["latitude"])


def test_parse_coord_handles_known_formats() -> None:
    s = pd.Series(["38.32", "1.51 N", "78.46 W ", "-37.81", "29.38 n", None])
    parsed = _parse_coord(s, pos="N", neg="S")
    # First, second, fourth, fifth values are latitude-like
    assert parsed.iloc[0] == 38.32
    assert parsed.iloc[1] == 1.51    # "1.51 N" -> +1.51
    assert parsed.iloc[3] == -37.81  # already negative
    assert parsed.iloc[4] == 29.38   # lowercase 'n' still positive

    s2 = pd.Series(["78.46 W "])
    parsed2 = _parse_coord(s2, pos="E", neg="W")
    assert parsed2.iloc[0] == -78.46  # "78.46 W " -> -78.46


def test_parse_coord_returns_nan_for_garbage() -> None:
    s = pd.Series(["", "n/a", None, "abc"])
    parsed = _parse_coord(s, pos="N", neg="S")
    assert parsed.isna().all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_disasters_loader.py -v`
Expected: ModuleNotFoundError for `src.mcp_servers.disasters.loader`.

- [ ] **Step 3: Implement the loader**

Create `src/mcp_servers/disasters/loader.py`:

```python
"""Load the EM-DAT disasters CSV into a clean Pandas DataFrame.

Used at MCP server startup; the resulting DataFrame becomes the singleton
backing store for the repository layer.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CATEGORICAL_COLUMNS: list[str] = [
    "Disaster Group",
    "Disaster Subgroup",
    "Disaster Type",
    "Disaster Subtype",
    "Continent",
    "Region",
    "ISO",
    "Country",
]

_COORD_RE: re.Pattern[str] = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*([NSEWnsew])?\s*$"
)


def load_disasters(path: Path) -> pd.DataFrame:
    """Read the disaster CSV and return a cleaned DataFrame.

    The DataFrame retains the original column names and adds four derived
    columns: country_lc, location_lc, latitude, longitude.
    """
    logger.info("Loading disasters CSV from %s", path)
    df = pd.read_csv(
        path,
        dtype_backend="pyarrow",
        dtype={col: "category" for col in CATEGORICAL_COLUMNS},
    )
    df["country_lc"] = df["Country"].astype("string").str.lower()
    df["location_lc"] = df["Location"].astype("string").str.lower()
    df["latitude"] = _parse_coord(df["Latitude"], pos="N", neg="S")
    df["longitude"] = _parse_coord(df["Longitude"], pos="E", neg="W")
    logger.info("Loaded %d disaster rows", len(df))
    return df


def _parse_coord(series: pd.Series, *, pos: str, neg: str) -> pd.Series:
    """Parse coordinate strings like '38.32', '1.51 N', '78.46 W ' into floats.

    The hemisphere suffix ``pos`` means positive sign (N or E); ``neg`` means
    negative sign (S or W). Unrecognized values become NaN.
    """
    pos_upper, neg_upper = pos.upper(), neg.upper()

    def _convert(raw: object) -> float:
        if raw is None or (isinstance(raw, float) and np.isnan(raw)):
            return float("nan")
        text = str(raw).strip()
        if not text:
            return float("nan")
        match = _COORD_RE.match(text)
        if match is None:
            return float("nan")
        value = float(match.group(1))
        suffix = (match.group(2) or "").upper()
        if suffix == neg_upper:
            return -abs(value)
        if suffix == pos_upper:
            return abs(value)
        return value  # no suffix — keep value's own sign

    return series.map(_convert).astype("float64")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_disasters_loader.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/disasters/loader.py tests/test_disasters_loader.py
git commit -m "feat: add disasters CSV loader with pyarrow + categorical dtypes"
```

---

## Task 5: Repository skeleton + filter helper + custom exception

**Files:**
- Create: `src/mcp_servers/disasters/repository.py` (initial skeleton)
- Create: `tests/test_disasters_repository.py` (initial filter tests)

This task lays down the shared filtering primitives. Subsequent tasks add `query`, `stats`, and `location_summary` on top.

- [ ] **Step 1: Write the failing tests for filter behaviour**

Create `tests/test_disasters_repository.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_disasters_repository.py -v`
Expected: ModuleNotFoundError for `src.mcp_servers.disasters.repository`.

- [ ] **Step 3: Implement the skeleton + filter helper**

Create `src/mcp_servers/disasters/repository.py`:

```python
"""DisasterRepository — pandas DataFrame query layer for the disasters MCP.

Holds a singleton DataFrame loaded once at startup. All public methods
(:meth:`query`, :meth:`stats`, :meth:`location_summary`) build their masks
through the shared :meth:`_apply_filters` helper to keep filtering semantics
consistent.
"""
from __future__ import annotations

import logging

import pandas as pd

from src.agent.config import (
    DISASTERS_CSV_PATH,
    DISASTERS_MIN_YEAR_FOR_LOCATION_SUMMARY,
)
from .loader import load_disasters

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


_repo: DisasterRepository | None = None


def get_repository() -> DisasterRepository:
    """Return the singleton repository, loading the CSV on first call."""
    global _repo
    if _repo is None:
        _repo = DisasterRepository(load_disasters(DISASTERS_CSV_PATH))
    return _repo
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_disasters_repository.py -v`
Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/disasters/repository.py tests/test_disasters_repository.py
git commit -m "feat: add disasters repository skeleton with shared filter helper"
```

---

## Task 6: Repository.query — paginated event listing

**Files:**
- Modify: `src/mcp_servers/disasters/repository.py`
- Modify: `tests/test_disasters_repository.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_disasters_repository.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_disasters_repository.py -v -k "test_query"`
Expected: AttributeError — `DisasterRepository` has no attribute `query`.

- [ ] **Step 3: Implement the `query` method**

Add these imports to the top of `src/mcp_servers/disasters/repository.py` (alongside existing imports):

```python
from .models import DisasterEvent, QueryResponse
```

Add the `query` method to the `DisasterRepository` class (after `_apply_filters`):

```python
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
```

Add the helper at module level (after the class):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_disasters_repository.py -v`
Expected: all repository tests PASS (now ~15 total).

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/disasters/repository.py tests/test_disasters_repository.py
git commit -m "feat: implement DisasterRepository.query with sorted paginated events"
```

---

## Task 7: Repository.stats — aggregations and rankings

**Files:**
- Modify: `src/mcp_servers/disasters/repository.py`
- Modify: `tests/test_disasters_repository.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_disasters_repository.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_disasters_repository.py -v -k "test_stats"`
Expected: AttributeError — `DisasterRepository` has no attribute `stats`.

- [ ] **Step 3: Implement the `stats` method**

Update the imports at the top of `src/mcp_servers/disasters/repository.py`:

```python
from .models import DisasterEvent, QueryResponse, StatsResponse, StatsRow
```

Add module-level constants and the `stats` method.

Constants near the top (after imports):

```python
_VALID_GROUP_BY: dict[str, str] = {
    "year": "Year",
    "decade": "_decade",
    "type": "Disaster Type",
    "country": "Country",
    "continent": "Continent",
}

_DAMAGES_COLUMN: str = "Total Damages ('000 US$)"
```

Add the `stats` method to `DisasterRepository` (after `query`):

```python
def stats(
    self,
    *,
    group_by: str,
    metric: str,
    country: str | None,
    disaster_type: str | None,
    start_year: int | None,
    end_year: int | None,
    top_n: int,
) -> StatsResponse:
    """Aggregate matching events by ``group_by`` and rank by ``metric``."""
    if group_by not in _VALID_GROUP_BY:
        raise DisasterRepositoryError(
            f"unknown group_by={group_by!r}; "
            f"expected one of {sorted(_VALID_GROUP_BY)}"
        )
    if metric not in {"count", "total_deaths", "total_damages_usd"}:
        raise DisasterRepositoryError(
            f"unknown metric={metric!r}; "
            "expected one of ['count', 'total_deaths', 'total_damages_usd']"
        )

    matched = self._apply_filters(
        country=country,
        disaster_type=disaster_type,
        location_contains=None,
        start_year=start_year,
        end_year=end_year,
    ).copy()

    if group_by == "decade":
        matched["_decade"] = (matched["Year"] // 10) * 10

    column = _VALID_GROUP_BY[group_by]
    grouped = matched.groupby(column, observed=True)

    if metric == "count":
        agg = grouped.size().rename("metric_value")
        counts = agg
    elif metric == "total_deaths":
        agg = grouped["Total Deaths"].sum().fillna(0).rename("metric_value")
        counts = grouped.size()
    else:  # total_damages_usd
        agg = grouped[_DAMAGES_COLUMN].sum().fillna(0).rename("metric_value")
        counts = grouped.size()

    combined = pd.concat([agg, counts.rename("event_count")], axis=1)
    combined = combined.sort_values("metric_value", ascending=False).head(top_n)

    rows = [
        StatsRow(
            group_value=str(idx),
            metric_value=float(row["metric_value"]),
            event_count=int(row["event_count"]),
        )
        for idx, row in combined.iterrows()
    ]
    return StatsResponse(group_by=group_by, metric=metric, rows=rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_disasters_repository.py -v`
Expected: all repository tests PASS (now ~23 total).

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/disasters/repository.py tests/test_disasters_repository.py
git commit -m "feat: implement DisasterRepository.stats with grouped aggregation and top-N ranking"
```

---

## Task 8: Repository.location_summary — narrative-shaped weather-flow tool

**Files:**
- Modify: `src/mcp_servers/disasters/repository.py`
- Modify: `tests/test_disasters_repository.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_disasters_repository.py`:

```python
def test_location_summary_japan_populated(repo) -> None:
    summary = repo.location_summary(country="Japan", location_contains=None)
    assert summary.country == "Japan"
    assert summary.location_filter is None
    assert summary.total_events == 3
    assert summary.time_span == "1995–2019"
    assert summary.deadliest_event is not None
    assert summary.deadliest_event.year == 2011
    assert summary.deadliest_event.disaster_type == "Earthquake"


def test_location_summary_top_types_capped_at_3(repo) -> None:
    summary = repo.location_summary(country="USA", location_contains=None)
    assert len(summary.top_types) <= 3
    types = {item.disaster_type for item in summary.top_types}
    assert "Storm" in types  # USA has 2 storms + 1 wildfire


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_disasters_repository.py -v -k "test_location_summary"`
Expected: AttributeError.

- [ ] **Step 3: Implement the `location_summary` method**

Update imports in `src/mcp_servers/disasters/repository.py` to include the new models:

```python
from .models import (
    DisasterEvent,
    DisasterTypeCount,
    LocationSummary,
    QueryResponse,
    StatsResponse,
    StatsRow,
)
```

Add the method to `DisasterRepository` (after `stats`):

```python
def location_summary(
    self,
    *,
    country: str,
    location_contains: str | None,
    min_year: int = DISASTERS_MIN_YEAR_FOR_LOCATION_SUMMARY,
) -> LocationSummary:
    """Summarize disasters at a location for the weather-flow context.

    Defaults to events from ``min_year`` onward to mitigate pre-1970 reporting
    bias. Returns an empty summary (total_events=0) when nothing matches.
    """
    matched = self._apply_filters(
        country=country,
        disaster_type=None,
        location_contains=location_contains,
        start_year=min_year,
        end_year=None,
    )

    if len(matched) == 0:
        return LocationSummary(
            country=country,
            location_filter=location_contains.strip().lower() if location_contains else None,
            total_events=0,
            time_span=None,
            top_types=[],
            deadliest_event=None,
        )

    years = matched["Year"]
    time_span = f"{int(years.min())}–{int(years.max())}"

    type_counts = (
        matched["Disaster Type"]
        .astype("string")
        .value_counts()
        .head(3)
    )
    top_types = [
        DisasterTypeCount(disaster_type=str(name), count=int(value))
        for name, value in type_counts.items()
    ]

    deadliest_idx = matched["Total Deaths"].idxmax()
    if pd.isna(deadliest_idx):
        deadliest_event = None
    else:
        deadliest_event = _row_to_event(matched.loc[deadliest_idx].to_dict())

    return LocationSummary(
        country=country,
        location_filter=location_contains.strip().lower() if location_contains else None,
        total_events=int(len(matched)),
        time_span=time_span,
        top_types=top_types,
        deadliest_event=deadliest_event,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_disasters_repository.py -v`
Expected: all repository tests PASS (now ~29 total).

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/disasters/repository.py tests/test_disasters_repository.py
git commit -m "feat: implement DisasterRepository.location_summary with 1980+ default window"
```

---

## Task 9: FastMCP server with three tools

**Files:**
- Create: `src/mcp_servers/disasters/server.py`
- Create: `tests/test_disasters_server.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_disasters_server.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_disasters_server.py -v`
Expected: ModuleNotFoundError for `src.mcp_servers.disasters.server`.

- [ ] **Step 3: Implement the server**

Create `src/mcp_servers/disasters/server.py`:

```python
"""FastMCP server exposing the three disasters tools.

Mirrors the structure of ``src/mcp_servers/news/server.py``: tool registration
only, no business logic. The repository owns querying; this module owns transport
and serialization.
"""
from __future__ import annotations

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_disasters_server.py -v`
Expected: all 6 server tests PASS.

- [ ] **Step 5: Run the full disasters test suite to confirm nothing regressed**

Run: `uv run pytest tests/ -v -k "disasters"`
Expected: ~35 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/mcp_servers/disasters/server.py tests/test_disasters_server.py
git commit -m "feat: add disasters FastMCP server with three tools"
```

---

## Task 10: Manual end-to-end test of the disasters MCP

**Files:** none modified — this is a manual validation step before agent integration.

- [ ] **Step 1: Start the disasters MCP server in isolation**

In one terminal, run: `uv run python -m src.mcp_servers.disasters.server`
Expected: log line `Loaded N disaster rows` (where N=16126) and `Uvicorn running on http://127.0.0.1:8082`. The process keeps running.

- [ ] **Step 2: Hit the MCP server with a JSON-RPC initialize request**

In a second terminal:

```bash
curl -s -X POST http://localhost:8082/mcp \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"manual-check","version":"0.1.0"}}}'
```

Expected: a 200 response containing `"serverInfo":{"name":"disasters-server"...}`.

- [ ] **Step 3: Stop the server**

Press `Ctrl+C` in the first terminal. Confirm clean shutdown.

- [ ] **Step 4: No commit — this task is verification only.**

---

## Task 11: Add `DisasterSummaryView` to agent models

**Files:**
- Modify: `src/agent/models.py`
- Create test: `tests/test_agent_models.py` already exists; extend it

- [ ] **Step 1: Read the existing agent models test file**

Open `tests/test_agent_models.py` in your editor. The existing test pattern uses imports from `src.agent.models` and Pydantic constructor calls — match that style.

- [ ] **Step 2: Write a failing test for the new field**

Update the import line at the top of `tests/test_agent_models.py` from:

```python
from src.agent.models import AgentResponse, ArticleData, WeatherData
```

to:

```python
from src.agent.models import AgentResponse, ArticleData, DisasterSummaryView, WeatherData
```

Then append three new tests at the end of the file:

```python
def test_disaster_summary_view_round_trip() -> None:
    view = DisasterSummaryView(
        total_events=3,
        time_span="1995–2019",
        top_types=[("Earthquake", 2), ("Storm", 1)],
        deadliest_event_summary="2011 Earthquake (Tohoku, 19,846 deaths)",
    )
    rehydrated = DisasterSummaryView.model_validate_json(view.model_dump_json())
    assert rehydrated.total_events == 3
    assert rehydrated.top_types == [("Earthquake", 2), ("Storm", 1)]


def test_agent_response_disasters_field_optional() -> None:
    response = AgentResponse(message="hello")
    assert response.disasters is None


def test_agent_response_with_disaster_summary() -> None:
    summary = DisasterSummaryView(
        total_events=1,
        time_span="2010",
        top_types=[("Earthquake", 1)],
        deadliest_event_summary="2010 Earthquake (Port-au-Prince, 222,570 deaths)",
    )
    response = AgentResponse(message="Haiti has had one major disaster.", disasters=summary)
    assert response.disasters is not None
    assert response.disasters.total_events == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent_models.py -v -k "disaster"`
Expected: ImportError — `DisasterSummaryView` not exported from `src.agent.models`.

- [ ] **Step 4: Add the new model and extend `AgentResponse`**

Edit `src/agent/models.py`. Replace the file contents with:

```python
from pydantic import BaseModel


class WeatherData(BaseModel):
    location: str
    temperature: float
    conditions: str
    humidity: float | None = None
    wind_speed: float | None = None


class ArticleData(BaseModel):
    title: str
    description: str
    source: str
    url: str
    image_url: str | None = None


class DisasterSummaryView(BaseModel):
    """Compact disaster summary rendered as a UI card for direct questions."""

    total_events: int
    time_span: str | None
    top_types: list[tuple[str, int]]
    deadliest_event_summary: str | None


class AgentResponse(BaseModel):
    message: str
    weather: WeatherData | None = None
    articles: list[ArticleData] | None = None
    disasters: DisasterSummaryView | None = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent_models.py -v`
Expected: all tests PASS, including the three new ones.

- [ ] **Step 6: Commit**

```bash
git add src/agent/models.py tests/test_agent_models.py
git commit -m "feat: add DisasterSummaryView and disasters field on AgentResponse"
```

---

## Task 12: Wire the disasters MCP into the agent + extend system prompt

**Files:**
- Modify: `src/agent/agent.py`

This task updates the agent in two coordinated edits and includes the mandatory full-prompt re-read flagged in the spec.

- [ ] **Step 1: Add the `disasters_mcp` toolset and import**

Edit `src/agent/agent.py`. Update the imports block:

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

from .config import DISASTERS_MCP_URL, LLM_MODEL, NEWS_MCP_URL, WEATHER_MCP_URL
from .models import AgentResponse
```

After the existing `news_mcp = ...` line, add:

```python
disasters_mcp = MCPServerStreamableHTTP(DISASTERS_MCP_URL)
```

Update the `toolsets` argument:

```python
agent = Agent(
    LLM_MODEL,
    output_type=AgentResponse,
    system_prompt=SYSTEM_PROMPT,
    toolsets=[weather_mcp, news_mcp, disasters_mcp],
)
```

- [ ] **Step 2: Extend `ALLOWED TOPICS` in the system prompt**

In the `SYSTEM_PROMPT` triple-quoted string, locate the `ALLOWED TOPICS (exhaustive list):` section. Replace it with:

```
ALLOWED TOPICS (exhaustive list):
- Current weather conditions, forecasts, temperature, humidity, wind for any location
- Latest news articles, headlines, and summaries on any news topic
- Historical natural disaster records (1900-2021) — what/where/when disasters happened, counts, deadliest events, and costliest events
```

- [ ] **Step 3: Add the `DISASTER RESPONSE FORMAT` and `WEATHER + DISASTER` rules**

Insert this new section in `SYSTEM_PROMPT` immediately AFTER the existing `WEATHER RESPONSE FORMAT` block and BEFORE the `COMBINED WEATHER + NEWS RESPONSE FORMAT` block (so disasters live next to weather, since they share a flow):

```
DISASTER RESPONSE FORMAT:
For direct disaster questions (what/where/when, counts, deadliest, costliest, \
rankings), use the disaster tools and populate the "disasters" field on your \
response. Tool routing:
- query_disasters — when the user wants specific events listed (filtered by \
country, type, location, year range).
- disaster_stats — when the user wants rankings, counts, totals, or "which \
decade/country/type" answers.
The "message" field should contain a friendly synthesis (2-4 sentences) — \
what the data shows and why the answer is interesting. Then populate \
"disasters" with a compact DisasterSummaryView (total_events, time_span, \
top_types, deadliest_event_summary) so the UI renders a card.

WEATHER + DISASTER RULE (ALWAYS APPLIES):
When the user asks about weather in a specific place, ALWAYS also call \
location_disaster_summary(country, location_contains) for that place. \
- If total_events > 0, weave ONE short sentence about the disaster history \
into your weather message (e.g. "This region has a long history of \
typhoons" or "The area was hit by a major flood in 2014"). Pick a fact from \
deadliest_event or top_types — do not invent details. Keep "disasters" set \
to null on the response (the weather card alone is enough; no disaster card \
on weather queries — that is the hybrid response rule).
- If total_events == 0, do NOT mention disasters at all. Stay silent. Do not \
say "I checked but found nothing"; let the weather speak for itself.

DISASTER SELF-REFLECTION:
Before returning disaster results, verify:
1. RELEVANCE — Do the events answer the user's question? A request for \
"earthquakes" should not return floods.
2. COMPLETENESS — If the user asked "deadliest" or "costliest", did you call \
disaster_stats and rank by the right metric (total_deaths or \
total_damages_usd)?
3. EMPTY-RESULT HONESTY — On direct disaster questions with no matches, say \
so plainly ("I couldn't find any recorded events matching that"). On weather \
queries with no matches, stay silent.
```

- [ ] **Step 4: Mandatory full-prompt re-read**

Open `src/agent/agent.py` in your editor and read the entire `SYSTEM_PROMPT` from `<system_instructions>` to `</system_instructions>` as one continuous text. Verify each of the following — fix inline as you go:

- [ ] **(a) Voice consistency.** The new `DISASTER RESPONSE FORMAT`, `WEATHER + DISASTER RULE`, and `DISASTER SELF-REFLECTION` blocks use the same instructional voice as `WEATHER RESPONSE FORMAT`, `NEWS RESPONSE FORMAT`, and the existing `SELF-REFLECTION` section. No tonal shifts.
- [ ] **(b) Section ordering.** Confirm the order is: ROLE AND SCOPE, ALLOWED TOPICS, INSTRUCTION PRIORITY, OFF-TOPIC HANDLING, DATA INTEGRITY, SELF-REFLECTION (news), NEWS RESPONSE FORMAT, WEATHER RESPONSE FORMAT, DISASTER RESPONSE FORMAT (NEW), WEATHER + DISASTER RULE (NEW), DISASTER SELF-REFLECTION (NEW), COMBINED WEATHER + NEWS RESPONSE FORMAT, GENERAL TONE, REMINDER. Adjust if disaster blocks read better in a different position.
- [ ] **(c) Terminology consistency.** Is the field uniformly called `"disasters"`? Is the model uniformly called `DisasterSummaryView`? Are the three tool names spelled exactly `query_disasters`, `disaster_stats`, `location_disaster_summary` with no variants? Fix any drift.
- [ ] **(d) Duplication and contradiction.** The existing `SELF-REFLECTION` rule applies to news; the new `DISASTER SELF-REFLECTION` applies to disasters. Confirm they don't accidentally cross-reference each other or contradict the `DATA INTEGRITY` rule.
- [ ] **(e) `REMINDER` section.** Update the closing `REMINDER: You ONLY answer about weather and news.` line to: `REMINDER: You ONLY answer about weather, news, and historical natural disasters. No exceptions.`
- [ ] **(f) `OFF-TOPIC HANDLING` refusal message.** Update the example refusal message: `"I can only help with weather, news, and historical natural disasters. Try asking me about the weather in a city, the latest news on a topic, or what disasters happened in a country!"`

If after the re-read the prompt feels disjointed, restructure the new sections — voice and ordering matter more than literal placement.

- [ ] **Step 5: Run all existing agent-related tests**

Run: `uv run pytest tests/test_agent_models.py -v`
Expected: all PASS (the prompt edits are runtime, not validated by these tests, but agent imports must still succeed).

Run: `uv run python -c "from src.agent.agent import agent; print('ok', len(agent._system_prompts))"` (any non-error output is acceptable; this verifies the prompt parses and the toolsets initialize without raising).

- [ ] **Step 6: Commit**

```bash
git add src/agent/agent.py
git commit -m "feat: wire disasters MCP into agent toolsets and extend system prompt"
```

---

## Task 13: Disaster card UI component

**Files:**
- Create: `src/ui/components/disaster_card.py`

- [ ] **Step 1: Inspect the existing weather card for styling patterns**

The new component mirrors `src/ui/components/weather_card.py`. Custom CSS in `src/ui/styles/custom.css` already defines `.weather-card` and `.news-card` styles; we reuse the structural patterns and add `.disaster-card` style classes.

- [ ] **Step 2: Implement `disaster_card.py`**

Create `src/ui/components/disaster_card.py`:

```python
import html

import streamlit as st

from src.agent.models import DisasterSummaryView

DISASTER_TYPE_ICONS: dict[str, str] = {
    "earthquake": "🪨",
    "flood": "🌊",
    "storm": "🌪️",
    "wildfire": "🔥",
    "drought": "🏜️",
    "landslide": "⛰️",
    "epidemic": "🦠",
    "extreme temperature": "🌡️",
    "volcanic": "🌋",
}

DEFAULT_DISASTER_ICON: str = "⚠️"


def _resolve_icon(disaster_type: str) -> str:
    key = disaster_type.lower()
    for fragment, icon in DISASTER_TYPE_ICONS.items():
        if fragment in key:
            return icon
    return DEFAULT_DISASTER_ICON


def render_disaster_card(summary: DisasterSummaryView) -> None:
    """Render a compact disaster summary card."""
    time_span = html.escape(summary.time_span or "")
    chips = "".join(
        f'<span class="disaster-chip">{_resolve_icon(t)} '
        f'{html.escape(t)} <strong>{c}</strong></span>'
        for t, c in summary.top_types
    )
    deadliest_html = ""
    if summary.deadliest_event_summary:
        deadliest_html = (
            f'<div class="disaster-card-deadliest">'
            f'Deadliest: {html.escape(summary.deadliest_event_summary)}'
            f'</div>'
        )

    markup = f"""
    <div class="disaster-card">
        <div class="disaster-card-header">
            <span class="disaster-icon">⚠️</span>
            <span class="disaster-card-title">
                {summary.total_events} historical events
                <span class="disaster-card-span"> · {time_span}</span>
            </span>
        </div>
        <div class="disaster-card-chips">{chips}</div>
        {deadliest_html}
    </div>
    """
    st.html(markup)
```

- [ ] **Step 3: Add card CSS**

Edit `src/ui/styles/custom.css`. Append at the bottom:

```css
.disaster-card {
    background: #fff7ed;
    border: 1px solid #fdba74;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
}
.disaster-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
}
.disaster-card-span {
    font-weight: 400;
    color: #9a3412;
    font-size: 14px;
}
.disaster-card-chips {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 8px;
}
.disaster-chip {
    background: #ffedd5;
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 13px;
}
.disaster-card-deadliest {
    margin-top: 8px;
    font-size: 13px;
    color: #7c2d12;
    font-style: italic;
}
```

- [ ] **Step 4: Sanity-check imports**

Run: `uv run python -c "from src.ui.components.disaster_card import render_disaster_card; print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add src/ui/components/disaster_card.py src/ui/styles/custom.css
git commit -m "feat: add disaster_card UI component with matching styles"
```

---

## Task 14: Wire disaster card into Streamlit app

**Files:**
- Modify: `src/ui/app.py`

- [ ] **Step 1: Update `_render_response` to render the disaster card**

Edit `src/ui/app.py`. Replace the `_render_response` function with:

```python
def _render_response(response) -> None:
    """Render the agent response with text and optional cards."""
    from src.ui.components.disaster_card import render_disaster_card
    from src.ui.components.news_card import render_news_cards
    from src.ui.components.weather_card import render_weather_card

    if response.message:
        st.markdown(response.message)
    if response.weather is not None:
        render_weather_card(response.weather)
    if response.articles is not None:
        render_news_cards(response.articles)
    if response.disasters is not None:
        render_disaster_card(response.disasters)
```

- [ ] **Step 2: Add a disaster-themed conversation starter**

In the `CONVERSATION_STARTERS` list near the top of `src/ui/app.py`, add a fourth (or fifth) starter:

```python
CONVERSATION_STARTERS: list[dict[str, str]] = [
    {"label": "Weather in New York", "icon": "🌤️", "prompt": "What's the weather like in New York right now?"},
    {"label": "Today's tech news", "icon": "💻", "prompt": "What are the latest technology news headlines?"},
    {"label": "Weather in Tokyo", "icon": "🗼", "prompt": "What's the current weather in Tokyo?"},
    {"label": "Deadliest earthquakes", "icon": "🪨", "prompt": "What were the deadliest earthquakes ever recorded?"},
]
```

(Replace one existing starter or extend to 5 — your choice; keep the grid balanced.)

- [ ] **Step 3: Sanity-check imports**

Run: `uv run python -c "from src.ui.app import main; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add src/ui/app.py
git commit -m "feat: render disaster card in Streamlit response and add disaster starter"
```

---

## Task 15: Launcher integration

**Files:**
- Modify: `launcher.py`

- [ ] **Step 1: Add the disasters MCP starter and health check**

Edit `launcher.py`. Update the imports:

```python
from src.agent.config import (
    DISASTERS_MCP_PORT,
    NEWS_MCP_PORT,
    STREAMLIT_PORT,
    WEATHER_MCP_PORT,
)
```

Add the `_start_disasters_mcp` function immediately after `_start_news_mcp`:

```python
def _start_disasters_mcp() -> subprocess.Popen[bytes]:
    """Start the disasters MCP server."""
    logger.info("Starting disasters MCP server on port %d...", DISASTERS_MCP_PORT)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "src.mcp_servers.disasters.server",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
```

In `main`, after the `news_proc = _start_news_mcp()` block, add:

```python
    disasters_proc = _start_disasters_mcp()
    processes.append(disasters_proc)
```

After the existing `_wait_for_server(NEWS_MCP_PORT, "News MCP")` check, add:

```python
    if not _wait_for_server(DISASTERS_MCP_PORT, "Disasters MCP"):
        _shutdown()
        return
```

- [ ] **Step 2: Sanity-check imports**

Run: `uv run python -c "from launcher import main; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add launcher.py
git commit -m "feat: launch disasters MCP alongside weather and news servers"
```

---

## Task 16: End-to-end manual smoke test

**Files:** none modified — final integration verification.

- [ ] **Step 1: Run the full test suite once**

Run: `uv run pytest tests/ -v`
Expected: all tests pass (existing news/weather tests + ~35 new disasters tests).

- [ ] **Step 2: Start the full stack**

Run: `uv run python launcher.py`
Expected log lines:
- `Starting weather MCP server on port 8080...`
- `Starting news MCP server on port 8081...`
- `Starting disasters MCP server on port 8082...`
- `Loaded 16126 disaster rows`
- `Weather MCP is ready ...`, `News MCP is ready ...`, `Disasters MCP is ready ...`
- Streamlit URL printed.

- [ ] **Step 3: Open the Streamlit UI in a browser and run four scripted prompts**

Open `http://localhost:8501`. For each prompt below, type it into the chat input and verify the listed expected behavior. Take a screenshot of each response for the PR description.

| # | Prompt | Expected behavior |
|---|---|---|
| 1 | `What's the weather in Tokyo?` | Weather card renders. Message includes ONE short sentence about disaster history (e.g. mentions earthquakes or storms). NO disaster card visible (hybrid rule). |
| 2 | `What's the weather in Riga?` | Weather card renders. Message contains NO mention of disasters at all. NO disaster card. |
| 3 | `What were the deadliest earthquakes in Japan?` | Disaster card renders with total_events, time span, top types, deadliest event summary. Message synthesizes the data in 2-4 sentences. |
| 4 | `Which decade had the most floods worldwide?` | Disaster card renders showing decade rankings. Message names the top decade. |

- [ ] **Step 4: Stop the launcher**

Press `Ctrl+C` in the launcher terminal. Confirm all three MCP processes shut down cleanly.

- [ ] **Step 5: Update README (lightweight, optional)**

If `README.md` documents the architecture, add a one-line mention of the disasters MCP. If not, skip.

- [ ] **Step 6: Final commit (if README touched)**

```bash
git add README.md
git commit -m "docs: mention disasters MCP in architecture overview"
```

---

## Self-review notes

(Run by the plan author after writing the plan.)

**Spec coverage:**
- Spec §4 architecture → Tasks 2, 4, 5, 9, 12, 14, 15 (directory structure, modules, agent wiring, UI, launcher).
- Spec §5 three MCP tools → Task 9.
- Spec §6 data models → Tasks 3 (server-side), 11 (agent-side).
- Spec §7 storage / loader → Task 4.
- Spec §8 repository → Tasks 5, 6, 7, 8.
- Spec §9 configuration → Task 1.
- Spec §10.1 system prompt + mandatory re-read → Task 12, Steps 2–4.
- Spec §10.2 toolset wiring → Task 12, Step 1.
- Spec §11 UI → Tasks 13, 14.
- Spec §12 launcher → Task 15.
- Spec §13 error handling → Tasks 5 (`DisasterRepositoryError`), 9 (server-side `{"error": ...}`), with empty-result tests in Tasks 6, 7, 8.
- Spec §14 testing → Tasks 3, 4, 5, 6, 7, 8, 9, 11; manual verification Tasks 10, 16.

**Placeholder scan:** No "TBD", "TODO", "implement later", or vague "add error handling" lines. Every step contains the actual code or command needed.

**Type consistency:** `DisasterEvent`, `DisasterTypeCount`, `LocationSummary`, `QueryResponse`, `StatsResponse`, `StatsRow` are defined in Task 3 and used unchanged in Tasks 6, 7, 8. `DisasterSummaryView` defined in Task 11 and used unchanged in Tasks 13, 14. `DisasterRepositoryError` defined in Task 5 and caught in Task 9. Method signatures (`query`, `stats`, `location_summary`) are consistent across tasks.
