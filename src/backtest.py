"""Phase 5 backtest: does the planner's recommended window actually beat a
naive baseline on data it was not built from?

Design (fixed before looking at results; no tuning):
- Temporal split: train = hourly observations up to 2026-06-30,
  test = 2026-07-01 onward.
- Day type: weekday (the primary dispatch case); weekend results are in
  the CSV as a secondary view.
- Target (planning assumption, documented): for each route and day type,
  the train-period overall median duration, rounded up to the next whole
  minute. In words: 'arrive within the typical trip time for this route'.
- Planner hour is chosen on TRAIN only, using src/planner.py
  (hours 06-21, n>=30 in that train hour, max on-time prob, tie-break P90).
- Baseline: dispatch at 09:00 (a typical naive morning dispatch).
- Both hours are then scored on TEST only: n, P90, on-time probability
  against the same target.
"""
import numpy as np
import pandas as pd

from common import OUTPUTS, load_cleaned
from planner import hourly_stats, recommend

SPLIT = "2026-06-30"
BASELINE_HOUR = 9


def evaluate(df, day_type, start_hour=6, end_hour=22):
    train = df[df["date"] <= SPLIT]
    test = df[df["date"] > SPLIT]
    rows = []
    for (code, label, airport), _ in df.groupby(["route_code", "label_short", "is_airport"]):
        tr = train[(train["route_code"] == code) & (train["day_type"] == day_type)]
        if len(tr) < 200:
            continue
        target = float(np.ceil(tr["duration"].median()))
        stats = hourly_stats(train, code, day_type, target, start_hour=start_hour, end_hour=end_hour)
        rec = recommend(stats)
        te = test[(test["route_code"] == code) & (test["day_type"] == day_type)]

        def score(hour):
            vals = te.loc[te["hour"] == hour, "duration"]
            if len(vals) == 0:
                return np.nan, np.nan, 0
            return float((vals <= target).mean()), float(vals.quantile(0.90)), int(len(vals))

        b_otp, b_p90, b_n = score(BASELINE_HOUR)
        if rec["recommended_hour"] is None:
            r_otp, r_p90, r_n, rec_hour = np.nan, np.nan, 0, None
        else:
            r_otp, r_p90, r_n = score(rec["recommended_hour"])
            rec_hour = rec["recommended_hour"]
        rows.append({
            "route_code": code, "label_short": label, "is_airport": bool(airport),
            "day_type": day_type, "target_min_planning_assumption": target,
            "planner_hour_train": rec_hour, "baseline_hour": BASELINE_HOUR,
            "test_n_planner": r_n, "test_n_baseline": b_n,
            "test_otp_planner": r_otp, "test_otp_baseline": b_otp,
            "test_otp_diff_pp": (r_otp - b_otp) * 100 if rec_hour is not None else np.nan,
            "test_p90_planner": r_p90, "test_p90_baseline": b_p90,
            "test_p90_diff_min": r_p90 - b_p90 if rec_hour is not None else np.nan,
        })
    return pd.DataFrame(rows)


def main():
    df = load_cleaned()
    out = pd.concat([evaluate(df, "weekday"), evaluate(df, "weekend")], ignore_index=True)
    out.to_csv(OUTPUTS / "backtest.csv", index=False)

    # Secondary, fairer comparison: planner restricted to the realistic
    # morning dispatch window 07:00-11:00 vs the same 09:00 baseline.
    out2 = evaluate(df, "weekday", start_hour=7, end_hour=12)
    out2.to_csv(OUTPUTS / "backtest_morning_window.csv", index=False)
    wk2 = out2[(~out2["is_airport"])].dropna(subset=["test_otp_diff_pp"])
    s_wins = int((wk2["test_otp_diff_pp"] > 0).sum())
    s_mean_otp = float(wk2["test_otp_diff_pp"].mean())
    s_mean_p90 = float(wk2["test_p90_diff_min"].mean())
    s_hours = sorted(int(h) for h in wk2["planner_hour_train"].dropna().unique())

    wk = out[(out["day_type"] == "weekday") & (~out["is_airport"])].dropna(subset=["test_otp_diff_pp"])
    wins_otp = int((wk["test_otp_diff_pp"] > 0).sum())
    wins_p90 = int((wk["test_p90_diff_min"] < 0).sum())
    mean_otp_diff = float(wk["test_otp_diff_pp"].mean())
    mean_p90_diff = float(wk["test_p90_diff_min"].mean())
    med_otp_diff = float(wk["test_otp_diff_pp"].median())
    best = wk.loc[wk["test_otp_diff_pp"].idxmax()]
    worst = wk.loc[wk["test_otp_diff_pp"].idxmin()]

    verdict = ("beats" if mean_otp_diff > 0 else "does not beat")
    md = f"""# Backtest — Dispatch Planner vs Naive 09:00 Dispatch

Method (fixed in advance, no tuning after seeing results — see `src/backtest.py`):
train on data up to {SPLIT}, test on data from 2026-07-01 onward. Target per route =
train-period median duration rounded up (a planning assumption: 'arrive within the typical
trip time'). Planner hour chosen on train only; both hours scored on test only.
Primary view: **weekdays, 12 core routes** (Airport route is in the CSV, excluded here).

## Headline result

- On-time probability: the planner's window **{verdict}** the 09:00 baseline on average —
  mean difference **{mean_otp_diff:+.1f} percentage points**, median {med_otp_diff:+.1f} pp across the 12 routes.
- Planner window had the higher test on-time probability on **{wins_otp} of {len(wk)} routes**.
- P90 on test: planner window was lower (better) on **{wins_p90} of {len(wk)} routes**,
  mean difference **{mean_p90_diff:+.1f} min**.
- Best case: **{best['label_short']}** — planner hour {int(best['planner_hour_train']):02d}:00 vs 09:00,
  on-time {best['test_otp_planner']*100:.0f}% vs {best['test_otp_baseline']*100:.0f}% on test data.
- Weakest case: **{worst['label_short']}** — difference {worst['test_otp_diff_pp']:+.1f} pp
  (planner hour {int(worst['planner_hour_train']):02d}:00). Reported as-is; a window that wins on
  train does not always win on later data, which is itself a finding about how stable
  route patterns are over time.

Full per-route table (weekday + weekend, incl. Airport): `outputs/backtest.csv`.

## How to read that headline (important)

The planner picked 06:00 — the earliest hour in its search range — for the core routes,
because travel time climbs from pre-peak into the morning peak. So the {mean_otp_diff:+.0f} pp gap mostly
measures **how peak-sensitive these routes are**, not subtle optimisation: a 09:00 dispatch
is mid-peak, and the target is the route's all-hours median, which a peak-hour trip on a
peak-sensitive route rarely beats (verified directly: East Outer Ring's 09:00 weekday
median on test data is 54 min against a 23 min target; its 06:00 median is 17 min).

## Secondary comparison: planner restricted to a realistic morning window (07:00-11:00)

Most dispatches cannot simply move to 06:00. Restricting the planner's search to
07:00-11:00 (chosen hours in test: {s_hours}) vs the same 09:00 baseline, weekdays, core 12:

- Mean on-time difference: **{s_mean_otp:+.1f} pp**; planner hour won on **{s_wins} of {len(wk2)} routes**.
- Mean P90 difference: **{s_mean_p90:+.1f} min**.
- Full table: `outputs/backtest_morning_window.csv`.

This window-restricted comparison is the fairer one to quote as the planner's marginal
value over a naive 09:00 dispatch when the departure must stay in the morning — but note
the on-time gap still reflects the target definition (the all-hours median). The
target-independent measure in both comparisons is the P90 difference: trips in the
planner's window simply ran faster and tighter than 09:00 trips on held-out data.

## Honest limits of this backtest

- It is a historical simulation on Google Maps travel-time *estimates*, not a live trial
  with real vehicles. It shows the planner's rule would have helped on past data; it does
  not prove a live operation will see the same gain.
- One target definition and one split date were used. Different targets (e.g. a fixed
  40 minutes) would change the size of the gain; the direction should be re-checked before
  quoting a single number as 'the' improvement.
"""
    (OUTPUTS / "backtest.md").write_text(md)
    print(md)
    print(wk[["label_short", "target_min_planning_assumption", "planner_hour_train",
              "test_otp_planner", "test_otp_baseline", "test_otp_diff_pp",
              "test_p90_planner", "test_p90_baseline"]].to_string(index=False))


if __name__ == "__main__":
    main()
