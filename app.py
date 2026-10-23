"""RouteWise BLR — Urban Logistics Decision Support System.

A decision-support app (not a traffic dashboard): it ranks Bengaluru
routes by reliability and recommends a dispatch window against a
user-set journey-time target.

Data: Traffic Monitor Lizard (https://github.com/thecont1/traffic-monitor-lizard),
dataset licensed CC BY 4.0. Frozen snapshot 2026-10-21; see data/raw/SNAPSHOT.md.
All app code written from scratch for this project.
"""
import json
import sys
from datetime import datetime as dt_datetime
from datetime import time as dt_time
from datetime import timedelta as dt_timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from anytrip import build_model, fetch_route, geocode_place, on_time_prob, predict  # noqa: E402
from common import OUTPUTS, load_cleaned, load_routes  # noqa: E402
from deliverby import (  # noqa: E402
    arrival_table_measured_span,
    arrival_table_modelled_span,
    fmt_dt,
    latest_safe_departure,
)
from planner import hourly_stats, recommend  # noqa: E402

try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

st.set_page_config(
    page_title="RouteWise BLR · Dispatch Intelligence",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def get_data():
    return load_cleaned()


@st.cache_data
def get_routes():
    return load_routes()


df = get_data()
routes = get_routes()
label_to_code = dict(zip(routes["label_full"], routes["route_code"]))

dashboard_css = (Path(__file__).parent / "assets" / "dashboard.css").read_text(encoding="utf-8")
st.markdown(f"<style>{dashboard_css}</style>", unsafe_allow_html=True)

core_routes = int(df.loc[~df["is_airport"], "route_code"].nunique())
obs_count = f"{len(df):,}"
date_max = pd.to_datetime(df["date"]).max().strftime("%b %Y")
st.sidebar.markdown(
    '<div class="rw-brand"><div class="rw-brand-mark">↗</div>'
    '<div><div class="rw-brand-name">ROUTEWISE <span style="color:#79d8c8">BLR</span></div>'
    '<div class="rw-brand-sub">Dispatch intelligence</div></div></div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown("#### WORKSPACE")

view = st.sidebar.radio(
    "Choose a view",
    ["Plan Any Trip", "Reliability Ranking", "Route Explorer", "Dispatch Planner",
     "Deliver-by Planner", "Weather Impact"],
    format_func=lambda item: {
        "Plan Any Trip": "⌖   Plan any trip",
        "Reliability Ranking": "◈   Reliability ranking",
        "Route Explorer": "⌁   Route explorer",
        "Dispatch Planner": "⏱   Dispatch planner",
        "Deliver-by Planner": "↩   Deliver-by planner",
        "Weather Impact": "☼   Weather impact",
    }[item],
)
st.sidebar.markdown(
    '<div class="rw-side-note"><strong>DATA SNAPSHOT</strong>'
    '<p>Traffic Monitor Lizard<br>25 Sep 2025 — 21 Oct 2026<br>'
    'Historical estimates · not live traffic</p></div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<section class="rw-hero"><div class="rw-hero-copy">'
    f'<div class="rw-kicker">BENGALURU · URBAN LOGISTICS</div>'
    f'<h1>Make every dispatch<br>more reliable.</h1>'
    f'<p>Explore route risk and plan around travel-time variation using a year of '
    f'historical journey estimates.</p></div>'
    f'<div class="rw-hero-stats"><div class="rw-stat"><strong>{core_routes}</strong>'
    f'<span>Core routes</span></div><div class="rw-stat"><strong>{obs_count}</strong>'
    f'<span>Hourly records</span></div><div class="rw-stat"><strong>{date_max}</strong>'
    f'<span>Data through</span></div></div></section>',
    unsafe_allow_html=True,
)


def show_chart(fig):
    """Apply RouteWise's shared chart styling."""
    if not HAS_PLOTLY:
        return
    fig.update_layout(
        template="plotly_white",
        font={"family": "Inter, ui-sans-serif, system-ui, sans-serif", "color": "#173449", "size": 12},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        colorway=["#0c8277", "#f28a65", "#4676a9", "#d5a644", "#7359a6"],
        margin={"l": 16, "r": 18, "t": 35, "b": 12},
        hoverlabel={"bgcolor": "#102b3f", "font_color": "#ffffff", "bordercolor": "#102b3f"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#dfe8e6")
    fig.update_yaxes(showgrid=True, gridcolor="#edf1f0", zeroline=False)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


@st.cache_resource
def get_model():
    return build_model(load_cleaned())


@st.cache_data(show_spinner=False)
def cached_geocode(query: str):
    return geocode_place(query)


@st.cache_data(show_spinner=False)
def cached_route(origin: dict, destination: dict):
    return fetch_route(origin, destination)


def _validated_error_pct() -> str:
    try:
        facts = json.loads((OUTPUTS / "anytrip_facts.json").read_text())
        return f"{facts['overall_mape_pct']:.1f}"
    except Exception:
        return "see outputs/anytrip_validation.md"


# ---------------------------------------------------------------- any trip (MODELLED)
if view == "Plan Any Trip":
    st.header("Plan any trip — modelled estimate for routes we did not measure")
    st.warning(
        "**MODELLED estimate** — predicted from Bengaluru-wide patterns learned from "
        "13 measured corridors. Not measured on this exact route. "
        f"Validated average error: **{_validated_error_pct()}%** (leave-one-route-out). "
        "The Reliability Ranking, Route Explorer, Dispatch Planner and Weather Impact "
        "views are MEASURED — every number there comes from actual readings on that "
        "route (the Deliver-by Planner is MEASURED too, in its measured mode). "
        "This view trades that certainty for coverage: "
        "it can say something about any trip, with the error stated up front."
    )
    st.write(
        "How it works: the model learned, from the 12 core measured routes, how many "
        "minutes one kilometre of Bengaluru road typically costs at each hour "
        "(median and P90, weekday/weekend), plus one global rain multiplier. "
        "Your trip's road distance comes from OpenStreetMap routing (OSRM); place "
        "names are resolved by Nominatim. Details: outputs/anytrip_model.md; "
        "accuracy audit: outputs/anytrip_validation.md."
    )
    with st.form("anytrip_form"):
        c1, c2 = st.columns(2)
        origin_text = c1.text_input("Start (origin)", value="Benniganahalli Metro Station")
        dest_text = c2.text_input("Destination", value="Embassy TechVillage")
        c3, c4 = st.columns(2)
        day_type = c3.radio("Day type", ["weekday", "weekend"], horizontal=True)
        scenario_label = c4.radio("Weather scenario", ["No rain", "Rain"], horizontal=True)
        target = st.number_input("Target travel time (minutes) — planning assumption",
                                 min_value=5, max_value=300, value=40)
        c5, c6 = st.columns(2)
        start_hour = c5.slider("Search from (hour)", 0, 23, 6)
        end_hour = c6.slider("Search until (hour, exclusive)", 1, 24, 22)
        submitted = st.form_submit_button("Plan this trip")

    if submitted:
        if end_hour <= start_hour:
            st.error("End hour must be after start hour.")
        else:
            origin = cached_geocode(origin_text)
            dest = cached_geocode(dest_text)
            if not origin.get("ok"):
                st.error(f"Start place problem — {origin.get('error', 'lookup failed.')}")
            elif not dest.get("ok"):
                st.error(f"Destination problem — {dest.get('error', 'lookup failed.')}")
            else:
                route = cached_route(origin, dest)
                if not route.get("ok"):
                    st.error(route.get("error", "Routing failed. Please try again."))
                else:
                    st.session_state["anytrip_result"] = {
                        "origin": origin, "dest": dest, "route": route,
                        "day_type": day_type,
                        "scenario": "rain" if scenario_label == "Rain" else "no_rain",
                        "target": float(target),
                        "start_hour": int(start_hour), "end_hour": int(end_hour),
                    }

    result = st.session_state.get("anytrip_result")
    if result:
        model = get_model()
        pred = predict(model, result["route"]["distance_km"],
                       result["day_type"], result["scenario"])
        window = pred[(pred["hour"] >= result["start_hour"])
                      & (pred["hour"] < result["end_hour"])].copy()
        window["on_time_prob"] = [on_time_prob(model, m, result["target"])
                                  for m in window["median_min"]]
        ranked = window.sort_values(["on_time_prob", "p90_min", "hour"],
                                    ascending=[False, True, True])
        best = ranked.iloc[0]
        st.success(
            f"Recommended departure: **{int(best['hour']):02d}:00–{int(best['hour']):02d}:59** — "
            f"modelled on-time probability {best['on_time_prob']*100:.0f}% "
            f"(predicted median {best['median_min']:.0f} min, P90 {best['p90_min']:.0f} min) "
            f"against your {result['target']:.0f}-minute planning target."
        )
        st.write(
            f"Route found: **{result['route']['distance_km']:.1f} km** by road "
            f"(OSRM free-flow reference {result['route']['freeflow_min']:.0f} min with no "
            "traffic — shown for reference only; the prediction below is RouteWise's, "
            "from the historical pattern). "
            f"Day type: {result['day_type']}; scenario: "
            f"{'rain (global multiplier applied)' if result['scenario'] == 'rain' else 'no rain'}."
        )
        show = window.sort_values("hour").copy()
        show["on_time_prob"] = (show["on_time_prob"] * 100).round(0)
        show = show.rename(columns={
            "hour": "Departure hour", "median_min": "Predicted median (min)",
            "p90_min": "Predicted P90 (min)", "on_time_prob": "Modelled on-time %"})
        st.dataframe(show, width="stretch")
        if HAS_PLOTLY:
            fig = px.line(pred.sort_values("hour"), x="hour",
                          y=["median_min", "p90_min"], markers=True,
                          labels={"value": "Predicted minutes", "hour": "Departure hour",
                                  "variable": ""})
            fig.add_hline(y=result["target"], line_dash="dash",
                          annotation_text="Your target (planning assumption)")
            show_chart(fig)
        st.caption("Modelled estimates — not measurements. Place lookup: OpenStreetMap "
                   "Nominatim; routing: OSRM (free public servers, demo-grade). "
                   "Traffic pattern: Traffic Monitor Lizard dataset (CC BY 4.0).")

# ---------------------------------------------------------------- ranking
elif view == "Reliability Ranking":
    st.header("Route reliability ranking — core 12 routes (~10 km)")
    st.write(
        "Ranked by **buffer index** = (P90 − median) / median: how much extra time you "
        "must budget over the typical trip for a 9-in-10 on-time plan. Rank 1 = most "
        "reliable. The Airport route (~34 km) is excluded — it is not comparable."
    )
    rel = pd.read_csv(OUTPUTS / "reliability_ranking.csv")
    show = rel[["reliability_rank", "label_short", "n", "median", "p90",
                "buffer_minutes", "buffer_index"]].rename(columns={
        "reliability_rank": "Rank", "label_short": "Route", "n": "Readings (hourly obs.)",
        "median": "Median (min)", "p90": "P90 (min)",
        "buffer_minutes": "Buffer (min)", "buffer_index": "Buffer index"})
    st.dataframe(show, width="stretch")
    if HAS_PLOTLY:
        fig = px.bar(rel.sort_values("buffer_index"), x="buffer_index", y="label_short",
                     orientation="h", labels={"buffer_index": "Buffer index", "label_short": "Route"})
        show_chart(fig)
    st.info("Headline: the fastest route by median is not the most reliable — "
            "see outputs/findings.md for the concrete route example.")

# ---------------------------------------------------------------- explorer
elif view == "Route Explorer":
    st.header("Route explorer — travel time by departure hour")
    full_label = st.selectbox("Route", list(label_to_code.keys()))
    day_type = st.radio("Day type", ["weekday", "weekend"], horizontal=True)
    code = label_to_code[full_label]
    sub = df[(df["route_code"] == code) & (df["day_type"] == day_type)]
    by_hour = sub.groupby("hour")["duration"].agg(
        n="size", median="median", p90=lambda s: s.quantile(0.90)).reset_index()
    if HAS_PLOTLY:
        fig = px.line(by_hour, x="hour", y=["median", "p90"], markers=True,
                      labels={"value": "Minutes", "hour": "Departure hour", "variable": ""})
        show_chart(fig)
    else:
        st.line_chart(by_hour.set_index("hour")[["median", "p90"]])
    st.dataframe(by_hour, width="stretch")
    wk = df[(df["route_code"] == code)].groupby(["day_type", "time_bucket"])["duration"].median().unstack()
    st.subheader("Median duration by time bucket (minutes)")
    st.dataframe(wk.round(1), width="stretch")

# ---------------------------------------------------------------- planner
elif view == "Dispatch Planner":
    st.header("Dispatch-window planner")
    st.write(
        "Pick a route, a day type and a journey-time target (**planning assumption**). "
        "The planner scores every departure hour in your search range on past trips: "
        "on-time probability = share of trips that finished within the target. "
        "Hours with fewer than 30 readings are flagged low-confidence and excluded "
        "from the recommendation. Recommendation = highest on-time probability, "
        "tie-break lowest P90."
    )
    full_label = st.selectbox("Route", list(label_to_code.keys()))
    code = label_to_code[full_label]
    day_type = st.radio("Day type", ["weekday", "weekend"], horizontal=True)
    route_median = float(df[(df["route_code"] == code) & (df["day_type"] == day_type)]["duration"].median())
    target = st.number_input("Target travel time (minutes) — planning assumption",
                             min_value=10, max_value=180, value=int(np.ceil(route_median)))
    c1, c2 = st.columns(2)
    start_hour = c1.slider("Search from (hour)", 0, 23, 6)
    end_hour = c2.slider("Search until (hour, exclusive)", 1, 24, 22)
    if end_hour <= start_hour:
        st.error("End hour must be after start hour.")
    else:
        stats = hourly_stats(df, code, day_type, float(target), start_hour, end_hour)
        rec = recommend(stats)
        if rec["recommended_hour"] is None:
            st.warning(rec["reason"])
        else:
            st.success(
                f"Recommended departure: **{rec['recommended_hour']:02d}:00–{rec['recommended_hour']:02d}:59** "
                f"— on-time probability {rec['on_time_prob']*100:.0f}% "
                f"(median {rec['median_min']:.0f} min, P90 {rec['p90_min']:.0f} min, n={rec['n']})."
            )
        show = stats.copy()
        show["on_time_prob"] = (show["on_time_prob"] * 100).round(1)
        show = show.rename(columns={
            "departure_hour": "Hour", "n": "Readings", "median_min": "Median (min)",
            "p90_min": "P90 (min)", "on_time_prob": "On-time %", "low_confidence": "Low confidence"})
        st.dataframe(show, width="stretch")
        if HAS_PLOTLY:
            fig = px.bar(stats, x="departure_hour", y="on_time_prob",
                         labels={"departure_hour": "Departure hour", "on_time_prob": "On-time probability"})
            show_chart(fig)

# ---------------------------------------------------------------- deliver-by
elif view == "Deliver-by Planner":
    st.header("Deliver-by planner — plan backward from a delivery deadline")
    st.write(
        "Companies rarely ask \"how long is the trip?\" — they ask **\"the goods are "
        "ready at this time, the customer wants delivery by that time: when is the "
        "latest we can safely leave?\"** That is backward scheduling (the same idea "
        "as planning a production job backward from its due date): fix the deadline, "
        "subtract the travel time hour by hour, and find the latest departure whose "
        "on-time chance still meets the safety level (**≥95%**)."
    )
    st.caption(
        "Weekday/weekend traffic is taken from each departure's own date — a "
        "Friday-night departure uses weekday data, a Saturday-morning one uses "
        "weekend data. Times are hourly because the readings are hourly."
    )
    mode = st.radio("Trip", ["Measured route", "Any trip (modelled)"], horizontal=True)
    distance_km = None
    code = None
    scenario = "no_rain"
    if mode == "Measured route":
        st.info("MEASURED — every probability below is counted from this route's own "
                "historical readings.")
        full_label = st.selectbox("Route", list(label_to_code.keys()), key="db_route")
        code = label_to_code[full_label]
    else:
        st.warning(
            "**MODELLED estimate** — predicted from Bengaluru-wide patterns learned from "
            "13 measured corridors. Not measured on this exact route. "
            f"Validated average error: **{_validated_error_pct()}%** (leave-one-route-out). "
            "In measured mode this same view counts a route's own readings instead."
        )
        oc, dc = st.columns(2)
        origin_text = oc.text_input("Start (origin)", value="Benniganahalli Metro Station",
                                    key="db_origin")
        dest_text = dc.text_input("Destination", value="Embassy TechVillage", key="db_dest")
        scenario_label = st.radio("Weather scenario", ["No rain", "Rain"],
                                  horizontal=True, key="db_scenario")
        scenario = "rain" if scenario_label == "Rain" else "no_rain"
        if st.button("Find route for this trip"):
            origin = cached_geocode(origin_text)
            dest = cached_geocode(dest_text)
            if not origin.get("ok"):
                st.error(f"Start place problem — {origin.get('error', 'lookup failed.')}")
            elif not dest.get("ok"):
                st.error(f"Destination problem — {dest.get('error', 'lookup failed.')}")
            else:
                route = cached_route(origin, dest)
                if not route.get("ok"):
                    st.error(route.get("error", "Routing failed. Please try again."))
                else:
                    st.session_state["deliverby_route"] = route
        db_route = st.session_state.get("deliverby_route")
        if db_route:
            distance_km = db_route["distance_km"]
            st.write(f"Route found: **{distance_km:.1f} km** by road "
                     f"(OSRM free-flow reference {db_route['freeflow_min']:.0f} min — "
                     "reference only; predictions come from the historical pattern).")
        else:
            st.write("Press **Find route for this trip** to resolve the two places "
                     "before planning.")
    _today = dt_datetime.now().date()
    c1, c2 = st.columns(2)
    with c1:
        ready_date = st.date_input("Goods ready (date)", value=_today, key="db_ready_date")
        ready_hour = st.selectbox("Goods ready (hour)", list(range(0, 24)), index=9,
                                  key="db_ready_hour")
    with c2:
        deadline_date = st.date_input("Deliver by (date)", value=ready_date,
                                      key="db_deadline_date")
        deadline_hour = st.selectbox("Deliver by (hour)", list(range(0, 24)), index=18,
                                     key="db_deadline_hour")
    ready_dt = dt_datetime.combine(ready_date, dt_time(int(ready_hour)))
    deadline_dt = dt_datetime.combine(deadline_date, dt_time(int(deadline_hour)))

    if deadline_dt <= ready_dt:
        st.error("Deliver-by must be after goods-ready.")
    elif deadline_dt - ready_dt > dt_timedelta(hours=72):
        st.error("That window is longer than 72 hours — please narrow it: pick a "
                 "goods-ready time and a deadline closer together.")
    else:
        table = None
        if mode == "Measured route":
            table = arrival_table_measured_span(df, code, ready_dt, deadline_dt)
        elif distance_km is not None:
            table = arrival_table_modelled_span(get_model(), float(distance_km),
                                                scenario, ready_dt, deadline_dt)
        if table is not None:
            result = latest_safe_departure(table)
            if result["feasible"]:
                st.success(
                    f"**Latest safe departure: {fmt_dt(result['departure_dt'])}** — "
                    f"typically arrives {fmt_dt(result['typical_arrival_dt'])}, "
                    f"bad-day (P90) arrival {fmt_dt(result['p90_arrival_dt'])}, "
                    f"on-time chance {result['on_time_prob']*100:.0f}% "
                    "(safety level ≥95%). "
                    "Leaving later than this drops below the safety level; leaving "
                    "earlier wastes vehicle and driver time you could use elsewhere."
                )
            else:
                best_dt = result["best_departure_dt"]
                when = (f"even leaving at {fmt_dt(best_dt)} (goods-ready time)"
                        if best_dt == pd.Timestamp(ready_dt) else
                        f"even the best departure in your window, {fmt_dt(best_dt)},")
                st.error(
                    f"**Not feasible safely** — {when} gives an on-time chance of only "
                    f"{result['best_prob']*100:.0f}% (typical arrival "
                    f"{fmt_dt(result['typical_arrival_dt'])}, bad-day (P90) arrival "
                    f"{fmt_dt(result['p90_arrival_dt'])}). Leaving earlier isn't "
                    "possible if goods aren't ready; the realistic options are "
                    "dispatching the previous day, renegotiating the deadline, or "
                    "accepting this risk knowingly."
                )
            show = table.copy()
            show["Departure"] = show["departure_dt"].map(fmt_dt)
            show["Day type"] = show["day_type_used"].str.capitalize()
            show["Typical arrival"] = show["typical_arrival_dt"].map(fmt_dt)
            show["P90 arrival"] = show["p90_arrival_dt"].map(fmt_dt)
            show["On-time %"] = (show["on_time_prob"] * 100).round(0)
            show["Travel median (min)"] = show["travel_median"].round(1)
            show["Travel P90 (min)"] = show["travel_p90"].round(1)
            cols = ["Departure", "Day type"]
            if mode == "Measured route":
                show = show.rename(columns={"n": "Readings",
                                            "low_confidence": "Low confidence"})
                cols += ["Readings"]
            cols += ["Travel median (min)", "Travel P90 (min)", "Typical arrival",
                     "P90 arrival", "On-time %"]
            if mode == "Measured route":
                cols += ["Low confidence"]
            st.dataframe(show[cols], width="stretch")
            if mode == "Measured route" and bool(table["low_confidence"].any()):
                st.caption("Hours flagged low-confidence have fewer than 30 readings "
                           "and are excluded from the latest-safe pick (shown for "
                           "completeness).")
            if HAS_PLOTLY:
                fig = px.line(table, x="departure_dt",
                              y=["typical_arrival_dt", "p90_arrival_dt"], markers=True,
                              labels={"value": "Arrival", "departure_dt": "Departure",
                                      "variable": ""})
                fig.add_hline(y=deadline_dt, line_dash="dash",
                              annotation_text=f"Deadline {fmt_dt(deadline_dt)}")
                show_chart(fig)
            st.caption("Backward scheduling across the whole window: budget for a "
                       "departure = deadline minus departure time; on-time chance is "
                       "the share of trips (measured, or modelled for any-trip) that "
                       "fit that budget. Each departure is scored on its own date's "
                       "traffic pattern.")

# ---------------------------------------------------------------- weather
elif view == "Weather Impact":
    st.header("Weather impact — scoped analysis")
    st.warning(
        "Weather was recorded only from 2026-05-24 onward and only on a subset of days "
        "(see outputs/data_audit.md). This view uses ONLY rows with a weather snapshot; "
        "core 12 routes. Rain = rsi_flag of Rain / Light Rain. Association, not causation."
    )
    overall = pd.read_csv(OUTPUTS / "weather_overall.csv")
    overall["condition"] = np.where(overall["is_rain"], "Rain", "No rain")
    st.subheader("Duration by rain condition (core 12 routes, weather-covered rows)")
    st.dataframe(overall[["condition", "n", "median", "p90", "iqr"]].rename(columns={
        "n": "Hourly obs.", "median": "Median (min)", "p90": "P90 (min)", "iqr": "IQR (min)"}),
        width="stretch")
    if HAS_PLOTLY:
        fig = px.bar(overall, x="condition", y=["median", "p90"], barmode="group",
                     labels={"value": "Minutes", "condition": "", "variable": ""})
        show_chart(fig)
    summ = pd.read_csv(OUTPUTS / "weather_summary.csv")
    summ["condition"] = np.where(summ["is_rain"], "Rain", "No rain")
    st.subheader("Peak vs off-peak")
    st.dataframe(summ[["period", "condition", "n", "median", "p90", "iqr"]],
                 width="stretch")
    st.write("Full write-up: outputs/weather_analysis.md")

st.divider()
st.caption(
    "RouteWise BLR · Data: Traffic Monitor Lizard "
    "(https://github.com/thecont1/traffic-monitor-lizard), CC BY 4.0 · "
    "Analysis and app code written from scratch for this project · "
    "Google Maps travel-time estimates, not observed vehicle trips."
)
