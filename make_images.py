"""Render the 4 RouteWise app views as PNG pages + one combined PDF.
Images/PDF carry their own white background, so no viewer dark-mode can break them."""
import pathlib, sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
from planner import hourly_stats, recommend  # noqa: E402

OUT = ROOT / "outputs"
IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)
plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white",
                     "savefig.facecolor": "white", "text.color": "#111827",
                     "axes.labelcolor": "#111827", "xtick.color": "#111827",
                     "ytick.color": "#111827", "axes.edgecolor": "#444444"})

rel = pd.read_csv(OUT / "reliability_ranking.csv")
by_hour = pd.read_csv(OUT / "duration_by_hour.csv")
weather = pd.read_csv(OUT / "weather_overall.csv")
cleaned = pd.read_csv(ROOT / "data/processed/cleaned.csv",
                      usecols=["route_code", "day_type", "hour", "duration"])
routes = pd.read_csv(ROOT / "data/raw/csv-routes-bangalore.csv")
code_to_full = dict(zip(routes["route_code"], routes["label_full"]))

HEADER = "RouteWise BLR — Urban Logistics Decision Support System"
SUB = "Data: Traffic Monitor Lizard dataset (CC BY 4.0), frozen snapshot 2026-10-21 (2025-09-25 to 2026-10-21)"

figs = []


# ---------- Page 0: Plan Any Trip (MODELLED) ----------
import sys as _sys
_sys.path.insert(0, str(ROOT / "src"))
from anytrip import build_model as _bm, predict as _pred, recommend_window as _recw  # noqa: E402
_model = _bm(pd.read_csv(ROOT / "data/processed/cleaned.csv", low_memory=False))
_pred_df = _pred(_model, 11.09, "weekday", "no_rain")
_rec = _recw(_model, _pred_df, 40.0, 6, 22)
fig, ax = plt.subplots(figsize=(11, 11.5))
ax.axis("off")
ax.set_title(f"{HEADER}\n0 · Plan Any Trip — worked example (MODELLED)\n"
             "Benniganahalli Metro Station \u2192 Embassy TechVillage · road distance 11.09 km (OSRM routing)\n"
             "weekday · no rain · target (planning assumption): \u2264 40 min",
             fontsize=12.5, fontweight="bold", pad=16)
_t = _rec["table"].copy()
_t["hour"] = _t["hour"].map(lambda h: f"{h:02d}:00")
_t["on_time_prob"] = (_t["on_time_prob"] * 100).round(0)
_t["median_min"] = _t["median_min"].round(1)
_t["p90_min"] = _t["p90_min"].round(1)
_t = _t[["hour", "median_min", "p90_min", "on_time_prob"]]
tt = ax.table(cellText=_t.values,
              colLabels=["Departure hour", "Predicted median (min)", "Predicted P90 (min)", "Modelled on-time %"],
              loc="center", cellLoc="center", bbox=[0.09, 0.22, 0.82, 0.62])
tt.auto_set_font_size(False); tt.set_fontsize(10); tt.scale(1, 1.5)
for j in range(4):
    tt[0, j].set_facecolor("#eef1ff")
_rrow = list(_t["hour"]).index(f"{int(_rec['recommended_hour']):02d}:00") + 1
for j in range(4):
    tt[_rrow, j].set_facecolor("#c8f2c8")
fig.text(0.5, 0.155, f"RECOMMENDED DEPARTURE: {int(_rec['recommended_hour']):02d}:00 — predicted median "
                     f"{_rec['median_min']:.0f} min, P90 {_rec['p90_min']:.0f} min, modelled on-time {_rec['on_time_prob']*100:.0f}% (green row).",
         ha="center", fontsize=11.5, fontweight="bold",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#eafbea", edgecolor="#57a857"))
fig.text(0.5, 0.095, "MODELLED estimate — from Bengaluru-wide patterns learned from the 13 measured corridors.\n"
                     "NOT measured on this exact trip.\nValidated error: 17.7% overall · 12.7% city trips · 76.8% (poor) airport-style trips.",
         ha="center", fontsize=9.5, fontweight="bold",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#fff7e0", edgecolor="#d9a400"))
fig.text(0.5, 0.03, "Sanity check: this pair IS one of the 13 measured routes — its real 06:00 median is 15 min (model predicts 21).\n"
                    "Rain option multiplies times by the learned rain factor 1.108. Places found via OpenStreetMap, routing via OSRM (free, no API key).",
         ha="center", fontsize=9, style="italic")
figs.append(("00-plan-any-trip", fig))

# ---------- Page 1: Reliability ranking ----------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 12),
                               gridspec_kw={"height_ratios": [1, 1.15]})
fig.suptitle(f"{HEADER}\n1 · Reliability Ranking — core 12 routes (~10 km)", fontsize=14, fontweight="bold")
d = rel.sort_values("buffer_index")
colors = ["#c0392b" if v == d["buffer_index"].max() else "#27ae60" if v == d["buffer_index"].min() else "#4361ee"
          for v in d["buffer_index"]]
ax1.barh(d["label_short"], d["buffer_index"], color=colors)
ax1.set_xlabel("Buffer index = (P90 − median) / median  ·  lower = more reliable")
for i, v in enumerate(d["buffer_index"]):
    ax1.text(v + 0.015, i, f"{v:.2f}", va="center", fontsize=9)
ax1.set_xlim(0, d["buffer_index"].max() * 1.15)
ax2.axis("off")
tbl = rel[["reliability_rank", "label_short", "n", "median", "p90", "buffer_minutes", "buffer_index"]].copy()
tbl["buffer_index"] = tbl["buffer_index"].round(2)
t = ax2.table(cellText=tbl.values,
              colLabels=["Rank", "Route", "Readings", "Median (min)", "P90 (min)", "Buffer (min)", "Buffer index"],
              loc="center", cellLoc="center", colWidths=[0.07,0.27,0.12,0.14,0.12,0.14,0.14])
t.auto_set_font_size(False); t.set_fontsize(9.5); t.scale(1, 1.55)
for j in range(len(tbl.columns)):
    t[0, j].set_facecolor("#eef1ff")
fig.text(0.5, 0.02, "Headline: East Outer Ring ties for fastest median (21 min) but is LEAST reliable (P90 40, buffer 0.90).", ha="center", fontsize=9.5, style="italic")
fig.text(0.5, 0.005, SUB, ha="center", fontsize=8, style="italic")
fig.tight_layout(rect=[0, 0.04, 1, 0.94])
figs.append(("01-reliability-ranking", fig))

# ---------- Page 2: Route explorer ----------
fig, ax = plt.subplots(figsize=(11, 7.5))
core = by_hour[by_hour["is_airport"] == False]  # noqa: E712
for name, g in core.groupby("label_short"):
    ax.plot(g["hour"], g["median"], marker="o", markersize=3, label=name)
ax.set_title(f"{HEADER}\n2 · Route Explorer — median travel time by departure hour (core 12 routes)",
             fontsize=13, fontweight="bold")
ax.set_xlabel("Departure hour"); ax.set_ylabel("Median duration (min)")
ax.set_xticks(range(0, 24)); ax.grid(alpha=0.3)
ax.legend(fontsize=8, loc="upper left", framealpha=0.95)
fig.text(0.5, 0.03, "Evening peak is worst on 9 of 12 routes (pooled median 35 min vs 30 morning, 19 night).", ha="center", fontsize=9.5, style="italic")
fig.text(0.5, 0.008, SUB, ha="center", fontsize=8, style="italic")
fig.tight_layout(rect=[0, 0.06, 1, 0.95])
figs.append(("02-route-explorer", fig))

# ---------- Page 3: Dispatch planner ----------
fig, ax = plt.subplots(figsize=(11, 11))
ax.axis("off")
code = rel.loc[rel["label_short"] == "East Outer Ring", "route_code"].iloc[0]
stats = hourly_stats(cleaned, code, "weekday", 40.0)
rec = recommend(stats)
ax.set_title(f"{HEADER}\n3 · Dispatch Planner — worked example\n"
             "Route: East Outer Ring — Benniganahalli Metro → Embassy TechVillage\nweekday · target (planning assumption): ≤ 40 min",
             fontsize=12.5, fontweight="bold", pad=18)
disp = stats.copy()
disp["departure_hour"] = disp["departure_hour"].map(lambda h: f"{h:02d}:00")
disp["on_time_prob"] = (disp["on_time_prob"] * 100).round(0)
disp["median_min"] = disp["median_min"].round(1)
disp["p90_min"] = disp["p90_min"].round(1)
disp = disp[["departure_hour", "n", "median_min", "p90_min", "on_time_prob", "low_confidence"]]
t = ax.table(cellText=disp.values,
             colLabels=["Departure hour", "Readings", "Median (min)", "P90 (min)", "On-time %", "Low confidence"],
             loc="center", cellLoc="center", bbox=[0.05, 0.18, 0.9, 0.68])
t.auto_set_font_size(False); t.set_fontsize(10); t.scale(1, 1.5)
for j in range(len(disp.columns)):
    t[0, j].set_facecolor("#eef1ff")
rec_row = disp.index[disp["departure_hour"] == f"{int(rec['recommended_hour']):02d}:00"][0] + 1
for j in range(len(disp.columns)):
    t[rec_row, j].set_facecolor("#c8f2c8")
fig.text(0.5, 0.08, f"RECOMMENDED DEPARTURE: {int(rec['recommended_hour']):02d}:00 — on-time probability "
                    f"{rec['on_time_prob']*100:.0f}%, median {rec['median_min']:.0f} min, P90 {rec['p90_min']:.0f} min (green row).",
         ha="center", fontsize=12, fontweight="bold",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#eafbea", edgecolor="#57a857"))
fig.text(0.5, 0.02, "In the live app you pick any route, day type and target — this table and recommendation update instantly.",
         ha="center", fontsize=9, style="italic")
figs.append(("03-dispatch-planner", fig))

# ---------- Page 4: Weather ----------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 6), gridspec_kw={"width_ratios": [1.2, 1]})
w = weather.copy(); w["condition"] = w["is_rain"].map({True: "Rain", False: "No rain"})
x = range(len(w))
ax1.bar([i - 0.2 for i in x], w["median"], width=0.4, label="Median", color="#4361ee")
ax1.bar([i + 0.2 for i in x], w["p90"], width=0.4, label="P90", color="#c0392b")
ax1.set_xticks(list(x)); ax1.set_xticklabels(w["condition"])
ax1.set_ylabel("Duration (min)"); ax1.legend(); ax1.grid(axis="y", alpha=0.3)
for i, row in enumerate(w.itertuples()):
    ax1.text(i - 0.2, row.median + 1, f"{row.median:.0f}", ha="center", fontsize=10)
    ax1.text(i + 0.2, row.p90 + 1, f"{row.p90:.0f}", ha="center", fontsize=10)
ax2.axis("off")
wt = w[["condition", "n", "median", "p90", "iqr"]].copy()
t = ax2.table(cellText=wt.values, colLabels=["Condition", "Readings", "Median", "P90", "IQR"],
              loc="center", cellLoc="center")
t.auto_set_font_size(False); t.set_fontsize(10); t.scale(1, 1.8)
for j in range(5):
    t[0, j].set_facecolor("#eef1ff")
fig.suptitle(f"{HEADER}\n4 · Weather Impact — rain vs no rain (core routes)", fontsize=13, fontweight="bold")
fig.text(0.5, 0.01, "Scope: weather recorded only from 2026-05-24, on 78 days, gap 2026-07-29 → 2026-10-09.\n"
                    "Rain is ASSOCIATED with longer, less predictable trips — association only, not proof of causation.",
         ha="center", fontsize=9, style="italic")
fig.tight_layout(rect=[0, 0.07, 1, 0.92])
figs.append(("04-weather-impact", fig))

pdf_path = ROOT / "RouteWise-BLR-app.pdf"
with PdfPages(pdf_path) as pdf:
    for name, fig in figs:
        png = IMG / f"{name}.png"
        fig.savefig(png, dpi=150)
        pdf.savefig(fig)
        plt.close(fig)
        print("saved", png)
print("saved", pdf_path)
