import json
import time
from datetime import date, datetime
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

st.set_page_config(page_title="TABS Lab Fitbit Research Tool", page_icon="⌚", layout="wide")

st.markdown("""
<style>
:root { --navy:#082b57; --teal:#0a8b98; --ink:#13233a; }
.stApp { background:#ffffff; color:var(--ink); }
[data-testid="stSidebar"] { background:#f7fafc; border-right:1px solid #dce5ec; }
[data-testid="stSidebar"] > div:first-child { padding-top:1.2rem; }
.block-container { padding-top:2.2rem; max-width:1400px; }
h1,h2,h3 { color:var(--navy); }
.hero-title { line-height:.95; margin:0; white-space:nowrap; font-family:"Helvetica Neue",Arial,sans-serif; }
.hero-title .tabs { font-size:4.15rem; font-weight:500; color:var(--navy); letter-spacing:.01em; }
.hero-title .lab { font-size:1.85rem; font-weight:400; color:var(--navy); margin-left:.18em; }
.hero-sub { color:var(--teal); font-weight:600; letter-spacing:.08em; font-size:1.35rem; margin-top:12px; }
.hero-rule { height:2px; width:100%; max-width:720px; background:linear-gradient(90deg,var(--teal),var(--navy)); margin:14px 0 10px; border-radius:3px; }
.hero-caption { color:#667085; font-size:1.02rem; font-style:italic; }
.status-card { border-radius:14px; padding:20px 24px; margin:18px 0; border:1px solid #b7e2d2; background:linear-gradient(90deg,#effaf5,#f8fcfa); }
.status-card strong { color:#08783f; font-size:1.2rem; }
.info-card { border-radius:14px; padding:18px 24px; margin:18px 0; border:1px solid #bfd7f4; background:linear-gradient(90deg,#f2f7fd,#f9fbfe); color:var(--navy); }
.info-card strong { font-size:1.15rem; }
[data-testid="stMetric"] { border:1px solid #dce3ea; border-radius:14px; padding:18px 20px; background:#fff; box-shadow:0 2px 8px rgba(8,43,87,.05); }
[data-testid="stMetricLabel"] { color:var(--navy); font-weight:700; }
[data-testid="stMetricValue"] { color:var(--navy); font-weight:800; }
.stButton > button[kind="primary"], .stLinkButton > a { background:var(--navy)!important; border-color:var(--navy)!important; border-radius:10px!important; font-weight:700!important; }
.stButton > button:hover, .stLinkButton > a:hover { border-color:var(--teal)!important; }
[data-testid="stDataFrame"] { border-radius:12px; overflow:hidden; border:1px solid #dce3ea; }
.sidebar-section { color:var(--teal); font-weight:800; font-size:1.15rem; margin-top:14px; }
.small-note { color:#667085; font-size:.9rem; }
.sidebar-logo-wrap { display:flex; justify-content:center; align-items:center; width:100%; margin:0 auto 12px; }
.sidebar-logo-wrap img { width:150px; max-width:70%; height:auto; display:block; }
</style>
""", unsafe_allow_html=True)


def secret(name, default=""):
    try:
        return st.secrets[name]
    except Exception:
        return default


def oauth_config():
    return {"client_id": secret("GOOGLE_CLIENT_ID"), "client_secret": secret("GOOGLE_CLIENT_SECRET"), "redirect_uri": secret("GOOGLE_REDIRECT_URI", "http://localhost:8501")}


def authorization_url():
    cfg = oauth_config()
    return AUTH_URL + "?" + urlencode({"client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"], "response_type": "code", "access_type": "offline", "prompt": "consent", "scope": " ".join(SCOPES)})


def exchange_code(code):
    cfg = oauth_config()
    r = requests.post(TOKEN_URL, data={"code": code, "client_id": cfg["client_id"], "client_secret": cfg["client_secret"], "redirect_uri": cfg["redirect_uri"], "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status(); token = r.json(); token["obtained_at"] = time.time(); return token


def refresh_access_token(refresh_token):
    cfg = oauth_config()
    r = requests.post(TOKEN_URL, data={"client_id": cfg["client_id"], "client_secret": cfg["client_secret"], "refresh_token": refresh_token, "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status(); new = r.json(); new["refresh_token"] = refresh_token; new["obtained_at"] = time.time(); return new


def access_token():
    token = st.session_state.get("token")
    if not token: return None
    if time.time() - token.get("obtained_at", 0) > token.get("expires_in", 3600) - 120 and token.get("refresh_token"):
        token = refresh_access_token(token["refresh_token"]); st.session_state.token = token
    return token.get("access_token")


def list_datapoints(data_type, token, page_size=10000):
    url = f"{API_BASE}/{data_type}/dataPoints"; headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}; params = {"pageSize": page_size}; rows = []
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=60); r.raise_for_status(); payload = r.json(); rows.extend(payload.get("dataPoints", [])); nxt = payload.get("nextPageToken")
        if not nxt: break
        params["pageToken"] = nxt
    return rows


def heart_rate_frame(points):
    rows = []
    for p in points:
        hr = p.get("heartRate", {}); civil = hr.get("sampleTime", {}).get("civilTime", {}); d, t = civil.get("date", {}), civil.get("time", {})
        if not d: continue
        ts = datetime(d.get("year"), d.get("month"), d.get("day"), t.get("hours", 0), t.get("minutes", 0), t.get("seconds", 0))
        rows.append({"timestamp": ts, "heart_rate_bpm": int(hr.get("beatsPerMinute", 0)), "device": p.get("dataSource", {}).get("device", {}).get("displayName", ""), "recording_method": p.get("dataSource", {}).get("recordingMethod", "")})
    return pd.DataFrame(rows).sort_values("timestamp") if rows else pd.DataFrame()


def steps_frame(points):
    rows = []
    for p in points:
        steps = p.get("steps", {}); civil = steps.get("interval", {}).get("civilStartTime", {}); d, t = civil.get("date", {}), civil.get("time", {})
        if not d: continue
        ts = datetime(d.get("year"), d.get("month"), d.get("day"), t.get("hours", 0), t.get("minutes", 0), t.get("seconds", 0))
        rows.append({"minute": ts.replace(second=0), "steps_per_minute": int(steps.get("count", 0)), "device": p.get("dataSource", {}).get("device", {}).get("displayName", ""), "recording_method": p.get("dataSource", {}).get("recordingMethod", "")})
    return pd.DataFrame(rows).sort_values("minute") if rows else pd.DataFrame()


def minute_summary(hr_df, steps_df, selected_date):
    day = pd.Timestamp(selected_date); next_day = day + pd.Timedelta(days=1)
    if not hr_df.empty:
        h = hr_df[(hr_df.timestamp >= day) & (hr_df.timestamp < next_day)].copy(); h["minute"] = h.timestamp.dt.floor("min"); hrm = h.groupby("minute").heart_rate_bpm.agg(hr_samples="count", hr_mean="mean", hr_min="min", hr_max="max").reset_index()
    else: hrm = pd.DataFrame(columns=["minute", "hr_samples", "hr_mean", "hr_min", "hr_max"])
    s = steps_df[(steps_df.minute >= day) & (steps_df.minute < next_day)][["minute", "steps_per_minute"]] if not steps_df.empty else pd.DataFrame(columns=["minute", "steps_per_minute"])
    out = pd.merge(hrm, s, on="minute", how="outer").sort_values("minute")
    if "hr_mean" in out: out["hr_mean"] = out["hr_mean"].round(1)
    return out


def telegram(method, payload=None):
    token = secret("TELEGRAM_BOT_TOKEN")
    if not token: raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured in Streamlit Secrets.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    r = requests.get(url, params=payload or {}, timeout=30) if method == "getUpdates" else requests.post(url, json=payload or {}, timeout=30)
    r.raise_for_status(); body = r.json()
    if not body.get("ok"): raise RuntimeError(body.get("description", "Telegram API request failed."))
    return body.get("result")


def telegram_updates():
    return telegram("getUpdates", {"limit": 100, "timeout": 0, "allowed_updates": json.dumps(["message", "callback_query"])})


def telegram_chats(updates):
    chats = {}
    for update in updates:
        cb = update.get("callback_query") or {}; msg = update.get("message") or cb.get("message") or {}; chat = msg.get("chat") or {}
        if chat.get("type") != "private" or "id" not in chat: continue
        user = (update.get("message") or {}).get("from") or cb.get("from") or {}; name = " ".join(x for x in [user.get("first_name", ""), user.get("last_name", "")] if x).strip(); username = user.get("username")
        label = name or (f"@{username}" if username else f"Chat {chat['id']}")
        if username and name: label += f" (@{username})"
        chats[str(chat["id"])] = label
    return chats


cfg = oauth_config()
if not cfg["client_id"] or not cfg["client_secret"]: st.warning("Google OAuth credentials have not been configured in Streamlit secrets yet."); st.stop()
query_code = st.query_params.get("code")
if query_code and "token" not in st.session_state:
    try: st.session_state.token = exchange_code(query_code); st.query_params.clear(); st.rerun()
    except Exception as e: st.error(f"Google authorization failed: {e}")
connected = bool(access_token())

with st.sidebar:
    st.markdown('<div class="sidebar-logo-wrap"><img src="https://raw.githubusercontent.com/StepAnalyzerTool/TABS-Fitbit-Research-Tool/main/Logo.png" alt="TABS Lab Fitbit Research Tool logo"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section">DATA</div>', unsafe_allow_html=True)
    selected_date = st.date_input("Date to analyze", value=date.today())
    if connected:
        if st.button("Disconnect this session", use_container_width=True): st.session_state.pop("token", None); st.rerun()
        st.markdown('<div class="small-note" style="margin-top:18px">Connected to <strong>Google Health</strong><br>Authorization active</div>', unsafe_allow_html=True)

st.markdown('''<div class="hero-title"><span class="tabs">TABS</span><span class="lab">Lab</span></div><div class="hero-sub">FITBIT RESEARCH TOOL</div><div class="hero-rule"></div><div class="hero-caption">From the CVC Cosmos · Turning movement into data</div>''', unsafe_allow_html=True)

if not connected:
    st.markdown('<div class="info-card"><strong>Connect Google Health</strong><br>Authorize read-only access to activity, fitness, and health measurements.</div>', unsafe_allow_html=True)
    st.link_button("Connect Google Health", authorization_url(), type="primary")
else:
    st.markdown('<div class="status-card"><strong>✓ Google Health connected</strong><br>Your Charge 6 data is securely linked and ready.</div>', unsafe_allow_html=True)
    if st.button("Retrieve Charge 6 data", type="primary"):
        try:
            token = access_token()
            with st.spinner("Retrieving all heart-rate and step data..."):
                hr_points = list_datapoints("heart-rate", token); step_points = list_datapoints("steps", token)
            st.session_state.hr_df = heart_rate_frame(hr_points); st.session_state.steps_df = steps_frame(step_points); st.session_state.last_retrieval = (len(hr_points), len(step_points))
        except requests.HTTPError as e: st.error(f"Google Health API error: {e.response.status_code} — {e.response.text}")
        except Exception as e: st.error(f"Could not retrieve data: {e}")

    if "last_retrieval" in st.session_state:
        nhr, nsteps = st.session_state.last_retrieval; st.markdown(f'<div class="info-card"><strong>Retrieved {nhr:,} heart-rate observations and {nsteps:,} step intervals.</strong><br>Data pulled successfully from Google Health.</div>', unsafe_allow_html=True)

    hr_df = st.session_state.get("hr_df", pd.DataFrame()); steps_df = st.session_state.get("steps_df", pd.DataFrame())
    if not hr_df.empty or not steps_df.empty:
        summary = minute_summary(hr_df, steps_df, selected_date); st.markdown(f"## Minute-level summary — {selected_date:%B %d, %Y}")
        if summary.empty: st.info("No observations were returned for this date.")
        else:
            c1, c2, c3 = st.columns(3); c1.metric("Minutes with HR", int(summary.hr_samples.notna().sum()) if "hr_samples" in summary else 0); c2.metric("Minutes with steps", int(summary.steps_per_minute.notna().sum()) if "steps_per_minute" in summary else 0); c3.metric("Total recorded steps", int(summary.steps_per_minute.fillna(0).sum()) if "steps_per_minute" in summary else 0)
            st.dataframe(summary, use_container_width=True, hide_index=True); st.download_button("Download minute-level CSV", summary.to_csv(index=False).encode("utf-8"), file_name=f"TABS_Fitbit_{selected_date.isoformat()}_minute_summary.csv", mime="text/csv")
            if not hr_df.empty:
                day = pd.Timestamp(selected_date); hday = hr_df[(hr_df.timestamp >= day) & (hr_df.timestamp < day + pd.Timedelta(days=1))]
                if not hday.empty: st.subheader("Heart rate"); st.line_chart(hday.set_index("timestamp")["heart_rate_bpm"])
            if not steps_df.empty:
                day = pd.Timestamp(selected_date); sday = steps_df[(steps_df.minute >= day) & (steps_df.minute < day + pd.Timedelta(days=1))]
                if not sday.empty: st.subheader("Steps per minute"); st.bar_chart(sday.set_index("minute")["steps_per_minute"])
            with st.expander("Raw heart-rate observations"): st.dataframe(hr_df, use_container_width=True, hide_index=True)
            with st.expander("Raw step