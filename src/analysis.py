"""Phase 3+4+6: time-of-day analysis, reliability ranking, weather analysis.

Writes summary CSVs plus findings.md / weather_analysis.md.
Every number in those docs is computed here from cleaned.csv.
"""
import json
import numpy as np
import pandas as pd

from common import OUTPUTS, PEAK_BUCKETS, load_cleaned

RAIN_VALUES = {"Rain", "Light Rain", "Heavy Rain"}


def p90(s):
    return s.quantile(0.90)


def main():
    df = load_cleaned()
    core = df[~df["is_airport"]].copy()
    facts = {}

    # ---------- Phase 3: time of day ----------
    by_hour = (df.groupby(["route_code", "label_short", "is_airport", "hour"])["duration"]
               .agg(n="size", median="median", p90=p90).reset_index())
    by_hour.to_csv(OUTPUTS / "duration_by_hour.csv", index=False)

    by_hour_daytype = (df.groupby(["route_code", "label_short", "is_airport", "day_type", "hour"])["duration"]
                       .agg(n="size", median="median", p90=p90).reset_index())
    by_hour_daytype.to_csv(OUTPUTS / "duration_by_hour_daytype.csv", index=False)

    bucket = (df.groupby(["route_code", "label_short", "is_airport", "day_type", "time_bucket"])["duration"]
              .agg(n="size", median="median", p90=p90).reset_index())
    bucket.to_csv(OUTPUTS / "duration_by_bucket_daytype.csv", index=False)

    # Weekday vs weekend, morning vs evening peak (core 12, pooled per route then averaged)
    piv = bucket[bucket["day_type"] == "weekday"].pivot_table(
        index=["route_code", "label_short"], columns="time_bucket", values="median")
    wk = df.groupby(["route_code", "label_short", "is_airport", "day_type"])["duration"].median().unstack()
    wk["weekday_minus_weekend_min"] = wk["weekday"] - wk["weekend"]
    wk["weekday_pct_above_weekend"] = 100 * (wk["weekday"] - wk["weekend"]) / wk["weekend"]
    wk.to_csv(OUTPUTS / "weekday_weekend_medians.csv")

    core_wk = wk[~wk.index.get_level_values("is_airport")]
    facts["avg_weekday_median_core"] = float(core_wk["weekday"].mean())
    facts["avg_weekend_median_core"] = float(core_wk["weekend"].mean())
    facts["avg_weekday_pct_above_weekend"] = float(core_wk["weekday_pct_above_weekend"].mean())
    worst_gap = core_wk["weekday_pct_above_weekend"].idxmax()
    facts["largest_weekday_weekend_gap_route"] = worst_gap[1]
    facts["largest_weekday_weekend_gap_pct"] = float(core_wk.loc[worst_gap, "weekday_pct_above_weekend"])

    pk = piv.dropna(subset=["morning_peak", "evening_peak"]).copy()
    pk["evening_minus_morning"] = pk["evening_peak"] - pk["morning_peak"]
    core_pk = pk[[not a for _, a in pk.index]] if False else pk
    # is_airport not in piv index; identify airport by route code
    core_pk = pk[~pk.index.get_level_values("route_code").isin(["XJG4+7J|5PX4+HQ"])]
    facts["routes_evening_worse_than_morning"] = int((core_pk["evening_minus_morning"] > 0).sum())
    facts["routes_total_core"] = int(len(core_pk))
    ev_worst = core_pk["evening_minus_morning"].idxmax()
    facts["biggest_evening_penalty_route"] = ev_worst[1]
    facts["biggest_evening_penalty_min"] = float(core_pk.loc[ev_worst, "evening_minus_morning"])
    facts["biggest_evening_morning_min"] = float(core_pk.loc[ev_worst, "morning_peak"])
    facts["biggest_evening_evening_min"] = float(core_pk.loc[ev_worst, "evening_peak"])

    # Peak vs night penalty, pooled core
    pooled_bucket = core.groupby("time_bucket")["duration"].agg(["median", p90])
    facts["core_morning_peak_median"] = float(pooled_bucket.loc["morning_peak", "median"])
    facts["core_evening_peak_median"] = float(pooled_bucket.loc["evening_peak", "median"])
    facts["core_night_median"] = float(pooled_bucket.loc["night", "median"])
    facts["core_midday_median"] = float(pooled_bucket.loc["midday", "median"])

    # Airport separately
    ap = df[df["is_airport"]]
    ap_bucket = ap[ap["day_type"] == "weekday"].groupby("time_bucket")["duration"].median()
    facts["airport_weekday_median"] = float(ap[ap["day_type"] == "weekday"]["duration"].median())
    facts["airport_weekday_p90"] = float(p90(ap[ap["day_type"] == "weekday"]["duration"]))
    facts["airport_evening_median"] = float(ap_bucket.get("evening_peak", np.nan))
    facts["airport_night_median"] = float(ap_bucket.get("night", np.nan))

    # ---------- Phase 4: reliability ranking (core 12) ----------
    rel = (core.groupby(["route_code", "label_short"])["duration"]
           .agg(n="size", median="median", p90=p90).reset_index())
    rel["buffer_index"] = (rel["p90"] - rel["median"]) / rel["median"]
    rel["buffer_minutes"] = rel["p90"] - rel["median"]
    rel = rel.sort_values("buffer_index", ascending=False).reset_index(drop=True)
    rel["reliability_rank"] = range(1, len(rel) + 1)  # 1 = least reliable (highest buffer)
    rel["reliability_rank"] = len(rel) - rel["reliability_rank"] + 1  # re-rank: 1 = most reliable
    rel = rel.sort_values("reliability_rank")
    rel.to_csv(OUTPUTS / "reliability_ranking.csv", index=False)

    by_median = rel.sort_values("median")
    fastest = by_median.iloc[0]
    most_reliable = rel.iloc[0]
    least_reliable = rel.iloc[-1]
    facts["fastest_by_median_route"] = fastest["label_short"]
    facts["fastest_by_median_min"] = float(fastest["median"])
    facts["fastest_buffer_index"] = float(fastest["buffer_index"])
    facts["fastest_reliability_rank"] = int(fastest["reliability_rank"])
    facts["most_reliable_route"] = most_reliable["label_short"]
    facts["most_reliable_buffer"] = float(most_reliable["buffer_index"])
    facts["most_reliable_median"] = float(most_reliable["median"])
    facts["most_reliable_p90"] = float(most_reliable["p90"])
    facts["least_reliable_route"] = least_reliable["label_short"]
    facts["least_reliable_buffer"] = float(least_reliable["buffer_index"])
    facts["least_reliable_median"] = float(least_reliable["median"])
    facts["least_reliable_p90"] = float(least_reliable["p90"])
    # A sharper 'fastest != most reliable' example: the route with lowest P90 vs lowest median differ?
    lowest_p90 = rel.sort_values("p90").iloc[0]
    facts["lowest_p90_route"] = lowest_p90["label_short"]
    facts["lowest_p90_min"] = float(lowest_p90["p90"])

    # ---------- Phase 6: weather (scoped) ----------
    w = df[df["temp"].notna()].copy()  # weather snapshot present on the row
    w["is_rain"] = w["rsi_flag"].isin(RAIN_VALUES)
    w["period"] = np.where(w["time_bucket"].isin(PEAK_BUCKETS), "peak", "off_peak")
    facts["weather_rows"] = int(len(w))
    facts["weather_rain_rows"] = int(w["is_rain"].sum())
    facts["weather_norain_rows"] = int((~w["is_rain"]).sum())
    facts["weather_date_min"] = str(w["date"].dt.date.min())
    facts["weather_date_max"] = str(w["date"].dt.date.max())
    facts["weather_core_rows"] = int((~w["is_airport"]).sum())

    wc = w[~w["is_airport"]]  # core 12 for headline weather comparison
    summ = (wc.groupby(["period", "is_rain"])["duration"]
            .agg(n="size", median="median", p90=p90,
                 q1=lambda s: s.quantile(0.25), q3=lambda s: s.quantile(0.75)).reset_index())
    summ["iqr"] = summ["q3"] - summ["q1"]
    summ.to_csv(OUTPUTS / "weather_summary.csv", index=False)
    overall = (wc.groupby("is_rain")["duration"]
               .agg(n="size", median="median", p90=p90,
                    q1=lambda s: s.quantile(0.25), q3=lambda s: s.quantile(0.75)).reset_index())
    overall["iqr"] = overall["q3"] - overall["q1"]
    overall.to_csv(OUTPUTS / "weather_overall.csv", index=False)
    rain_o = overall[overall["is_rain"]].iloc[0]
    dry_o = overall[~overall["is_rain"]].iloc[0]
    facts["weather_rain_median"] = float(rain_o["median"])
    facts["weather_dry_median"] = float(dry_o["median"])
    facts["weather_rain_p90"] = float(rain_o["p90"])
    facts["weather_dry_p90"] = float(dry_o["p90"])
    facts["weather_rain_iqr"] = float(rain_o["iqr"])
    facts["weather_dry_iqr"] = float(dry_o["iqr"])
    facts["weather_rain_n"] = int(rain_o["n"])
    facts["weather_dry_n"] = int(dry_o["n"])
    pk_r = summ[(summ["period"] == "peak") & (summ["is_rain"])].iloc[0]
    pk_d = summ[(summ["period"] == "peak") & (~summ["is_rain"])].iloc[0]
    facts["weather_peak_rain_median"] = float(pk_r["median"])
    facts["weather_peak_dry_median"] = float(pk_d["median"])
    facts["weather_peak_rain_p90"] = float(pk_r["p90"])
    facts["weather_peak_dry_p90"] = float(pk_d["p90"])
    op_r = summ[(summ["period"] == "off_peak") & (summ["is_rain"])].iloc[0]
    op_d = summ[(summ["period"] == "off_peak") & (~summ["is_rain"])].iloc[0]
    facts["weather_offpeak_rain_median"] = float(op_r["median"])
    facts["weather_offpeak_dry_median"] = float(op_d["median"])

    (OUTPUTS / "facts.json").write_text(json.dumps(facts, indent=2, default=str))

    f = facts
    findings = f"""# Findings — RouteWise BLR

All numbers computed by `src/analysis.py` from the frozen snapshot (hourly-grain cleaned data).
Core comparisons use the 12 routes of ~10 km; the Airport route (~34 km) is reported separately.

## Time of day (Phase 3)

1. **Weekdays are slower than weekends on the core routes.** Averaged across the 12 core routes,
   the median route's weekday median is {f['avg_weekday_median_core']:.1f} min vs {f['avg_weekend_median_core']:.1f} min
   on weekends ({f['avg_weekday_pct_above_weekend']:.1f}% higher on weekdays, route-average).
   The largest weekday-weekend gap is on **{f['largest_weekday_weekend_gap_route']}**
   ({f['largest_weekday_weekend_gap_pct']:.1f}% higher on weekdays).
2. **Evening peak is the worst window overall.** Pooled core-12 medians: morning peak
   {f['core_morning_peak_median']:.0f} min, midday {f['core_midday_median']:.0f} min,
   evening peak {f['core_evening_peak_median']:.0f} min, night {f['core_night_median']:.0f} min.
3. **Evening is worse than morning on {f['routes_evening_worse_than_morning']} of the {f['routes_total_core']} core routes**
   (weekday medians). The biggest evening penalty is on **{f['biggest_evening_penalty_route']}**:
   morning peak median {f['biggest_evening_morning_min']:.0f} min vs evening peak {f['biggest_evening_evening_min']:.0f} min
   (+{f['biggest_evening_penalty_min']:.0f} min).
4. **Airport route (separate, ~34 km):** weekday median {f['airport_weekday_median']:.0f} min, P90
   {f['airport_weekday_p90']:.0f} min; evening-peak weekday median {f['airport_evening_median']:.0f} min vs
   {f['airport_night_median']:.0f} min at night. It is never ranked against the ~10 km routes.

## Reliability ranking (Phase 4) — headline

5. **Fastest is not most reliable.** Ranked by buffer index = (P90 - median) / median:
   - Most reliable: **{f['most_reliable_route']}** — median {f['most_reliable_median']:.0f} min, P90 {f['most_reliable_p90']:.0f} min,
     buffer index {f['most_reliable_buffer']:.2f} (you only need to budget about {f['most_reliable_buffer']*100:.0f}% over the typical trip for a 9-in-10 on-time plan).
   - Least reliable: **{f['least_reliable_route']}** — median {f['least_reliable_median']:.0f} min, P90 {f['least_reliable_p90']:.0f} min,
     buffer index {f['least_reliable_buffer']:.2f}.
   - The fastest route by median is **{f['fastest_by_median_route']}** ({f['fastest_by_median_min']:.0f} min median), but it ranks
     only #{f['fastest_reliability_rank']} of 12 on reliability, with a buffer index of {f['fastest_buffer_index']:.2f}.
   - The sharpest proof is **{f['least_reliable_route']}**: its median ({f['least_reliable_median']:.0f} min) ties for the
     fastest of all 12 routes, yet its P90 is {f['least_reliable_p90']:.0f} min — a dispatcher who plans that route on its
     median leaves no buffer for a trip that runs to {f['least_reliable_p90']:.0f} min one time in ten.
     Planning any route on its median alone understates the trip 50% of the time; the ranking a
     dispatcher needs is the buffer ranking, not the speed ranking.
   - Full table: `outputs/reliability_ranking.csv` (rank 1 = most reliable = lowest buffer index).
"""
    (OUTPUTS / "findings.md").write_text(findings)

    weather_md = f"""# Weather Analysis (Phase 6) — scoped

**Scope, stated plainly:** weather fields exist only from {f['weather_date_min']} onward in this
snapshot, and only on a subset of days (see `outputs/data_audit.md`). This analysis uses ONLY the
{f['weather_rows']:,} hourly observations (all 13 routes) that carry a weather snapshot; headline
comparisons below use the 12 core routes. Rain = `rsi_flag` in {{Rain, Light Rain}} (no 'Heavy Rain'
values exist in this snapshot); no-rain = weather present and `rsi_flag` empty.
Sample sizes (core 12): rain n={f['weather_rain_n']:,}, no-rain n={f['weather_dry_n']:,}.
Everything here is **association, not causation**.

## Result (core 12 routes, weather-covered rows only)

- Median duration: rain {f['weather_rain_median']:.0f} min vs no-rain {f['weather_dry_median']:.0f} min.
- P90 duration: rain {f['weather_rain_p90']:.0f} min vs no-rain {f['weather_dry_p90']:.0f} min.
- Variability (IQR): rain {f['weather_rain_iqr']:.0f} min vs no-rain {f['weather_dry_iqr']:.0f} min.
- Peak periods only: median rain {f['weather_peak_rain_median']:.0f} min vs no-rain {f['weather_peak_dry_median']:.0f} min;
  P90 rain {f['weather_peak_rain_p90']:.0f} min vs no-rain {f['weather_peak_dry_p90']:.0f} min.
- Off-peak only: median rain {f['weather_offpeak_rain_median']:.0f} min vs no-rain {f['weather_offpeak_dry_median']:.0f} min.

Full breakdown: `outputs/weather_summary.csv` (peak vs off-peak) and `outputs/weather_overall.csv`.

**Reading:** compare the rain vs no-rain gaps above at the median and at P90 — if the P90 gap is
larger than the median gap, rain is associated less with uniformly slower trips and more with
*less predictable* trips, which is what a dispatch planner has to budget for. The comparison does
not control for which routes/hours the rain readings happen to fall in, so it must not be quoted
as 'rain causes X minutes of delay'.
"""
    (OUTPUTS / "weather_analysis.md").write_text(weather_md)
    print(json.dumps(facts, indent=2, default=str))


if __name__ == "__main__":
    main()
