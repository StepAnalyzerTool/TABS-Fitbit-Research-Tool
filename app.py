import time
from datetime import date, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st
from telegram_widget import render_telegram_test
from activity_alert_widget import render_activity_alert_test
from time_diagnostics import render_time_diagnostics

API_BASE="https://health.googleapis.com/v4/users/me/dataTypes"
AUTH_URL="https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL="https://oauth2.googleapis.com/token"
EASTERN=ZoneInfo("America/New_York")
SCOPES=["https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly","https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly"]
st.set_page_config(page_title="TABS Lab Fitbit Research Tool",page_icon="⌚",layout="wide")
st.markdown('''<style>:root{--navy:#082b57;--teal:#0a8b98;--ink:#13233a}.stApp{background:#fff;color:var(--ink)}[data-testid="stSidebar"]{background:#f7fafc;border-right:1px solid #dce5ec}.block-container{padding-top:2.2rem;max-width:1400px}h1,h2,h3{color:var(--navy)}.hero-title{line-height:.95;white-space:nowrap;font-family:"Helvetica Neue",Arial,sans-serif}.hero-title .tabs{font-size:4.15rem;font-weight:500;color:var(--navy)}.hero-title .lab{font-size:1.85rem;font-weight:400;color:var(--navy);margin-left:.18em}.hero-sub{color:var(--teal);font-weight:600;letter-spacing:.08em;font-size:1.35rem;margin-top:12px}.hero-rule{height:2px;max-width:720px;background:linear-gradient(90deg,var(--teal),var(--navy));margin:14px 0 10px}.hero-caption{color:#667085;font-size:1.02rem;font-style:italic}.status-card{border-radius:14px;padding:20px 24px;margin:18px 0;border:1px solid #b7e2d2;background:#effaf5}.status-card strong{color:#08783f;font-size:1.2rem}.info-card{border-radius:14px;padding:18px 24px;margin:18px 0;border:1px solid #bfd7f4;background:#f2f7fd;color:var(--navy)}[data-testid="stMetric"]{border:1px solid #dce3ea;border-radius:14px;padding:18px 20px}.stButton>button[kind="primary"],.stLinkButton>a{background:var(--navy)!important;border-color:var(--navy)!important;border-radius:10px!important;font-weight:700!important}.sidebar-section{color:var(--teal);font-weight:800;font-size:1.15rem;margin-top:14px}.small-note{color:#667085;font-size:.9rem}.sidebar-logo-wrap{display:flex;justify-content:center;width:100%;margin:0 auto 12px}.sidebar-logo-wrap img{width:150px;max-width:70%;height:auto}</style>''',unsafe_allow_html=True)
def secret(n,d=""):
    try:return st.secrets[n]
    except:return d
def cfg():return {"id":secret("GOOGLE_CLIENT_ID"),"secret":secret("GOOGLE_CLIENT_SECRET"),"redirect":secret("GOOGLE_REDIRECT_URI","http://localhost:8501")}
def auth_url():
    c=cfg();return AUTH_URL+"?"+urlencode({"client_id":c["id"],"redirect_uri":c["redirect"],"response_type":"code","access_type":"offline","prompt":"consent","scope":" ".join(SCOPES)})
def exchange(code):
    c=cfg();r=requests.post(TOKEN_URL,data={"code":code,"client_id":c["id"],"client_secret":c["secret"],"redirect_uri":c["redirect"],"grant_type":"authorization_code"},timeout=30);r.raise_for_status();t=r.json();t["obtained_at"]=time.time();return t
def token():
    t=st.session_state.get("token")
    if not t:return None
    if time.time()-t.get("obtained_at",0)>t.get("expires_in",3600)-120 and t.get("refresh_token"):
        c=cfg();r=requests.post(TOKEN_URL,data={"client_id":c["id"],"client_secret":c["secret"],"refresh_token":t["refresh_token"],"grant_type":"refresh_token"},timeout=30);r.raise_for_status();n=r.json();n["refresh_token"]=t["refresh_token"];n["obtained_at"]=time.time();st.session_state.token=n;t=n
    return t.get("access_token")
def points(kind,access):
    u=f"{API_BASE}/{kind}/dataPoints";h={"Authorization":f"Bearer {access}","Accept":"application/json"};p={"pageSize":10000};out=[]
    while True:
        r=requests.get(u,headers=h,params=p,timeout=60);r.raise_for_status();j=r.json();out+=j.get("dataPoints",[]);n=j.get("nextPageToken")
        if not n:break
        p["pageToken"]=n
    return out
def utc_to_eastern(value):
    if not value:return None
    return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(EASTERN).replace(tzinfo=None)
def hr_frame(items):
    out=[]
    for p in items:
        x=p.get("heartRate",{});sample=x.get("sampleTime",{});ts=utc_to_eastern(sample.get("time"))
        if ts is None:
            c=sample.get("civilTime",{});d,t=c.get("date",{}),c.get("time",{});ts=datetime(d["year"],d["month"],d["day"],t.get("hours",0),t.get("minutes",0),t.get("seconds",0)) if d else None
        if ts:out.append({"timestamp":ts,"heart_rate_bpm":int(x.get("beatsPerMinute",0)),"device":p.get("dataSource",{}).get("device",{}).get("displayName","")})
    return pd.DataFrame(out).sort_values("timestamp") if out else pd.DataFrame()
def step_frame(items):
    out=[]
    for p in items:
        x=p.get("steps",{});interval=x.get("interval",{});ts=utc_to_eastern(interval.get("startTime"))
        if ts is None:
            c=interval.get("civilStartTime",{});d,t=c.get("date",{}),c.get("time",{});ts=datetime(d["year"],d["month"],d["day"],t.get("hours",0),t.get("minutes",0)) if d else None
        if ts:out.append({"minute":ts.replace(second=0,microsecond=0),"steps_per_minute":int(x.get("count",0)),"device":p.get("dataSource",{}).get("device",{}).get("displayName","")})
    return pd.DataFrame(out).sort_values("minute") if out else pd.DataFrame()
def minute_summary(hr,steps,chosen):
    a=pd.Timestamp(chosen);b=a+pd.Timedelta(days=1)
    if not hr.empty:
        h=hr[(hr.timestamp>=a)&(hr.timestamp<b)].copy();h["minute"]=h.timestamp.dt.floor("min");hm=h.groupby("minute").heart_rate_bpm.agg(hr_samples="count",hr_mean="mean",hr_min="min",hr_max="max").reset_index()
    else:hm=pd.DataFrame(columns=["minute","hr_samples","hr_mean","hr_min","hr_max"])
    sm=steps[(steps.minute>=a)&(steps.minute<b)][["minute","steps_per_minute"]] if not steps.empty else pd.DataFrame(columns=["minute","steps_per_minute"])
    out=pd.merge(hm,sm,on="minute",how="outer").sort_values("minute")
    if "hr_mean" in out:out["hr_mean"]=out["hr_mean"].round(1)
    return out
c=cfg()
if not c["id"] or not c["secret"]:st.warning("Google OAuth credentials have not been configured in Streamlit secrets yet.");st.stop()
code=st.query_params.get("code")
if code and "token" not in st.session_state:
    try:st.session_state.token=exchange(code);st.query_params.clear();st.rerun()
    except Exception as e:st.error(f"Google authorization failed: {e}")
connected=bool(token())
with st.sidebar:
    st.markdown('<div class="sidebar-logo-wrap"><img src="https://raw.githubusercontent.com/StepAnalyzerTool/TABS-Fitbit-Research-Tool/main/Logo.png"></div>',unsafe_allow_html=True);st.markdown('<div class="sidebar-section">DATA</div>',unsafe_allow_html=True);chosen=st.date_input("Date to analyze",value=date.today())
    if connected:
        if st.button("Disconnect this session",use_container_width=True):st.session_state.pop("token",None);st.rerun()
        st.markdown('<div class="small-note">Connected to <strong>Google Health</strong><br>Authorization active</div>',unsafe_allow_html=True)
st.markdown('''<div class="hero-title"><span class="tabs">TABS</span><span class="lab">Lab</span></div><div class="hero-sub">FITBIT RESEARCH TOOL</div><div class="hero-rule"></div><div class="hero-caption">From the CVC Cosmos · Turning movement into data</div>''',unsafe_allow_html=True)
if not connected:
    st.markdown('<div class="info-card"><strong>Connect Google Health</strong><br>Authorize read-only access to activity, fitness, and health measurements.</div>',unsafe_allow_html=True);st.link_button("Connect Google Health",auth_url(),type="primary")
else:
    st.markdown('<div class="status-card"><strong>✓ Google Health connected</strong><br>Your Charge 6 data is securely linked and ready.</div>',unsafe_allow_html=True)
    if st.button("Retrieve Charge 6 data",type="primary"):
        try:
            with st.spinner("Retrieving all heart-rate and step data..."):hp=points("heart-rate",token());sp=points("steps",token())
            st.session_state.raw_hr_points=hp;st.session_state.raw_step_points=sp;st.session_state.hr_df=hr_frame(hp);st.session_state.steps_df=step_frame(sp);st.session_state.last_retrieval=(len(hp),len(sp))
        except Exception as e:st.error(f"Could not retrieve data: {e}")
    if "last_retrieval" in st.session_state:
        a,b=st.session_state.last_retrieval;st.markdown(f'<div class="info-card"><strong>Retrieved {a:,} heart-rate observations and {b:,} step intervals.</strong></div>',unsafe_allow_html=True)
    hr=st.session_state.get("hr_df",pd.DataFrame());steps=st.session_state.get("steps_df",pd.DataFrame())
    if not hr.empty or not steps.empty:
        s=minute_summary(hr,steps,chosen);st.markdown(f"## Minute-level summary — {chosen:%B %d, %Y}")
        if s.empty:st.info("No observations were returned for this date.")
        else:
            x,y,z=st.columns(3);x.metric("Minutes with HR",int(s.hr_samples.notna().sum()));y.metric("Minutes with steps",int(s.steps_per_minute.notna().sum()));z.metric("Total recorded steps",int(s.steps_per_minute.fillna(0).sum()));st.dataframe(s,use_container_width=True,hide_index=True);st.download_button("Download minute-level CSV",s.to_csv(index=False).encode(),file_name=f"TABS_Fitbit_{chosen.isoformat()}_minute_summary.csv",mime="text/csv")
            if not hr.empty:
                d=pd.Timestamp(chosen);h=hr[(hr.timestamp>=d)&(hr.timestamp<d+pd.Timedelta(days=1))]
                if not h.empty:st.subheader("Heart rate");st.line_chart(h.set_index("timestamp")["heart_rate_bpm"])
            if not steps.empty:
                d=pd.Timestamp(chosen);q=steps[(steps.minute>=d)&(steps.minute<d+pd.Timedelta(days=1))]
                if not q.empty:st.subheader("Steps per minute");st.bar_chart(q.set_index("minute")["steps_per_minute"])
            with st.expander("Raw heart-rate observations"):st.dataframe(hr,use_container_width=True,hide_index=True)
            with st.expander("Raw step intervals"):st.dataframe(steps,use_container_width=True,hide_index=True)
    render_time_diagnostics(st.session_state.get("raw_hr_points",[]),st.session_state.get("raw_step_points",[]))
st.divider();render_telegram_test();render_activity_alert_test(st.session_state.get("steps_df",pd.DataFrame()))