"""Shared pytest fixtures for the test suite."""
from pathlib import Path

import pandas as pd
import pytest

DISASTER_FIXTURE_ROWS: list[dict] = [
    # Japan — multiple events for top-N and location_summary tests
    {"Year": 2011, "Seq": 9001, "Disaster Group": "Natural", "Disaster Subgroup": "Geophysical",
     "Disaster Type": "Earthquake", "Disaster Subtype": "Earthquake", "Event Name": "Tohoku",
     "Country": "Japan", "ISO": "JPN", "Region": "Eastern Asia", "Continent": "Asia",
     "Location": "Tohoku region", "Latitude": "38.32", "Longitude": "142.37",
     "Start Year": 2011, "Start Month": 3, "Start Day": 11,
     "End Year": 2011, "End Month": 3, "End Day": 11,
     "Total Deaths": 19846, "Total Affected": 469000,
     "Total Damages ('000 US$)": 210000000, "CPI": 87.5},
    {"Year": 1995, "Seq": 9002, "Disaster Group": "Natural", "Disaster Subgroup": "Geophysical",
     "Disaster Type": "Earthquake", "Disaster Subtype": "Earthquake", "Event Name": "Kobe",
     "Country": "Japan", "ISO": "JPN", "Region": "Eastern Asia", "Continent": "Asia",
     "Location": "Kobe", "Latitude": "34.7", "Longitude": "135.2",
     "Start Year": 1995, "Start Month": 1, "Start Day": 17,
     "End Year": 1995, "End Month": 1, "End Day": 17,
     "Total Deaths": 6434, "Total Damages ('000 US$)": 100000000, "CPI": 72.3},
    {"Year": 2019, "Seq": 9003, "Disaster Group": "Natural", "Disaster Subgroup": "Meteorological",
     "Disaster Type": "Storm", "Disaster Subtype": "Tropical cyclone", "Event Name": "Hagibis",
     "Country": "Japan", "ISO": "JPN", "Region": "Eastern Asia", "Continent": "Asia",
     "Location": "Tokyo, Chiba", "Latitude": "35.69 N", "Longitude": "139.69 E",
     "Start Year": 2019, "Start Month": 10, "Start Day": 11,
     "End Year": 2019, "End Month": 10, "End Day": 13,
     "Total Deaths": 90, "Total Damages ('000 US$)": 17000000, "CPI": 99.0},
    # USA — multiple types, lat/lon with N/W suffix
    {"Year": 2005, "Seq": 9101, "Disaster Group": "Natural", "Disaster Subgroup": "Meteorological",
     "Disaster Type": "Storm", "Disaster Subtype": "Tropical cyclone", "Event Name": "Katrina",
     "Country": "United States of America (the)", "ISO": "USA",
     "Region": "Northern America", "Continent": "Americas",
     "Location": "Louisiana, Mississippi, Florida", "Latitude": "29.95",
     "Longitude": "-90.07",
     "Start Year": 2005, "Start Month": 8, "Start Day": 23,
     "End Year": 2005, "End Month": 8, "End Day": 31,
     "Total Deaths": 1833, "Total Damages ('000 US$)": 125000000, "CPI": 80.6},
    {"Year": 2017, "Seq": 9102, "Disaster Group": "Natural", "Disaster Subgroup": "Meteorological",
     "Disaster Type": "Storm", "Disaster Subtype": "Tropical cyclone", "Event Name": "Harvey",
     "Country": "United States of America (the)", "ISO": "USA",
     "Region": "Northern America", "Continent": "Americas",
     "Location": "Texas, Houston", "Latitude": "29.38 N", "Longitude": "95.16 W ",
     "Start Year": 2017, "Start Month": 8, "Start Day": 17,
     "End Year": 2017, "End Month": 9, "End Day": 2,
     "Total Deaths": 88, "Total Damages ('000 US$)": 95000000, "CPI": 96.1},
    {"Year": 2018, "Seq": 9103, "Disaster Group": "Natural", "Disaster Subgroup": "Climatological",
     "Disaster Type": "Wildfire", "Disaster Subtype": "Forest fire", "Event Name": "Camp Fire",
     "Country": "United States of America (the)", "ISO": "USA",
     "Region": "Northern America", "Continent": "Americas",
     "Location": "California, Butte County", "Latitude": "39.79", "Longitude": "-121.61",
     "Start Year": 2018, "Start Month": 11, "Start Day": 8,
     "End Year": 2018, "End Month": 11, "End Day": 25,
     "Total Deaths": 85, "Total Damages ('000 US$)": 16500000, "CPI": 98.0},
    # India — pre-1980 high-deaths event for top-N
    {"Year": 1900, "Seq": 9201, "Disaster Group": "Natural", "Disaster Subgroup": "Climatological",
     "Disaster Type": "Drought", "Disaster Subtype": "Drought",
     "Country": "India", "ISO": "IND", "Region": "Southern Asia", "Continent": "Asia",
     "Location": "Bengal",
     "Start Year": 1900, "End Year": 1900,
     "Total Deaths": 1250000, "CPI": 3.22},
    {"Year": 2019, "Seq": 9202, "Disaster Group": "Natural", "Disaster Subgroup": "Hydrological",
     "Disaster Type": "Flood", "Disaster Subtype": "Riverine flood",
     "Country": "India", "ISO": "IND", "Region": "Southern Asia", "Continent": "Asia",
     "Location": "Bengal, Odisha", "Latitude": "22.57", "Longitude": "88.36",
     "Start Year": 2019, "Start Month": 7, "Start Day": 1,
     "End Year": 2019, "End Month": 8, "End Day": 31,
     "Total Deaths": 3000, "Total Damages ('000 US$)": 5000000, "CPI": 99.0},
    # Australia — wildfires + flood
    {"Year": 2009, "Seq": 9301, "Disaster Group": "Natural", "Disaster Subgroup": "Climatological",
     "Disaster Type": "Wildfire", "Disaster Subtype": "Forest fire", "Event Name": "Black Saturday",
     "Country": "Australia", "ISO": "AUS", "Region": "Australia and New Zealand", "Continent": "Oceania",
     "Location": "Victoria", "Latitude": "-37.81", "Longitude": "144.96",
     "Start Year": 2009, "Start Month": 2, "Start Day": 7,
     "End Year": 2009, "End Month": 3, "End Day": 14,
     "Total Deaths": 173, "Total Damages ('000 US$)": 1300000, "CPI": 82.4},
    {"Year": 2011, "Seq": 9302, "Disaster Group": "Natural", "Disaster Subgroup": "Hydrological",
     "Disaster Type": "Flood", "Disaster Subtype": "Riverine flood",
     "Country": "Australia", "ISO": "AUS", "Region": "Australia and New Zealand", "Continent": "Oceania",
     "Location": "Queensland, Brisbane",
     "Start Year": 2010, "Start Month": 12, "Start Day": 25,
     "End Year": 2011, "End Month": 1, "End Day": 14,
     "Total Deaths": 35, "Total Damages ('000 US$)": 7300000, "CPI": 87.5},
    # Haiti — single deadliest event for ranking tests
    {"Year": 2010, "Seq": 9401, "Disaster Group": "Natural", "Disaster Subgroup": "Geophysical",
     "Disaster Type": "Earthquake", "Disaster Subtype": "Earthquake",
     "Country": "Haiti", "ISO": "HTI", "Region": "Caribbean", "Continent": "Americas",
     "Location": "Port-au-Prince", "Latitude": "18.54", "Longitude": "-72.34",
     "Start Year": 2010, "Start Month": 1, "Start Day": 12,
     "End Year": 2010, "End Month": 1, "End Day": 12,
     "Total Deaths": 222570, "Total Damages ('000 US$)": 8000000, "CPI": 84.0},
    # Latvia — only event, pre-1980 (used to test silence in location_disaster_summary)
    {"Year": 1969, "Seq": 9501, "Disaster Group": "Natural", "Disaster Subgroup": "Meteorological",
     "Disaster Type": "Storm", "Disaster Subtype": "Convective storm",
     "Country": "Latvia", "ISO": "LVA", "Region": "Northern Europe", "Continent": "Europe",
     "Location": "Riga",
     "Start Year": 1969, "End Year": 1969,
     "Total Deaths": 3, "CPI": 12.0},
]

ALL_FIXTURE_COLUMNS: list[str] = [
    "Year", "Seq", "Glide", "Disaster Group", "Disaster Subgroup", "Disaster Type",
    "Disaster Subtype", "Disaster Subsubtype", "Event Name", "Country", "ISO",
    "Region", "Continent", "Location", "Origin", "Associated Dis", "Associated Dis2",
    "OFDA Response", "Appeal", "Declaration", "Aid Contribution", "Dis Mag Value",
    "Dis Mag Scale", "Latitude", "Longitude", "Local Time", "River Basin",
    "Start Year", "Start Month", "Start Day", "End Year", "End Month", "End Day",
    "Total Deaths", "No Injured", "No Affected", "No Homeless", "Total Affected",
    "Insured Damages ('000 US$)", "Total Damages ('000 US$)", "CPI",
    "Adm Level", "Admin1 Code", "Admin2 Code", "Geo Locations",
]


@pytest.fixture
def disasters_fixture_path(tmp_path: Path) -> Path:
    """Write the disaster fixture rows to a temp CSV and return its path."""
    df = pd.DataFrame(DISASTER_FIXTURE_ROWS)
    # Ensure every column exists in the right order, even if blank
    for col in ALL_FIXTURE_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[ALL_FIXTURE_COLUMNS]
    csv_path = tmp_path / "fixture.csv"
    df.to_csv(csv_path, index=False)
    return csv_path
