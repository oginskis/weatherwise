# Test Suite

Two buckets, each self-contained with its own conftest:

```
tests/
├── unit/              # offline tests — no LLM, no live MCP servers, no API calls
│   ├── conftest.py        # disasters CSV fixture (used by repository/loader/server)
│   └── test_*.py
└── eval/              # live tests — real agent + MCP servers, costs API quota
    ├── conftest.py        # agent_runner fixture, MCP probe, shared event loop
    ├── golden_dataset.py  # EvalCase dataset
    ├── validators.py      # year-regex grounding + tool-call helpers
    └── test_*.py
```

Default `pytest tests/` runs only `tests/unit/`. Eval tests are deselected via the `-m 'not eval'` addopts in `pyproject.toml`. Run them explicitly when you want them.

## `tests/unit/` — offline (9 files, 101 tests)

Run on every commit. Fast (~1s). No agent, no LLM, no live MCP processes.

| File | What it covers |
|---|---|
| `test_agent_models.py` | `AgentResponse`, `WeatherData`, `ArticleData`, `DisasterSummaryView` — Pydantic round-trip and field shape |
| `test_disaster_card.py` | `build_disaster_card()` — deterministic construction from fake tool-return messages: stats-only, query-only, both, dict vs JSON-string content, deadliest/costliest intent detection, time_span via decade and year groupings, null-deaths fallback |
| `test_disasters_loader.py` | EM-DAT CSV loader: PyArrow + categorical dtypes, lat/lon parsing across N/S/E/W formats, integer-only coords, garbage |
| `test_disasters_models.py` | Disasters MCP response models (`DisasterEvent`, `LocationSummary`, `QueryResponse`, `StatsResponse`) — full-field round-trip + JSON shape |
| `test_disasters_repository.py` | Repository: country matching (exact name + ISO + substring fallback), three-filter AND combination, year-range exact counts, descending sort by metric, stats by year/decade/type/country/continent, top-N cap |
| `test_disasters_server.py` | Disasters MCP tools called directly with a fixture-backed repository — no LLM. Includes invalid `group_by` and invalid `metric` error-JSON paths. |
| `test_eval_validators.py` | Pure-function unit tests for `is_subsequence` and `args_subset_match` from `tests/eval/validators.py` |
| `test_gnews_client.py` | News HTTP client (mocked via `respx`): success, API error, network failure (`httpx.ConnectError`), category/country query params |
| `test_news_models.py` | News MCP `Article` / `SearchResponse` |

## `tests/eval/` — live (2 test files, 40 tests)

Opt-in. Goes through the real PydanticAI agent, which calls the three MCP servers over HTTP. Costs API quota. Skipped from the default run.

**Prerequisite:** start the launcher in another terminal first.

```bash
uv run python launcher.py             # in another terminal
uv run pytest tests/eval/ -m eval     # then run the evals here
```

If the MCP servers aren't reachable, the `agent_runner` fixture skips all evals cleanly (does not fail).

| File | What it covers |
|---|---|
| `golden_dataset.py` | The `EvalCase` Pydantic model + a 9-case `DATASET` covering hybrid weather rule, decade aggregates, deadliest/costliest with tool chaining, location/year scoped queries, news flow, and prompt-injection refusal. Each case declares which assertions apply (e.g. `expect_disasters_field`, `required_tool_sequence`, `forbidden_tools`, `max_tool_calls`, `require_deadliest_event`). |
| `validators.py` | `find_hallucinations` (year-regex grounding of message text against EM-DAT) plus `extract_tool_call_sequence` / `extract_tool_calls` / `args_subset_match` / `is_subsequence` (tool-call introspection from `result.new_messages()`). |
| `conftest.py` | Session-scoped `agent_runner` fixture: probes the MCP servers, runs the agent, and returns `(response, new_messages, disaster_card)` per prompt; caches by prompt across the session. |
| `test_grounding.py` | Hybrid-rule structure (which response fields are populated for this prompt shape), regex-based hallucination check on the message text, and required disaster-card content for ranking-style prompts. The structured card itself is built deterministically from tool returns and cannot hallucinate. |
| `test_trajectory.py` | Tool-call sequence assertions: required tools called, required ordering, forbidden tools NOT called, required argument subsets, and total tool-call count within `max_tool_calls`. |

## How to run

```bash
# Offline only (default, fast, no API)
uv run pytest tests/

# With evals (requires running launcher; costs API quota)
uv run python launcher.py             # in another terminal
uv run pytest tests/eval/ -m eval

# A single eval case across all assertions
uv run pytest tests/eval/ -m eval -k haiti_2010_event

# Just the trajectory tests
uv run pytest tests/eval/test_trajectory.py -m eval
```

## Adding a new eval case

Edit `tests/eval/golden_dataset.py` and append an `EvalCase`. Set only the fields whose assertions apply; every test function uses `[c for c in DATASET if c.<flag>]` to opt cases in.

```python
EvalCase(
    name="droughts_in_africa",
    prompt="What were the worst droughts in Africa?",
    expect_disasters_field=True,                                          # grounding test
    grounded_disaster_type="Drought",                                     # grounding test
    require_deadliest_event=True,                                         # grounding test
    required_tool_sequence=("disaster_stats", "query_disasters"),         # trajectory test
    required_tool_args={"query_disasters": {"disaster_type": "Drought"}}, # trajectory test
    forbidden_tools=frozenset({"location_disaster_summary"}),             # trajectory test
    max_tool_calls=6,                                                     # trajectory test
),
```
