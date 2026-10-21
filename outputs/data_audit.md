# Data Audit — Frozen Snapshot (2026-10-21)

Source: Traffic Monitor Lizard (dataset CC BY 4.0). See `data/raw/SNAPSHOT.md` for provenance.
All numbers below were computed by `src/audit_and_clean.py` from the frozen raw files.

## Size and coverage
- Raw traffic rows: **111,637**
- Date range: **2025-09-25 to 2026-10-21**
- Routes present: **13** (12 core routes of ~10 km + the Airport route at ~34 km, analysed separately)
- Missing/unparseable durations: **0**; missing timestamps: **0**
- Duration range in raw data: 2 to 107 minutes

## Duplicates and sampling grain
- Exact duplicate rows: **0**; duplicate (route, date, time): **0**
- Normal sampling is one reading per route per hour (312 rows/day = 13 routes x 24 h).
- Rows that fall in a multi-reading (route, date, hour) cell: **1,794** — concentrated on 2026-10-19/20, when sampling briefly ran about 3x per hour.
- Unique (route, date, hour) cells: **110,441**
- **Dedup rule used throughout this project:** one observation per (route, date, hour), using the median duration/distance in that hour. This stops the two high-frequency days from triple-weighting hourly statistics.

## Invalid readings removed
- Readings with duration < 10 minutes on routes of at least 9 km: **2**, excluded as physically implausible:
  - 2026-10-12 15:25, Airport Expy: duration 2 min over 34.0 km
  - 2026-10-19 19:25, Airport Expy: duration 3 min over 35.2 km

## Distance per route (raw)
| Route | Readings | Median distance (km) | Min | Max | Median duration (min) |
|---|---|---|---|---|---|
| North Inner Ring | 8,651 | 10.6 | 9.3 | 16.5 | 30.0 |
| North Outer Ring | 8,651 | 9.7 | 9.6 | 16.1 | 27.0 |
| Hosur Road | 8,651 | 10.4 | 9.6 | 18.3 | 21.0 |
| Mysore Road | 8,525 | 9.9 | 9.9 | 14.1 | 26.0 |
| Double Decker Flyover | 8,651 | 10.1 | 9.5 | 13.1 | 24.0 |
| Central Diagonal 2 | 8,651 | 10.2 | 9.2 | 13.9 | 34.0 |
| Sarjapur Road | 8,395 | 10.1 | 9.8 | 25.8 | 28.0 |
| South Outer Ring | 8,216 | 10.6 | 9.5 | 21.6 | 33.0 |
| Central Diagonal 1 | 8,651 | 10.5 | 9.5 | 13.5 | 30.0 |
| Airport Expy | 8,642 | 34.3 | 32.4 | 38.6 | 51.0 |
| East Inner Ring | 8,651 | 10.5 | 9.2 | 13.9 | 32.0 |
| East Outer Ring | 8,651 | 10.0 | 9.8 | 15.3 | 21.0 |
| Old Airport Road | 8,651 | 9.4 | 4.3 | 15.2 | 26.0 |

Note: distance varies within a route because Google Maps returns alternative paths; the median is the representative length.

## Weather coverage (the key limitation)
- Weather fields first appear on **2026-05-24** and last on **2026-10-21** — there is **no weather data at all before 2026-05-24**.
- Days with any temperature reading in that span: **78**, with gaps: 2026-07-29 to 2026-10-09 (73 days).
- Of rows dated on/after 2026-05-24, only **49.52%** carry a temperature reading.

| Column | Populated rows | % of all rows | First date | Last date |
|---|---|---|---|---|
| temp | 23,386 | 20.95% | 2026-05-24 | 2026-10-21 |
| realfeel | 23,386 | 20.95% | 2026-05-24 | 2026-10-21 |
| humidity | 23,254 | 20.83% | 2026-05-24 | 2026-10-21 |
| rsi_flag | 1,825 | 1.63% | 2026-05-24 | 2026-10-18 |
| aqi | 23,437 | 20.99% | 2026-05-24 | 2026-10-21 |

- `rsi_flag` values actually present: {'Light Rain': 1475, 'Rain': 350} — plus empty, which on a row that otherwise has weather values is read as 'no rain reported'. There is no 'Heavy Rain' value in this snapshot.
- Consequence: the weather analysis (Phase 6) is restricted to rows where weather was recorded, and states its sample sizes and period. It must never be described as a full-year weather analysis.

## Cleaned analysis dataset
- File: `data/processed/cleaned.csv` — **110,440** hourly observations, 2025-09-25 to 2026-10-21.
