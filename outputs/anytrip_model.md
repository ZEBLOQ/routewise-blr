# Any-trip model — how the prediction works, in plain words

The 13 routes in the main app are **measured**: real readings exist for them.
This layer answers a different question — *"what about a trip that is NOT one
of those 13 routes?"* — and its answers are **modelled estimates**, not
measurements. Nothing about this layer changes any number in the main app.

## The method, step by step

1. **Learn the price of a kilometre.** On the 12 core measured routes, every
   historical trip is divided by its distance to get *minutes per kilometre*.
   For each hour of the day, separately for weekdays and weekends, we keep the
   median and the P90 of that rate. That table is the whole "city pattern":
   e.g. a weekday kilometre costs the median rate shown below.
2. **One rain factor.** Rain was recorded only in part of the data, so instead
   of inventing fine detail we compute a single multiplier:
   median minutes-per-km in rain / without rain, on weather-covered rows =
   **1.108** (rain rows n=1,628, no-rain rows n=18,812).
   Choosing the "rain" scenario multiplies every predicted time by this one
   factor. It is a level shift only — we do not claim rain changes the shape
   of the day.
3. **Predict a new trip.** Predicted median for an hour = that hour's median
   minutes-per-km x the trip's distance in km (x the rain factor if rain).
   P90 the same way. The trip's distance comes from the road route between
   the two places (OSRM), not from a straight line.
4. **On-time probability.** A median alone says nothing about risk, so we keep
   the *spread* the measured routes showed: every historical trip divided by
   the typical (median) trip for its own route, day type and hour gives a
   "ratio" — 1.0 means exactly typical, 1.5 means 50% worse than typical.
   Pooled over all core routes, those ratios are the model's spread. For a
   target T and predicted median M, on-time probability = share of pooled
   ratios <= T / M.
5. **Recommendation.** Same rule as the measured planner: in the chosen hour
   range, the hour with the highest on-time probability wins; ties break to
   the lowest P90.

## The learned pattern (weekday, minutes per km)

| Hour | Median min/km | P90 min/km | Readings |
|---|---|---|---|
| 00:00 | 1.89 | 2.25 | 3,143 |
| 01:00 | 1.78 | 2.08 | 3,216 |
| 02:00 | 1.70 | 1.98 | 3,240 |
| 03:00 | 1.67 | 1.90 | 3,288 |
| 04:00 | 1.68 | 1.96 | 3,265 |
| 05:00 | 1.79 | 2.08 | 3,277 |
| 06:00 | 1.89 | 2.24 | 1,583 |
| 07:00 | 2.41 | 3.18 | 2,149 |
| 08:00 | 3.02 | 4.04 | 2,677 |
| 09:00 | 3.52 | 4.62 | 2,881 |
| 10:00 | 3.64 | 4.55 | 3,073 |
| 11:00 | 3.45 | 4.21 | 2,953 |
| 12:00 | 3.30 | 3.94 | 3,001 |
| 13:00 | 3.14 | 3.83 | 3,217 |
| 14:00 | 2.98 | 3.65 | 3,119 |
| 15:00 | 3.20 | 3.94 | 3,203 |
| 16:00 | 3.51 | 4.26 | 3,239 |
| 17:00 | 3.68 | 4.54 | 3,157 |
| 18:00 | 3.86 | 4.67 | 2,832 |
| 19:00 | 3.65 | 4.47 | 3,216 |
| 20:00 | 3.15 | 3.86 | 3,084 |
| 21:00 | 2.74 | 3.36 | 3,156 |
| 22:00 | 2.42 | 2.88 | 3,204 |
| 23:00 | 2.08 | 2.48 | 3,084 |

Learned from 101,891 hourly observations on 12 routes. The Airport route is excluded from
learning (a ~34 km expressway trip is not a city route).

## What this model cannot do

- It knows nothing about a specific road — two trips of the same distance
  get the same prediction, whatever roads they use. Corridor-specific
  behaviour (a chronically jammed junction) is exactly what it misses.
- Its accuracy is a measured fact, not a hope: see
  `outputs/anytrip_validation.md` (leave-one-route-out). The modelled layer
  is less accurate than the measured routes, and the app shows the error
  next to every modelled answer.
- Live place/route lookup needs the internet and free public servers;
  this file and `outputs/anytrip_examples.md` are fully offline.

Dataset: Traffic Monitor Lizard (CC BY 4.0) — see README.md.
