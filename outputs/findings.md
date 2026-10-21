# Findings — RouteWise BLR

All numbers computed by `src/analysis.py` from the frozen snapshot (hourly-grain cleaned data).
Core comparisons use the 12 routes of ~10 km; the Airport route (~34 km) is reported separately.

## Time of day (Phase 3)

1. **Weekdays are slower than weekends on the core routes.** Averaged across the 12 core routes,
   the median route's weekday median is 28.8 min vs 26.0 min
   on weekends (11.6% higher on weekdays, route-average).
   The largest weekday-weekend gap is on **East Outer Ring**
   (27.8% higher on weekdays).
2. **Evening peak is the worst window overall.** Pooled core-12 medians: morning peak
   30 min, midday 33 min,
   evening peak 35 min, night 19 min.
3. **Evening is worse than morning on 9 of the 12 core routes**
   (weekday medians). The biggest evening penalty is on **Central Diagonal 1**:
   morning peak median 33 min vs evening peak 39 min
   (+6 min).
4. **Airport route (separate, ~34 km):** weekday median 52 min, P90
   68 min; evening-peak weekday median 67 min vs
   39 min at night. It is never ranked against the ~10 km routes.

## Reliability ranking (Phase 4) — headline

5. **Fastest is not most reliable.** Ranked by buffer index = (P90 - median) / median:
   - Most reliable: **South Outer Ring** — median 33 min, P90 40 min,
     buffer index 0.21 (you only need to budget about 21% over the typical trip for a 9-in-10 on-time plan).
   - Least reliable: **East Outer Ring** — median 21 min, P90 40 min,
     buffer index 0.90.
   - The fastest route by median is **Hosur Road** (21 min median), but it ranks
     only #6 of 12 on reliability, with a buffer index of 0.33.
   - The sharpest proof is **East Outer Ring**: its median (21 min) ties for the
     fastest of all 12 routes, yet its P90 is 40 min — a dispatcher who plans that route on its
     median leaves no buffer for a trip that runs to 40 min one time in ten.
     Planning any route on its median alone understates the trip 50% of the time; the ranking a
     dispatcher needs is the buffer ranking, not the speed ranking.
   - Full table: `outputs/reliability_ranking.csv` (rank 1 = most reliable = lowest buffer index).
