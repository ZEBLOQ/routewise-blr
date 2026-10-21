# Weather Analysis (Phase 6) — scoped

**Scope, stated plainly:** weather fields exist only from 2026-05-24 onward in this
snapshot, and only on a subset of days (see `outputs/data_audit.md`). This analysis uses ONLY the
22,189 hourly observations (all 13 routes) that carry a weather snapshot; headline
comparisons below use the 12 core routes. Rain = `rsi_flag` in {Rain, Light Rain} (no 'Heavy Rain'
values exist in this snapshot); no-rain = weather present and `rsi_flag` empty.
Sample sizes (core 12): rain n=1,628, no-rain n=18,812.
Everything here is **association, not causation**.

## Result (core 12 routes, weather-covered rows only)

- Median duration: rain 30 min vs no-rain 26 min.
- P90 duration: rain 45 min vs no-rain 41 min.
- Variability (IQR): rain 16 min vs no-rain 15 min.
- Peak periods only: median rain 38 min vs no-rain 33 min;
  P90 rain 48 min vs no-rain 45 min.
- Off-peak only: median rain 24 min vs no-rain 22 min.

Full breakdown: `outputs/weather_summary.csv` (peak vs off-peak) and `outputs/weather_overall.csv`.

**Reading:** compare the rain vs no-rain gaps above at the median and at P90 — if the P90 gap is
larger than the median gap, rain is associated less with uniformly slower trips and more with
*less predictable* trips, which is what a dispatch planner has to budget for. The comparison does
not control for which routes/hours the rain readings happen to fall in, so it must not be quoted
as 'rain causes X minutes of delay'.
