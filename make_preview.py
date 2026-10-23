"""Offline interactive preview of RouteWise BLR.
Light theme is forced (dark-mode browsers made v1 unreadable) and Plotly JS is
embedded inline so charts work offline with no CDN."""
import json, pathlib, sys
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
cleaned = pd.read_csv(ROOT / "data/processed/cleaned_slim.csv",
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
html,body{background:#f3f6f5 !important;color:#102b3f !important}
body{font-family:Inter,system-ui,Arial,sans-serif;max-width:1180px;margin:24px auto;padding:0 22px}
h1{margin-bottom:9px;color:#ffffff !important;letter-spacing:-.045em;font-size:clamp(30px,4vw,44px)}
h2{margin-top:36px;border-bottom:1px solid #d9e3e0;padding-bottom:10px;color:#102b3f !important;letter-spacing:-.03em}
p,li,span,div{color:#102b3f}
.sub{color:#444444 !important}
table{border-collapse:collapse;width:100%;font-size:14px;background:#ffffff !important;border-radius:12px;overflow:hidden;box-shadow:0 6px 20px #102b3f0b}
th,td{border-bottom:1px solid #e4ebea;padding:9px 11px;text-align:right;background:#ffffff !important;color:#173449 !important}
th{background:#eaf2f0 !important;text-align:center;color:#315c62 !important;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
td:first-child,th:first-child{text-align:left}
.callout{background:#e6f5ef !important;border:1px solid #b5ded2;padding:14px 16px;border-radius:12px;color:#123a37 !important}
.warn{background:#fff5e8 !important;border:1px solid #f1d6ae;padding:14px 16px;border-radius:12px;color:#574326 !important}
footer{margin-top:40px;color:#657785 !important;font-size:13px;padding:20px 0;border-top:1px solid #d9e3e0}
.rw-hero{position:relative;overflow:hidden;border-radius:22px;padding:30px 32px;margin-bottom:24px;
 background:linear-gradient(115deg,#102b3f 0%,#163f50 58%,#126d69 100%);color:#f7fbfa;
 box-shadow:0 16px 38px #102b3f26;display:flex;justify-content:space-between;align-items:flex-end;gap:25px}
.rw-copy,.rw-stats{position:relative;z-index:1}
.rw-kicker{color:#a7e6db !important;font-size:10px;font-weight:750;letter-spacing:.19em;text-transform:uppercase}
.rw-hero p{color:#c4d5d8 !important;max-width:650px;line-height:1.55;margin:0}
.rw-stats{display:flex;gap:22px;flex-shrink:0}
.rw-stat{border-left:1px solid #ffffff47;padding-left:14px;min-width:78px}
.rw-stat b{display:block;color:#fff;font-size:23px}
.rw-stat small{display:block;color:#adcbc9;font-size:9px;text-transform:uppercase;letter-spacing:.1em;margin-top:5px}
.rw-hero:after{content:"";position:absolute;width:330px;height:330px;right:-70px;top:-210px;border:1px solid #dcfff829;border-radius:50%;box-shadow:0 0 0 28px #dcfff809,0 0 0 58px #dcfff808}
.planner{background:#f8faff;border:1px solid #cbd5e1;border-radius:12px;padding:18px;margin:18px 0}
.controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
.control label{display:block;font-weight:650;margin-bottom:6px}
.control input,.control select{box-sizing:border-box;width:100%;padding:10px;border:1px solid #94a3b8;border-radius:7px;background:white;color:#111827;font-size:15px}
.result{margin:16px 0;padding:14px;border-radius:8px;background:#eafbea;border:1px solid #57a857;font-size:17px}
.muted{color:#4b5563 !important;font-size:13px}
#planner-chart{height:330px}
</style></head><body>
<section class="rw-hero"><div class="rw-copy">
<div class="rw-kicker">BENGALURU · URBAN LOGISTICS</div>
<h1>Make every dispatch<br>more reliable.</h1>
<p>Route risk and dispatch planning from a year of historical journey estimates.
Targets are planning assumptions, not observed business requirements.</p></div>
<div class="rw-stats"><div class="rw-stat"><b>12</b><small>Core routes</small></div>
<div class="rw-stat"><b>110k</b><small>Hourly records</small></div>
<div class="rw-stat"><b>2026</b><small>Data through</small></div></div></section>
<p class="sub">Traffic Monitor Lizard dataset (CC BY 4.0), frozen snapshot 2026-10-21
(2025-09-25 to 2026-10-21). Offline preview using the cleaned hourly data.</p>""")

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

# ---- Interactive Dispatch Planner
parts.append("<h2>3 · Interactive Dispatch Planner</h2>")
parts.append("""<p>Enter a route, day type, travel-time target and departure-hour range.
The recommendation and table update from the historical readings below. The
target is a planning assumption; fewer than 30 readings at an hour is marked
low confidence and excluded from the recommendation.</p>
<section class="planner">
  <div class="controls">
    <div class="control"><label for="route-input">Route</label><select id="route-input"></select></div>
    <div class="control"><label for="day-input">Day type</label><select id="day-input"><option value="weekday">Weekday</option><option value="weekend">Weekend</option></select></div>
    <div class="control"><label for="target-input">Target travel time (minutes)</label><input id="target-input" type="number" min="10" max="180" value="40"></div>
    <div class="control"><label for="start-input">Search from (hour)</label><input id="start-input" type="number" min="0" max="23" value="6"></div>
    <div class="control"><label for="end-input">Search until (hour, exclusive)</label><input id="end-input" type="number" min="1" max="24" value="22"></div>
  </div>
  <div id="planner-result" class="result" aria-live="polite">Choose inputs to see a recommendation.</div>
  <div id="planner-chart"></div>
  <div id="planner-table"></div>
  <p class="muted">Historical estimates only. A recommendation is not a guarantee of future arrival time.</p>
</section>""")

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

by_route_day = {}
for (route_code, day_type, hour), group in cleaned.groupby(["route_code", "day_type", "hour"]):
    by_route_day.setdefault(route_code, {}).setdefault(day_type, {})[str(int(hour))] = sorted(
        float(value) for value in group["duration"].dropna().tolist())
planner_data = json.dumps(by_route_day, separators=(",", ":"), allow_nan=False)
route_options = "".join(
    f'<option value="{code}">{label}</option>'
    for code, label in sorted(code_to_full.items(), key=lambda item: item[1]))
default_route = next(
    (str(row["route_code"]) for _, row in rel.iterrows()
     if row["label_short"] == "East Outer Ring"),
    str(next(iter(code_to_full))))
interactive_script = """
<script>
const plannerData = __PLANNER_DATA__;
const routeSelect = document.getElementById("route-input");
const daySelect = document.getElementById("day-input");
const targetInput = document.getElementById("target-input");
const startInput = document.getElementById("start-input");
const endInput = document.getElementById("end-input");
const resultBox = document.getElementById("planner-result");
const tableBox = document.getElementById("planner-table");
routeSelect.innerHTML = __ROUTE_OPTIONS__;
routeSelect.value = __DEFAULT_ROUTE__;
function quantile(sorted, q) {
  if (!sorted.length) return NaN;
  const pos = (sorted.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}
function updatePlanner() {
  const route = routeSelect.value, day = daySelect.value;
  const target = Number(targetInput.value), start = Number(startInput.value), end = Number(endInput.value);
  if (!Number.isFinite(target) || target < 10 || target > 180 || !Number.isInteger(start) ||
      !Number.isInteger(end) || start < 0 || start > 23 || end < 1 || end > 24 || end <= start) {
    resultBox.textContent = "Enter a target from 10 to 180 minutes and a valid hour range (end is exclusive).";
    tableBox.innerHTML = ""; Plotly.purge("planner-chart"); return;
  }
  const rows = [];
  const hours = plannerData[route]?.[day] || {};
  for (let hour = start; hour < end; hour++) {
    const values = hours[String(hour)] || [];
    const n = values.length, median = quantile(values, .5), p90 = quantile(values, .9);
    let onTime = 0;
    for (const duration of values) if (duration <= target) onTime++;
    rows.push({hour, n, median, p90, probability: n ? onTime / n : NaN, lowConfidence: n < 30});
  }
  const eligible = rows.filter(row => !row.lowConfidence && row.n > 0);
  eligible.sort((a,b) => (b.probability-a.probability) || (a.p90-b.p90) ||
    (a.median-b.median) || (a.hour-b.hour));
  if (!eligible.length) {
    resultBox.textContent = "No departure hour in this range has at least 30 historical readings.";
  } else {
    const best = eligible[0];
    resultBox.innerHTML = "<b>Recommended departure: " + String(best.hour).padStart(2,"0") +
      ":00–" + String(best.hour).padStart(2,"0") + ":59</b> — historical on-time chance " +
      (best.probability*100).toFixed(0) + "% (median " + best.median.toFixed(1) +
      " min, P90 " + best.p90.toFixed(1) + " min, n=" + best.n + ").";
  }
  tableBox.innerHTML = "<table><thead><tr><th>Departure hour</th><th>Readings</th>" +
    "<th>Median (min)</th><th>P90 (min)</th><th>On-time %</th><th>Low confidence</th></tr></thead><tbody>" +
    rows.map(row => "<tr><td>" + String(row.hour).padStart(2,"0") + ":00</td><td>" + row.n +
      "</td><td>" + (Number.isFinite(row.median) ? row.median.toFixed(1) : "—") +
      "</td><td>" + (Number.isFinite(row.p90) ? row.p90.toFixed(1) : "—") +
      "</td><td>" + (Number.isFinite(row.probability) ? (row.probability*100).toFixed(1) + "%" : "—") +
      "</td><td>" + (row.lowConfidence ? "Yes" : "No") + "</td></tr>").join("") + "</tbody></table>";
  Plotly.react("planner-chart", [{type:"bar", x:rows.map(r=>String(r.hour).padStart(2,"0")+":00"),
    y:rows.map(r=>Number.isFinite(r.probability)?r.probability*100:null),
    marker:{color:rows.map(r=>r.lowConfidence?"#cbd5e1":"#4361ee")},
    hovertemplate:"%{x}<br>On-time: %{y:.1f}%<extra></extra>"}],
    {margin:{t:28,r:20,b:48,l:55},paper_bgcolor:"white",plot_bgcolor:"white",
     yaxis:{title:"Historical on-time chance (%)",range:[0,100]},xaxis:{title:"Departure hour"},
     font:{color:"#111827"}},{responsive:true,displayModeBar:false});
}
for (const el of [routeSelect,daySelect,targetInput,startInput,endInput]) el.addEventListener("input",updatePlanner);
for (const el of [routeSelect,daySelect]) el.addEventListener("change",updatePlanner);
updatePlanner();
</script>
""".replace("__PLANNER_DATA__", planner_data).replace("__ROUTE_OPTIONS__", route_options).replace(
    "__DEFAULT_ROUTE__", json.dumps(default_route))
html = "\n".join(parts).replace("</body></html>", interactive_script + "</body></html>")
dest = ROOT / "preview.html"
dest.write_text(html, encoding="utf-8")
print("wrote", dest, f"{len(html)/1024:.0f} KB")
for token in ["South Outer Ring", "East Outer Ring", "Recommended departure", "Rain",
              "color-scheme", "plotly"]:
    print(token, "present:", token.lower() in html.lower())
