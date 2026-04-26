# Disasters MCP Server & Agent Integration — Design Spec

**Date:** 2026-04-26
**Status:** Draft (awaiting user approval)
**Owner:** oginskis

---

## 1. Goal

Add a third MCP server backed by the local EM-DAT natural disasters dataset (`data/emdat_disasters_1900_2021.csv`) and extend the existing weather/news agent so it can:

- Answer **direct disaster questions** ("what was the deadliest earthquake in Japan?", "how many floods in 2010?", "list wildfires in Australia 2010–2020").
- **Augment weather answers** with one-sentence historical-disaster context for the location, but only when there is non-trivial recent history. Stay silent about disasters when the location has none.

The dataset is small (16,126 rows × 45 columns, ~4.7 MB CSV) and read-only at runtime, so it lives entirely in memory in the MCP-server process.

## 2. Non-goals

- Geocoding or lat/lon radius search. Country + free-text `Location` substring match is sufficient.
- Inflation-adjusted damages (`damages_real_usd`). Easy follow-up; no current tool needs it.
- Caching of repository results. Pandas filters on 16k rows are fast enough.
- Real-time / live disaster feeds. EM-DAT data is historical and static.
- Integration tests over the real full CSV in CI (fixture-only).

## 3. Decisions made during brainstorming

| # | Decision | Rationale |
|---|---|---|
| 1 | **Location matching = country + `Location` substring** (case-insensitive) | Simple, no geocoder dep; degrades to country-level when no city is mentioned. |
| 2 | **Three focused MCP tools** — `query_disasters`, `disaster_stats`, `location_disaster_summary` | Distinct intents → distinct tools. Mirrors news server's `search_news` vs `top_headlines`. Tool docstrings carry the routing rules. |
| 3 | **Storage: Pandas + PyArrow + categorical dtypes**, load-once singleton | Modern Pandas 2.x idiom; categorical for low-vocab columns (Disaster Type, Continent, ISO, Country, etc.); PyArrow string backend for the rest. ~3 MB RAM, faster groupby/filter. |
| 4 | **Time window: split by tool purpose** | `location_disaster_summary` defaults to **1980+** (mitigates pre-1970 reporting bias flagged in the data report). `query_disasters` and `disaster_stats` accept optional year filters with no default cap. |
| 5 | **Response shape: hybrid** | Direct disaster questions → typed `disasters` field on `AgentResponse` + UI card. Weather-flow disaster context → message prose only, no UI card. Set `disasters = None` in the weather flow regardless. |

## 4. Architecture

```
launcher.py
  ├── weather MCP        (port 8080, external mcp-weather-server)
  ├── news MCP           (port 8081, custom)
  ├── disasters MCP      (port 8082, NEW — this spec)
  └── streamlit UI       (port 8501)

agent.py
  └── pydantic-ai Agent
        ├── weather_mcp toolset
        ├── news_mcp toolset
        └── disasters_mcp toolset                  (NEW)

src/mcp_servers/disasters/                         (NEW package)
  ├── __init__.py
  ├── server.py          – FastMCP tool registration & JSON serialization
  ├── repository.py      – pandas DataFrame query layer (singleton)
  ├── loader.py          – CSV → DataFrame at startup, cleanup pass
  └── models.py          – Pydantic response contracts
```

The split between `loader.py` (one-time concern) and `repository.py` (per-request concern) keeps each module's responsibility small and matches the SRP rules in `agents.md`.

`server.py` contains no business logic — only tool registration, parameter forwarding to the repository, and JSON serialization of typed responses, identical to the pattern in `src/mcp_servers/news/server.py`.

## 5. The three MCP tools

### 5.1 `query_disasters` — direct event listing

```python
@mcp.tool()
async def query_disasters(
    country: str | None = None,            # case-insensitive vs Country or ISO
    disaster_type: str | None = None,      # e.g. "Flood", "Earthquake"
    location_contains: str | None = None,  # substring on free-text Location
    start_year: int | None = None,
    end_year: int | None = None,
    limit: int = 20,
) -> str:
```

Use case: "wildfires in Australia 2010–2020", "what happened in Haiti in 2010".
Returns: `QueryResponse(total_matched, events: list[DisasterEvent])`.
Sort: chronological descending by `Year, Start Month, Start Day`.

### 5.2 `disaster_stats` — aggregations & rankings

```python
@mcp.tool()
async def disaster_stats(
    group_by: Literal["year", "decade", "type", "country", "continent"],
    metric: Literal["count", "total_deaths", "total_damages_usd"] = "count",
    country: str | None = None,
    disaster_type: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    top_n: int = 10,
) -> str:
```

Use case: "deadliest earthquakes", "which decade had the most floods", "costliest storms in the US".
Returns: `StatsResponse(group_by, metric, rows: list[StatsRow])` — top-N rows ordered by metric descending.

### 5.3 `location_disaster_summary` — weather-flow background context

```python
@mcp.tool()
async def location_disaster_summary(
    country: str,
    location_contains: str | None = None,
) -> str:
```

Use case: invoked alongside every weather question. Hard-codes `min_year=1980`.
Returns: `LocationSummary` with:
- `total_events: int`
- `time_span: str | None` (`"1985–2019"` or null when zero events)
- `top_types: list[DisasterTypeCount]` — up to 3
- `deadliest_event: DisasterEvent | None`

When `total_events == 0`, the agent must say nothing about disasters in its response (per system prompt). The empty body is the signal for silence.

### 5.4 Tool docstrings carry routing rules

Each tool's docstring tells the LLM:
- *"Use this for X."*
- *"Do NOT use this for Y — use `<other_tool>` instead."*

This reinforces the routing already specified in the system prompt, so the LLM picks correctly even before reading the prompt.

## 6. Data models

`src/mcp_servers/disasters/models.py`:

```python
class DisasterEvent(BaseModel):
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
    disaster_type: str
    count: int

class LocationSummary(BaseModel):
    country: str
    location_filter: str | None
    total_events: int
    time_span: str | None
    top_types: list[DisasterTypeCount]
    deadliest_event: DisasterEvent | None

class StatsRow(BaseModel):
    group_value: str
    metric_value: float
    event_count: int

class QueryResponse(BaseModel):
    total_matched: int
    events: list[DisasterEvent]

class StatsResponse(BaseModel):
    group_by: str
    metric: str
    rows: list[StatsRow]
```

`src/agent/models.py` gains:

```python
class DisasterSummaryView(BaseModel):
    """Compact view rendered as a UI card for direct disaster questions."""
    total_events: int
    time_span: str | None
    top_types: list[tuple[str, int]]
    deadliest_event_summary: str | None  # e.g. "1995 Earthquake (Kobe, 6,434 deaths)"

class AgentResponse(BaseModel):
    message: str
    weather: WeatherData | None = None
    articles: list[ArticleData] | None = None
    disasters: DisasterSummaryView | None = None   # NEW
```

## 7. Storage strategy & loader

Per Q3 decision: Pandas 2.x with PyArrow string backend and categorical dtypes for low-vocab columns. Load the CSV once at server startup; hold a module-level singleton `DataFrame`.

```python
CATEGORICAL_COLUMNS = [
    "Disaster Group", "Disaster Subgroup", "Disaster Type",
    "Disaster Subtype", "Continent", "Region", "ISO", "Country",
]

def load_disasters(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        dtype_backend="pyarrow",
        dtype={col: "category" for col in CATEGORICAL_COLUMNS},
    )
    df["country_lc"]  = df["Country"].astype(str).str.lower()
    df["location_lc"] = df["Location"].astype(str).str.lower()
    df["latitude"]    = _parse_coord(df["Latitude"], pos="N", neg="S")
    df["longitude"]   = _parse_coord(df["Longitude"], pos="E", neg="W")
    return df
```

Cleanups (each justified by the data report):
- `country_lc` / `location_lc` — pre-lowercased, so substring filters don't pay the lowercase cost on every request.
- Latitude/Longitude parsing — source values are dirty strings (`"1.51 N"`, `"78.46 W "`); we parse once at load.
- Reads keep the original column names to avoid coupling the loader to internal choices made elsewhere; the cleaned columns are additive.

`pyarrow` becomes a new runtime dependency, added to the `[project].dependencies` list in `pyproject.toml` (alongside `pandas`, also new). Both are needed in the disasters-MCP process at startup; not dev-only.

## 8. Repository — query layer

`src/mcp_servers/disasters/repository.py` holds the singleton DataFrame and exposes three methods, one per MCP tool:

```python
class DisasterRepository:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def query(self, *, country, disaster_type, location_contains,
              start_year, end_year, limit) -> QueryResponse: ...

    def stats(self, *, group_by, metric, country, disaster_type,
              start_year, end_year, top_n) -> StatsResponse: ...

    def location_summary(self, *, country, location_contains,
                         min_year: int = DISASTERS_MIN_YEAR_FOR_LOCATION_SUMMARY
                         ) -> LocationSummary: ...

_repo: DisasterRepository | None = None

def get_repository() -> DisasterRepository:
    global _repo
    if _repo is None:
        _repo = DisasterRepository(load_disasters(DISASTERS_CSV_PATH))
    return _repo
```

Internal helper `_apply_filters(...)` is the single source of truth for building boolean masks; all three public methods reuse it.

Country matching rule: case-insensitive equality on `country_lc` **OR** exact match on `ISO` — so the LLM can pass any of "USA" / "United States of America" / "US" and they all work.

When both `country` and `location_contains` are provided they are ANDed: rows must satisfy the country match **and** contain the substring in `location_lc`. `location_contains` alone (no country) is allowed for queries like "all events with 'Bengal' in the location".

`location_summary` defaults `min_year=1980` per Q4 (the MCP tool exposes no year parameter, so 1980+ is fixed for that user-facing tool; the repository method itself remains parameterizable for tests). The other repository methods leave year filtering optional with no default cap.

A new exception class `DisasterRepositoryError` (defined in `repository.py`) is raised for invalid inputs — unknown `group_by`/`metric` literals, malformed year ranges, etc. `server.py` catches it and returns `{"error": "..."}` JSON.

## 9. Configuration

Additions to `src/agent/config.py`:

```python
DISASTERS_MCP_PORT: int = 8082
DISASTERS_MCP_URL: str = f"http://localhost:{DISASTERS_MCP_PORT}/mcp"
DISASTERS_CSV_PATH: Path = Path("data/emdat_disasters_1900_2021.csv")
DISASTERS_MIN_YEAR_FOR_LOCATION_SUMMARY: int = 1980
DISASTERS_DEFAULT_QUERY_LIMIT: int = 20
DISASTERS_DEFAULT_TOP_N: int = 10
```

## 10. Agent integration

### 10.1 System prompt — additions to `SYSTEM_PROMPT` in `src/agent/agent.py`

Two surgical additions, no rewriting of the existing prompt:

1. Extend `ALLOWED TOPICS`:
   - "Historical natural disaster records (1900–2021) — what/where/when disasters happened, counts, deadliest, costliest."

2. New `DISASTER RESPONSE FORMAT` section:
   - **Direct disaster questions** → call `query_disasters` (event listings) or `disaster_stats` (rankings/counts). Populate the `disasters` field on the response with a compact `DisasterSummaryView`. The UI will render a card.
   - **Weather questions** → ALWAYS also call `location_disaster_summary(country, location_contains)` for the requested place. If `total_events > 0`, weave **one short sentence** into your message. If `total_events == 0`, do NOT mention disasters at all. Set `disasters = null` in the weather flow regardless (per the hybrid response rule).
   - Self-reflection: empty results mean silence about disasters, not "I checked but found nothing".

**Mandatory final step after editing the prompt:** re-read the full `SYSTEM_PROMPT` from top to bottom as one continuous text. Tone, register, terminology, and section ordering must flow naturally — the new disaster section should feel like part of the original prompt, not a tacked-on addendum. Pay attention to: (a) consistent voice across `WEATHER`, `NEWS`, `COMBINED`, and the new `DISASTER` blocks; (b) section ordering that groups related rules logically; (c) terminology drift (e.g. "articles" vs "results", "summary" vs "card"); (d) duplication or contradiction with existing rules. Adjust until the prompt reads as a single coherent document. This re-read is part of the implementation work, not a follow-up.

### 10.2 Toolset wiring — `src/agent/agent.py`

```python
disasters_mcp = MCPServerStreamableHTTP(DISASTERS_MCP_URL)

agent = Agent(
    LLM_MODEL,
    output_type=AgentResponse,
    system_prompt=SYSTEM_PROMPT,
    toolsets=[weather_mcp, news_mcp, disasters_mcp],   # disasters added
)
```

## 11. UI integration

New component `src/ui/components/disaster_card.py` mirroring `weather_card.py` styling:

- Header row: `🌪️ {total_events} historical events · {time_span}`
- Row of inline chips: top 3 disaster types with counts.
- Subtle highlight row: deadliest event summary string.

`src/ui/app.py` gets one new render branch immediately after the news card branch:

```python
if response.disasters is not None:
    render_disaster_card(response.disasters)
```

Per the hybrid decision, the disaster card only appears for direct disaster questions — never on a pure weather query.

## 12. Launcher

`launcher.py` gains `_start_disasters_mcp()` — a clone of `_start_news_mcp()` pointing at `src.mcp_servers.disasters.server` — and a third `_wait_for_server` health check. Estimated diff: ~15 lines, no other changes.

## 13. Error handling

| Mode | Behaviour |
|---|---|
| CSV missing or unreadable at startup | `load_disasters` raises `FileNotFoundError` / `pd.errors.ParserError`; `get_repository()` propagates; MCP process exits. Launcher health check fails loudly. Same shape as a bad GNews API key today. |
| Invalid filter values (unknown country, malformed year, bad `group_by`) | Tool catches `DisasterRepositoryError` and returns `{"error": "..."}` JSON, mirroring `news/server.py`'s `GNewsAPIError` handling. Agent surfaces "data temporarily unavailable" per the existing `DATA INTEGRITY` rule. |
| Empty result set | Not an error. `query` returns `total_matched=0`; `stats` returns empty `rows`; `location_summary` returns `total_events=0`. Agent handles per system prompt (silence on weather flow; honest "no events found" on direct flow). |

No bare `except`. Every catch logs the operation and parameters per `agents.md`.

## 14. Testing

Three new test modules, mirroring existing test structure:

- **`tests/test_disasters_loader.py`** — Golden tests on a 50-row fixture CSV: column dtypes (categoricals applied, PyArrow strings), `latitude` / `longitude` parsed correctly including `"1.51 N"` / `"78.46 W "` / `"32.04"` / null cases, lowercase derived columns built.
- **`tests/test_disasters_repository.py`** — Unit tests on the same fixture: country case-insensitivity, ISO fallback, `Location` substring match (case-insensitive, partial), year-range filtering, top-N ordering by each metric, empty-result correctness, `location_summary` honoring 1980+ default.
- **`tests/test_disasters_models.py`** — Pydantic round-trip tests: serialization shape stable, `total_events==0` produces clean empty `LocationSummary`.

No live-CSV integration tests in CI — fixture-only, fast, deterministic. Manual verification before merge: run `uv run python launcher.py`, ask a few questions through the chat UI ("weather in Tokyo", "weather in Riga", "deadliest earthquake in Japan", "all wildfires in Australia 2010-2020"), confirm cards render and silence holds for quiet locations.

## 15. Out of scope (explicit follow-ups)

- Inflation-adjusted damages (`damages_real_usd` derived column + alternative `metric` value).
- Geocoding / lat-lon radius search.
- Caching of repository results.
- Live disaster feeds.

## 16. Open questions / risks

- **PyArrow as a new dependency** — adds ~30 MB install footprint. Acceptable trade for the modern Pandas idiom; well-maintained.
- **Country name variants** — EM-DAT uses parenthetical articles like `"United States of America (the)"`. The `country_lc` + ISO fallback handles this, but the LLM may still call with unusual variants. Mitigation: tool docstring example values.
- **Reporting bias caveat** — even with the 1980+ default for `location_disaster_summary`, locations with very poor recent reporting could still produce misleading silence. Acceptable for a v1; the `query_disasters` and `disaster_stats` tools remain available with no default cap.

---

**Next step after approval:** invoke the `writing-plans` skill to produce a step-by-step implementation plan against this spec.
