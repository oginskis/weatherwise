"""Trajectory evals — assertions on the path the agent took.

Reads the ordered tool calls from ``Agent.run(...).all_messages()`` and
verifies:

- required tools were called (presence, any order)
- required tools were called in a specific order (subsequence)
- forbidden tools were NOT called (e.g. weather flow must not call
  disaster_stats)
- specific tool arguments are present (e.g. query_disasters was called
  with disaster_type="Earthquake")
- total tool-call count stays within a sane upper bound (catches retry
  loops and runaway tool use)

No external observability stack needed — the message log is the source
of truth.

Run with::

    uv run pytest tests/eval/ -v -m eval
"""
import pytest

from .golden_dataset import DATASET, EvalCase
from .validators import (
    args_subset_match,
    extract_tool_call_sequence,
    extract_tool_calls,
    is_subsequence,
)

pytestmark = pytest.mark.eval


def _has_l3_assertions(case: EvalCase) -> bool:
    return bool(
        case.required_tools
        or case.required_tool_sequence
        or case.forbidden_tools
        or case.required_tool_args
        or case.max_tool_calls is not None
    )


_L3_CASES = [c for c in DATASET if _has_l3_assertions(c)]


@pytest.mark.parametrize(
    "case",
    _L3_CASES,
    ids=[c.name for c in _L3_CASES],
)
def test_eval_case_tool_presence_and_order(
    case: EvalCase, agent_runner
) -> None:
    """Required and forbidden tool presence; required ordering."""
    _response, messages, _card = agent_runner(case.prompt)
    actual = extract_tool_call_sequence(messages)

    if case.required_tools:
        missing = case.required_tools - set(actual)
        assert not missing, (
            f"{case.name}: required tools {sorted(missing)} were not called. "
            f"Actual sequence: {actual}"
        )

    if case.required_tool_sequence:
        assert is_subsequence(case.required_tool_sequence, actual), (
            f"{case.name}: tools were not called in the required order "
            f"{case.required_tool_sequence}. Actual sequence: {actual}"
        )

    if case.forbidden_tools:
        called_forbidden = case.forbidden_tools & set(actual)
        assert not called_forbidden, (
            f"{case.name}: forbidden tools {sorted(called_forbidden)} were "
            f"called. Actual sequence: {actual}"
        )


@pytest.mark.parametrize(
    "case",
    [c for c in DATASET if c.required_tool_args],
    ids=[c.name for c in DATASET if c.required_tool_args],
)
def test_eval_case_tool_args(case: EvalCase, agent_runner) -> None:
    """Each required tool was called with the expected argument subset."""
    _response, messages, _card = agent_runner(case.prompt)
    actual_calls = extract_tool_calls(messages)
    for tool_name, expected_args in case.required_tool_args.items():
        matching_calls = [args for name, args in actual_calls if name == tool_name]
        assert matching_calls, (
            f"{case.name}: required tool {tool_name!r} was not called at all"
        )
        assert any(args_subset_match(expected_args, args) for args in matching_calls), (
            f"{case.name}: tool {tool_name!r} was called but never with the "
            f"expected args subset {expected_args}. Actual calls to "
            f"{tool_name!r}: {matching_calls}"
        )


@pytest.mark.parametrize(
    "case",
    [c for c in DATASET if c.max_tool_calls is not None],
    ids=[c.name for c in DATASET if c.max_tool_calls is not None],
)
def test_eval_case_tool_call_count(case: EvalCase, agent_runner) -> None:
    """Total tool calls must stay within ``max_tool_calls`` (catches retry loops)."""
    _response, messages, _card = agent_runner(case.prompt)
    actual = extract_tool_call_sequence(messages)
    assert len(actual) <= case.max_tool_calls, (
        f"{case.name}: agent made {len(actual)} tool calls, exceeding "
        f"max_tool_calls={case.max_tool_calls}. Sequence: {actual}"
    )
