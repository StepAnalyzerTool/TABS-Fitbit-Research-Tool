import json
import requests
import streamlit as st


def render_telegram_test():
    with st.expander("💬 Telegram Notification Test"):
        st.write("Test interactive notifications before connecting them to Fitbit criteria.")
        token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            st.error("Telegram bot token is not configured in Streamlit Secrets.")
            return

        def api(method, payload=None):
            url = f"https://api.telegram.org/bot{token}/{method}"
            if method == "getUpdates":
                r = requests.get(url, params=payload or {}, timeout=30)
            else:
                r = requests.post(url, json=payload or {}, timeout=30)
            r.raise_for_status()
            body = r.json()
            if not body.get("ok"):
                raise RuntimeError(body.get("description", "Telegram API error"))
            return body.get("result", [])

        def updates():
            return api("getUpdates", {
                "limit": 100,
                "timeout": 0,
                "allowed_updates": json.dumps(["message", "callback_query"]),
            })

        if st.button("1. Find Telegram chats", type="primary"):
            try:
                st.session_state.tg_updates = updates()
            except Exception as exc:
                st.error(str(exc))

        chats = {}
        for item in st.session_state.get("tg_updates", []):
            cb = item.get("callback_query") or {}
            msg = item.get("message") or cb.get("message") or {}
            chat = msg.get("chat") or {}
            if chat.get("type") != "private" or "id" not in chat:
                continue
            user = (item.get("message") or {}).get("from") or cb.get("from") or {}
            name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])).strip()
            chats[str(chat["id"])] = name or user.get("username") or str(chat["id"])

        chat_id = None
        if chats:
            chat_id = st.selectbox("Private chat", list(chats), format_func=lambda value: chats[value])
            st.session_state.tg_chat_id = chat_id
            st.success(f"Found: {chats[chat_id]}")
        else:
            chat_id = st.session_state.get("tg_chat_id")

        if not chat_id:
            return

        message = st.text_area("Message", "TABS Activity test: This is your first automated activity notification.")
        if st.button("2. Send test notification", type="primary"):
            keyboard = {"inline_keyboard": [[
                {"text": "👍 Got it", "callback_data": "got_it"},
                {"text": "⏰ Remind me later", "callback_data": "remind_me_later"},
            ]]}
            try:
                api("sendMessage", {"chat_id": chat_id, "text": message, "reply_markup": keyboard})
                st.success("Sent. Tap a button in Telegram on your phone.")
            except Exception as exc:
                st.error(str(exc))

        if st.button("3. Check button response"):
            try:
                callbacks = [x["callback_query"] for x in updates() if x.get("callback_query")]
                if callbacks:
                    cb = callbacks[-1]
                    st.success(f"Received: {cb.get('data')}")
                    st.write({"response": cb.get("data"), "user": (cb.get("from") or {}).get("first_name")})
                else:
                    st.info("No button response yet.")
            except Exception as exc:
                st.error(str(exc))
