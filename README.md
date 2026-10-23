# RouteWise BLR — Urban Logistics Decision Support System

**Time-Dependent Route Reliability and Dispatch Planning for Urban Logistics in Bengaluru**

RouteWise BLR answers one question for a delivery or service operation:
*for this route, when should we dispatch so the trip is reliably on time?*
It is a decision-support system, not a traffic dashboard. Its original
contribution is the **dispatch-window planner**: pick a route, a day type and a
journey-time target (a planning assumption you set), and it recommends the
departure hour with the highest on-time probability in the historical data,
with low-confidence hours excluded.

Built on real data: 111,637 travel-time readings over 13 Bengaluru routes,
2025-09-25 to 2026-10-21, frozen on 2026-10-21 (`data/raw/SNAPSHOT.md`).

## Key findings (all verified — see `outputs/validation.md`, 11/11 checks pass)

- **Fastest ≠ most reliable.** East Outer Ring (Benniganahalli → Embassy TechVillage)
  ties for the fastest median (21 min) of the 12 core routes but is the *least*
  reliable: P90 40 min, buffer index 0.90. Most reliable is South Outer Ring
  (median 33, P90 40, buffer index 0.21). Ranking: `outputs/reliability_ranking.csv`.
- **Evening peak is the worst window** (pooled core median 35 min vs 30 morning
  peak, 19 at night); evening is worse than morning on 9 of 12 routes.
- **Planner backtest** (train ≤ 2026-06-30, test from 2026-07-01, target = each
  route's train median): the planner's window beat a naive 09:00 dispatch on
  on-time probability on all 12 core routes; the target-independent result is a
  mean P90 advantage of 24.5 min (19.0 min when the planner is restricted to a
  realistic 07:00–11:00 window). Read `outputs/backtest.md` for the honest
  reading of these numbers — the on-time gap partly reflects that 09:00 is
  mid-peak and the target is the all-hours median.
- **Weather (scoped):** on rows where weather was actually recorded (only from
  2026-05-24, with a 2026-07-29 → 2026-10-09 gap), rain was *associated* with
  slower trips on the core routes — median 30 vs 26 min, P90 45 vs 41 min
  (rain n=1,628 hourly obs.). Association, not causation.

## Run the app

```bash
cd ~/workspace/major-project/routewise-blr
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # first time only
.venv/bin/streamlit run app.py
```

Six views: (1) **Plan Any Trip** (modelled — see below), (2) Reliability Ranking,
(3) Route Explorer, (4) Dispatch Planner, (5) **Deliver-by Planner**,
(6) Weather Impact. Views 2–4 and 6 are MEASURED: every number comes from actual
readings on the 13 dataset routes. The Deliver-by Planner works backward from a
delivery deadline (goods-ready time + deliver-by time → latest safe departure at
≥95% on-time, with an honest "not feasible safely" state) and runs in measured
mode on the 13 routes or in modelled mode on any trip. It is date-aware:
goods ready Friday evening can be planned against a Saturday-morning
deadline, each departure scored on its own date's traffic pattern.

### Try the dispatch inputs without starting Streamlit

After installing the requirements, run `python make_preview.py` and open
`preview.html`. This offline preview includes route, day type, target-time and
departure-window inputs; its recommendation, confidence table and chart update
from the cleaned historical observations.

**Plan Any Trip (MODELLED layer, `src/anytrip.py`):** type any start and
destination; the app geocodes them (OSM Nominatim), gets the road distance
(OSRM), and predicts per-hour median/P90 and on-time probability from a
minutes-per-km pattern learned from the 12 core routes (one global rain
multiplier, ×1.109). These are estimates, not measurements — leave-one-route-out
validation puts the average error at **17.7%** overall (core 12: 12.7%;
Airport: 76.8%, reported openly in `outputs/anytrip_validation.md`), and the
view shows that error next to every answer.

## Reproduce the analysis

```bash
cd src
python3 audit_and_clean.py   # Phase 1+2: audit + cleaned hourly dataset
python3 analysis.py          # Phase 3+4+6: time-of-day, ranking, weather
python3 backtest.py          # Phase 5: planner backtest
python3 validate.py          # Phase 8: independent cross-checks (must print ALL CHECKS PASS)
python3 anytrip.py           # Any-trip layer: model write-up + offline worked examples
python3 validate_anytrip.py  # Any-trip layer: leave-one-route-out validation
```

## Project structure

```
app.py                  Streamlit app (6 views; first view is the modelled any-trip layer)
requirements.txt        streamlit, pandas, numpy, plotly, requests
src/  common.py         shared constants/loaders
      audit_and_clean.py, analysis.py, planner.py, backtest.py, validate.py
      anytrip.py          generalised pattern model + geocode/route lookups
      validate_anytrip.py leave-one-route-out validation of the any-trip model
      deliverby.py        backward (deliver-by) planner: deadline -> latest safe departure
data/raw/               frozen source CSVs + SNAPSHOT.md (provenance)
data/processed/         cleaned.csv — 110,440 hourly observations
outputs/                data_audit.md, findings.md, reliability_ranking.csv,
                        backtest.md/.csv, weather_analysis.md, validation.md,
                        anytrip_model.md, anytrip_examples.md,
                        anytrip_validation.md/.csv, anytrip_facts.json, ...
docs/                   data_dictionary.md, viva_prep.md,
                        internal_test_playbook.md
report.md               full project report
```

## Data source and licence

- Dataset: **Traffic Monitor Lizard** — https://github.com/thecont1/traffic-monitor-lizard
  — travel-time estimates collected from Google Maps, plus weather snapshots.
  Licensed **CC BY 4.0**; attribution is given here and in the app.
- That project's own dashboard is traffiCOracle; RouteWise BLR is not a copy of it.
  All RouteWise analysis and app code was written from scratch for this project
  (the source repo's code is AGPL v3 and was not copied).
- Durations are Google Maps *estimates*, not observed vehicle trips.

## Scope notes

- The 12 core routes (~10 km) are compared like-for-like. The Airport route
  (~34 km, MG Road → Kempegowda International Airport) is analysed separately
  and never ranked against them.
- Any journey-time target used by the planner is a **user-set planning
  assumption**, not an observed business requirement.
- This project was **not** implemented at any company. A possible future live
  pilot is described in `report.md` as future work only.
