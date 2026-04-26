"""Unit tests for the deterministic disaster card builder.

The tests construct fake ``ModelMessage`` lists that mimic what
``Agent.run(...).all_messages()`` produces, then assert the resulting
``DisasterSummaryView`` field-by-field. No LLM, no MCP, no agent.
"""
import json
from datetime import datetime, timezone

from pydantic_ai.messages import ModelRequest, ToolReturnPart

from src.agent.disaster_card import build_disaster_card


def _msg_with_tool_return(tool_name: str, content: object) -> ModelRequest:
    """Build a ModelRequest carrying one ToolReturnPart (matches pydantic-ai shape).

    Content is JSON-encoded (the wire format pydantic-ai produces today).
    Use :func:`_msg_with_dict_content` to test the parsed-dict branch.
    """
    payload = content if isinstance(content, str) else json.dumps(content)
    return ModelRequest(
        parts=[
            ToolReturnPart(
                tool_name=tool_name,
                content=payload,
                tool_call_id="t1",
                timestamp=datetime.now(timezone.utc),
            )
        ]
    )


def _msg_with_dict_content(tool_name: str, content: dict) -> ModelRequest:
    """Build a ModelRequest with raw-dict (not JSON-string) content.

    Exercises the ``isinstance(content, dict)`` branch of ``_coerce_to_dict``
    that handles pydantic-ai versions returning parsed content directly.
    """
    return ModelRequest(
        parts=[
            ToolReturnPart(
                tool_name=tool_name,
                content=content,
                tool_call_id="t1",
                timestamp=datetime.now(timezone.utc),
            )
        ]
    )


def test_build_card_returns_none_when_no_disaster_tools_called() -> None:
    assert build_disaster_card([]) is None


def test_build_card_returns_none_when_only_location_summary_called() -> None:
    """Weather flow: location_disaster_summary only → no card."""
    messages = [
        _msg_with_tool_return(
            "location_disaster_summary",
            {
                "country": "Japan",
                "location_filter": None,
                "total_events": 16,
                "time_span": "1985-2019",
                "top_types": [],
                "deadliest_event": None,
            },
        )
    ]
    assert build_disaster_card(messages) is None


def test_build_card_returns_none_on_empty_query() -> None:
    messages = [
        _msg_with_tool_return(
            "query_disasters", {"total_matched": 0, "events": []}
        )
    ]
    assert build_disaster_card(messages) is None


def test_build_card_skips_error_returns() -> None:
    messages = [_msg_with_tool_return("disaster_stats", {"error": "bad"})]
    assert build_disaster_card(messages) is None


def test_build_card_from_stats_only_decade_aggregate() -> None:
    """'Which decade had most floods' → stats only, no specific events."""
    messages = [
        _msg_with_tool_return(
            "disaster_stats",
            {
                "group_by": "decade",
                "metric": "count",
                "rows": [
                    {"group_value": "2000", "metric_value": 1725.0, "event_count": 1725},
                    {"group_value": "2010", "metric_value": 1533.0, "event_count": 1533},
                    {"group_value": "1990", "metric_value": 1051.0, "event_count": 1051},
                ],
            },
        )
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.total_events == 1725 + 1533 + 1051
    assert card.time_span == "1990-2010"
    assert card.top_types == []
    assert card.deadliest_event_summary is None


def test_build_card_total_events_prefers_query_total_matched() -> None:
    """When both stats and query are present, total_events comes from query.total_matched.

    The two values are deliberately divergent (9999 vs 1544) so the assertion
    actually proves which source wins.
    """
    messages = [
        _msg_with_tool_return(
            "disaster_stats",
            {
                "group_by": "type",
                "metric": "count",
                "rows": [{"group_value": "Earthquake", "metric_value": 9999.0, "event_count": 9999}],
            },
        ),
        _msg_with_tool_return(
            "query_disasters",
            {
                "total_matched": 1544,
                "events": [
                    {
                        "year": 1976,
                        "country": "China",
                        "location": "Tangshan",
                        "disaster_type": "Earthquake",
                        "disaster_subtype": None,
                        "total_deaths": 242000,
                        "total_affected": None,
                        "total_damages_usd_thousands": 5600000.0,
                        "event_name": None,
                    }
                ],
            },
        ),
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.total_events == 1544, "should pick query.total_matched, not stats.event_count"


def test_build_card_top_types_verbatim_from_stats() -> None:
    messages = [
        _msg_with_tool_return(
            "disaster_stats",
            {
                "group_by": "type",
                "metric": "count",
                "rows": [
                    {"group_value": "Flood", "metric_value": 5551, "event_count": 5551},
                    {"group_value": "Storm", "metric_value": 4496, "event_count": 4496},
                    {"group_value": "Earthquake", "metric_value": 1544, "event_count": 1544},
                    {"group_value": "Drought", "metric_value": 770, "event_count": 770},
                ],
            },
        ),
        _msg_with_tool_return(
            "query_disasters",
            {"total_matched": 5551, "events": []},
        ),
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.top_types == [
        ("Flood", 5551),
        ("Storm", 4496),
        ("Earthquake", 1544),
    ]


def test_build_card_top_types_fallback_to_query_distribution() -> None:
    """No stats group_by='type' call → derive from query event distribution."""
    messages = [
        _msg_with_tool_return(
            "query_disasters",
            {
                "total_matched": 3,
                "events": [
                    {"year": 2010, "country": "Haiti", "location": "PaP",
                     "disaster_type": "Earthquake", "disaster_subtype": None,
                     "total_deaths": 222570, "total_affected": None,
                     "total_damages_usd_thousands": 8000000.0, "event_name": None},
                    {"year": 2010, "country": "Haiti", "location": "PaP",
                     "disaster_type": "Earthquake", "disaster_subtype": None,
                     "total_deaths": 100, "total_affected": None,
                     "total_damages_usd_thousands": None, "event_name": None},
                    {"year": 2010, "country": "Haiti", "location": "PaP",
                     "disaster_type": "Epidemic", "disaster_subtype": None,
                     "total_deaths": 9000, "total_affected": None,
                     "total_damages_usd_thousands": None, "event_name": "Cholera"},
                ],
            },
        )
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.top_types == [("Earthquake", 2), ("Epidemic", 1)]


def test_build_card_deadliest_event_default_intent() -> None:
    """Without a stats call, default intent is 'deadliest' → sort by deaths."""
    messages = [
        _msg_with_tool_return(
            "query_disasters",
            {
                "total_matched": 2,
                "events": [
                    {"year": 2010, "country": "Haiti", "location": "Port-au-Prince",
                     "disaster_type": "Earthquake", "disaster_subtype": None,
                     "total_deaths": 222570, "total_affected": None,
                     "total_damages_usd_thousands": 8000000.0, "event_name": None},
                    {"year": 2010, "country": "Haiti", "location": "Port-au-Prince",
                     "disaster_type": "Epidemic", "disaster_subtype": None,
                     "total_deaths": 9000, "total_affected": None,
                     "total_damages_usd_thousands": None, "event_name": "Cholera"},
                ],
            },
        )
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.deadliest_event_summary == (
        "2010 Earthquake in Haiti (Port-au-Prince), 222,570 deaths"
    )


def test_build_card_costliest_intent_uses_damages() -> None:
    """When stats called with metric=total_damages_usd, top event is by damages."""
    messages = [
        _msg_with_tool_return(
            "disaster_stats",
            {
                "group_by": "country",
                "metric": "total_damages_usd",
                "rows": [
                    {"group_value": "United States", "metric_value": 5e8, "event_count": 270}
                ],
            },
        ),
        _msg_with_tool_return(
            "query_disasters",
            {
                "total_matched": 2,
                "events": [
                    {"year": 2005, "country": "United States", "location": "LA",
                     "disaster_type": "Storm", "disaster_subtype": "Hurricane",
                     "total_deaths": 1833, "total_affected": None,
                     "total_damages_usd_thousands": 125000000.0, "event_name": "Katrina"},
                    {"year": 2017, "country": "United States", "location": "TX",
                     "disaster_type": "Storm", "disaster_subtype": "Hurricane",
                     "total_deaths": 88, "total_affected": None,
                     "total_damages_usd_thousands": 95000000.0, "event_name": "Harvey"},
                ],
            },
        ),
    ]
    card = build_disaster_card(messages)
    assert card is not None
    # 125,000,000 in thousands USD = $125B (presented as 125,000,000K)
    assert card.deadliest_event_summary == (
        "2005 Storm in United States (Katrina), $125,000,000K damages"
    )


def test_build_card_uses_event_name_over_location() -> None:
    messages = [
        _msg_with_tool_return(
            "query_disasters",
            {
                "total_matched": 1,
                "events": [
                    {"year": 2011, "country": "Japan", "location": "Tohoku region",
                     "disaster_type": "Earthquake", "disaster_subtype": None,
                     "total_deaths": 19846, "total_affected": None,
                     "total_damages_usd_thousands": 210000000.0, "event_name": "Tohoku"},
                ],
            },
        )
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.deadliest_event_summary == (
        "2011 Earthquake in Japan (Tohoku), 19,846 deaths"
    ), "must use event_name 'Tohoku', not the longer 'Tohoku region' location"


def test_build_card_handles_null_deaths_in_top_event() -> None:
    """If the candidate event has null deaths, skip it and try the next."""
    messages = [
        _msg_with_tool_return(
            "query_disasters",
            {
                "total_matched": 2,
                "events": [
                    {"year": 1900, "country": "India", "location": "Bengal",
                     "disaster_type": "Drought", "disaster_subtype": None,
                     "total_deaths": None, "total_affected": None,
                     "total_damages_usd_thousands": None, "event_name": None},
                    {"year": 1928, "country": "China", "location": "",
                     "disaster_type": "Drought", "disaster_subtype": None,
                     "total_deaths": 3000000, "total_affected": None,
                     "total_damages_usd_thousands": None, "event_name": None},
                ],
            },
        )
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.deadliest_event_summary is not None
    assert "1928" in card.deadliest_event_summary
    assert "3,000,000 deaths" in card.deadliest_event_summary


def test_build_card_handles_all_null_deaths() -> None:
    """No event has a death count → deadliest_event_summary is None."""
    messages = [
        _msg_with_tool_return(
            "query_disasters",
            {
                "total_matched": 1,
                "events": [
                    {"year": 2020, "country": "X", "location": "Y",
                     "disaster_type": "Drought", "disaster_subtype": None,
                     "total_deaths": None, "total_affected": None,
                     "total_damages_usd_thousands": None, "event_name": None},
                ],
            },
        )
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.total_events == 1
    assert card.deadliest_event_summary is None


def test_build_card_time_span_from_query_events() -> None:
    messages = [
        _msg_with_tool_return(
            "query_disasters",
            {
                "total_matched": 3,
                "events": [
                    {"year": 1976, "country": "China", "location": "T",
                     "disaster_type": "Earthquake", "disaster_subtype": None,
                     "total_deaths": 242000, "total_affected": None,
                     "total_damages_usd_thousands": None, "event_name": None},
                    {"year": 2010, "country": "Haiti", "location": "P",
                     "disaster_type": "Earthquake", "disaster_subtype": None,
                     "total_deaths": 222570, "total_affected": None,
                     "total_damages_usd_thousands": None, "event_name": None},
                    {"year": 2011, "country": "Japan", "location": "T",
                     "disaster_type": "Earthquake", "disaster_subtype": None,
                     "total_deaths": 19846, "total_affected": None,
                     "total_damages_usd_thousands": None, "event_name": "Tohoku"},
                ],
            },
        )
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.time_span == "1976-2011"


def test_build_card_time_span_from_year_groupby_stats() -> None:
    """The 'year' branch of _compute_time_span (sibling to 'decade')."""
    messages = [
        _msg_with_tool_return(
            "disaster_stats",
            {
                "group_by": "year",
                "metric": "count",
                "rows": [
                    {"group_value": "2005", "metric_value": 50.0, "event_count": 50},
                    {"group_value": "2010", "metric_value": 80.0, "event_count": 80},
                    {"group_value": "2007", "metric_value": 65.0, "event_count": 65},
                ],
            },
        )
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.time_span == "2005-2010"


def test_build_card_accepts_dict_content_not_just_json_string() -> None:
    """The card builder coerces ToolReturnPart.content from either str or dict.

    pydantic-ai currently delivers JSON-string content, but the builder also
    handles already-parsed dicts so a future version change doesn't break us.
    """
    messages = [
        _msg_with_dict_content(
            "query_disasters",
            {
                "total_matched": 1,
                "events": [
                    {
                        "year": 2010,
                        "country": "Haiti",
                        "location": "Port-au-Prince",
                        "disaster_type": "Earthquake",
                        "disaster_subtype": None,
                        "total_deaths": 222570,
                        "total_affected": None,
                        "total_damages_usd_thousands": 8000000.0,
                        "event_name": None,
                    }
                ],
            },
        )
    ]
    card = build_disaster_card(messages)
    assert card is not None
    assert card.total_events == 1
    assert card.deadliest_event_summary == (
        "2010 Earthquake in Haiti (Port-au-Prince), 222,570 deaths"
    )
