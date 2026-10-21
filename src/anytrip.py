"""Any-trip layer: predict travel time for an arbitrary Bengaluru trip.

The four main RouteWise views are MEASURED: every number comes from
actual readings on one of the 13 routes in the dataset. This module is
different — it is MODELLED. It lets a user ask about a trip that is NOT
one of the 13 measured routes ("HSR Layout to Whitefield", say), for
which no historical readings exist at all.

How it works, in plain words:

1. From the 12 core measured routes (all ~10 km), learn how expensive
   one kilometre of Bengaluru road is at each hour of the day, for
   weekdays and weekends separately: median minutes-per-km and
   P90 minutes-per-km. This is the "city pattern". The Airport route is
   left out of the learning pool — it is a ~34 km expressway trip, not
   a city route, the same reason it is never ranked with the core 12.
2. Rain is handled by one global multiplier: on rows where weather was
   actually recorded (temp present), median minutes-per-km in rain
   divided by median minutes-per-km without rain. Rain data is sparse,
   so one overall factor is all the data honestly supports — there is
   no per-hour or per-route rain effect.
3. To predict a new trip: predicted median minutes for an hour =
   that hour's median minutes-per-km x trip distance in km
   (x rain multiplier if the scenario is rain). P90 likewise.
4. On-time probability needs a spread, not just a median. We reuse the
   spread the measured routes actually showed: for every historical
   reading, compute ratio = duration / (median duration for that same
   route, day type and hour). Those ratios pool into one route-free
   distribution of "how much better or worse than typical a trip can
   be". Then P(trip <= target) ~= share of pooled ratios
   <= target / predicted median. For the rain scenario the same ratio
   spread is reused and only the level shifts by the rain multiplier —
   an approximation, stated as such.

Honesty rules for this layer:
- Outputs from this module are estimates, never measurements, and the
  app labels them MODELLED with the validated error attached.
- Accuracy is measured by leave-one-route-out validation
  (src/validate_anytrip.py, outputs/anytrip_validation.md): predict a
  route the model never learned from, compare with its real data.

Live lookups (geocoding + routing) use free public OpenStreetMap
services — Nominatim for place names, OSRM for the road route. They
need internet, are demo-grade, and are only a way to get the trip's
distance; the traffic prediction itself is entirely from our dataset.
"""
from pathlib import Path

import numpy as np
import pandas as pd

RAIN_FLAGS = ["Rain", "Light Rain"]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = ("https://router.project-osrm.org/route/v1/driving/"
            "{lon1},{lat1};{lon2},{lat2}?overview=false")
HEADERS = {"User-Agent": "RouteWiseBLR/1.0"}


# ---------------------------------------------------------------- model
def build_model(df: pd.DataFrame, exclude_route_code: str | None = None) -> dict:
    """Learn the generalised Bengaluru pattern from the core 12 routes.

    exclude_route_code drops one route from the learning pool — used by
    leave-one-route-out validation so the predicted route is genuinely
    unseen. The Airport route is never in the pool (is_airport filter).
    """
    core = df[~df["is_airport"]].copy()
    if exclude_route_code is not None:
        core = core[core["route_code"] != exclude_route_code]
    core["min_per_km"] = core["duration"] / core["distance"]

    curve = (core.groupby(["day_type", "hour"])["min_per_km"]
             .agg(median_min_per_km="median",
                  p90_min_per_km=lambda s: s.quantile(0.90),
                  n="size")
             .reset_index())
    # Guarantee a full day_type x hour grid; a missing cell (should not
    # happen with this dataset) falls back to that day type's overall rate.
    grid = pd.MultiIndex.from_product([["weekday", "weekend"], range(24)],
                                      names=["day_type", "hour"])
    curve = curve.set_index(["day_type", "hour"]).reindex(grid).reset_index()
    for col, agg in [("median_min_per_km", "median"), ("p90_min_per_km", "median")]:
        fill = core.groupby("day_type")["min_per_km"].agg(agg)
        curve[col] = curve.apply(
            lambda r: fill[r["day_type"]] if pd.isna(r[col]) else r[col], axis=1)
    curve["n"] = curve["n"].fillna(0).astype(int)

    # Rain multiplier: weather-covered rows only (a weather snapshot is
    # present exactly when temp was recorded — the same definition the
    # project's weather analysis uses). Core routes only, like the model.
    w = core[core["temp"].notna()]
    is_rain = w["rsi_flag"].isin(RAIN_FLAGS)
    rain_rate = float(w.loc[is_rain, "min_per_km"].median())
    dry_rate = float(w.loc[~is_rain, "min_per_km"].median())
    rain_multiplier = rain_rate / dry_rate

    # Pooled ratio distribution for on-time probabilities (see docstring).
    hourly_median = core.groupby(["route_code", "day_type", "hour"])["duration"].transform("median")
    ratios = np.sort((core["duration"] / hourly_median).to_numpy())

    return {
        "curve": curve,
        "rain_multiplier": float(rain_multiplier),
        "rain_rows": int(is_rain.sum()),
        "dry_rows": int((~is_rain).sum()),
        "ratios": ratios,
        "n_learning_rows": int(len(core)),
        "n_learning_routes": int(core["route_code"].nunique()),
        "excluded_route_code": exclude_route_code,
    }


def predict(model: dict, distance_km: float, day_type: str, scenario: str = "no_rain") -> pd.DataFrame:
    """Per-hour predicted median and P90 minutes for a trip of distance_km.

    scenario is "no_rain" or "rain". Rain scales both median and P90 by
    the single global rain multiplier.
    """
    factor = model["rain_multiplier"] if scenario == "rain" else 1.0
    c = model["curve"][model["curve"]["day_type"] == day_type].sort_values("hour")
    return pd.DataFrame({
        "hour": c["hour"].to_numpy(),
        "median_min": c["median_min_per_km"].to_numpy() * distance_km * factor,
        "p90_min": c["p90_min_per_km"].to_numpy() * distance_km * factor,
    })


def on_time_prob(model: dict, predicted_median: float, target_minutes: float) -> float:
    """P(trip <= target) from the pooled ratio distribution.

    share of pooled (duration / route-hour-median) ratios that are
    <= target / predicted_median.
    """
    if predicted_median <= 0:
        return float("nan")
    threshold = target_minutes / predicted_median
    return float(np.searchsorted(model["ratios"], threshold, side="right") / len(model["ratios"]))


def recommend_window(model: dict, pred: pd.DataFrame, target_minutes: float,
                     start_hour: int = 6, end_hour: int = 22) -> dict:
    """Best departure hour in [start_hour, end_hour) for a predicted trip.

    Same rule as the measured planner: highest on-time probability,
    tie-break lowest P90, then earliest hour.
    """
    sub = pred[(pred["hour"] >= start_hour) & (pred["hour"] < end_hour)].copy()
    if sub.empty:
        return {"recommended_hour": None, "reason": "No hours in the selected range."}
    sub["on_time_prob"] = [on_time_prob(model, m, target_minutes) for m in sub["median_min"]]
    ranked = sub.sort_values(["on_time_prob", "p90_min", "hour"],
                             ascending=[False, True, True])
    best = ranked.iloc[0]
    return {
        "recommended_hour": int(best["hour"]),
        "median_min": float(best["median_min"]),
        "p90_min": float(best["p90_min"]),
        "on_time_prob": float(best["on_time_prob"]),
        "reason": "Highest modelled on-time probability in range; tie-break lowest P90.",
        "table": sub.sort_values("hour"),
    }


# ---------------------------------------------------------------- live lookups
def geocode_place(query: str) -> dict:
    """Resolve a place name to coordinates via OSM Nominatim.

    Appends a Bengaluru bias when the query does not already name the
    city. Never raises: returns {"ok": False, "error": ...} on failure.
    """
    import requests

    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "Please type a place name."}
    if "bengaluru" not in q.lower() and "bangalore" not in q.lower():
        q = f"{q}, Bengaluru, India"
    try:
        resp = requests.get(NOMINATIM_URL,
                            params={"q": q, "format": "json", "limit": 1},
                            headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # network down, timeout, bad JSON — one friendly path
        return {"ok": False,
                "error": f"Could not reach the place-lookup service ({type(exc).__name__}). "
                         "Check the internet connection and try again."}
    if not data:
        return {"ok": False, "error": f"Place not found: “{query}”. Try a fuller name, "
                                      "e.g. add a landmark or area name."}
    top = data[0]
    return {"ok": True, "lat": float(top["lat"]), "lon": float(top["lon"]),
            "display_name": top.get("display_name", q)}


def fetch_route(origin: dict, destination: dict) -> dict:
    """Road distance + free-flow duration between two geocoded points via OSRM.

    The OSRM duration is a no-traffic reference number only — RouteWise
    does NOT use it as the prediction; distance is what feeds the model.
    Never raises: returns {"ok": False, "error": ...} on failure.
    """
    import requests

    url = OSRM_URL.format(lon1=origin["lon"], lat1=origin["lat"],
                          lon2=destination["lon"], lat2=destination["lat"])
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {"ok": False,
                "error": f"Could not reach the routing service ({type(exc).__name__}). "
                         "Check the internet connection and try again."}
    routes = data.get("routes") or []
    if data.get("code") != "Ok" or not routes:
        return {"ok": False, "error": "No road route found between those two places."}
    best = routes[0]
    return {"ok": True,
            "distance_km": float(best["distance"]) / 1000.0,
            "freeflow_min": float(best["duration"]) / 60.0}


# ---------------------------------------------------------------- offline outputs
def _fmt_table(pred: pd.DataFrame, model: dict, target: float,
               start_hour: int, end_hour: int, rec_hour: int) -> list[str]:
    lines = ["| Departure hour | Predicted median (min) | Predicted P90 (min) | Modelled on-time % (≤ target) |",
             "|---|---|---|---|"]
    for _, r in pred[(pred["hour"] >= start_hour) & (pred["hour"] < end_hour)].iterrows():
        otp = on_time_prob(model, float(r["median_min"]), target) * 100
        mark = " **← recommended**" if int(r["hour"]) == rec_hour else ""
        lines.append(f"| {int(r['hour']):02d}:00 | {r['median_min']:.1f} | {r['p90_min']:.1f} | "
                     f"{otp:.0f} |{mark}")
    return lines


def main():
    from common import BASE, OUTPUTS, load_cleaned

    df = load_cleaned()
    model = build_model(df)
    curve = model["curve"]

    # ---- outputs/anytrip_model.md (plain words)
    wk = curve[curve["day_type"] == "weekday"].set_index("hour")
    lines = [
        "# Any-trip model — how the prediction works, in plain words",
        "",
        "The 13 routes in the main app are **measured**: real readings exist for them.",
        "This layer answers a different question — *\"what about a trip that is NOT one",
        "of those 13 routes?\"* — and its answers are **modelled estimates**, not",
        "measurements. Nothing about this layer changes any number in the main app.",
        "",
        "## The method, step by step",
        "",
        "1. **Learn the price of a kilometre.** On the 12 core measured routes, every",
        "   historical trip is divided by its distance to get *minutes per kilometre*.",
        "   For each hour of the day, separately for weekdays and weekends, we keep the",
        "   median and the P90 of that rate. That table is the whole \"city pattern\":",
        "   e.g. a weekday kilometre costs the median rate shown below.",
        "2. **One rain factor.** Rain was recorded only in part of the data, so instead",
        "   of inventing fine detail we compute a single multiplier:",
        f"   median minutes-per-km in rain / without rain, on weather-covered rows =",
        f"   **{model['rain_multiplier']:.3f}** (rain rows n={model['rain_rows']:,}, "
        f"no-rain rows n={model['dry_rows']:,}).",
        "   Choosing the \"rain\" scenario multiplies every predicted time by this one",
        "   factor. It is a level shift only — we do not claim rain changes the shape",
        "   of the day.",
        "3. **Predict a new trip.** Predicted median for an hour = that hour's median",
        "   minutes-per-km x the trip's distance in km (x the rain factor if rain).",
        "   P90 the same way. The trip's distance comes from the road route between",
        "   the two places (OSRM), not from a straight line.",
        "4. **On-time probability.** A median alone says nothing about risk, so we keep",
        "   the *spread* the measured routes showed: every historical trip divided by",
        "   the typical (median) trip for its own route, day type and hour gives a",
        "   \"ratio\" — 1.0 means exactly typical, 1.5 means 50% worse than typical.",
        "   Pooled over all core routes, those ratios are the model's spread. For a",
        "   target T and predicted median M, on-time probability = share of pooled",
        "   ratios <= T / M.",
        "5. **Recommendation.** Same rule as the measured planner: in the chosen hour",
        "   range, the hour with the highest on-time probability wins; ties break to",
        "   the lowest P90.",
        "",
        "## The learned pattern (weekday, minutes per km)",
        "",
        "| Hour | Median min/km | P90 min/km | Readings |",
        "|---|---|---|---|",
    ]
    for h, r in wk.iterrows():
        lines.append(f"| {int(h):02d}:00 | {r['median_min_per_km']:.2f} | "
                     f"{r['p90_min_per_km']:.2f} | {int(r['n']):,} |")
    lines += [
        "",
        f"Learned from {model['n_learning_rows']:,} hourly observations on "
        f"{model['n_learning_routes']} routes. The Airport route is excluded from",
        "learning (a ~34 km expressway trip is not a city route).",
        "",
        "## What this model cannot do",
        "",
        "- It knows nothing about a specific road — two trips of the same distance",
        "  get the same prediction, whatever roads they use. Corridor-specific",
        "  behaviour (a chronically jammed junction) is exactly what it misses.",
        "- Its accuracy is a measured fact, not a hope: see",
        "  `outputs/anytrip_validation.md` (leave-one-route-out). The modelled layer",
        "  is less accurate than the measured routes, and the app shows the error",
        "  next to every modelled answer.",
        "- Live place/route lookup needs the internet and free public servers;",
        "  this file and `outputs/anytrip_examples.md` are fully offline.",
        "",
        "Dataset: Traffic Monitor Lizard (CC BY 4.0) — see README.md.",
    ]
    (OUTPUTS / "anytrip_model.md").write_text("\n".join(lines) + "\n")

    # ---- outputs/anytrip_examples.md (pure model path, no live APIs)
    examples = [
        ("Example 1 — short cross-town trip, dry weekday",
         8.5, "weekday", "no_rain", 30.0,
         "A delivery run of 8.5 km on a weekday, no rain, target: arrive within 30 min."),
        ("Example 2 — longer trip, rainy weekday",
         14.0, "weekday", "rain", 45.0,
         "A 14 km weekday trip in rain, target: arrive within 45 min. Every time "
         f"below already includes the rain multiplier ({model['rain_multiplier']:.3f})."),
    ]
    lines = [
        "# Any-trip layer — worked examples (fully offline)",
        "",
        "Computed with the pure model path in `src/anytrip.py` from the frozen",
        "dataset — no live geocoding or routing calls — so anyone can reproduce",
        "these exact numbers by running `python3 anytrip.py` in `src/`.",
        "Search window for the recommendation: departures 06:00–21:00, the same",
        "default as the app's planner. All figures are MODELLED estimates.",
        "",
    ]
    for title, dist, day_type, scenario, target, blurb in examples:
        pred = predict(model, dist, day_type, scenario)
        rec = recommend_window(model, pred, target, 6, 22)
        lines += [f"## {title}", "", blurb, "",
                  f"**Recommended departure: {rec['recommended_hour']:02d}:00** — "
                  f"predicted median {rec['median_min']:.1f} min, P90 {rec['p90_min']:.1f} min, "
                  f"modelled on-time probability {rec['on_time_prob']*100:.0f}% "
                  f"against the {target:.0f}-minute target.", ""]
        lines += _fmt_table(pred, model, target, 6, 22, rec["recommended_hour"])
        lines.append("")
    (OUTPUTS / "anytrip_examples.md").write_text("\n".join(lines) + "\n")
    print(f"model: rain_multiplier={model['rain_multiplier']:.4f} "
          f"(rain n={model['rain_rows']}, dry n={model['dry_rows']}), "
          f"learning rows={model['n_learning_rows']}")
    print("wrote outputs/anytrip_model.md and outputs/anytrip_examples.md")


if __name__ == "__main__":
    main()
