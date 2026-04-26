"""Golden dataset of agent eval cases.

Each case asserts hybrid-rule structure (which response fields must be
populated) and, for direct disaster questions, hallucination grounds (which
specific facts must come from the EM-DAT dataset).

Run with: ``uv run pytest tests/evals/ -v -m eval``
"""
from pydantic import BaseModel, ConfigDict


class EvalCase(BaseModel):
    """One agent eval — prompt plus structural and grounding assertions."""

    model_config = ConfigDict(frozen=True)

    name: str
    prompt: str

    # Hybrid-rule structural expectations.
    expect_weather: bool = False
    expect_disasters_field: bool = False
    expect_articles: bool = False

    # Grounding expectations for direct disaster questions.
    # When set, restricts hallucination checks to events with this country/type.
    grounded_country: str | None = None
    grounded_disaster_type: str | None = None

    # Optional positive assertions about the disaster summary.
    # If set, the response.disasters.deadliest_event_summary should match
    # one of the (year, country, disaster_type) tuples returned by the
    # repository's actual data — verified by the hallucination check.
    require_deadliest_event: bool = False

    # Optional content checks.
    forbidden_substrings_in_message: tuple[str, ...] = ()


DATASET: list[EvalCase] = [
    # --- Hybrid rule: weather flow never shows a disaster card. ---
    EvalCase(
        name="weather_tokyo_hybrid_rule",
        prompt="What's the weather in Tokyo right now?",
        expect_weather=True,
        expect_disasters_field=False,
    ),
    EvalCase(
        name="weather_riga_hybrid_rule",
        prompt="What's the weather in Riga right now?",
        expect_weather=True,
        expect_disasters_field=False,
    ),
    # --- Direct disaster: stats only, no specific event lookup needed. ---
    EvalCase(
        name="floods_decade_aggregate",
        prompt="Which decade had the most floods worldwide?",
        expect_disasters_field=True,
    ),
    # --- Direct disaster: deadliest events — the agent MUST chain
    #     disaster_stats + query_disasters and produce a deadliest event
    #     summary. The hallucination check enforces grounding. ---
    EvalCase(
        name="deadliest_earthquakes_global",
        prompt="What were the deadliest earthquakes ever recorded?",
        expect_disasters_field=True,
        grounded_disaster_type="Earthquake",
        require_deadliest_event=True,
    ),
    EvalCase(
        name="deadliest_earthquake_japan",
        prompt="What was the deadliest earthquake in Japan?",
        expect_disasters_field=True,
        grounded_country="Japan",
        grounded_disaster_type="Earthquake",
        require_deadliest_event=True,
    ),
    EvalCase(
        name="costliest_storms_usa",
        prompt="What were the costliest storms in the United States?",
        expect_disasters_field=True,
        grounded_country="United States of America (the)",
        grounded_disaster_type="Storm",
        require_deadliest_event=True,
    ),
    # --- Direct disaster: location/year scoped query. ---
    EvalCase(
        name="haiti_2010_event",
        prompt="What disaster happened in Haiti in 2010?",
        expect_disasters_field=True,
        grounded_country="Haiti",
        require_deadliest_event=True,
    ),
]
