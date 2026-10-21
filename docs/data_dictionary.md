# Data Dictionary

## Raw files (frozen snapshot, `data/raw/` — source: Traffic Monitor Lizard, CC BY 4.0)

### csv-traffic-bangalore.csv — 111,637 rows
| Column | Meaning | Example |
|---|---|---|
| date | Collection date (local) | 2025-09-25 |
| time | Collection time, 24h local | 14:25 |
| route_code | Origin\|destination Plus Codes; join key to routes file | 2HM2+P8\|XJV5+RG |
| duration | Google Maps estimated travel time, minutes | 32 |
| distance | Route distance for that reading, km (varies — Google Maps returns alternative paths) | 11.0 |
| temp | Temperature °C — only from 2026-05-24, subset of days | 24 |
| realfeel | "Real feel" temperature °C — same coverage as temp | 23 |
| humidity | Relative humidity % — same coverage | 77 |
| rsi_flag | Rain status: `Rain` (350 raw rows), `Light Rain` (1,475), or empty = no rain reported on a weather-covered row / no weather before 2026-05-24. No `Heavy Rain` values exist in this snapshot | Light Rain |
| aqi | Air quality index — same coverage as temp | 96 |

### csv-routes-bangalore.csv — 13 rows
| Column | Meaning |
|---|---|
| route_code | Join key |
| label_full | Human-readable origin → destination |
| label_short | Short corridor name used in all RouteWise outputs (e.g. East Outer Ring) |
| map_link | Google Maps link for the route |
| accuweather_station | Weather station used for that route |

## Cleaned analysis file (`data/processed/cleaned.csv`) — 110,440 rows

One observation per (route, date, hour) — median duration/distance within the hour,
first non-null weather values. Built by `src/audit_and_clean.py`.
Two raw readings with duration < 10 min (both Airport route, 2 and 3 min over ~34 km)
were excluded as physically implausible before collapsing.

| Column | Meaning |
|---|---|
| timestamp | Date + hour of the observation |
| date, hour | Date and departure hour (0–23) |
| day_of_week | Monday…Sunday |
| is_weekend, day_type | day_type is `weekday` or `weekend` |
| time_bucket | night = 21:00–06:59, morning_peak = 07:00–10:59, midday = 11:00–15:59, evening_peak = 16:00–20:59 |
| route_code, label_short, label_full | Route identity |
| is_airport | True only for MG Road → Kempegowda International Airport (~34 km); always analysed separately, never ranked with the 12 core routes |
| duration | Median travel-time estimate for that hour, minutes |
| distance | Median distance for that hour, km |
| avg_speed_kmh | distance / (duration/60) |
| temp, realfeel, humidity, rsi_flag, aqi | Weather as above; empty where no weather snapshot exists |
| raw_readings_in_hour | How many raw readings were collapsed into this row (normally 1; 2–3 on 2026-10-19/20) |

## Derived metrics (used across outputs)
| Metric | Definition |
|---|---|
| Median / P50 | Middle value of durations; the "typical" trip |
| P90 | 90th percentile; 9 of 10 trips are at or below this |
| Buffer index | (P90 − P50) / P50 — extra time, as a share of the typical trip, needed for a 9-in-10 on-time plan |
| Buffer minutes | P90 − P50 |
| On-time probability | For a stated target (a user-set planning assumption): share of trips with duration ≤ target |
