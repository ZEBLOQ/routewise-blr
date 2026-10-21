"""Validation for the any-trip layer: leave-one-route-out (LOO).

For each of the 13 routes in turn:
- rebuild the generalised pattern model WITHOUT that route
  (src/anytrip.build_model with exclude_route_code),
- predict that route's median trip time for every (day type, hour)
  cell from its median distance alone,
- compare against the route's ACTUAL hourly medians in cleaned.csv.

Metrics per route and overall: MAPE on hourly medians and MAE in
minutes, reported for all 13 routes — no cherry-picking — and split
core-12 vs Airport.

Note on the Airport route: it is never part of the model's learning
pool by design, so its LOO check is a fully out-of-sample test of
whether a city-route pattern transfers to a 34 km expressway trip.
Its error is expected to be the honest worst case, and it is reported,
not hidden.
"""
import json

import numpy as np
import pandas as pd

from anytrip import build_model, predict
from common import OUTPUTS, load_cleaned, load_routes


def main():
    cleaned = load_cleaned()
    routes = load_routes()

    rows = []
    pooled = []  # cell-level APEs: (group, ape, abs_err)
    for _, route in routes.iterrows():
        code = route["route_code"]
        group = "airport_separate" if route["is_airport"] else "core12"
        model = build_model(cleaned, exclude_route_code=code)

        sub = cleaned[cleaned["route_code"] == code]
        dist_km = float(sub["distance"].median())
        actual = (sub.groupby(["day_type", "hour"])["duration"].median()
                  .rename("actual").reset_index())

        preds = []
        for day_type in ["weekday", "weekend"]:
            p = predict(model, dist_km, day_type, "no_rain")
            p["day_type"] = day_type
            preds.append(p)
        pred = pd.concat(preds).rename(columns={"median_min": "predicted"})
        merged = actual.merge(pred[["day_type", "hour", "predicted"]],
                              on=["day_type", "hour"], how="inner")
        ape = (merged["predicted"] - merged["actual"]).abs() / merged["actual"]
        abs_err = (merged["predicted"] - merged["actual"]).abs()
        rows.append({
            "route_code": code,
            "label_short": route["label_short"],
            "group": group,
            "median_distance_km": round(dist_km, 1),
            "n_cells": int(len(merged)),
            "mape_pct": round(float(ape.mean() * 100), 2),
            "mae_min": round(float(abs_err.mean()), 2),
        })
        for a, e in zip(ape, abs_err):
            pooled.append((group, float(a), float(e)))

    per_route = pd.DataFrame(rows).sort_values("mape_pct", ascending=False)
    pooled_df = pd.DataFrame(pooled, columns=["group", "ape", "abs_err"])
    overall_mape = float(pooled_df["ape"].mean() * 100)
    overall_mae = float(pooled_df["abs_err"].mean())
    core = pooled_df[pooled_df["group"] == "core12"]
    airport = pooled_df[pooled_df["group"] == "airport_separate"]
    core_mape = float(core["ape"].mean() * 100)
    airport_mape = float(airport["ape"].mean() * 100)
    worst = per_route.iloc[0]
    best = per_route.iloc[-1]

    per_route.to_csv(OUTPUTS / "anytrip_validation.csv", index=False)

    facts = {
        "overall_mape_pct": round(overall_mape, 1),
        "overall_mae_min": round(overall_mae, 1),
        "core12_mape_pct": round(core_mape, 1),
        "airport_mape_pct": round(airport_mape, 1),
        "worst_route": str(worst["label_short"]),
        "worst_route_mape_pct": float(worst["mape_pct"]),
        "best_route": str(best["label_short"]),
        "best_route_mape_pct": float(best["mape_pct"]),
        "n_routes_validated": int(len(per_route)),
        "n_cells_total": int(len(pooled_df)),
    }
    (OUTPUTS / "anytrip_facts.json").write_text(json.dumps(facts, indent=2) + "\n")

    lines = [
        "# Any-trip validation — leave-one-route-out",
        "",
        f"**Honest headline: predicting a route the model has never seen, from its",
        f"distance alone, is off by {overall_mape:.1f}% on average** (MAPE on hourly",
        f"medians across all {len(pooled_df)} route × day-type × hour cells of all 13",
        f"routes; MAE {overall_mae:.1f} min). Core 12 routes: **{core_mape:.1f}%**.",
        f"Airport route: **{airport_mape:.1f}%** — it is never in the learning pool,",
        "so this is a fully out-of-sample check, and the city-pattern model transfers",
        "to a 34 km expressway trip only as well as that number says.",
        "",
        "Method: for each route, rebuild the pattern model from the other routes",
        "only (the held-out route contributes nothing — not its curve, not its rain",
        "rows, not its ratios), predict each (day type, hour) median as",
        "minutes-per-km x the route's median distance, and compare with the route's",
        "actual hourly medians in cleaned.csv. Dry scenario throughout. All 13",
        "routes are reported; worst first.",
        "",
        "| Route | Group | Median distance (km) | Cells | MAPE % | MAE (min) |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in per_route.iterrows():
        lines.append(f"| {r['label_short']} | {r['group']} | {r['median_distance_km']:.1f} "
                     f"| {int(r['n_cells'])} | {r['mape_pct']:.2f} | {r['mae_min']:.2f} |")
    lines += [
        "",
        f"Worst predicted route: **{worst['label_short']}** (MAPE {worst['mape_pct']:.1f}%) — "
        f"its corridor behaviour differs most from the city-wide pattern, which is",
        f"exactly the kind of route-specific effect a distance-only model cannot see.",
        f"Best predicted route: **{best['label_short']}** (MAPE {best['mape_pct']:.1f}%).",
        "",
        "Reproduce: `cd src && python3 validate_anytrip.py`. Per-route numbers:",
        "`outputs/anytrip_validation.csv`. Summary consumed by the app banner:",
        "`outputs/anytrip_facts.json`.",
    ]
    (OUTPUTS / "anytrip_validation.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
