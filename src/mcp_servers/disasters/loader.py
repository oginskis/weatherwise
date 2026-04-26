"""Load the EM-DAT disasters CSV into a clean Pandas DataFrame.

Used at MCP server startup; the resulting DataFrame becomes the singleton
backing store for the repository layer.
"""
import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

CATEGORICAL_COLUMNS: list[str] = [
    "Disaster Group",
    "Disaster Subgroup",
    "Disaster Type",
    "Disaster Subtype",
    "Continent",
    "Region",
    "ISO",
    "Country",
]

_COORD_RE: re.Pattern[str] = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*([NSEWnsew])?\s*$"
)


def load_disasters(path: Path) -> pd.DataFrame:
    """Read the disaster CSV and return a cleaned DataFrame.

    The DataFrame retains the original column names and adds four derived
    columns: country_lc, location_lc, latitude, longitude.
    """
    logger.info("Loading disasters CSV from %s", path)
    df = pd.read_csv(
        path,
        dtype_backend="pyarrow",
        dtype={col: "category" for col in CATEGORICAL_COLUMNS},
    )
    df["country_lc"] = df["Country"].astype("string").str.lower()
    df["location_lc"] = df["Location"].astype("string").str.lower()
    df["latitude"] = _parse_coord(df["Latitude"], pos="N", neg="S")
    df["longitude"] = _parse_coord(df["Longitude"], pos="E", neg="W")
    logger.info("Loaded %d disaster rows", len(df))
    return df


def _parse_coord(series: pd.Series, *, pos: str, neg: str) -> pd.Series:
    """Parse coordinate strings like '38.32', '1.51 N', '78.46 W ' into floats.

    The hemisphere suffix ``pos`` means positive sign (N or E); ``neg`` means
    negative sign (S or W). Unrecognized values become NaN.
    """
    pos_upper, neg_upper = pos.upper(), neg.upper()

    def _convert(raw: object) -> float:
        if pd.isna(raw):
            return float("nan")
        text = str(raw).strip()
        if not text:
            return float("nan")
        match = _COORD_RE.match(text)
        if match is None:
            return float("nan")
        value = float(match.group(1))
        suffix = (match.group(2) or "").upper()
        if suffix == neg_upper:
            return -abs(value)
        if suffix == pos_upper:
            return abs(value)
        return value  # no suffix — keep value's own sign

    return series.map(_convert).astype("float64")
