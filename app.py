import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import pandas as pd
import requests
import streamlit as st

API_BASE = "https://health.googleapis.com/v4/users/me/dataTypes"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
]

st.set_page_config(page_title="TABS Fitbit Research Tool", page_icon="⌚", layout="wide")


def secret(name, default=""):
    try:
        return st.secrets[name]
    except Exception:
        return default


def oauth_config():
    return {
        "client_id": secret("GOOGLE_CLIENT_ID"),
        "client_secret": secret("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": secret("GOOGLE_REDIRECT_URI", "http://localhost:8501"),
    }


def authorization_url():
    cfg = oauth_config()
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "scope": " ".join(SCOPES),
    }
    return AUTH_URL + "?" + urlencode(params)


def exchange_code(code):
    cfg = oauth_config()
    r = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "redirect_uri": cfg["redirect_uri"],
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    r.raise_for_status()
    token = r.json()
    token["obtained_at"] = time.time()
    return token


def refresh_access_token(refresh_token):
    cfg = oauth_config()
    r = requests.post(
        TOKEN_URL,
        data={
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    new = r.json()
    new["refresh_token"] = refresh_token
    new["obtained_at"] = time.time()
    return new


def access_token():
    token = st.session_state.get("token")
    if not token:
        return None
    if time.time() - token.get("obtained_at", 0) > token.get("expires_in", 3600) - 120:
        if token.get("refresh_token"):
            token = refresh_access_token(token["refresh_token"])
            st.session_state.token = token
    return token.get("access_token")


def list_datapoints(data_type, token, page_size=10000):
    url = f"{API_BASE}/{data_type}/dataPoints"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"pageSize": page_size}
    rows = []
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=60)
        r.raise_for_status()
        payload = r.json()
        rows.extend(payload.get("dataPoints", []))
        next_token = payload.get("nextPageToken")
        if not next_token:
            break
        params["pageToken"] = next_token
    return rows


def heart_rate_frame(points):
    rows = []
    for p in points:
        hr = p.get("heartRate", {})
        sample = hr.get("sampleTime", {})
        civil = sample.get("civilTime", {})
        d, t = civil.get("date", {}), civil.get("time", {})
        if not d:
            continue
        ts = datetime(
            d.get("year"), d.get("month"), d.get("day"),
            t.get("hours", 0), t.get("minutes", 0), t.get("seconds", 0)
        )
        rows.append({
            "timestamp": ts,
            "heart_rate_bpm": int(hr.get("beatsPerMinute", 0)),
            "device": p.get("dataSource", {}).get("device", {}).get("displayName", ""),
            "recording_method": p.get("dataSource", {}).get("recordingMethod", ""),
        })
    return pd.DataFrame(rows).sort_values("timestamp") if rows else pd.DataFrame()


def steps_frame(points):
    rows = []
    for p in points:
        steps = p.get("steps", {})
        interval = steps.get("interval", {})
        civil = interval.get("civilStartTime", {})
        d, t = civil.get("date", {}), civil.get("time", {})
        if not d:
            continue
        ts = datetime(
            d.get("year"), d.get("month"), d.get("day"),
            t.get("hours", 0), t.get("minutes", 0), t.get("seconds", 0)
        )
        rows.append({
            "minute": ts.replace(second=0),
            "steps_per_minute": int(steps.get("count", 0)),
            "device": p.get("dataSource", {}).get("device", {}).get("displayName", ""),
            "recording_method": p.get("dataSource", {}).get("recordingMethod", ""),
        })
    return pd.DataFrame(rows).sort_values("minute") if rows else pd.DataFrame()


def minute_summary(hr_df, steps_df, selected_date):
    day = pd.Timestamp(selected_date)
    next_day = day + pd.Timedelta(days=1)
    if not hr_df.empty:
        h = hr_df[(hr_df.timestamp >= day) & (hr_df.timestamp < next_day)].copy()
        h["minute"] = h.timestamp.dt.floor("min")
        hrm = h.groupby("minute").heart_rate_bpm.agg(
            hr_samples="count", hr_mean="mean", hr_min="min", hr_max="max"
        ).reset_index()
    else:
        hrm = pd.DataFrame(columns=["minute", "hr_samples", "hr_mean", "hr_min", "hr_max"])
    if not steps_df.empty:
        s = steps_df[(steps_df.minute >= day) & (steps_df.minute < next_day)][["minute", "steps_per_minute"]]
    else:
        s = pd.DataFrame(columns=["minute", "steps_per_minute"])
    out = pd.merge(hrm, s, on="minute", how="outer").sort_values("minute")
    if "hr_mean" in out:
        out["hr_mean"] = out["hr_mean"].round(1)
    return out


st.title("TABS Fitbit Research Tool")
st.caption("Charge 6 heart rate + minute-by-minute steps via Google Health API")

cfg = oauth_config()
if not cfg["client_id"] or not cfg["client_secret"]:
    st.warning("Google OAuth credentials have not been configured in Streamlit secrets yet.")
    st.code('GOOGLE_CLIENT_ID = "..."\nGOOGLE_CLIENT_SECRET = "..."\nGOOGLE_REDIRECT_URI = "http://localhost:8501"')
    st.stop()

query_code = st.query_params.get("code")
if query_code and "token" not in st.session_state:
    try:
        st.session_state.token = exchange_code(query_code)
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Google authorization failed: {e}")

if not access_token():
    st.subheader("1. Connect Fitbit / Google Health")
    st.write("Authorize read-only access to activity/fitness and health measurements.")
    st.link_button("Connect Google Health", authorization_url(), type="primary")
    st.stop()

st.success("Google Health connected")

with st.sidebar:
    st.header("Data")
    selected_date = st.date_input("Date to analyze", value=date.today())
    if st.button("Disconnect this session"):
        st.session_state.pop("token", None)
        st.rerun()

if st.button("Retrieve Charge 6 data", type="primary"):
    try:
        token = access_token()
        with st.spinner("Retrieving all heart-rate pages..."):
            hr_points = list_datapoints("heart-rate", token)
        with st.spinner("Retrieving all step pages..."):
            step_points = list_datapoints("steps", token)
        st.session_state.hr_df = heart_rate_frame(hr_points)
        st.session_state.steps_df = steps_frame(step_points)
        st.success(f"Retrieved {len(hr_points):,} heart-rate observations and {len(step_points):,} step intervals.")
    except requests.HTTPError as e:
        st.error(f"Google Health API error: {e.response.status_code} — {e.response.text}")
    except Exception as e:
        st.error(f"Could not retrieve data: {e}")

hr_df = st.session_state.get("hr_df", pd.DataFrame())
steps_df = st.session_state.get("steps_df", pd.DataFrame())

if not hr_df.empty or not steps_df.empty:
    summary = minute_summary(hr_df, steps_df, selected_date)
    st.subheader(f"Minute-level summary — {selected_date:%B %d, %Y}")
    if summary.empty:
        st.info("No observations were returned for this date.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Minutes with HR", int(summary.hr_samples.notna().sum()) if "hr_samples" in summary else 0)
        c2.metric("Minutes with steps", int(summary.steps_per_minute.notna().sum()) if "steps_per_minute" in summary else 0)
        c3.metric("Total recorded steps", int(summary.steps_per_minute.fillna(0).sum()) if "steps_per_minute" in summary else 0)

        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.download_button(
            "Download minute-level CSV",
            summary.to_csv(index=False).encode("utf-8"),
            file_name=f"TABS_Fitbit_{selected_date.isoformat()}_minute_summary.csv",
            mime="text/csv",
        )

        if not hr_df.empty:
            day = pd.Timestamp(selected_date)
            hday = hr_df[(hr_df.timestamp >= day) & (hr_df.timestamp < day + pd.Timedelta(days=1))]
            if not hday.empty:
                st.subheader("Heart rate")
                st.line_chart(hday.set_index("timestamp")["heart_rate_bpm"])

        if not steps_df.empty:
            day = pd.Timestamp(selected_date)
            sday = steps_df[(steps_df.minute >= day) & (steps_df.minute < day + pd.Timedelta(days=1))]
            if not sday.empty:
                st.subheader("Steps per minute")
                st.bar_chart(sday.set_index("minute")["steps_per_minute"])

        with st.expander("Raw heart-rate observations"):
            st.dataframe(hr_df, use_container_width=True, hide_index=True)
        with st.expander("Raw step intervals"):
            st.dataframe(steps_df, use_container_width=True, hide_index=True)

st.divider()
st.caption("From the CVC Cosmos · Turning movement into measurable data")
