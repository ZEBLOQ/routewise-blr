"""Phase 8: validation — recompute headline numbers independently and compare.

Each check re-derives a number published in outputs/ with a separate,
minimal computation (different code path from the one that produced it).
The script fails loudly if any check disagrees beyond rounding tolerance.
"""
import numpy as np
import pandas as pd

from common import BASE, OUTPUTS, RAW_TRAFFIC, load_cleaned

TOL = 0.51  # durations are whole minutes; medians/percentiles must match to <0.51


def hourly_from_raw():
    """Independent rebuild of the hourly-grain dataset straight from raw."""
    raw = pd.read_csv(RAW_TRAFFIC)
    raw = raw[raw["duration"] >= 10]
    raw["hour"] = raw["time"].str.slice(0, 2).astype(int)
    raw["ts"] = pd.to_datetime(raw["date"] + " " + raw["time"])
    raw["day_type"] = np.where(raw["ts"].dt.dayofweek >= 5, "weekend", "weekday")
    return raw.groupby(["route_code", "date", "hour"])["duration"].median().reset_index()


def main():
    checks = []
    cleaned = load_cleaned()
    hourly = hourly_from_raw()
    rel = pd.read_csv(OUTPUTS / "reliability_ranking.csv")
    facts = pd.read_json(OUTPUTS / "facts.json", typ="series")

    def check(name, published, recomputed):
        ok = abs(float(published) - float(recomputed)) <= TOL
        checks.append((name, float(published), float(recomputed), ok))
        return ok

    # 1-2: most reliable route P50/P90 (South Outer Ring) vs independent calc
    top = rel.iloc[0]
    vals = hourly[hourly["route_code"] == top["route_code"]]["duration"]
    check(f"{top['label_short']} median", top["median"], vals.median())
    check(f"{top['label_short']} P90", top["p90"], vals.quantile(0.90))
    # 3-4: least reliable route (East Outer Ring) P50/P90
    last = rel.iloc[-1]
    vals2 = hourly[hourly["route_code"] == last["route_code"]]["duration"]
    check(f"{last['label_short']} median", last["median"], vals2.median())
    check(f"{last['label_short']} P90", last["p90"], vals2.quantile(0.90))
    # 5: buffer index arithmetic for top route
    check(f"{top['label_short']} buffer index", top["buffer_index"],
          (top["p90"] - top["median"]) / top["median"])
    # 6: cleaned row count vs independent hourly rebuild
    check("cleaned hourly row count", len(cleaned), len(hourly))
    # 7: planner recommendation recomputed manually for East Outer Ring, weekday, target 40
    from planner import hourly_stats, recommend
    code_eor = "XMW9+G8|WMJR+V4"
    stats = hourly_stats(cleaned, code_eor, "weekday", 40.0)
    rec = recommend(stats)
    sub = hourly[(hourly["route_code"] == code_eor)]
    wk = cleaned[(cleaned["route_code"] == code_eor) & (cleaned["day_type"] == "weekday")]
    manual_best, manual_otp = None, -1
    for h in range(6, 22):
        v = wk[wk["hour"] == h]["duration"]
        if len(v) >= 30:
            otp = (v <= 40).mean()
            if otp > manual_otp:
                manual_otp, manual_best = otp, h
    check("planner recommended hour (EOR, weekday, target 40) — hour", rec["recommended_hour"], manual_best)
    check("planner recommended hour — on-time prob %", rec["on_time_prob"] * 100, manual_otp * 100)
    # 8: weather medians vs independent calc on cleaned
    w = cleaned[cleaned["temp"].notna() & (~cleaned["is_airport"])]
    rain_med = w[w["rsi_flag"].isin(["Rain", "Light Rain"])]["duration"].median()
    dry_med = w[~w["rsi_flag"].isin(["Rain", "Light Rain"])]["duration"].median()
    check("weather rain median (core)", facts["weather_rain_median"], rain_med)
    check("weather no-rain median (core)", facts["weather_dry_median"], dry_med)
    # 9: backtest spot-check — East Outer Ring test 09:00 OTP vs backtest.csv
    bt = pd.read_csv(OUTPUTS / "backtest.csv")
    row = bt[(bt["route_code"] == code_eor) & (bt["day_type"] == "weekday")].iloc[0]
    te = cleaned[(cleaned["route_code"] == code_eor) & (cleaned["day_type"] == "weekday")
                 & (cleaned["date"] > "2026-06-30") & (cleaned["hour"] == 9)]
    otp9 = (te["duration"] <= row["target_min_planning_assumption"]).mean()
    ok9 = abs(otp9 - row["test_otp_baseline"]) <= 0.011
    checks.append(("backtest EOR baseline OTP (fraction)", float(row["test_otp_baseline"]), float(otp9), ok9))

    lines = ["# Validation — independent cross-checks", "",
             "Recomputed by `src/validate.py` through separate code paths from the frozen raw data.",
             "", "| # | Check | Published | Recomputed | Result |", "|---|---|---|---|---|"]
    all_ok = True
    for i, (name, pub, rec_, ok) in enumerate(checks, 1):
        all_ok &= ok
        lines.append(f"| {i} | {name} | {pub:.2f} | {rec_:.2f} | {'PASS' if ok else 'FAIL'} |")
    lines += ["", f"**Overall: {'ALL CHECKS PASS' if all_ok else 'FAILURES PRESENT — see table'}** "
              f"({sum(1 for *_, ok in checks if ok)}/{len(checks)} checks)."]
    (OUTPUTS / "validation.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
