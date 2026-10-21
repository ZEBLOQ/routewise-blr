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

Date-aware spans (the *_span functions): goods-ready and deliver-by
are full datetimes, so a window can cross midnight — production
finishing Friday 20:00 for a Saturday 09:00 delivery is the ordinary
case, not an edge case. Every candidate departure is scored on **its
own date's** traffic pattern (weekday vs weekend comes from the
departure's calendar date), because scoring a Saturday 02:00 departure
with Friday-evening data would be quietly wrong. Windows are capped
at 72 hours.
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


# ---------------------------------------------------------------- date-aware spans
MAX_SPAN_HOURS = 72

_WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def day_type_for_date(d) -> str:
    """'weekday' for Mon–Fri, 'weekend' for Sat–Sun (accepts date/datetime)."""
    return "weekday" if pd.Timestamp(d).weekday() < 5 else "weekend"


def fmt_dt(dt) -> str:
    """Datetime -> 'Sat 08:00' (short weekday name + HH:MM, nearest minute —
    the same rounding fmt_clock applies to minutes-since-midnight)."""
    if dt is None or pd.isna(dt):
        return "—"
    ts = pd.Timestamp(dt).round("min")
    return f"{_WEEKDAY_SHORT[ts.weekday()]} {ts.hour:02d}:{ts.minute:02d}"


def _span_candidates(ready_dt, deadline_dt):
    """Hourly departure datetimes in [ready_dt, deadline_dt), hour-aligned.

    Returns (departures, deadline). Raises ValueError for an empty or
    over-long window so the app can show the message instead of a
    silently wrong table.
    """
    ready = pd.Timestamp(ready_dt).floor("h")
    deadline = pd.Timestamp(deadline_dt).floor("h")
    if deadline <= ready:
        raise ValueError("Deliver-by must be after goods-ready.")
    if deadline - ready > pd.Timedelta(hours=MAX_SPAN_HOURS):
        raise ValueError(
            f"Window is longer than {MAX_SPAN_HOURS} hours — narrow it: "
            "pick a goods-ready time and deadline closer together.")
    deps = []
    t = ready
    while t < deadline:
        deps.append(t)
        t += pd.Timedelta(hours=1)
    return deps, deadline


def arrival_table_measured_span(cleaned_df: pd.DataFrame, route_code: str,
                                ready_dt, deadline_dt) -> pd.DataFrame:
    """Per-departure arrival risk across a date-aware window (MEASURED).

    One row per candidate departure datetime. Each departure is scored
    on its own date's day type: durations come from the route's
    readings for (day_type_for_date(departure), departure.hour), and
    the budget is the full time left until the deadline.
    """
    deps, deadline = _span_candidates(ready_dt, deadline_dt)
    sub = cleaned_df[cleaned_df["route_code"] == route_code]
    rows = []
    for dep in deps:
        dtype = day_type_for_date(dep)
        budget = float((deadline - dep).total_seconds() / 60.0)
        vals = sub.loc[(sub["day_type"] == dtype) & (sub["hour"] == dep.hour),
                       "duration"]
        n = len(vals)
        median = float(vals.median()) if n else np.nan
        p90 = float(vals.quantile(0.90)) if n else np.nan
        rows.append({
            "departure_dt": dep,
            "day_type_used": dtype,
            "n": int(n),
            "travel_median": median,
            "travel_p90": p90,
            "budget_min": budget,
            "typical_arrival_dt": dep + pd.Timedelta(minutes=median) if n else pd.NaT,
            "p90_arrival_dt": dep + pd.Timedelta(minutes=p90) if n else pd.NaT,
            "on_time_prob": float((vals <= budget).mean()) if n else np.nan,
            "low_confidence": bool(n < MIN_READINGS),
        })
    return _normalise_dt_units(pd.DataFrame(rows))


def arrival_table_modelled_span(model: dict, distance_km: float, scenario: str,
                                ready_dt, deadline_dt) -> pd.DataFrame:
    """Per-departure arrival risk across a date-aware window (MODELLED).

    Same columns as arrival_table_measured_span. Predictions are cached
    per day type: a candidate uses the any-trip pattern for its own
    date's day type and its own hour.
    """
    deps, deadline = _span_candidates(ready_dt, deadline_dt)
    preds = {}
    rows = []
    for dep in deps:
        dtype = day_type_for_date(dep)
        if dtype not in preds:
            preds[dtype] = predict(model, distance_km, dtype, scenario).set_index("hour")
        budget = float((deadline - dep).total_seconds() / 60.0)
        median = float(preds[dtype].loc[dep.hour, "median_min"])
        p90 = float(preds[dtype].loc[dep.hour, "p90_min"])
        rows.append({
            "departure_dt": dep,
            "day_type_used": dtype,
            "n": np.nan,
            "travel_median": median,
            "travel_p90": p90,
            "budget_min": budget,
            "typical_arrival_dt": dep + pd.Timedelta(minutes=median),
            "p90_arrival_dt": dep + pd.Timedelta(minutes=p90),
            "on_time_prob": on_time_prob(model, median, budget),
            "low_confidence": False,
        })
    return _normalise_dt_units(pd.DataFrame(rows))


def _normalise_dt_units(table: pd.DataFrame) -> pd.DataFrame:
    """Force all datetime columns to one resolution (ns).

    Timedelta arithmetic on float minutes can yield a mix of us/ns
    columns depending on the values; consumers that melt the arrival
    columns together (the app's chart) require a single dtype.
    """
    for col in ("departure_dt", "typical_arrival_dt", "p90_arrival_dt"):
        if col in table.columns:
            table[col] = table[col].astype("datetime64[ns]")
    return table


def _latest_safe_departure_span(table: pd.DataFrame, threshold: float) -> dict:
    """latest_safe_departure for span tables (departure_dt columns)."""
    usable = table[table["on_time_prob"].notna()]
    confident = usable[~usable["low_confidence"]]
    pool = confident if not confident.empty else usable
    if pool.empty:
        return {"feasible": False, "departure_dt": None, "threshold": threshold,
                "best_departure_dt": None, "best_prob": None}
    meeting = pool[pool["on_time_prob"] >= threshold]
    if not meeting.empty:
        row = meeting.sort_values("departure_dt").iloc[-1]
        return {"feasible": True, "departure_dt": row["departure_dt"],
                "threshold": threshold,
                "on_time_prob": float(row["on_time_prob"]),
                "typical_arrival_dt": row["typical_arrival_dt"],
                "p90_arrival_dt": row["p90_arrival_dt"],
                "best_departure_dt": row["departure_dt"],
                "best_prob": float(row["on_time_prob"])}
    best = pool.sort_values(["on_time_prob", "departure_dt"],
                            ascending=[False, True]).iloc[0]
    return {"feasible": False, "departure_dt": None, "threshold": threshold,
            "on_time_prob": float(best["on_time_prob"]),
            "typical_arrival_dt": best["typical_arrival_dt"],
            "p90_arrival_dt": best["p90_arrival_dt"],
            "best_departure_dt": best["departure_dt"],
            "best_prob": float(best["on_time_prob"])}


def latest_safe_departure(table: pd.DataFrame,
                          threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Latest departure hour whose on-time probability meets the safety level.

    Low-confidence hours (too few readings) are excluded when any
    full-confidence hour exists, mirroring the planner's rule. If no
    hour meets the threshold, returns feasible=False plus the best
    available hour (highest on-time probability, tie-break earliest)
    and its probability — the caller must present that honestly as
    "not feasible safely", not as a recommendation.

    Span tables (with a departure_dt column, from the *_span table
    builders) get the same rule keyed on datetimes instead of hours;
    see _latest_safe_departure_span.
    """
    if "departure_dt" in table.columns:
        return _latest_safe_departure_span(table, threshold)
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
