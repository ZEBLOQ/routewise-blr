# Backtest — Dispatch Planner vs Naive 09:00 Dispatch

Method (fixed in advance, no tuning after seeing results — see `src/backtest.py`):
train on data up to 2026-06-30, test on data from 2026-07-01 onward. Target per route =
train-period median duration rounded up (a planning assumption: 'arrive within the typical
trip time'). Planner hour chosen on train only; both hours scored on test only.
Primary view: **weekdays, 12 core routes** (Airport route is in the CSV, excluded here).

## Headline result

- On-time probability: the planner's window **beats** the 09:00 baseline on average —
  mean difference **+92.2 percentage points**, median +94.4 pp across the 12 routes.
- Planner window had the higher test on-time probability on **12 of 12 routes**.
- P90 on test: planner window was lower (better) on **12 of 12 routes**,
  mean difference **-24.5 min**.
- Best case: **Double Decker Flyover** — planner hour 06:00 vs 09:00,
  on-time 100% vs 4% on test data.
- Weakest case: **South Outer Ring** — difference +71.2 pp
  (planner hour 06:00). Reported as-is; a window that wins on
  train does not always win on later data, which is itself a finding about how stable
  route patterns are over time.

Full per-route table (weekday + weekend, incl. Airport): `outputs/backtest.csv`.

## How to read that headline (important)

The planner picked 06:00 — the earliest hour in its search range — for the core routes,
because travel time climbs from pre-peak into the morning peak. So the +92 pp gap mostly
measures **how peak-sensitive these routes are**, not subtle optimisation: a 09:00 dispatch
is mid-peak, and the target is the route's all-hours median, which a peak-hour trip on a
peak-sensitive route rarely beats (verified directly: East Outer Ring's 09:00 weekday
median on test data is 54 min against a 23 min target; its 06:00 median is 17 min).

## Secondary comparison: planner restricted to a realistic morning window (07:00-11:00)

Most dispatches cannot simply move to 06:00. Restricting the planner's search to
07:00-11:00 (chosen hours in test: [7]) vs the same 09:00 baseline, weekdays, core 12:

- Mean on-time difference: **+81.4 pp**; planner hour won on **12 of 12 routes**.
- Mean P90 difference: **-19.0 min**.
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
