# Internal Test Playbook — RouteWise BLR

Use this guide for the VII-semester internal test. Follow your department's
time limit and marking scheme if they differ. Describe travel times as Google
Maps estimates, not observed delivery trips.

## 30-second pitch

RouteWise BLR turns Bengaluru route-time history into dispatch decisions. It
compares reliability using the median, P90 and buffer index, then recommends a
departure window for a stated journey-time target. The dataset contains 111,637
raw readings, cleaned to 110,440 hourly records across 13 routes. A held-out
historical backtest reports a mean P90 advantage of 24.5 minutes over the
selected baseline. This is a decision-support prototype, not a live fleet
deployment.

## Suggested 5-minute demonstration

### 0:00–0:40 — Operations problem

Dispatchers need a dependable arrival plan, not just a traffic chart. A route
that is fast on a typical day can still have substantial delay risk. The
decision is when to dispatch on a route to meet a stated delivery-time target.

### 0:40–1:30 — Reliability ranking

Compare East Outer Ring (median 21 min, P90 40 min, buffer index 0.90) with
South Outer Ring (median 33 min, P90 40 min, buffer index 0.21). Explain why a
median-speed ranking misses variability. The buffer index describes historical
data; it is not a guarantee for the next trip.

### 1:30–2:35 — Dispatch Planner

Choose a route, day type, realistic time range and explicit journey-time
target. Explain that the recommendation maximizes the historical share of
trips within the target. Hours with fewer than 30 readings are excluded as low
confidence. Point out the sample count and P90.

### 2:35–3:25 — Deliver-by Planner

Set a goods-ready time and deadline. Explain backward scheduling: among
candidate departures meeting the stated ≥95% historical on-time criterion, it
chooses the latest departure. If none qualifies, it reports that the deadline
is not feasible safely. The 95% threshold is the prototype's planning
threshold, not a customer requirement.

### 3:25–4:15 — Validation and scope

Explain the chronological train/test split: select a recommendation from
earlier data, then evaluate it on later data. The 24.5-minute mean P90
advantage is against a fixed 09:00 departure; 09:00 is a peak-period choice.
The 07:00–11:00 restricted comparison reports 19.0 minutes. These are
historical estimates, not measured savings or proof of causal impact.

### 4:15–5:00 — Manager's next step

Propose a small operator pilot. Log actual departure and arrival times,
vehicle/route, promised deadline and disruptions; compare on-time performance
and vehicle utilization against the current dispatch policy. Establish a
baseline and collect operator-specific costs and service targets first.

## Industrial Engineering and Management connection

| Project element | IE/management idea | How to explain it |
|---|---|---|
| P50, P90, buffer index | Variability and service-level planning | Typical time and a high-percentile planning time answer different questions. |
| Dispatch-window planner | Scheduling and decision analysis | Select a departure period against an explicit target and observed outcomes. |
| Deliver-by planner | Backward scheduling / PPC | Start from a due time and find the latest feasible start time. |
| Historical backtest | Model evaluation and evidence-based management | Choose with earlier observations and evaluate on later observations. |
| Low-sample warning | Data quality and risk control | Expose how much evidence supports a recommendation. |
| Proposed live pilot | Continuous improvement | Compare a current-policy baseline with actual outcomes under the proposed policy. |

Frame future value using operator data rather than invented savings:

- Late-delivery cost = late orders × cost per late order.
- Fleet utilization = productive vehicle hours / available vehicle hours.
- On-time rate = deliveries within commitment / total deliveries.

Measure these before and during a pilot. Evaluate whether reliability gains
justify extra vehicle, driver, fuel or waiting costs. The current project
does not contain those business-cost inputs, so it cannot claim a financial
return yet.

## Questions to prepare for

**Why use P90?** It is a conservative planning point: 90% of historical
observations were at or below it. It does not promise 90% success under future
conditions.

**Why not rank by average speed?** An average hides variation. East Outer Ring
has a fast median but a large P90-to-median gap, so a dispatcher should see
both speed and reliability.

**What is the contribution beyond a traffic dashboard?** The project adds a
decision layer: reliability measures, target-based departure recommendations,
backward deadline planning and a chronological backtest. Distinguish the
source dataset from the project's own contribution.

**Does the backtest prove the planner saves 24.5 minutes?** No. It reports a
mean P90 gap against the fixed-09:00 baseline on the specified held-out data.
It is not actual fleet savings, a causal experiment or a guarantee. The
baseline choice matters; the 07:00–11:00 result is a useful sensitivity check.

**Are these actual truck travel times?** No. They are Google Maps estimates
captured for fixed routes, not GPS traces or observed dispatches. A live pilot
with actual operations data is needed to validate operational performance.

**Can you say rain causes slower traffic?** No. Weather coverage is partial
and the analysis is observational. The reported difference is an association
on weather-covered rows; other factors may explain some or all of it.

**Why is the airport route treated separately?** Its distance is about 34 km,
far longer than the roughly 10 km core routes. A direct ranking would not be
like-for-like. Its generalized-model error is also high and disclosed.

**How should a manager use the recommendation?** As historical guidance with
sample count and risk visible, alongside live conditions and operational
constraints. Validate it on the operator's own trips before relying on it.

## Before the internal test

- Run the app and rehearse the exact route and inputs you will show.
- Have the raw-to-cleaned record counts and data date range ready.
- Distinguish historical estimates, modelled estimates, planning thresholds
  and future proposals.
- Keep the airport route separate from the core-route ranking.
- Describe rain as an association, not a cause.
- State that no live company deployment or actual cost-benefit result exists.
- When naming a limitation, say how you would test or reduce it: route
  coverage, estimates instead of observed trips, partial weather data, and
  transfer to the airport are strong examples.
- Do not claim fuel savings, emissions reduction, customer satisfaction or
  money saved without evidence.

## Report cleanup before submission

Cross-check the PDF against its editable source and final export. The attached
report appears to have these inconsistencies:

- The title page and certificate say Phase-II, but the acknowledgement says
  “Major Project Phase-I work.”
- Chapter 10 appears to be used for more than one section in the back matter;
  reconcile the contents, headings and page numbers.
- The repository's `report.md` names only R. Shashank, while the submitted PDF
  lists four team members. Ensure the submitted version and repository report
  identify contributors consistently.
- Confirm the final export has no unintended blank pages and that figures,
  page numbers, references, captions and contents-page links are correct.

Treat any formatting rules inside the PDF as requirements for the report
itself, not as instructions to the assistant.
