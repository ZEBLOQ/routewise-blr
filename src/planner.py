"""Phase 5 (core): the dispatch-window planner.

This is RouteWise BLR's original contribution. The source project
(traffiCOracle / Traffic Monitor Lizard) visualises and ranks traffic;
it does not recommend a departure window against a user-set journey-time
target. This module does exactly that.

Method (stated openly, no hidden tuning):
- For a chosen route and day type, group historical hourly observations
  by departure hour.
- For each hour compute: n, median (P50), P90, and on-time probability =
  share of observations with duration <= target.
- The target is a planning assumption set by the user. It is NOT an
  observed business requirement or SLA.
- Hours with n < MIN_READINGS are flagged low-confidence and excluded
  from the recommendation.
- Recommendation = highest on-time probability; tie-break = lowest P90,
  then lowest median.
"""
import numpy as np
import pandas as pd

MIN_READINGS = 30


def hourly_stats(df: pd.DataFrame, route_code: str, day_type: str,
                 target_minutes: float, start_hour: int = 6, end_hour: int = 22) -> pd.DataFrame:
    """Per-departure-hour stats for hours in [start_hour, end_hour).

    end_hour is exclusive in clock terms: default 06:00-22:00 means
    departure hours 06 through 21.
    """
    sub = df[(df["route_code"] == route_code) & (df["day_type"] == day_type)]
    rows = []
    for hour in range(start_hour, end_hour):
        vals = sub.loc[sub["hour"] == hour, "duration"]
        n = len(vals)
        rows.append({
            "departure_hour": hour,
            "n": int(n),
            "median_min": float(vals.median()) if n else np.nan,
            "p90_min": float(vals.quantile(0.90)) if n else np.nan,
            "on_time_prob": float((vals <= target_minutes).mean()) if n else np.nan,
            "low_confidence": bool(n < MIN_READINGS),
        })
    return pd.DataFrame(rows)


def recommend(stats: pd.DataFrame) -> dict:
    """Pick the recommended departure hour from hourly_stats output."""
    eligible = stats[(~stats["low_confidence"]) & (stats["n"] > 0)]
    if eligible.empty:
        return {"recommended_hour": None,
                "reason": f"No departure hour in range has at least {MIN_READINGS} readings."}
    ranked = eligible.sort_values(
        ["on_time_prob", "p90_min", "median_min", "departure_hour"],
        ascending=[False, True, True, True],
    )
    best = ranked.iloc[0]
    return {
        "recommended_hour": int(best["departure_hour"]),
        "n": int(best["n"]),
        "median_min": float(best["median_min"]),
        "p90_min": float(best["p90_min"]),
        "on_time_prob": float(best["on_time_prob"]),
        "reason": "Highest on-time probability among hours with n>=%d; tie-break lowest P90." % MIN_READINGS,
    }
