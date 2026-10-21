# Any-trip validation — leave-one-route-out

**Honest headline: predicting a route the model has never seen, from its
distance alone, is off by 17.7% on average** (MAPE on hourly
medians across all 624 route × day-type × hour cells of all 13
routes; MAE 6.1 min). Core 12 routes: **12.7%**.
Airport route: **76.8%** — it is never in the learning pool,
so this is a fully out-of-sample check, and the city-pattern model transfers
to a 34 km expressway trip only as well as that number says.

Method: for each route, rebuild the pattern model from the other routes
only (the held-out route contributes nothing — not its curve, not its rain
rows, not its ratios), predict each (day type, hour) median as
minutes-per-km x the route's median distance, and compare with the route's
actual hourly medians in cleaned.csv. Dry scenario throughout. All 13
routes are reported; worst first.

| Route | Group | Median distance (km) | Cells | MAPE % | MAE (min) |
|---|---|---|---|---|---|
| Airport Expy | airport_separate | 34.3 | 48 | 76.80 | 39.72 |
| Hosur Road | core12 | 10.4 | 48 | 31.97 | 7.03 |
| East Outer Ring | core12 | 10.0 | 48 | 26.33 | 5.64 |
| Double Decker Flyover | core12 | 10.1 | 48 | 19.62 | 4.57 |
| Central Diagonal 2 | core12 | 10.2 | 48 | 18.83 | 6.24 |
| South Outer Ring | core12 | 10.6 | 48 | 9.80 | 3.10 |
| East Inner Ring | core12 | 10.5 | 48 | 8.94 | 2.90 |
| Old Airport Road | core12 | 9.4 | 48 | 7.49 | 2.00 |
| Sarjapur Road | core12 | 10.1 | 48 | 7.29 | 2.09 |
| North Outer Ring | core12 | 9.7 | 48 | 6.91 | 2.01 |
| Central Diagonal 1 | core12 | 10.5 | 48 | 6.61 | 1.96 |
| Mysore Road | core12 | 9.9 | 48 | 4.98 | 1.39 |
| North Inner Ring | core12 | 10.6 | 48 | 3.93 | 1.19 |

Worst predicted route: **Airport Expy** (MAPE 76.8%) — its corridor behaviour differs most from the city-wide pattern, which is
exactly the kind of route-specific effect a distance-only model cannot see.
Best predicted route: **North Inner Ring** (MAPE 3.9%).

Reproduce: `cd src && python3 validate_anytrip.py`. Per-route numbers:
`outputs/anytrip_validation.csv`. Summary consumed by the app banner:
`outputs/anytrip_facts.json`.
