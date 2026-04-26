"""Deterministic construction of the disaster UI card from tool returns.

The LLM is intentionally NOT in this loop. It produces conversational
``message`` text and decides which tools to call; the application then
parses the tool returns directly and builds the structured
:class:`DisasterSummaryView` rendered as a card. This guarantees that
every number and event name in the card matches what the EM-DAT data
actually returned, regardless of how the model paraphrased things.

Decision logic:

- If only ``location_disaster_summary`` was called (the agent's
  weather-flow signal), no card is built. The card is for direct
  disaster questions only — the weather flow gets prose mention only.
- If ``disaster_stats`` and/or ``query_disasters`` was called, a card is
  built from those returns.
- If both were called, ``query_disasters`` provides the deadliest /
  costliest event and ``disaster_stats`` (when ``group_by="type"``)
  provides ``top_types``.
- Otherwise, fall back to whatever's available. An empty result yields
  no card.
"""
import json
from collections.abc import Iterable

from pydantic_ai.messages import ModelMessage, ToolReturnPart

from .models import DisasterSummaryView

# Tool names served by the disasters MCP server.
_STATS_TOOL: str = "disaster_stats"
_QUERY_TOOL: str = "query_disasters"
_LOCATION_SUMMARY_TOOL: str = "location_disaster_summary"

_TOP_TYPES_CAP: int = 3


def build_disaster_card(
    messages: Iterable[ModelMessage],
) -> DisasterSummaryView | None:
    """Build the UI card from disaster-tool returns, or return None.

    Returns None when:
    - No disaster tools were called.
    - Only ``location_disaster_summary`` was called (weather flow).
    - All tools returned errors or empty data.
    """
    stats_returns = _collect_returns(messages, _STATS_TOOL)
    query_returns = _collect_returns(messages, _QUERY_TOOL)

    # Hybrid rule: if only ``location_disaster_summary`` was used (or no
    # disaster tool at all), this is the weather flow. The card is
    # reserved for direct disaster questions; no card here.
    if not stats_returns and not query_returns:
        return None

    total_events = _compute_total_events(stats_returns, query_returns)
    if total_events == 0:
        return None

    return DisasterSummaryView(
        total_events=total_events,
        time_span=_compute_time_span(stats_returns, query_returns),
        top_types=_compute_top_types(stats_returns, query_returns),
        deadliest_event_summary=_compute_top_event_summary(
            stats_returns, query_returns
        ),
    )


def _collect_returns(
    messages: Iterable[ModelMessage], tool_name: str
) -> list[dict]:
    """Collect successfully-parsed JSON returns from a single tool, in call order."""
    out: list[dict] = []
    for msg in messages:
        for part in getattr(msg, "parts", ()) or ():
            if not isinstance(part, ToolReturnPart):
                continue
            if part.tool_name != tool_name:
                continue
            data = _coerce_to_dict(part.content)
            if data is None or "error" in data:
                continue
            out.append(data)
    return out


def _coerce_to_dict(content: object) -> dict | None:
    """ToolReturnPart.content is JSON-string in our setup but defensively handle dict too."""
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _compute_total_events(
    stats_returns: list[dict], query_returns: list[dict]
) -> int:
    """Prefer query_disasters.total_matched; fall back to stats event_count sum."""
    if query_returns:
        return max((r.get("total_matched") or 0 for r in query_returns), default=0)
    total = 0
    for r in stats_returns:
        for row in r.get("rows", []):
            count = row.get("event_count")
            if isinstance(count, int):
                total += count
    return total


def _compute_time_span(
    stats_returns: list[dict], query_returns: list[dict]
) -> str | None:
    """Smallest-min, largest-max year across all event years and stats year/decade groups."""
    years: list[int] = []
    for r in query_returns:
        for ev in r.get("events", []):
            y = ev.get("year")
            if isinstance(y, int):
                years.append(y)
    for r in stats_returns:
        if r.get("group_by") not in ("year", "decade"):
            continue
        for row in r.get("rows", []):
            v = row.get("group_value")
            if isinstance(v, str) and v.isdigit():
                years.append(int(v))
    if not years:
        return None
    return f"{min(years)}-{max(years)}"


def _compute_top_types(
    stats_returns: list[dict], query_returns: list[dict]
) -> list[tuple[str, int]]:
    """Verbatim from disaster_stats group_by='type' rows; fall back to query event distribution."""
    for r in stats_returns:
        if r.get("group_by") == "type":
            return [
                (str(row["group_value"]), int(row["event_count"]))
                for row in r.get("rows", [])[:_TOP_TYPES_CAP]
                if "group_value" in row and "event_count" in row
            ]
    type_counts: dict[str, int] = {}
    for r in query_returns:
        for ev in r.get("events", []):
            dt = ev.get("disaster_type")
            if isinstance(dt, str):
                type_counts[dt] = type_counts.get(dt, 0) + 1
    if not type_counts:
        return []
    sorted_items = sorted(type_counts.items(), key=lambda kv: -kv[1])
    return sorted_items[:_TOP_TYPES_CAP]


def _compute_top_event_summary(
    stats_returns: list[dict], query_returns: list[dict]
) -> str | None:
    """Build a short event summary from query_disasters' top event by deaths or damages.

    Question intent (deadliest vs costliest) is read from the most recent
    ``disaster_stats`` call's ``metric``. Default is deadliest.
    """
    intent = _detect_intent(stats_returns)
    candidates: list[dict] = []
    for r in query_returns:
        candidates.extend(r.get("events", []))
    if not candidates:
        return None

    if intent == "costliest":
        sort_key = "total_damages_usd_thousands"
    else:
        sort_key = "total_deaths"

    candidates_with_value = [
        ev for ev in candidates if isinstance(ev.get(sort_key), (int, float))
    ]
    if not candidates_with_value:
        return None

    top = max(candidates_with_value, key=lambda ev: ev[sort_key])
    return _format_event_summary(top, intent=intent)


def _detect_intent(stats_returns: list[dict]) -> str:
    """Return 'costliest' if the most recent stats call ranked by damages, else 'deadliest'."""
    for r in reversed(stats_returns):
        metric = r.get("metric")
        if metric == "total_damages_usd":
            return "costliest"
        if metric == "total_deaths":
            return "deadliest"
    return "deadliest"


def _format_event_summary(event: dict, *, intent: str) -> str:
    """Format a DisasterEvent dict into a single-line summary string."""
    year = event.get("year")
    disaster_type = event.get("disaster_type") or "event"
    country = event.get("country") or ""
    descriptor = event.get("event_name") or event.get("location") or ""
    descriptor_part = f" ({descriptor})" if descriptor else ""
    country_part = f" in {country}" if country else ""

    if intent == "costliest":
        damages = event.get("total_damages_usd_thousands")
        if damages is None:
            return f"{year} {disaster_type}{country_part}{descriptor_part}"
        return (
            f"{year} {disaster_type}{country_part}{descriptor_part}, "
            f"${int(damages):,}K damages"
        )

    deaths = event.get("total_deaths")
    if deaths is None:
        return f"{year} {disaster_type}{country_part}{descriptor_part}"
    return (
        f"{year} {disaster_type}{country_part}{descriptor_part}, "
        f"{int(deaths):,} deaths"
    )
