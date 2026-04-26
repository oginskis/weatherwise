"""Grounding evals — deterministic, rule-based.

Code-only assertions on the agent's final ``AgentResponse`` and the
deterministically-built ``DisasterSummaryView`` card. The disaster card is
built by :func:`src.agent.disaster_card.build_disaster_card` from the run's
tool returns — the LLM does not populate it, so structured-data
hallucination is impossible by construction. Free-text ``message`` years
are still cross-checked against EM-DAT.

Run with::

    uv run pytest tests/eval/ -v -m eval
"""
import pytest

from src.agent.config import DISASTERS_CSV_PATH

from .golden_dataset import DATASET, EvalCase
from .validators import find_hallucinations

pytestmark = pytest.mark.eval


@pytest.mark.parametrize(
    "case",
    DATASET,
    ids=[case.name for case in DATASET],
)
def test_eval_case_structure(case: EvalCase, agent_runner) -> None:
    """Hybrid-rule structure: weather/articles fields on AgentResponse, plus
    disaster card presence/absence depending on the case."""
    response, _messages, disaster_card = agent_runner(case.prompt)

    if case.expect_weather:
        assert response.weather is not None, (
            f"{case.name}: weather field must be populated"
        )
    else:
        assert response.weather is None, (
            f"{case.name}: weather field must be null for non-weather prompts"
        )

    if case.expect_disasters_field:
        assert disaster_card is not None, (
            f"{case.name}: a disaster card must be built for direct disaster "
            f"questions. message={response.message!r}"
        )
        assert disaster_card.total_events > 0, (
            f"{case.name}: card.total_events must be > 0; "
            f"got card={disaster_card.model_dump_json()}"
        )
    else:
        assert disaster_card is None, (
            f"{case.name}: disaster card must be absent on weather-flow "
            "responses (hybrid rule). The agent should call only "
            "location_disaster_summary, never query_disasters or disaster_stats."
        )

    if case.expect_articles:
        assert response.articles is not None, (
            f"{case.name}: articles field must be populated"
        )

    for forbidden in case.forbidden_substrings_in_message:
        assert forbidden.lower() not in (response.message or "").lower(), (
            f"{case.name}: forbidden substring {forbidden!r} appeared in message"
        )


@pytest.mark.parametrize(
    "case",
    [c for c in DATASET if c.expect_disasters_field],
    ids=[c.name for c in DATASET if c.expect_disasters_field],
)
def test_eval_case_no_hallucinations(case: EvalCase, agent_runner) -> None:
    """Anti-hallucination — message text only.

    The structured card cannot hallucinate (built deterministically from
    tool returns). The free-text ``message`` still can: we extract every
    dataset-range year (1900-2021) it mentions and verify each appears in
    EM-DAT under the case's grounding filter. Death counts, named events,
    and comparative claims in prose are out of scope for this regex-only
    check — those would need an LLM-based judge, which we don't run.
    """
    response, _messages, _card = agent_runner(case.prompt)
    findings = find_hallucinations(
        response,
        csv_path=DISASTERS_CSV_PATH,
        grounded_country=case.grounded_country,
        grounded_disaster_type=case.grounded_disaster_type,
    )
    assert findings == [], (
        f"{case.name}: agent stated facts not present in EM-DAT:\n  "
        + "\n  ".join(f.model_dump_json() for f in findings)
    )


@pytest.mark.parametrize(
    "case",
    [c for c in DATASET if c.require_deadliest_event],
    ids=[c.name for c in DATASET if c.require_deadliest_event],
)
def test_eval_case_deadliest_event_populated(
    case: EvalCase, agent_runner
) -> None:
    """For 'deadliest'/'costliest' prompts the card's deadliest_event_summary
    must be a non-empty string, meaning the agent chained
    ``disaster_stats`` + ``query_disasters`` and the card builder found at
    least one event with the relevant metric in the result."""
    _response, _messages, disaster_card = agent_runner(case.prompt)
    assert disaster_card is not None, (
        f"{case.name}: no disaster card was built — the agent did not call "
        "query_disasters or disaster_stats."
    )
    assert disaster_card.deadliest_event_summary, (
        f"{case.name}: card.deadliest_event_summary must be a non-empty string "
        "for ranking-style prompts. The card builder requires a "
        "query_disasters event with the relevant metric (deaths or damages). "
        f"Got card={disaster_card.model_dump_json()}"
    )
