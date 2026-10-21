# Viva Prep — RouteWise BLR

Answers are written from the actual results in `outputs/`. Keep answers this short.

**Q: What does your project do, in one line?**
It recommends *when* to dispatch a vehicle on a Bengaluru route — the departure window
with the best chance of meeting a journey-time target — using a year of real travel-time
data (111,637 readings, 2025-09-25 to 2026-10-21), instead of just showing traffic charts.

**Q: Why P90 and not the average travel time?**
Averages hide the bad days. A dispatcher who plans on the mean or median will be late
roughly half the time. P90 is the time that 9 of 10 past trips beat, so planning to P90
is planning to be on time about 90% of the time. Example from the data: East Outer Ring's
median is 21 min but its P90 is 40 min — the average story and the planning story are
completely different on that route.

**Q: What is the buffer index?**
(P90 − median) / median. It is the extra time you must budget, as a share of the typical
trip, to be on time 9 times out of 10. South Outer Ring needs only 0.21 (21% extra);
East Outer Ring needs 0.90 (90% extra). It lets you compare reliability across routes
with different lengths and speeds, which raw minutes cannot do fairly.

**Q: Your headline finding?**
Fastest is not most reliable. East Outer Ring (Benniganahalli → Embassy TechVillage) ties
for the fastest median of all 12 core routes at 21 min, yet it is the *least* reliable —
P90 of 40 min and the worst buffer index, 0.90. At 09:00 on weekdays its median trip in
the held-out test period was 54 min. A speed ranking would put it first; a reliability
ranking puts it last. And the planner backtest: choosing the departure window on older
data and scoring it on later data, the planner's window beat a fixed 09:00 dispatch on
all 12 routes — but I am careful about that number, because 09:00 is mid-peak and the
target was the all-hours median; the target-independent result is the P90 gap
(on average 24.5 min lower for the full-range planner, 19.0 min lower when restricted
to 07:00–11:00).

**Q: How is this different from the existing traffiCOracle dashboard / Traffic Monitor Lizard?**
They collect the data and visualise and rank traffic. I reuse only their *dataset*
(CC BY 4.0, attributed), and I wrote all of my code myself — their code is AGPL, so
copying it would also have licence consequences. My addition is the decision layer:
a dispatch-window planner with an explicit objective (maximise on-time probability
against a user-set target, low-confidence hours excluded), a reliability ranking built
on the buffer index, and a train/test backtest of the planner's rule. They describe
traffic; this recommends a decision.

**Q: What are the limitations of your data?**
Four. (1) The durations are Google Maps *estimates*, not observed vehicle trips.
(2) Weather data exists only from 2026-05-24, on 78 days, with a gap from
2026-07-29 to 2026-10-09 — so my weather analysis is scoped to the 22,189 hourly
observations that carry weather, and it shows association, not causation: rain rows
had a median of 30 min vs 26 min for no-rain on the core routes, P90 45 vs 41.
(3) The Airport route is ~34 km while the rest are ~10 km, so it is analysed
separately and never ranked with them. (4) Distance varies per reading because
Google Maps returns alternative paths, so I use median distance per route.

**Q: Why did you deduplicate to one reading per hour?**
Normal sampling is exactly one reading per route per hour. On two days in October 2026
it briefly ran about three times per hour. Keeping raw rows would triple-weight those
two days in every hourly statistic. I collapsed each (route, date, hour) to its median —
one documented rule, applied everywhere, and my validation script rebuilds the dataset
independently and gets the same 110,440 rows and the same headline numbers (11/11 checks pass).

**Q: What IE / OR concepts does this use?**
Operations Research — selecting a departure window against a defined objective under
uncertainty. Statistical analysis — percentiles and variability instead of averages.
Capacity and scheduling — planning around travel-time uncertainty with a buffer,
the same logic as safety stock for lead times. Decision-support systems — turning
historical data into one actionable recommendation with its risk stated.

**Q: Was this implemented in a company?**
No — and I won't claim it was. It is a working decision-support system validated by
backtesting on held-out historical data. A live pilot (for example at a Bengaluru
manufacturer with regular dispatch runs) would mean logging real departures for a few
weeks, dispatching in the recommended windows, and comparing actual on-time rates.
That is future work, described in the report.

**Q: If you had more time?**
Add the company's or operator's own routes to the collector (the method works for any
origin–destination pair), run the live pilot above, and test whether the recommended
windows are stable month-to-month — my backtest already shows the weakest route's
advantage changes over time, so window stability deserves its own analysis.

**Q: What is the difference between your measured views and the "Plan Any Trip" modelled view?**
Measured means the number was counted from real readings on that exact route — the ranking,
explorer, planner and weather views use the 110,440 hourly observations for the 13 routes.
Modelled means no readings exist for that trip, so the app *predicts* it: it takes the road
distance between the two places and multiplies by the minutes-per-km pattern learned from
the 12 core routes for that hour and day type (with one global rain multiplier, ×1.109).
The app never mixes the two silently — the any-trip view carries a MODELLED banner with its
validated error printed on it.

**Q: How does leave-one-route-out validation work, and what did it give you?**
It is the honest test for a model that claims to predict routes it has never seen. For each
of the 13 routes in turn, I rebuild the model with that route completely removed, predict
the route's hourly medians from its distance alone, and compare against its actual hourly
medians — 624 route × day-type × hour cells in all. Result: overall MAPE 17.7%; the core 12
routes average 12.7% (best North Inner Ring 3.9%, worst Hosur Road 32.0%); the Airport route
is 76.8%, because a city-street minutes-per-km pattern cannot describe a 34 km expressway
trip — and I report that failure instead of hiding it. No route is dropped from the table.

**Q: Why not just use the Google Maps API for any start and destination?**
Three reasons. (1) Practical: it needs a billing-enabled API key — cost and account setup
for what is a demonstration. (2) It answers a different question: Google gives a travel-time
estimate for *now*, for that pair. It does not give a year of history, a P90, an on-time
probability against your target, or a best departure hour — the reliability layer is the
project, and Google does not sell it to me. (3) What I built instead is free and auditable:
OpenStreetMap geocoding and OSRM routing supply only the trip's distance, the prediction
comes from our own validated pattern model, and its error is published. Where Google is
genuinely better — live conditions on an arbitrary pair — I say so; that is not the claim
this project makes.

**Q: What is the difference between forward planning and backward planning in your app?**
The Dispatch Planner plans forward: fix a departure hour, ask whether the trip fits a
duration target. The Deliver-by Planner plans backward: the delivery deadline is fixed
and the goods-ready time is known, so it subtracts travel time from the deadline hour by
hour and finds the latest departure that still arrives on time. It is the same idea as
backward scheduling in production planning (PPC) — schedule a job backward from its due
date to get its latest start time — applied to dispatch instead of machines. If no
departure reaches the safety level (≥95% on-time), the view says "not feasible safely"
and shows the best real probability, instead of dressing up a gamble as a plan.

**Q: Why recommend the LATEST safe departure instead of the earliest?**
Because leaving early is not free. A vehicle and driver sent out hours before they need
to be are a vehicle and driver that cannot do another trip — that is wasted capacity, the
same reason production doesn't start every job the moment material arrives. The latest
departure that still meets the ≥95% on-time bar respects the customer's deadline and
keeps the fleet free for other work. Example: East Outer Ring, goods ready 09:00,
deadline 18:00 — every departure up to 16:00 was on time in 100% of historical readings,
so the planner says leave at 16:00 (typical arrival 16:36), not 09:00. The 17:00
departure, at 94.3%, falls below the safety level and is visibly marked as the cliff edge.

**Q: How does overnight / next-day planning work in the Deliver-by Planner?**
The goods-ready and deliver-by inputs are dates plus hours, not just hours, so a
window can cross midnight (up to 72 hours). Every candidate departure in the window
is scored against the deadline using the traffic pattern of *its own* date:
weekday vs weekend is derived from the departure's calendar date. That rule matters —
a Friday 23:00 departure faces weekday late-evening traffic, while a Saturday 02:00
departure faces weekend night traffic, and scoring either with the other's data would
be quietly wrong. Example: East Outer Ring, goods ready Friday 20:00, deliver by
Saturday 09:00 — all thirteen candidate departures are on time in 100% of historical
readings, so the planner recommends the latest, Saturday 08:00 (typical arrival
08:16, P90 arrival 08:18). The correct operational answer there is "don't dispatch
at night at all", and the tool proves it from the route's own data instead of
assuming an evening dispatch is necessary.
