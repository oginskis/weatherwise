"""Validation helpers for agent eval tests.

The hallucination check pulls every (year, type, country) triple a response
implies — from the structured ``disasters`` field and from year mentions in
the message text — and verifies each appears in the EM-DAT CSV. Anything
the agent states without backing data is flagged.
"""
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict

from src.agent.models import AgentResponse, DisasterSummaryView
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
    """Scan response for facts that don't appear in the EM-DAT dataset.

    The check applies year-level provenance: every dataset-range year
    (1900-2021) referenced in the response must correspond to at least one
    real event in the CSV under the case's country/type filter. Years
    outside the dataset span are ignored — they are clearly not data claims.
    """
    df = _disasters_dataframe(str(csv_path))
    findings: list[HallucinationFinding] = []

    summary: DisasterSummaryView | None = response.disasters
    if summary is not None:
        for year in _years_in_text(summary.deadliest_event_summary or ""):
            if not _event_exists(
                df,
                year=year,
                country=grounded_country,
                disaster_type=grounded_disaster_type,
            ):
                findings.append(
                    HallucinationFinding(
                        where="disasters.deadliest_event_summary",
                        claim=str(summary.deadliest_event_summary),
                        reason=(
                            f"year {year} not present in EM-DAT for "
                            f"country={grounded_country!r}, "
                            f"disaster_type={grounded_disaster_type!r}"
                        ),
                    )
                )
        for disaster_type, _count in summary.top_types:
            valid_types = set(df["Disaster Type"].astype("string").unique())
            if disaster_type not in valid_types:
                findings.append(
                    HallucinationFinding(
                        where="disasters.top_types",
                        claim=disaster_type,
                        reason=(
                            f"disaster_type {disaster_type!r} not in EM-DAT "
                            "Disaster Type categorical values"
                        ),
                    )
                )

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
