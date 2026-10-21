# Validation — independent cross-checks

Recomputed by `src/validate.py` through separate code paths from the frozen raw data.

| # | Check | Published | Recomputed | Result |
|---|---|---|---|---|
| 1 | South Outer Ring median | 33.00 | 33.00 | PASS |
| 2 | South Outer Ring P90 | 40.00 | 40.00 | PASS |
| 3 | East Outer Ring median | 21.00 | 21.00 | PASS |
| 4 | East Outer Ring P90 | 40.00 | 40.00 | PASS |
| 5 | South Outer Ring buffer index | 0.21 | 0.21 | PASS |
| 6 | cleaned hourly row count | 110440.00 | 110440.00 | PASS |
| 7 | planner recommended hour (EOR, weekday, target 40) — hour | 6.00 | 6.00 | PASS |
| 8 | planner recommended hour — on-time prob % | 100.00 | 100.00 | PASS |
| 9 | weather rain median (core) | 30.00 | 30.00 | PASS |
| 10 | weather no-rain median (core) | 26.00 | 26.00 | PASS |
| 11 | backtest EOR baseline OTP (fraction) | 0.05 | 0.05 | PASS |

**Overall: ALL CHECKS PASS** (11/11 checks).
