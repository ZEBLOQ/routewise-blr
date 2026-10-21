# Any-trip layer — worked examples (fully offline)

Computed with the pure model path in `src/anytrip.py` from the frozen
dataset — no live geocoding or routing calls — so anyone can reproduce
these exact numbers by running `python3 anytrip.py` in `src/`.
Search window for the recommendation: departures 06:00–21:00, the same
default as the app's planner. All figures are MODELLED estimates.

## Example 1 — short cross-town trip, dry weekday

A delivery run of 8.5 km on a weekday, no rain, target: arrive within 30 min.

**Recommended departure: 06:00** — predicted median 16.0 min, P90 19.1 min, modelled on-time probability 100% against the 30-minute target.

| Departure hour | Predicted median (min) | Predicted P90 (min) | Modelled on-time % (≤ target) |
|---|---|---|---|
| 06:00 | 16.0 | 19.1 | 100 | **← recommended**
| 07:00 | 20.5 | 27.0 | 99 |
| 08:00 | 25.7 | 34.3 | 93 |
| 09:00 | 30.0 | 39.3 | 61 |
| 10:00 | 30.9 | 38.6 | 35 |
| 11:00 | 29.4 | 35.7 | 61 |
| 12:00 | 28.0 | 33.5 | 79 |
| 13:00 | 26.7 | 32.6 | 88 |
| 14:00 | 25.3 | 31.1 | 94 |
| 15:00 | 27.2 | 33.5 | 85 |
| 16:00 | 29.8 | 36.2 | 61 |
| 17:00 | 31.3 | 38.6 | 31 |
| 18:00 | 32.8 | 39.7 | 15 |
| 19:00 | 31.1 | 38.0 | 34 |
| 20:00 | 26.8 | 32.8 | 88 |
| 21:00 | 23.3 | 28.6 | 98 |

## Example 2 — longer trip, rainy weekday

A 14 km weekday trip in rain, target: arrive within 45 min. Every time below already includes the rain multiplier (1.108).

**Recommended departure: 06:00** — predicted median 29.3 min, P90 34.8 min, modelled on-time probability 100% against the 45-minute target.

| Departure hour | Predicted median (min) | Predicted P90 (min) | Modelled on-time % (≤ target) |
|---|---|---|---|
| 06:00 | 29.3 | 34.8 | 100 | **← recommended**
| 07:00 | 37.4 | 49.3 | 95 |
| 08:00 | 46.8 | 62.6 | 32 |
| 09:00 | 54.7 | 71.7 | 4 |
| 10:00 | 56.4 | 70.5 | 3 |
| 11:00 | 53.6 | 65.3 | 5 |
| 12:00 | 51.2 | 61.2 | 9 |
| 13:00 | 48.7 | 59.5 | 18 |
| 14:00 | 46.3 | 56.7 | 36 |
| 15:00 | 49.6 | 61.1 | 14 |
| 16:00 | 54.4 | 66.1 | 4 |
| 17:00 | 57.1 | 70.4 | 2 |
| 18:00 | 59.9 | 72.5 | 1 |
| 19:00 | 56.7 | 69.4 | 2 |
| 20:00 | 48.9 | 59.9 | 17 |
| 21:00 | 42.5 | 52.2 | 76 |

