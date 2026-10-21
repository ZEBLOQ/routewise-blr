"""Deliver-by planner: plan BACKWARD from a delivery deadline.

The dispatch planner (src/planner.py) thinks forward: "if I leave at
hour X, will the trip fit inside a duration target?" Real dispatchers
usually face the opposite question — the one production planning calls
**backward scheduling**: the customer's deadline is fixed, the goods
become ready at a known time, so *what is the latest I can leave and
still arrive on time?*

Method (stated openly, no hidden tuning):
- For each candidate departure hour h from the goods-ready hour up to
  (but not including) the deadline hour, the travel-time budget is
  deadline - h. Everything else is a probability against that budget:
  - measured mode: on-time probability = share of that hour's actual
    readings on the route (same day type) with duration <= budget.
  - modelled mode: predicted per-hour medians from the any-trip layer
    (src/anytrip.py) and its pooled-ratio on-time probability against
    the same budget.
- The headline answer is the **latest** departure hour whose on-time
  probability still meets the safety level (default >= 95%).
  Recommending the latest safe departure — not the earliest — is the
  point: leaving hours earlier than necessary ties up a vehicle and a
  driver that could be doing other work.
- If no departure hour meets the safety level, this module says so
  (feasible = False) and returns the best available hour and its real
  probability, so the app can be honest instead of reassuring: the
  goods are not ready earlier, so the realistic options are dispatching
  the previous day, renegotiating the deadline, or accepting the risk
  knowingly.
- Granularity is one hour, because the dataset is hourly.
- Measured hours with fewer than MIN_READINGS readings (same rule as
  the planner) are flagged low-confidence and excluded from the
  latest-safe pick; they are still shown in the table.
"""
import numpy as np
import pandas as pd

from anytrip import on_time_prob, predict
from planner import MIN_READINGS

DEFAULT_THRESHOLD = 0.95


def fmt_clock(minutes: float) -> str:
    """Minutes since midnight -> 'H:MM' clock string (may exceed 23:59)."""
    if minutes is None or pd.isna(minutes):
        return "—"
    m = int(round(float(minutes)))
    return f"{m // 60}:{m % 60:02d}"


def _check_window(ready_hour: int, deadline_hour: int) -> None:
    if not (0 <= ready_hour <= 23 and 1 <= deadline_hour <= 23):
        raise ValueError("ready_hour must be 0-23 and deadline_hour 1-23.")
    if deadline_hour <= ready_hour:
        raise ValueError("deadline_hour must be after ready_hour.")


def arrival_table_measured(cleaned_df: pd.DataFrame, route_code: str, day_type: str,
                           ready_hour: int, deadline_hour: int) -> pd.DataFrame:
    """Per-departure-hour arrival risk from the route's own readings (MEASURED).

    One row per departure hour h in [ready_hour, deadline_hour):
    budget_min = deadline - h (minutes); typical arrival = h + median
    travel time; P90 arrival = h + P90 travel time; on_time_prob =
    share of that hour's actual durations (same day type) <= budget.
    """
    _check_window(ready_hour, deadline_hour)
    sub = cleaned_df[(cleaned_df["route_code"] == route_code)
                     & (cleaned_df["day_type"] == day_type)]
    rows = []
    for h in range(ready_hour, deadline_hour):
        budget = float(deadline_hour * 60 - h * 60)
        vals = sub.loc[sub["hour"] == h, "duration"]
        n = len(vals)
        median = float(vals.median()) if n else np.nan
        p90 = float(vals.quantile(0.90)) if n else np.nan
        rows.append({
            "departure_hour": h,
            "n": int(n),
            "travel_median": median,
            "travel_p90": p90,
            "budget_min": budget,
            "typical_arrival": h * 60 + median if n else np.nan,
            "p90_arrival": h * 60 + p90 if n else np.nan,
            "on_time_prob": float((vals <= budget).mean()) if n else np.nan,
            "low_confidence": bool(n < MIN_READINGS),
        })
    return pd.DataFrame(rows)


def arrival_table_modelled(model: dict, distance_km: float, day_type: str,
                           scenario: str, ready_hour: int,
                           deadline_hour: int) -> pd.DataFrame:
    """Per-departure-hour arrival risk from the any-trip model (MODELLED).

    Same columns as arrival_table_measured; n is NaN (a modelled hour
    has no readings) and low_confidence is False (confidence is carried
    by the layer's validated error, not by a per-hour count).
    """
    _check_window(ready_hour, deadline_hour)
    pred = predict(model, distance_km, day_type, scenario).set_index("hour")
    rows = []
    for h in range(ready_hour, deadline_hour):
        budget = float(deadline_hour * 60 - h * 60)
        median = float(pred.loc[h, "median_min"])
        p90 = float(pred.loc[h, "p90_min"])
        rows.append({
            "departure_hour": h,
            "n": np.nan,
            "travel_median": median,
            "travel_p90": p90,
            "budget_min": budget,
            "typical_arrival": h * 60 + median,
            "p90_arrival": h * 60 + p90,
            "on_time_prob": on_time_prob(model, median, budget),
            "low_confidence": False,
        })
    return pd.DataFrame(rows)


def latest_safe_departure(table: pd.DataFrame,
                          threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Latest departure hour whose on-time probability meets the safety level.

    Low-confidence hours (too few readings) are excluded when any
    full-confidence hour exists, mirroring the planner's rule. If no
    hour meets the threshold, returns feasible=False plus the best
    available hour (highest on-time probability, tie-break earliest)
    and its probability — the caller must present that honestly as
    "not feasible safely", not as a recommendation.
    """
    usable = table[table["on_time_prob"].notna()]
    confident = usable[~usable["low_confidence"]]
    pool = confident if not confident.empty else usable
    if pool.empty:
        return {"feasible": False, "hour": None, "threshold": threshold,
                "best_hour": None, "best_prob": None}
    meeting = pool[pool["on_time_prob"] >= threshold]
    if not meeting.empty:
        row = meeting.sort_values("departure_hour").iloc[-1]
        return {"feasible": True, "hour": int(row["departure_hour"]),
                "threshold": threshold,
                "on_time_prob": float(row["on_time_prob"]),
                "typical_arrival": float(row["typical_arrival"]),
                "p90_arrival": float(row["p90_arrival"]),
                "best_hour": int(row["departure_hour"]),
                "best_prob": float(row["on_time_prob"])}
    best = pool.sort_values(["on_time_prob", "departure_hour"],
                            ascending=[False, True]).iloc[0]
    return {"feasible": False, "hour": None, "threshold": threshold,
            "on_time_prob": float(best["on_time_prob"]),
            "typical_arrival": float(best["typical_arrival"]),
            "p90_arrival": float(best["p90_arrival"]),
            "best_hour": int(best["departure_hour"]),
            "best_prob": float(best["on_time_prob"])}
