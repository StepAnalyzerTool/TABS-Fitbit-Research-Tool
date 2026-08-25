from datetime import datetime, timedelta
import time
import requests
import streamlit as st


def render_activity_alert_test(steps_df):
    with st.expander("🚶 Activity Alert Test", expanded=False):
        st.write("Prototype step-dependent Telegram contingencies using the Fitbit data currently loaded in this app.")
        token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = st.session_state.get("tg_chat_id")
        if not token:
            st.error("Telegram bot token is not configured.")
            return
        if not chat_id:
            st.info("First use Telegram Notification Test to find/select your Telegram chat.")
            return
        if steps_df is None or steps_df.empty:
            st.info("Retrieve Fitbit data first so the alert test has step data to evaluate.")
            return

        def api(method, payload):
            r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=30)
            r.raise_for_status()
            body = r.json()
            if not body.get("ok"):
                raise RuntimeError(body.get("description", "Telegram API error"))
            return body.get("result")

        today = datetime.now().date()
        day = steps_df[steps_df["minute"].dt.date == today].copy()
        total_steps = int(day["steps_per_minute"].fillna(0).sum()) if not day.empty else 0
        st.metric("Steps currently available for today", total_steps)

        if "activity_alert_log" not in st.session_state:
            st.session_state.activity_alert_log = []
        if "step_milestones_sent" not in st.session_state:
            st.session_state.step_milestones_sent = set()
        if "low_hours_sent" not in st.session_state:
            st.session_state.low_hours_sent = set()

        if st.button("Evaluate step-alert rules now", type="primary"):
            now = datetime.now()
            # 500-step milestones. Only new boundaries are sent once per app session.
            reached = (total_steps // 500) * 500
            milestones = list(range(500, reached + 1, 500))
            new_milestones = [m for m in milestones if m not in st.session_state.step_milestones_sent]
            if new_milestones:
                # For a first test with existing data, send only the highest current milestone to avoid a burst of old alerts.
                milestone = max(new_milestones)
                text = f"🎉 Good job! You reached another 500 steps! Total for today is {total_steps:,} steps."
                keyboard = {"inline_keyboard": [[{"text": "👍 Got it", "callback_data": f"step_got_it:{milestone}:{int(time.time())}"}]]}
                result = api("sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": keyboard})
                st.session_state.step_milestones_sent.update(milestones)
                st.session_state.activity_alert_log.append({"type":"500-step milestone","criterion":milestone,"criterion_time":"available at check","sent_time":now.strftime("%Y-%m-%d %H:%M:%S"),"message_id":result.get("message_id"),"response":"","response_time":"","latency":""})
                st.success(f"Sent milestone alert. Current total: {total_steps:,} steps.")
            else:
                st.info("No new 500-step milestone to send at this check.")

            # Evaluate completed clock hours today with <=10 steps.
            if not day.empty:
                day["hour"] = day["minute"].dt.floor("h")
                hourly = day.groupby("hour")["steps_per_minute"].sum()
                completed = hourly[hourly.index + timedelta(hours=1) <= now]
                eligible = [(hour, int(count)) for hour, count in completed.items() if count <= 10 and str(hour) not in st.session_state.low_hours_sent]
                if eligible:
                    hour, count = eligible[-1]
                    label = f"{hour.strftime('%-I:%M %p')}–{(hour + timedelta(hours=1)).strftime('%-I:%M %p')}"
                    text = f"Don't forget to move! Only {count} steps were recorded from {label}."
                    keyboard = {"inline_keyboard": [[{"text":"🏃 On it!","callback_data":f"on_it:{int(time.time())}"},{"text":"⏰ Remind me later","callback_data":f"remind30:{int(time.time())}"}]]}
                    result = api("sendMessage", {"chat_id":chat_id,"text":text,"reply_markup":keyboard})
                    st.session_state.low_hours_sent.add(str(hour))
                    st.session_state.activity_alert_log.append({"type":"low-activity reminder","criterion":f"{label}: {count} steps","criterion_time":str(hour + timedelta(hours=1)),"sent_time":now.strftime("%Y-%m-%d %H:%M:%S"),"message_id":result.get("message_id"),"response":"","response_time":"","latency":""})
                    st.success(f"Sent low-activity reminder for {label}.")

        st.caption("For this prototype, click Evaluate after new Fitbit data are retrieved. Automatic background evaluation comes later.")
        if st.session_state.activity_alert_log:
            st.subheader("Alert log")
            st.dataframe(st.session_state.activity_alert_log, use_container_width=True, hide_index=True)
