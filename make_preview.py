"""Static preview of RouteWise BLR — same 4 views, same output data as app.py.
Light theme is forced (dark-mode browsers made v1 unreadable) and Plotly JS is
embedded inline so charts work offline with no CDN."""
import pathlib, sys
import pandas as pd
import plotly.express as px
import plotly.io as pio

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
from planner import hourly_stats, recommend  # noqa: E402

OUT = ROOT / "outputs"
rel = pd.read_csv(OUT / "reliability_ranking.csv")
by_hour = pd.read_csv(OUT / "duration_by_hour.csv")
weather = pd.read_csv(OUT / "weather_overall.csv")
cleaned = pd.read_csv(ROOT / "data/processed/cleaned.csv",
                      usecols=["route_code", "day_type", "hour", "duration"])
routes = pd.read_csv(ROOT / "data/raw/csv-routes-bangalore.csv")
code_to_full = dict(zip(routes["route_code"], routes["label_full"]))

_first = [True]
def chart_html(fig):
    fig.update_layout(paper_bgcolor="white", plot_bgcolor="white",
                      font=dict(color="#111827"))
    if _first[0]:
        _first[0] = False
        return pio.to_html(fig, full_html=False, include_plotlyjs="inline")
    return pio.to_html(fig, full_html=False, include_plotlyjs=False)

parts = []
parts.append("""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="color-scheme" content="light only">
<title>RouteWise BLR — App Preview</title>
<style>
:root{color-scheme:light only}
html,body{background:#ffffff !important;color:#111827 !important}
body{font-family:system-ui,Arial,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px}
h1{margin-bottom:4px;color:#111827 !important}
h2{margin-top:36px;border-bottom:2px solid #4361ee;padding-bottom:4px;color:#1e3a8a !important}
p,li,span,div{color:#111827 !important}
.sub{color:#444444 !important}
table{border-collapse:collapse;width:100%;font-size:14px;background:#ffffff !important}
th,td{border:1px solid #bbbbbb;padding:5px 8px;text-align:right;background:#ffffff !important;color:#111827 !important}
th{background:#eef1ff !important;text-align:center}
td:first-child,th:first-child{text-align:left}
.callout{background:#eafbea !important;border:1px solid #57a857;padding:10px 14px;border-radius:6px;color:#111827 !important}
.warn{background:#fff7e0 !important;border:1px solid #d9a400;padding:10px 14px;border-radius:6px;color:#111827 !important}
footer{margin-top:40px;color:#555555 !important;font-size:13px}
</style></head><body>
<h1>RouteWise BLR — Urban Logistics Decision Support System</h1>
<p class="sub">Static preview of the Streamlit app (same views, same data). For a logistics/dispatch
planner: which departure window is most reliable for each Bengaluru route?<br>
Data: Traffic Monitor Lizard dataset (CC BY 4.0), frozen snapshot 2026-10-21
(2025-09-25 to 2026-10-21). Journey-time targets are planning assumptions set by the user —
not observed business requirements.</p>""")

# ---- View 1: Reliability Ranking
parts.append("<h2>1 · Reliability Ranking — core 12 routes (~10 km)</h2>")
parts.append("<p>Ranked by <b>buffer index</b> = (P90 − median) / median. Rank 1 = most reliable. "
             "The Airport route (~34 km) is excluded — not comparable.</p>")
show = rel[["reliability_rank", "label_short", "n", "median", "p90", "buffer_minutes", "buffer_index"]].copy()
show.columns = ["Rank", "Route", "Readings", "Median (min)", "P90 (min)", "Buffer (min)", "Buffer index"]
show["Buffer index"] = show["Buffer index"].round(2)
parts.append(show.to_html(index=False))
fig = px.bar(rel.sort_values("buffer_index"), x="buffer_index", y="label_short", orientation="h",
             labels={"buffer_index": "Buffer index", "label_short": "Route"})
parts.append(chart_html(fig))
parts.append('<div class="callout"><b>Headline:</b> East Outer Ring (Benniganahalli → Embassy TechVillage) '
             'ties for the fastest median (21 min) but is the <b>least reliable</b> route — P90 40 min, '
             'buffer 0.90. Fastest ≠ most reliable.</div>')

# ---- View 2: Route Explorer
parts.append("<h2>2 · Route Explorer — median travel time by departure hour</h2>")
parts.append("<p>Click route names in the legend to isolate one corridor.</p>")
core = by_hour[by_hour["is_airport"] == False]  # noqa: E712
fig2 = px.line(core, x="hour", y="median", color="label_short",
               labels={"hour": "Departure hour", "median": "Median duration (min)", "label_short": "Route"})
parts.append(chart_html(fig2))

# ---- View 3: Dispatch Planner (worked example)
parts.append("<h2>3 · Dispatch Planner — worked example</h2>")
eor = rel.loc[rel["label_short"] == "East Outer Ring", "route_code"]
if len(eor):
    code = eor.iloc[0]
    stats = hourly_stats(cleaned, code, "weekday", 40.0)
    rec = recommend(stats)
    parts.append(f"<p>Route: <b>{code_to_full.get(code, code)}</b> · Day type: <b>weekday</b> · "
                 f"Target (planning assumption): <b>≤ 40 min</b></p>")
    if rec.get("recommended_hour") is not None:
        parts.append(f'<div class="callout"><b>Recommended departure: {int(rec["recommended_hour"]):02d}:00</b> — '
                     f'on-time probability {rec["on_time_prob"]*100:.0f}%, median {rec["median_min"]:.0f} min, '
                     f'P90 {rec["p90_min"]:.0f} min.</div>')
    disp = stats.copy()
    disp["on_time_prob"] = (disp["on_time_prob"] * 100).round(0)
    disp.columns = ["Departure hour", "Readings", "Median (min)", "P90 (min)", "On-time % (≤40 min)", "Low confidence"]
    parts.append(disp.to_html(index=False))
parts.append("<p>In the live app you pick any route, day type and target and this table + recommendation update instantly.</p>")

# ---- View 4: Weather Impact
parts.append("<h2>4 · Weather Impact — rain vs no rain (core routes)</h2>")
w = weather.copy()
w["condition"] = w["is_rain"].map({True: "Rain", False: "No rain"})
fig4 = px.bar(w, x="condition", y="median", text="median",
              labels={"condition": "", "median": "Median duration (min)"})
parts.append(chart_html(fig4))
wt = w[["condition", "n", "median", "p90", "iqr"]].copy()
wt.columns = ["Condition", "Readings", "Median (min)", "P90 (min)", "IQR (min)"]
parts.append(wt.to_html(index=False))
parts.append('<div class="warn"><b>Scope:</b> weather was recorded only from 2026-05-24, on 78 days, '
             'with a gap 2026-07-29 → 2026-10-09. Rain is associated with longer, less predictable trips '
             '(median 30 vs 26 min; P90 45 vs 41) — association only, not proof of causation.</div>')

parts.append("<footer>RouteWise BLR · Built on the Traffic Monitor Lizard open dataset "
             "(thecont1/traffic-monitor-lizard), licensed CC BY 4.0. Full interactive app: "
             "Streamlit (app.py in the project folder).</footer></body></html>")

html = "\n".join(parts)
dest = ROOT / "preview.html"
dest.write_text(html, encoding="utf-8")
print("wrote", dest, f"{len(html)/1024:.0f} KB")
for token in ["South Outer Ring", "East Outer Ring", "Recommended departure", "Rain",
              "color-scheme", "plotly"]:
    print(token, "present:", token.lower() in html.lower())
