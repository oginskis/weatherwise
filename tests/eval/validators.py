"""Validation helpers for agent eval tests.

The hallucination check pulls every (year, type, country) triple a response
implies — from the structured ``disasters`` field and from year mentions in
the message text — and verifies each appears in the EM-DAT CSV. Anything
the agent states without backing data is flagged.
"""
import json
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict
from pydantic_ai.messages import ModelMessage, ToolCallPart

from src.agent.models import AgentResponse
from src.mcp_servers.disasters.loader import load_disasters

# Years referenced in the agent message must match the EM-DAT span.
MIN_DATASET_YEAR: int = 1900
MAX_DATASET_YEAR: int = 2021

# Match years 1900-2099 (we'll filter to dataset span downstream).
_YEAR_RE: re.Pattern[str] = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


class HallucinationFinding(BaseModel):
    """One ungrounded fact stated by the agent."""

    model_config = ConfigDict(frozen=True)

    where: str  # e.g. "deadliest_event_summary" or "message"
    claim: str  # the snippet of text containing the unverified claim
    reason: str


# pydantic-ai injects a synthetic tool named "final_result" to deliver
# structured output back to the caller — it is not a user tool and must
# be excluded from trajectory assertions and tool-count budgets.
_INTERNAL_TOOLS: frozenset[str] = frozenset({"final_result"})


def extract_tool_call_sequence(messages: Iterable[ModelMessage]) -> list[str]:
    """Return the ordered list of user-tool names called during the agent run.

    Pulled from ``Agent.run(...).all_messages()``. Each ToolCallPart in
    chronological order contributes one entry; ToolReturnParts are ignored.
    pydantic-ai's internal ``final_result`` tool is excluded so that
    trajectory budgets reflect actual MCP/tool usage.
    """
    sequence: list[str] = []
    for message in messages:
        for part in getattr(message, "parts", ()) or ():
            if isinstance(part, ToolCallPart) and part.tool_name not in _INTERNAL_TOOLS:
                sequence.append(part.tool_name)
    return sequence


def is_subsequence(needles: tuple[str, ...], haystack: list[str]) -> bool:
    """True iff ``needles`` appears in ``haystack`` in order (gaps allowed)."""
    iterator = iter(haystack)
    return all(needle in iterator for needle in needles)


def extract_tool_calls(
    messages: Iterable[ModelMessage],
) -> list[tuple[str, dict[str, object]]]:
    """Return chronological list of (tool_name, parsed_args) tuples.

    pydantic-ai stores ToolCallPart.args as either dict or JSON string;
    we coerce to dict here so callers can treat them uniformly. The
    ``final_result`` synthetic tool is excluded.
    """
    calls: list[tuple[str, dict[str, object]]] = []
    for message in messages:
        for part in getattr(message, "parts", ()) or ():
            if not isinstance(part, ToolCallPart):
                continue
            if part.tool_name in _INTERNAL_TOOLS:
                continue
            raw = part.args
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except json.JSONDecodeError:
                    raw = {}
            if not isinstance(raw, dict):
                raw = {}
            calls.append((part.tool_name, raw))
    return calls


def args_subset_match(
    expected: dict[str, object], actual: dict[str, object]
) -> bool:
    """True iff every key/value in ``expected`` appears in ``actual``.

    Used to assert tool arguments without requiring an exact-match —
    the agent may pass additional arguments we don't care about.
    """
    return all(actual.get(k) == v for k, v in expected.items())


@lru_cache(maxsize=1)
def _disasters_dataframe(csv_path: str) -> pd.DataFrame:
    return load_disasters(Path(csv_path))


def _event_exists(
    df: pd.DataFrame,
    *,
    year: int,
    country: str | None = None,
    disaster_type: str | None = None,
) -> bool:
    """Return True iff at least one row in the EM-DAT CSV matches the triple."""
    mask = df["Year"] == year
    if country is not None:
        country_lc = country.strip().lower()
        country_upper = country.strip().upper()
        mask &= (df["country_lc"] == country_lc) | (
            df["ISO"].astype("string") == country_upper
        )
    if disaster_type is not None:
        mask &= df["Disaster Type"].astype("string") == disaster_type
    return bool(df[mask].shape[0] > 0)


def _years_in_text(text: str) -> set[int]:
    return {
        int(match)
        for match in _YEAR_RE.findall(text or "")
        if MIN_DATASET_YEAR <= int(match) <= MAX_DATASET_YEAR
    }


def find_hallucinations(
    response: AgentResponse,
    *,
    csv_path: Path,
    grounded_country: str | None,
    grounded_disaster_type: str | None,
) -> list[HallucinationFinding]:
    """Scan the agent's free-text ``message`` for years not in EM-DAT.

    The structured disaster card is built deterministically from tool
    returns and is grounded by construction; we don't check it here. The
    free-text message still goes through the LLM and can mention years
    that don't correspond to real events. We extract every dataset-range
    year (1900-2021) the message mentions and verify each appears in EM-DAT
    under the case's country/type filter. Years outside the dataset span
    are ignored — they are clearly not data claims.
    """
    df = _disasters_dataframe(str(csv_path))
    findings: list[HallucinationFinding] = []

    for year in _years_in_text(response.message):
        if not _event_exists(
            df,
            year=year,
            country=grounded_country,
            disaster_type=grounded_disaster_type,
        ):
            findings.append(
                HallucinationFinding(
                    where="message",
                    claim=f"year {year} mentioned in message",
                    reason=(
                        f"year {year} not present in EM-DAT for "
                        f"country={grounded_country!r}, "
                        f"disaster_type={grounded_disaster_type!r}"
                    ),
                )
            )

    return findings
