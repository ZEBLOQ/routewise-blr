# RouteWise BLR — Project Report

**Time-Dependent Route Reliability and Dispatch Planning for Urban Logistics in Bengaluru**
R. Shashank — Final-year B.Tech, Industrial Engineering & Management, B.M.S. College of Engineering

---

## 1. Problem

A delivery or service operation in Bengaluru does not mainly need to know that
"traffic is bad". It needs to decide **when to dispatch** a vehicle on a given
route so that the trip finishes within a planned time, reliably. Two routes with
the same average travel time can behave very differently: one is steady, the
other is fast on a good day and very slow on a bad one. Dispatching on averages
systematically under-budgets the second kind of route.

RouteWise BLR is a decision-support system that, for each of 13 fixed Bengaluru
routes, (a) measures how travel time varies by hour, day type and weather,
(b) ranks routes by *reliability* rather than speed, and (c) recommends a
departure window that maximises the probability of meeting a user-set
journey-time target. The target is a planning assumption set by the user; it is
not presented as an observed business requirement.

## 2. Data and audit

Source: the open-source **Traffic Monitor Lizard** project, which queries
Google Maps travel-time estimates for fixed Bengaluru routes and records them
with weather snapshots (dataset CC BY 4.0; attribution in README and app).
The data was **frozen on 2026-10-21** so every number in this report is
reproducible from `data/raw/` (see `data/raw/SNAPSHOT.md`).

Audit results (`outputs/data_audit.md`, computed by `src/audit_and_clean.py`):

- **111,637 raw readings, 2025-09-25 to 2026-10-21, 13 routes**, no missing
  durations or timestamps, no exact duplicate rows.
- Normal sampling is one reading per route per hour (312 rows/day). On
  2026-10-19/20 sampling briefly ran ~3× per hour (1,794 rows fall in
  multi-reading hour cells). To stop those two days triple-weighting hourly
  statistics, the analysis dataset uses **one observation per (route, date,
  hour)** — the median within the hour — giving **110,440 hourly observations**.
- Two readings were removed as physically implausible: Airport-route durations
  of 2 and 3 minutes over ~34 km.
- Distance varies per reading (Google Maps returns alternative paths); the
  core 12 routes have median distances of 9.4–10.6 km, the Airport route 34.3 km.
  The Airport route is therefore analysed separately and never ranked with the 12.
- **Weather coverage is the dataset's main limitation:** weather fields are
  entirely absent before **2026-05-24**, present on only **78 days** after that,
  with one continuous gap from **2026-07-29 to 2026-10-09**. Only 20.95% of all
  rows carry a temperature reading. `rsi_flag` contains only `Light Rain`
  (1,475 raw rows) and `Rain` (350); empty means no rain reported.

Features built in cleaning (`docs/data_dictionary.md`): timestamp, hour,
day-of-week, weekday/weekend day type, time buckets (night 21:00–06:59,
morning peak 07:00–10:59, midday 11:00–15:59, evening peak 16:00–20:59),
and average speed.

## 3. Method

- **Time-of-day analysis:** per route, median and P90 duration by departure
  hour, by day type, and by time bucket.
- **Reliability ranking:** per core route — median (P50), P90, and
  **buffer index = (P90 − P50) / P50**, the extra time, as a share of the
  typical trip, that must be budgeted for a 9-in-10 on-time plan. Routes are
  ranked by buffer index, deliberately not by speed.
- **Dispatch-window planner** (`src/planner.py`): for a route, day type,
  target and search range, it computes per departure hour the reading count,
  median, P90 and on-time probability (share of trips ≤ target). Hours with
  fewer than 30 readings are flagged low-confidence and excluded. The
  recommendation is the hour with the highest on-time probability, tie-broken
  by lowest P90.
- **Backtest:** planner choices were made on data up to 2026-06-30 only and
  scored on data from 2026-07-01 onward, against a naive "dispatch at 09:00"
  baseline. Target per route = its train-period median (documented planning
  assumption). The split and target were fixed before running; results are
  reported as they came out.
- **Weather analysis:** restricted to the 22,189 hourly observations that
  carry a weather snapshot; rain vs no-rain compared on median, P90 and IQR,
  overall and split by peak vs off-peak. Association language only.
- **Validation:** `src/validate.py` recomputes 11 headline numbers through
  independent code paths from the raw data. **All 11 checks pass**
  (`outputs/validation.md`).

## 4. Findings

Full numbers in `outputs/findings.md` and the summary CSVs.

1. **Weekdays are slower than weekends** on the core routes: route-average
   median 28.8 min (weekday) vs 26.0 min (weekend), +11.6%. The largest gap is
   East Outer Ring, +27.8% on weekdays.
2. **Evening peak is the worst window**: pooled core medians — morning peak
   30 min, midday 33, evening peak 35, night 19. Evening is worse than morning
   on 9 of 12 routes; the largest evening penalty is Central Diagonal 1
   (33 → 39 min).
3. **Fastest ≠ most reliable (headline).** Ranked by buffer index, the most
   reliable core route is **South Outer Ring** (median 33 min, P90 40,
   buffer 0.21) and the least reliable is **East Outer Ring** (median 21,
   P90 40, buffer 0.90). East Outer Ring's median *ties for fastest* of all
   12 routes — a planner using speed alone would rank it first and budget no
   buffer for trips that reach 40 minutes one time in ten. The fastest route
   by median, Hosur Road (21 min), ranks only 6th of 12 on reliability.
4. **Airport route (separate):** weekday median 52 min, P90 68 min; evening
   peak median 67 min vs 39 at night. Its scale is different, which is why it
   is never merged into the core ranking.

## 5. Planner and backtest

On held-out test data (from 2026-07-01), for weekday dispatch on the 12 core
routes, the planner's recommended window (chosen on train data only) had a
higher on-time probability than the 09:00 baseline on **12 of 12 routes**
(mean +92.2 percentage points) and a lower P90 on 12 of 12 routes
(mean **−24.5 min**). Restricted to a realistic morning window (07:00–11:00,
the planner chose 07:00), the advantage was +81.4 pp on-time and **−19.0 min**
on P90, again 12 of 12 routes.

These numbers must be read honestly (`outputs/backtest.md`): the planner
usually picks the earliest hour offered, because travel time climbs into the
morning peak, and the on-time target was each route's all-hours median, which
a mid-peak 09:00 trip on a peak-sensitive route rarely beats — verified
directly on East Outer Ring, whose 09:00 weekday median on test data is
54 min against a 23 min target, while its 06:00 median is 17 min. So the
on-time gap largely measures **how peak-sensitive these routes are**. The
target-independent result — the P90 advantage — is the sound one to quote:
trips departing in the planner's window ran faster and tighter than 09:00
trips on data the planner never saw.

## 6. Weather finding

On weather-covered rows for the core routes (rain n = 1,628 hourly
observations; no-rain n = 18,812): median duration 30 min in rain vs 26 min
with no rain; P90 45 vs 41 min; IQR 16 vs 15 min. In peak periods the median
gap was 38 vs 33 min. Rain is therefore *associated* with slower and slightly
less predictable trips in the covered period. This does not establish that
rain caused the difference — the comparison does not control for which routes
and hours rain readings fall in, and coverage is limited to part of the year
(2026-05-24 to 2026-07-28 plus 2026-10-10 to 2026-10-21).

## 7. The application

A Streamlit app (`app.py`, smoke-tested — all four views execute without
error) provides: (1) Reliability Ranking, (2) Route Explorer (travel time by
hour for any route and day type), (3) Dispatch Planner (interactive version
of `src/planner.py`), and (4) Weather Impact (the scoped analysis, with its
coverage warning shown in the view itself). Header and footer credit the
dataset source and licence.

## 8. Limitations

- Durations are Google Maps **estimates**, not observed vehicle trips; a live
  operation's actuals will differ in level, though peak patterns are the
  decision-relevant part.
- Weather analysis covers only part of the year and a subset of days
  (Section 2); it must not be quoted as a full-year result.
- The planner recommends within the hours offered and optimises one
  objective; it does not consider vehicle availability, loading time, or
  delivery deadlines at the destination end — a real deployment would set the
  search window from the required arrival time backwards.
- Backtest used one split date and one target definition; the size of the
  gain will change with other choices, even where the direction holds.
- Route set is fixed at 13 corridors; results do not generalise to other
  origin–destination pairs without collecting data for them (the same
  collection method supports arbitrary routes).

## 9. Future work

- Month-by-month stability analysis of the recommended windows.
- Adding operator-specific routes to the collection pipeline and re-running
  the same reliability/planner layer on them.
- **Possible future pilot (not done, not claimed):** a Bengaluru operation
  with regular, repeated dispatch runs — for example a manufacturer such as
  Spectrum Tool Engineers, if it has recurring trips to the same customers or
  vendors — could log actual departure/arrival times for a baseline period,
  then dispatch inside the planner's recommended windows for a trial period,
  and compare actual on-time performance. Only after such a pilot could any
  implementation claim be made; none is made in this project.
- A live-arrival mode: given a required arrival time, work backwards through
  the P90 for each candidate departure hour and present the latest safe
  departure, rather than the single best hour.

## Appendix — reproducibility

```
cd src && python3 audit_and_clean.py && python3 analysis.py && python3 backtest.py && python3 validate.py
```
Outputs land in `outputs/`. Viva preparation notes are in `docs/viva_prep.md`.

---

## 10. Any-trip layer (added after the main build)

Sections 1–9 cover the 13 measured routes. This section adds one capability
the original scope deliberately lacked: estimating a trip that is **not** one
of the 13 routes, where no historical readings exist. Everything in this
section is **modelled**, and the app labels it that way, next to the validated
error. No number in Sections 1–9 changes.

### Method (`src/anytrip.py`)

1. **Minutes-per-km pattern.** On the 12 core routes, each hourly observation
   is divided by its distance. For every (day type, hour) cell we keep the
   median and P90 minutes-per-km — one generalised Bengaluru pattern, learned
   from 101,891 hourly observations. The Airport route is excluded from
   learning for the same reason it is excluded from the ranking: a 34 km
   expressway trip is not a city route.
2. **Rain: one global multiplier.** On weather-covered rows only, median
   minutes-per-km in rain ÷ without rain = **1.109** (rain n = 1,628;
   no-rain n = 18,812). The rain scenario scales all predicted times by this
   single factor. The data is too sparse for per-hour or per-route rain
   effects, so none are claimed.
3. **Prediction.** Predicted median for an hour = that hour's median
   minutes-per-km × trip distance (× rain multiplier if rain); P90 likewise.
   Trip distance is the road distance from OSRM routing between the two
   geocoded places (OpenStreetMap Nominatim + OSRM, free public services).
4. **On-time probability.** Every historical trip is expressed as a ratio to
   the median trip for its own route, day type and hour; pooled over the core
   routes, those ratios form one route-free spread distribution.
   P(trip ≤ target) = share of pooled ratios ≤ target ÷ predicted median.
   The rain scenario reuses the same spread and shifts only the level — an
   approximation, stated as such.
5. **Recommendation.** Same rule as the measured planner: highest on-time
   probability in the chosen hour range, tie-break lowest P90.

Worked examples computed entirely offline are in `outputs/anytrip_examples.md`;
the model write-up is `outputs/anytrip_model.md`.

### Validation — leave-one-route-out (`src/validate_anytrip.py`)

Each route in turn was removed from the learning pool, its hourly medians
were predicted from its median distance alone, and predictions were compared
with its actual hourly medians in the cleaned data (624 route × day-type ×
hour cells). Results, all 13 routes reported in
`outputs/anytrip_validation.md`:

- **Overall MAPE 17.7%** (MAE 6.1 min) on hourly medians.
- **Core 12 routes: MAPE 12.7%.** Best: North Inner Ring 3.9%. Worst core
  route: Hosur Road 32.0% — a corridor whose behaviour departs most from the
  city-wide pattern, which a distance-only model cannot see.
- **Airport route: MAPE 76.8%.** The airport route is never in the learning
  pool, so this is a fully out-of-sample check, and it fails openly: city
  minutes-per-km badly over-predict an expressway trip (MAE 39.7 min). The
  modelled layer should therefore be read as a *city-trip* estimator; for
  airport trips the measured view is the honest source.

### Limitations of this layer

- **Modelled is weaker than measured — by a measured amount.** A distance-only
  model cannot know a specific corridor's chronic bottlenecks; the 17.7%
  average error (and 32% on the worst core corridor) is the price of covering
  arbitrary trips. Where a measured route exists, use the measured views.
- **Needs the internet.** Place lookup and routing call free public
  OpenStreetMap servers (Nominatim, OSRM). They are demo-grade — rate-limited,
  no uptime guarantee — acceptable for a project demonstration, not for a
  production service. The model itself and all measured views work offline.
- **Rain is one global factor** (×1.109 on every hour and route), because that
  is all the sparse weather coverage supports.
- The on-time probability borrows the *spread* of the measured routes; it is
  a modelled probability, not a frequency counted on the user's own route.
