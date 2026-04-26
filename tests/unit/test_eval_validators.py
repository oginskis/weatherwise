"""Unit tests for the pure functions in ``tests/eval/validators.py``.

The eval validators are themselves used by tests, so they get their own
unit coverage to make sure subtle one-line idioms (``is_subsequence``
consumes its iterator) don't silently break.
"""
import pytest

from tests.eval.validators import args_subset_match, is_subsequence


@pytest.mark.parametrize(
    ("needles", "haystack", "expected"),
    [
        # Empty needles match anything (vacuous truth).
        ((), [], True),
        ((), ["a", "b"], True),
        # Single-needle present / absent.
        (("a",), ["a", "b"], True),
        (("c",), ["a", "b"], False),
        # In-order subsequence with gaps.
        (("a", "c"), ["a", "b", "c", "d"], True),
        # Wrong order — first needle must come before second in haystack.
        (("c", "a"), ["a", "b", "c"], False),
        # Repeated tool name in needles must match repeated occurrences.
        (("a", "a"), ["a", "a", "b"], True),
        (("a", "a"), ["a", "b"], False),
        # Needle longer than haystack.
        (("a", "b", "c"), ["a", "b"], False),
    ],
)
def test_is_subsequence(
    needles: tuple[str, ...], haystack: list[str], expected: bool
) -> None:
    assert is_subsequence(needles, haystack) is expected


@pytest.mark.parametrize(
    ("expected_args", "actual_args", "expected_match"),
    [
        # Empty expected matches anything.
        ({}, {}, True),
        ({}, {"country": "Japan"}, True),
        # Exact match.
        ({"country": "Japan"}, {"country": "Japan"}, True),
        # Subset match — actual has more keys, that's fine.
        ({"country": "Japan"}, {"country": "Japan", "limit": 5}, True),
        # Missing key in actual.
        ({"country": "Japan"}, {"limit": 5}, False),
        # Wrong value.
        ({"country": "Japan"}, {"country": "China"}, False),
        # Mixed types — string vs int (str "5" != int 5).
        ({"limit": 5}, {"limit": "5"}, False),
        # Multiple keys, all must match.
        (
            {"country": "Japan", "disaster_type": "Earthquake"},
            {"country": "Japan", "disaster_type": "Earthquake", "limit": 10},
            True,
        ),
        (
            {"country": "Japan", "disaster_type": "Earthquake"},
            {"country": "Japan", "disaster_type": "Storm"},
            False,
        ),
    ],
)
def test_args_subset_match(
    expected_args: dict[str, object],
    actual_args: dict[str, object],
    expected_match: bool,
) -> None:
    assert args_subset_match(expected_args, actual_args) is expected_match
