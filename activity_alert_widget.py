from datetime import datetime, timedelta
import time
import requests
import streamlit as st


def render_activity_alert_test(steps_df):
    with st.expander("🚶 Activity Alert Test", expanded=False):
        st.write("Prototype step-dependent Telegram contingencies using the Fitbit data currently loaded in this app.")
        token=st.secrets.get("TELEGRAM_BOT_TOKEN",""); chat_id=st.session_state.get("tg_chat_id")
        if not token: st.error("Telegram bot token is not configured."); return
        if not chat_id: st.info("First use Telegram Notification Test to find/select your Telegram chat."); return
        if steps_df is None or steps_df.empty: st.info("Retrieve Fitbit data first so the alert test has step data to evaluate."); return
        base=f"https://api.telegram.org/bot{token}/"
        def post(method,payload):
            r=requests.post(base+method,json=payload,timeout=30); r.raise_for_status(); body=r.json()
            if not body.get("ok"): raise RuntimeError(body.get("description","Telegram API error"))
            return body.get("result")
        def get_updates():
            r=requests.get(base+"getUpdates",params={"limit":100,"timeout":0,"allowed_updates":"[\"callback_query\"]"},timeout=30); r.raise_for_status(); return r.json().get("result",[])
        today=datetime.now().date(); day=steps_df[steps_df["minute"].dt.date==today].copy(); total_steps=int(day["steps_per_minute"].fillna(0).sum()) if not day.empty else 0
        st.metric("Steps currently available for today",total_steps)
        st.session_state.setdefault("activity_alert_log",[]); st.session_state.setdefault("step_milestones_sent",set()); st.session_state.setdefault("low_hours_sent",set()); st.session_state.setdefault("processed_alert_callbacks",set())
        if st.button("Evaluate step-alert rules now",type="primary"):
            now=datetime.now(); reached=(total_steps//500)*500; milestones=list(range(500,reached+1,500)); new=[m for m in milestones if m not in st.session_state.step_milestones_sent]
            if new:
                milestone=max(new); text=f"🎉 Good job! You reached another 500 steps! Total for today is {total_steps:,} steps."; keyboard={"inline_keyboard":[[{"text":"👍 Got it","callback_data":f"step_got_it:{milestone}:{int(time.time())}"}]]}; result=post("sendMessage",{"chat_id":chat_id,"text":text,"reply_markup":keyboard}); st.session_state.step_milestones_sent.update(milestones); st.session_state.activity_alert_log.append({"type":"500-step milestone","criterion":milestone,"criterion_time":"available at check","sent_time":now.strftime("%Y-%m-%d %H:%M:%S"),"message_id":result.get("message_id"),"response":"","response_time":"","latency":""}); st.success(f"Sent milestone alert. Current total: {total_steps:,} steps.")
            else: st.info("No new 500-step milestone to send at this check.")
            if not day.empty:
                day["hour"]=day["minute"].dt.floor("h"); hourly=day.groupby("hour")["steps_per_minute"].sum(); completed=hourly[hourly.index+timedelta(hours=1)<=now]; eligible=[(h,int(c)) for h,c in completed.items() if c<=10 and str(h) not in st.session_state.low_hours_sent]
                if eligible:
                    hour,count=eligible[-1]; label=f"{hour.strftime('%-I:%M %p')}–{(hour+timedelta(hours=1)).strftime('%-I:%M %p')}"; text=f"Don't forget to move! Only {count} steps were recorded from {label}."; keyboard={"inline_keyboard":[[{"text":"🏃 On it!","callback_data":f"on_it:{int(time.time())}"},{"text":"⏰ Remind me later","callback_data":f"remind30:{int(time.time())}"}]]}; result=post("sendMessage",{"chat_id":chat_id,"text":text,"reply_markup":keyboard}); st.session_state.low_hours_sent.add(str(hour)); st.session_state.activity_alert_log.append({"type":"low-activity reminder","criterion":f"{label}: {count} steps","criterion_time":str(hour+timedelta(hours=1)),"sent_time":now.strftime("%Y-%m-%d %H:%M:%S"),"message_id":result.get("message_id"),"response":"","response_time":"","latency":""}); st.success(f"Sent low-activity reminder for {label}.")
        if st.button("Check activity-alert responses"):
            try:
                found=0
                for update in get_updates():
                    cb=update.get("callback_query") or {}; cid=str(cb.get("id","")); msg=cb.get("message") or {}; mid=msg.get("message_id"); data=cb.get("data","")
                    if not cid or cid in st.session_state.processed_alert_callbacks: continue
                    if not (data.startswith("step_got_it:") or data.startswith("on_it:") or data.startswith("remind30:")): continue
                    matching=next((row for row in reversed(st.session_state.activity_alert_log) if row.get("message_id")==mid),None)
                    if matching:
                        response_time=datetime.now(); sent=datetime.strptime(matching["sent_time"],"%Y-%m-%d %H:%M:%S"); seconds=max(0,int((response_time-sent).total_seconds())); matching["response"]={"step_got_it":"Got it","on_it":"On it!","remind30":"Remind me later"}.get(data.split(":")[0],data); matching["response_time"]=response_time.strftime("%Y-%m-%d %H:%M:%S"); matching["latency"]=f"{seconds//60}m {seconds%60}s"
                        # Callback acknowledgement can expire quickly; button removal is the important persistent UI action.
                        try: post("editMessageReplyMarkup",{"chat_id":chat_id,"message_id":mid,"reply_markup":{"inline_keyboard":[]}})
                        except Exception: pass
                        found+=1
                    st.session_state.processed_alert_callbacks.add(cid)
                if found: st.success(f"Recorded {found} response(s). Used Telegram buttons were removed when possible.")
                else: st.info("No new activity-alert responses found.")
            except Exception as exc: st.error(str(exc))
        st.caption("For this prototype, click Evaluate after new Fitbit data are retrieved. Automatic background evaluation comes later.")
        if st.session_state.activity_alert_log:
            st.subheader("Alert log"); st.dataframe(st.session_state.activity_alert_log,use_container_width=True,hide_index=True)
