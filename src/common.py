"""Shared constants and loading helpers for RouteWise BLR.

All analysis/app code in this project was written from scratch for
RouteWise BLR. The dataset itself is from Traffic Monitor Lizard
(https://github.com/thecont1/traffic-monitor-lizard), CC BY 4.0.
"""
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW_TRAFFIC = BASE / "data" / "raw" / "csv-traffic-bangalore.csv"
RAW_ROUTES = BASE / "data" / "raw" / "csv-routes-bangalore.csv"
CLEANED = BASE / "data" / "processed" / "cleaned.csv"
CLEANED_SLIM = BASE / "data" / "processed" / "cleaned_slim.csv"
OUTPUTS = BASE / "outputs"

AIRPORT_ROUTE_CODE = "XJG4+7J|5PX4+HQ"  # MG Road -> KIA, ~34 km, analysed separately

TIME_BUCKETS = {
    "night": list(range(21, 24)) + list(range(0, 7)),
    "morning_peak": list(range(7, 11)),
    "midday": list(range(11, 16)),
    "evening_peak": list(range(16, 21)),
}
HOUR_TO_BUCKET = {h: name for name, hours in TIME_BUCKETS.items() for h in hours}
PEAK_BUCKETS = {"morning_peak", "evening_peak"}


def load_routes() -> pd.DataFrame:
    routes = pd.read_csv(RAW_ROUTES)
    routes["is_airport"] = routes["route_code"] == AIRPORT_ROUTE_CODE
    routes["route_group"] = routes["is_airport"].map({True: "airport_separate", False: "core12"})
    return routes


def load_cleaned() -> pd.DataFrame:
    # Full cleaned data when present (local analysis); the slim file carries
    # every column the app uses and is what the hosted deployment ships.
    if CLEANED.exists():
        return pd.read_csv(CLEANED, parse_dates=["timestamp", "date"], low_memory=False)
    df = pd.read_csv(CLEANED_SLIM, low_memory=False)
    if "label_short" not in df.columns:  # slim omits it; recover from routes
        labels = load_routes().set_index("route_code")["label_short"]
        df["label_short"] = df["route_code"].map(labels)
    return df
