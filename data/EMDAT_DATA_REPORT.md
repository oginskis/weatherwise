# EM-DAT Disasters Dataset — Analysis Report

**Source file:** `emdat_disasters_1900_2021.csv`
**Generated:** 2026-04-26

---

## 1. Overview

The file contains **EM-DAT** (Emergency Events Database) records of natural disasters worldwide.

| Property | Value |
|---|---|
| Rows (events) | 16,126 |
| Columns | 45 |
| Year range | 1900 – 2021 |
| Disaster Group | 100% `Natural` (single value — biological, geophysical, climatological, hydrological, meteorological, extra-terrestrial) |
| File size | ~4.7 MB |

---

## 2. What's in the data

Each row is one disaster event. Columns fall into five logical groups:

### 2.1 Identifiers & classification
- `Year`, `Seq` — composite event ID
- `Glide` — GLIDE disaster code (where available)
- `Disaster Group` / `Subgroup` / `Type` / `Subtype` / `Subsubtype` — 4-level taxonomy
- `Event Name` — e.g. hurricane name

### 2.2 Geography
- `Country`, `ISO`, `Region`, `Continent`
- `Location` — free-text sub-national description
- `Latitude`, `Longitude` — point coordinates (stored as text, see issues below)
- `River Basin`
- `Adm Level`, `Admin1 Code`, `Admin2 Code`, `Geo Locations` — administrative hierarchy

### 2.3 Timing
- `Start Year` / `Start Month` / `Start Day`
- `End Year` / `End Month` / `End Day`
- `Local Time`

### 2.4 Magnitude & physical characteristics
- `Dis Mag Value` + `Dis Mag Scale` (e.g. Km², Richter)
- `Origin`, `Associated Dis`, `Associated Dis2` — cause / cascading hazards

### 2.5 Impacts & response
- Human: `Total Deaths`, `No Injured`, `No Affected`, `No Homeless`, `Total Affected`
- Economic: `Insured Damages ('000 US$)`, `Total Damages ('000 US$)`, `CPI`
- Response flags: `OFDA Response`, `Appeal`, `Declaration`, `Aid Contribution`

---

## 3. Distribution snapshot

### Disaster types (top)
| Type | Events |
|---|---:|
| Flood | 5,551 |
| Storm | 4,496 |
| Earthquake | 1,544 |
| Epidemic | 1,501 |
| Landslide | 776 |
| Drought | 770 |
| Extreme temperature | 603 |
| Wildfire | 471 |
| Volcanic activity | 265 |

### By continent
Asia 6,490 · Americas 3,971 · Africa 2,946 · Europe 1,997 · Oceania 722

### Top countries
USA (1,087) · China (980) · India (752) · Philippines (668) · Indonesia (572)

### Events per decade — strong reporting bias visible
```
1900s    79    1960s    602    2000s   4,476
1910s    78    1970s    911    2010s   3,768
1920s   108    1980s  1,801    2020s     713 (partial)
1930s   134    1990s  2,975
1940s   171
1950s   310
```
The exponential growth almost certainly reflects **improved reporting & satellite/communication coverage**, not a real ~50× rise in disaster frequency. Pre-1970 records should be treated as a non-representative sample.

### Most extreme events
- Deadliest: 1931 China flood (3.7 M deaths), 1928 China drought (3.0 M), 1917 Soviet Union epidemic (2.5 M)
- Costliest: 2011 Japan earthquake ($210 B), 2005 USA storm — Katrina ($125 B), 1995 Japan Kobe earthquake ($100 B)

---

## 4. Data quality check

### Strengths
- **Zero fully-duplicate rows** — clean primary key handling.
- All "structural" fields (`Year`, `Country`, `ISO`, `Continent`, `Region`, `Disaster Type`, `Disaster Group`, `Disaster Subgroup`, `Start Year`, `End Year`, `Seq`) are **100% populated**.
- ISO codes and continent labels are consistent enough to group on directly.

### Issues found

| # | Issue | Severity | Detail |
|---|---|---|---|
| 1 | **Heavy missingness on impact fields** | High | `Total Damages` missing 67% of rows, `Insured Damages` 93%, `Total Deaths` 29%, `No Injured` 76%. Any cost/casualty aggregate must explicitly say "where reported". |
| 2 | **Lat/Lon stored as text** | Medium | Mixed formats: `"14"`, `"32.04"`, `"1.51 N"`, `"78.46 W "` (note trailing space). Cannot be plotted without parsing the hemisphere suffix and stripping whitespace. |
| 3 | **`Year` vs `Start Year` mismatch** | Low | 130 rows where `Year != Start Year`. Likely indicates the event was *registered* in a different year than it began (multi-year disasters). Pick one canonical column for time series. |
| 4 | **`(Year, Seq)` is not unique** | Medium | 1,745 duplicate `(Year, Seq)` pairs — so the natural composite key collides. EM-DAT's true unique ID is the `DisNo` (`YYYY-SEQ-ISO`); this file appears to omit the ISO suffix from the key. Use `(Year, Seq, ISO)` instead. |
| 5 | **`Disaster Group` has only one value** | Low | All rows are `Natural` — column is dead weight in this extract. |
| 6 | **Sparse columns of low analytical value** | Low | `Aid Contribution`, `Glide`, `Local Time`, `Disaster Subsubtype`, `Associated Dis2`, `River Basin`, `OFDA Response` are all >90% null. |
| 7 | **Reporting bias by decade** | High (interpretation) | Pre-1970 counts are 5–50× lower than post-2000. Do **not** use raw event counts to claim "disasters are increasing" without normalising by reporting coverage. |
| 8 | **`Total Affected` ≠ sum of components** | Low–Medium | EM-DAT defines `Total Affected = Injured + Affected + Homeless`, but with so many nulls in the components, this aggregate is partially imputed. Verify before recomputing. |
| 9 | **Country labels include parenthetical articles** | Low | e.g. `"United States of America (the)"`, `"Iran (Islamic Republic of)"`, `"Philippines (the)"`. Prefer joining on `ISO` rather than `Country` text. |
| 10 | **No CPI deflator applied** | Medium | `CPI` is provided per row but `Total Damages` is **nominal** USD. To compare 1980 and 2020 damages you must deflate using the supplied CPI. |
| 11 | **Outliers / scale of damage values** | Low | `Total Damages` max is $210 B (2011 Tohoku) — plausible, not a typo, but a few orders of magnitude above the median ($60 M); use log-scale for plots. |

### Recommended cleanup before analysis
1. Build a real key: `dis_no = f"{Year}-{Seq:04d}-{ISO}"`.
2. Parse `Latitude`/`Longitude` to floats with sign from `N/S/E/W`.
3. Drop or archive: `Disaster Group`, `Glide`, `Aid Contribution`, `Local Time`, `Disaster Subsubtype`, `Associated Dis2`.
4. Add `damages_real_usd = Total Damages * (CPI_2021 / CPI)` for time-series comparability.
5. Restrict trend analyses to **1980 onwards** to mitigate reporting bias.
6. Always report missingness alongside any aggregate of `Total Deaths` / `Total Damages`.

---

## 5. TL;DR

A rich, well-structured event-level disaster catalogue covering 122 years and ~16k events. **Identifier and classification fields are clean**, but **impact fields (deaths, damages) are sparsely populated**, **coordinates need parsing**, and **reporting frequency is heavily biased toward recent decades**. Useful out-of-the-box for categorical/geographic analysis; needs deflation, coordinate parsing, and a stricter unique key before quantitative or time-series work.
