"""Phase 1+2: audit the frozen raw snapshot and build the cleaned,
hourly-grain analysis dataset.

Dedup rule (documented, applied consistently everywhere):
- There are 0 exact duplicate rows and 0 duplicate (route, date, time) rows.
- Normal sampling is exactly one reading per route per hour
  (312 rows/day = 13 routes x 24 hours). On 2026-10-19/20 sampling briefly
  ran ~3x per hour, which would triple-weight those two days in hourly
  statistics. Therefore every per-hour statistic in this project uses ONE
  observation per (route, date, hour): the median duration/distance and
  the first non-null weather values within that hour.
- Two readings with duration < 10 minutes on routes of >= 9 km are
  physically implausible (both are Airport-route readings of 2 and 3
  minutes for ~34 km) and are excluded as invalid. Count is reported.
"""
import json
import numpy as np
import pandas as pd

from common import BASE, RAW_TRAFFIC, OUTPUTS, HOUR_TO_BUCKET, load_routes

INVALID_DURATION_MIN = 10  # minutes; routes are all >= 9 km


def contiguous_gaps(dates_with, start, end):
    all_days = pd.date_range(start, end, freq="D")
    have = set(pd.to_datetime(dates_with).date)
    gaps, cur = [], []
    for d in all_days:
        if d.date() not in have:
            cur.append(d)
        elif cur:
            gaps.append((cur[0], cur[-1], len(cur)))
            cur = []
    if cur:
        gaps.append((cur[0], cur[-1], len(cur)))
    return [(str(a.date()), str(b.date()), n) for a, b, n in gaps]


def main():
    raw = pd.read_csv(RAW_TRAFFIC, dtype=str, keep_default_na=False).replace("", np.nan)
    routes = load_routes()
    label = dict(zip(routes.route_code, routes.label_short))
    full_label = dict(zip(routes.route_code, routes.label_full))

    n_raw = len(raw)
    raw["duration_num"] = pd.to_numeric(raw["duration"], errors="coerce")
    raw["distance_num"] = pd.to_numeric(raw["distance"], errors="coerce")
    raw["timestamp"] = pd.to_datetime(raw["date"] + " " + raw["time"], errors="coerce")
    raw["hour"] = raw["timestamp"].dt.hour

    stats = {}
    stats["total_rows_raw"] = int(n_raw)
    stats["date_min"] = str(raw["date"].min())
    stats["date_max"] = str(raw["date"].max())
    stats["n_routes"] = int(raw["route_code"].nunique())
    stats["exact_duplicate_rows"] = int(raw.duplicated().sum())
    stats["dup_route_date_time"] = int(raw.duplicated(subset=["route_code", "date", "time"]).sum())
    dup_hour_rows = raw.duplicated(subset=["route_code", "date", "hour"], keep=False)
    stats["rows_in_multi_reading_hours"] = int(dup_hour_rows.sum())
    stats["unique_route_date_hour"] = int(raw.drop_duplicates(subset=["route_code", "date", "hour"]).shape[0])
    stats["missing_duration"] = int(raw["duration_num"].isna().sum())
    stats["missing_timestamp"] = int(raw["timestamp"].isna().sum())
    invalid = raw[raw["duration_num"] < INVALID_DURATION_MIN]
    stats["invalid_duration_lt10"] = int(len(invalid))
    stats["invalid_rows"] = [
        {"date": r.date, "time": r.time, "route": label.get(r.route_code, r.route_code),
         "duration": int(r.duration_num), "distance_km": float(r.distance_num)}
        for r in invalid.itertuples()
    ]
    stats["duration_min"], stats["duration_max"] = float(raw["duration_num"].min()), float(raw["duration_num"].max())

    per_route = (
        raw.groupby("route_code")
        .agg(readings=("duration_num", "size"), dist_median=("distance_num", "median"),
             dist_min=("distance_num", "min"), dist_max=("distance_num", "max"),
             dur_median=("duration_num", "median"))
        .reset_index()
    )
    per_route["label_short"] = per_route["route_code"].map(label)
    per_route["label_full"] = per_route["route_code"].map(full_label)
    stats["per_route"] = per_route.round(2).to_dict("records")

    # Weather coverage
    wcols = ["temp", "realfeel", "humidity", "rsi_flag", "aqi"]
    weather = {}
    for c in wcols:
        pop = raw[c].notna()
        weather[c] = {
            "populated_rows": int(pop.sum()),
            "pct_of_all_rows": round(100 * float(pop.mean()), 2),
            "first_date": str(raw.loc[pop, "date"].min()) if pop.any() else None,
            "last_date": str(raw.loc[pop, "date"].max()) if pop.any() else None,
        }
    stats["weather_columns"] = weather
    stats["rsi_values"] = {str(k): int(v) for k, v in raw["rsi_flag"].value_counts(dropna=True).items()}
    temp_days = sorted(raw.loc[raw["temp"].notna(), "date"].unique())
    stats["weather_days_with_temp"] = len(temp_days)
    stats["weather_span"] = [temp_days[0], temp_days[-1]]
    stats["weather_gap_ranges"] = contiguous_gaps(temp_days, temp_days[0], temp_days[-1])
    in_span = raw[(raw["date"] >= temp_days[0])]
    stats["rows_from_weather_start"] = int(len(in_span))
    stats["temp_pct_from_weather_start"] = round(100 * float(in_span["temp"].notna().mean()), 2)

    # ---- Cleaning: drop invalid durations, collapse to hourly grain ----
    valid = raw[raw["duration_num"] >= INVALID_DURATION_MIN].copy()
    for c in ["temp", "realfeel", "humidity", "aqi"]:
        valid[c] = pd.to_numeric(valid[c], errors="coerce")

    def first_non_null(s):
        s = s.dropna()
        return s.iloc[0] if len(s) else np.nan

    hourly = (
        valid.groupby(["route_code", "date", "hour"], as_index=False)
        .agg(duration=("duration_num", "median"), distance=("distance_num", "median"),
             temp=("temp", first_non_null), realfeel=("realfeel", first_non_null),
             humidity=("humidity", first_non_null), rsi_flag=("rsi_flag", first_non_null),
             aqi=("aqi", first_non_null), raw_readings_in_hour=("duration_num", "size"))
    )
    hourly["timestamp"] = pd.to_datetime(hourly["date"]) + pd.to_timedelta(hourly["hour"], unit="h")
    hourly["day_of_week"] = hourly["timestamp"].dt.day_name()
    hourly["is_weekend"] = hourly["timestamp"].dt.dayofweek >= 5
    hourly["day_type"] = np.where(hourly["is_weekend"], "weekend", "weekday")
    hourly["time_bucket"] = hourly["hour"].map(HOUR_TO_BUCKET)
    hourly["avg_speed_kmh"] = hourly["distance"] / (hourly["duration"] / 60.0)
    hourly["label_short"] = hourly["route_code"].map(label)
    hourly["label_full"] = hourly["route_code"].map(full_label)
    hourly["is_airport"] = hourly["route_code"] == "XJG4+7J|5PX4+HQ"
    hourly = hourly.sort_values(["timestamp", "route_code"]).reset_index(drop=True)
    cols = ["timestamp", "date", "time_bucket", "hour", "day_of_week", "is_weekend", "day_type",
            "route_code", "label_short", "label_full", "is_airport", "duration", "distance",
            "avg_speed_kmh", "temp", "realfeel", "humidity", "rsi_flag", "aqi", "raw_readings_in_hour"]
    out_path = BASE / "data" / "processed" / "cleaned.csv"
    hourly[cols].to_csv(out_path, index=False)
    stats["cleaned_hourly_rows"] = int(len(hourly))
    stats["cleaned_date_min"] = str(hourly["date"].min())
    stats["cleaned_date_max"] = str(hourly["date"].max())

    OUTPUTS.mkdir(exist_ok=True)
    (OUTPUTS / "audit_stats.json").write_text(json.dumps(stats, indent=2))
    per_route.to_csv(OUTPUTS / "readings_per_route.csv", index=False)

    # ---- data_audit.md ----
    w = stats["weather_columns"]
    gap_txt = "; ".join(
        f"{a} to {b} ({n} days)" if n > 1 else f"{a} (1 day)" for a, b, n in stats["weather_gap_ranges"]
    ) or "none"
    lines = [
        "# Data Audit — Frozen Snapshot (2026-10-21)",
        "",
        "Source: Traffic Monitor Lizard (dataset CC BY 4.0). See `data/raw/SNAPSHOT.md` for provenance.",
        "All numbers below were computed by `src/audit_and_clean.py` from the frozen raw files.",
        "",
        "## Size and coverage",
        f"- Raw traffic rows: **{stats['total_rows_raw']:,}**",
        f"- Date range: **{stats['date_min']} to {stats['date_max']}**",
        f"- Routes present: **{stats['n_routes']}** (12 core routes of ~10 km + the Airport route at ~34 km, analysed separately)",
        f"- Missing/unparseable durations: **{stats['missing_duration']}**; missing timestamps: **{stats['missing_timestamp']}**",
        f"- Duration range in raw data: {stats['duration_min']:.0f} to {stats['duration_max']:.0f} minutes",
        "",
        "## Duplicates and sampling grain",
        f"- Exact duplicate rows: **{stats['exact_duplicate_rows']}**; duplicate (route, date, time): **{stats['dup_route_date_time']}**",
        "- Normal sampling is one reading per route per hour (312 rows/day = 13 routes x 24 h).",
        f"- Rows that fall in a multi-reading (route, date, hour) cell: **{stats['rows_in_multi_reading_hours']:,}** — "
        "concentrated on 2026-10-19/20, when sampling briefly ran about 3x per hour.",
        f"- Unique (route, date, hour) cells: **{stats['unique_route_date_hour']:,}**",
        "- **Dedup rule used throughout this project:** one observation per (route, date, hour), "
        "using the median duration/distance in that hour. This stops the two high-frequency days "
        "from triple-weighting hourly statistics.",
        "",
        "## Invalid readings removed",
        f"- Readings with duration < {INVALID_DURATION_MIN} minutes on routes of at least 9 km: **{stats['invalid_duration_lt10']}**, excluded as physically implausible:",
    ]
    for r in stats["invalid_rows"]:
        lines.append(f"  - {r['date']} {r['time']}, {r['route']}: duration {r['duration']} min over {r['distance_km']} km")
    lines += [
        "",
        "## Distance per route (raw)",
        "| Route | Readings | Median distance (km) | Min | Max | Median duration (min) |",
        "|---|---|---|---|---|---|",
    ]
    for r in stats["per_route"]:
        lines.append(f"| {r['label_short']} | {r['readings']:,} | {r['dist_median']} | {r['dist_min']} | {r['dist_max']} | {r['dur_median']} |")
    lines += [
        "",
        "Note: distance varies within a route because Google Maps returns alternative paths; the median is the representative length.",
        "",
        "## Weather coverage (the key limitation)",
        f"- Weather fields first appear on **{stats['weather_span'][0]}** and last on **{stats['weather_span'][1]}** — there is **no weather data at all before 2026-05-24**.",
        f"- Days with any temperature reading in that span: **{stats['weather_days_with_temp']}**, with gaps: {gap_txt}.",
        f"- Of rows dated on/after 2026-05-24, only **{stats['temp_pct_from_weather_start']}%** carry a temperature reading.",
        "",
        "| Column | Populated rows | % of all rows | First date | Last date |",
        "|---|---|---|---|---|",
    ]
    for c in wcols:
        x = w[c]
        lines.append(f"| {c} | {x['populated_rows']:,} | {x['pct_of_all_rows']}% | {x['first_date']} | {x['last_date']} |")
    lines += [
        "",
        f"- `rsi_flag` values actually present: {stats['rsi_values']} — plus empty, which on a row that "
        "otherwise has weather values is read as 'no rain reported'. There is no 'Heavy Rain' value in this snapshot.",
        "- Consequence: the weather analysis (Phase 6) is restricted to rows where weather was recorded, "
        "and states its sample sizes and period. It must never be described as a full-year weather analysis.",
        "",
        "## Cleaned analysis dataset",
        f"- File: `data/processed/cleaned.csv` — **{stats['cleaned_hourly_rows']:,}** hourly observations, "
        f"{stats['cleaned_date_min']} to {stats['cleaned_date_max']}.",
    ]
    (OUTPUTS / "data_audit.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: stats[k] for k in ["total_rows_raw", "date_min", "date_max", "cleaned_hourly_rows",
                                            "rows_in_multi_reading_hours", "weather_span", "weather_days_with_temp"]}, indent=2))


if __name__ == "__main__":
    main()
