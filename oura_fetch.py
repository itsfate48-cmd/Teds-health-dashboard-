import os
import sys
import json
import datetime
import requests

API_KEY = os.environ.get("OURA_API_KEY")
if not API_KEY:
    sys.exit("Error: OURA_API_KEY environment variable is not set.")

BASE = "https://api.ouraring.com/v2/usercollection"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

today = datetime.date.today()
start = (today - datetime.timedelta(days=7)).isoformat()
end = today.isoformat()

def fetch(endpoint, params=None):
    r = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params or {}, timeout=15)
    r.raise_for_status()
    return r.json().get("data", [])

readiness     = fetch("daily_readiness", {"start_date": start, "end_date": end})
sleep         = fetch("daily_sleep",     {"start_date": start, "end_date": end})
sleep_detail  = fetch("sleep",           {"start_date": start, "end_date": end})
activity      = fetch("daily_activity",  {"start_date": start, "end_date": end})

# Build HRV lookup keyed by date (day = YYYY-MM-DD of the night)
hrv_by_date = {}
for s in sleep_detail:
    day = s.get("day")
    hrv_val = s.get("average_hrv")
    if day and hrv_val:
        hrv_by_date[day] = round(hrv_val)

# Most recent readiness
latest_readiness = readiness[-1] if readiness else {}
readiness_score = latest_readiness.get("score")

# Most recent sleep score from daily_sleep
latest_sleep = sleep[-1] if sleep else {}
sleep_score = latest_sleep.get("score")

# Duration fields from detailed sleep sessions — sum sessions for the latest night
latest_day = latest_sleep.get("day") or end
night_sessions = [s for s in sleep_detail if s.get("day") == latest_day and s.get("type") != "rest"]
if not night_sessions:
    night_sessions = [s for s in sleep_detail if s.get("day") == latest_day]

def sum_field(sessions, key):
    vals = [s.get(key) for s in sessions if s.get(key) is not None]
    return sum(vals) if vals else None

raw_total = sum_field(night_sessions, "total_sleep_duration")
raw_deep  = sum_field(night_sessions, "deep_sleep_duration")
raw_rem   = sum_field(night_sessions, "rem_sleep_duration")
raw_awake = sum_field(night_sessions, "awake_time")

total_hrs = round(raw_total / 3600, 2) if raw_total else None
deep_hrs  = round(raw_deep  / 3600, 2) if raw_deep  else None
rem_hrs   = round(raw_rem   / 3600, 2) if raw_rem   else None
awake_hrs = round(raw_awake / 3600, 2) if raw_awake else None

# Today's HRV (from readiness payload if available, else hrv endpoint)
todays_hrv = latest_readiness.get("contributors", {}).get("hrv_balance")
if todays_hrv is None:
    todays_hrv = hrv_by_date.get(end)

# Temperature deviation (latest readiness)
temp_delta = latest_readiness.get("temperature_deviation")

# Build last-7-day lookups keyed by day name (Mon–Sun for current week window)
date_range = [(today - datetime.timedelta(days=6 - i)) for i in range(7)]

hrv_week = {}
for d in date_range:
    day_name = d.strftime("%a")
    hrv_week[day_name] = hrv_by_date.get(d.isoformat())

# Steps by date
steps_by_date = {a["day"]: a.get("steps") for a in activity if a.get("day")}
steps_today = steps_by_date.get(end)

steps_week = {}
for d in date_range:
    day_name = d.strftime("%a")
    steps_week[day_name] = steps_by_date.get(d.isoformat())

output = {
    "fetch_date": today.isoformat(),
    "readiness_score": readiness_score,
    "sleep_score": sleep_score,
    "hrv_ms": todays_hrv,
    "temp_deviation_c": temp_delta,
    "sleep_total_hrs": total_hrs,
    "sleep_deep_hrs": deep_hrs,
    "sleep_rem_hrs": rem_hrs,
    "sleep_awake_hrs": awake_hrs,
    "hrv_week": hrv_week,
    "steps_today": steps_today,
    "steps_week": steps_week,
}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oura_data.json")
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)

print(f"Saved to {out_path}")
print(json.dumps(output, indent=2))
