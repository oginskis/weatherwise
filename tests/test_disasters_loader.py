import math

import pandas as pd

from src.mcp_servers.disasters.loader import _parse_coord, load_disasters


def test_load_disasters_reads_all_rows(disasters_fixture_path) -> None:
    df = load_disasters(disasters_fixture_path)
    assert len(df) == 12


def test_load_disasters_applies_categorical_dtypes(disasters_fixture_path) -> None:
    df = load_disasters(disasters_fixture_path)
    for col in ["Disaster Type", "Disaster Subgroup", "Continent", "ISO", "Country"]:
        assert isinstance(df[col].dtype, pd.CategoricalDtype), (
            f"column {col!r} should be categorical, got {df[col].dtype}"
        )


def test_load_disasters_adds_lowercase_helpers(disasters_fixture_path) -> None:
    df = load_disasters(disasters_fixture_path)
    assert "country_lc" in df.columns
    assert "location_lc" in df.columns
    # Japan rows should all be lowercase "japan" in country_lc
    japan_rows = df[df["ISO"] == "JPN"]
    assert (japan_rows["country_lc"] == "japan").all()
    # Tokyo row should match a "tokyo" substring
    tokyo_mask = df["location_lc"].str.contains("tokyo", na=False)
    assert tokyo_mask.sum() == 1


def test_load_disasters_parses_lat_lon_floats(disasters_fixture_path) -> None:
    df = load_disasters(disasters_fixture_path)
    # Plain decimal: row with Latitude="38.32" (Tohoku)
    tohoku = df[df["Event Name"] == "Tohoku"].iloc[0]
    assert tohoku["latitude"] == 38.32
    assert tohoku["longitude"] == 142.37
    # N/W suffix: row with Latitude="29.38 N", Longitude="95.16 W "
    harvey = df[df["Event Name"] == "Harvey"].iloc[0]
    assert harvey["latitude"] == 29.38
    assert harvey["longitude"] == -95.16
    # N/E suffix: Hagibis row uses "35.69 N" / "139.69 E"
    hagibis = df[df["Event Name"] == "Hagibis"].iloc[0]
    assert hagibis["latitude"] == 35.69
    assert hagibis["longitude"] == 139.69
    # Already-negative decimal: Australia "-37.81"
    bs = df[df["Event Name"] == "Black Saturday"].iloc[0]
    assert bs["latitude"] == -37.81
    # Missing lat/lon (1900 Bengal drought) -> NaN
    drought_1900 = df[(df["Year"] == 1900) & (df["Country"] == "India")].iloc[0]
    assert math.isnan(drought_1900["latitude"])


def test_parse_coord_handles_known_formats() -> None:
    s = pd.Series(["38.32", "1.51 N", "78.46 W ", "-37.81", "29.38 n", None])
    parsed = _parse_coord(s, pos="N", neg="S")
    # First, second, fourth, fifth values are latitude-like
    assert parsed.iloc[0] == 38.32
    assert parsed.iloc[1] == 1.51    # "1.51 N" -> +1.51
    assert parsed.iloc[3] == -37.81  # already negative
    assert parsed.iloc[4] == 29.38   # lowercase 'n' still positive

    s2 = pd.Series(["78.46 W "])
    parsed2 = _parse_coord(s2, pos="E", neg="W")
    assert parsed2.iloc[0] == -78.46  # "78.46 W " -> -78.46


def test_parse_coord_handles_east_suffix() -> None:
    """E suffix should produce a positive longitude (added per code review of Task 2)."""
    s = pd.Series(["139.69 E", "139.69 e", "78.46 E "])
    parsed = _parse_coord(s, pos="E", neg="W")
    assert parsed.iloc[0] == 139.69
    assert parsed.iloc[1] == 139.69
    assert parsed.iloc[2] == 78.46


def test_parse_coord_returns_nan_for_garbage() -> None:
    s = pd.Series(["", "n/a", None, "abc"])
    parsed = _parse_coord(s, pos="N", neg="S")
    assert parsed.isna().all()
