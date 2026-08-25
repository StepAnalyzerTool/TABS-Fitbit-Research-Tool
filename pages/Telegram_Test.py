import json
from datetime import datetime

import requests
import streamlit as st

st.set_page_config(page_title="Telegram Test · TABS Lab", page_icon="💬", layout="centered")

st.markdown("""
<style>
:root { --navy:#082b57; --teal:#0a8b98; --ink:#13233a; }
.block-container { max-width:850px; padding-top:2rem; }
h1,h2,h3 { color:var(--navy); }
.stButton > button[kind="primary"] { background:var(--navy)!important; border-color:var(--navy)!important; border-radius:10px!important; font-weight:700!important; }
.telegram-card { border:1px solid #dce3ea; border-radius:14px; padding:18px 22px; background:#f8fbfd; margin:14px 0; }
.small { color:#667085; font-size:.92rem; }
</style>
""", unsafe_allow_html=True)


def bot_token():
    try:
        return st.secrets["TELEGRAM_BOT_TOKEN"]
    except Exception:
        return ""


def telegram(method, payload=None):
    token = bot_token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured in Streamlit Secrets.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    if method == "getUpdates":
        r = requests.get(url, params=payload or {}, timeout=30)
    else:
        r = requests.post(url, json=payload or {}, timeout=30)
    r.raise_for_status()
    body = r.json()
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "Telegram API request failed."))
    return body.get("result")


def recent_updates():
    return telegram("getUpdates", {"limit": 100, "timeout": 0, "allowed_updates": json.dumps(["message", "callback_query"])})


def find_private_chats(updates):
    chats = {}
    for update in updates:
        msg = update.get("message") or {}
        cb = update.get("callback_query") or {}
        if cb:
            msg = cb.get("message") or msg
        chat = msg.get("chat") or {}
        if chat.get("type") != "private" or "id" not in chat:
            continue
        user = (update.get("message") or {}).get("from") or cb.get("from") or {}
        name = " ".join(x for x in [user.get("first_name", ""), user.get("last_name", "")] if x).strip()
        username = user.get("username")
        label = name or (f"@{username}" if username else f"Chat {chat['id']}")
        if username and name:
            label += f" (@{username})"
        chats[str(chat["id"])] = label
    return chats


def callback_rows(updates):
    rows = []
    for update in updates:
        cb = update.get("callback_query")
        if not cb:
            continue
        user = cb.get("from", {})
        msg = cb.get("message", {})
        rows.append({
            "response": cb.get("data", ""),
            "telegram_user": user.get("username") or user.get("first_name", ""),
            "chat_id": (msg.get("chat") or {}).get("id"),
            "message_id": msg.get("message_id"),
            "update_id": update.get("update_id"),
        })
    return rows


st.title("Telegram Notification Test")
st.caption("TABS Lab · interactive participant-notification proof of concept")

if not bot_token():
    st.error("Telegram bot token is not configured yet.")
    st.stop()

st.markdown('<div class="telegram-card"><strong>Step 1 — Find the test chat</strong><br><span class="small">This reads recent messages sent to TABS Activity, including the /start message.</span></div>', unsafe_allow_html=True)

if st.button("Find Telegram chats", type="primary"):
    try:
        st.session_state.telegram_updates = recent_updates()
    except Exception as e:
        st.error(f"Could not read Telegram updates: {e}")

updates = st.session_state.get("telegram_updates", [])
chats = find_private_chats(updates) if updates else {}

if chats:
    options = list(chats.keys())
    selected_chat = st.selectbox("Private chat", options, format_func=lambda x: chats[x])
    st.session_state.telegram_chat_id = selected_chat
    st.success(f"Found private chat: {chats[selected_chat]}")
else:
    selected_chat = st.session_state.get("telegram_chat_id")
    if updates:
        st.warning("No private chat was found. Send /start or another message to TABS Activity in Telegram, then click Find Telegram chats again.")

if selected_chat:
    st.markdown('<div class="telegram-card"><strong>Step 2 — Send an interactive notification</strong><br><span class="small">The buttons are real Telegram inline buttons. Your selection will be returned to the bot.</span></div>', unsafe_allow_html=True)
    default_message = "TABS Activity test: This is your first automated activity notification."
    message = st.text_area("Test message", value=default_message, height=90)

    if st.button("Send test notification", type="primary"):
        keyboard = {
            "inline_keyboard": [[
                {"text": "👍 Got it", "callback_data": "got_it"},
                {"text": "⏰ Remind me later", "callback_data": "remind_me_later"},
            ]]
        }
        try:
            result = telegram("sendMessage", {
                "chat_id": selected_chat,
                "text": message,
                "reply_markup": keyboard,
            })
            st.session_state.telegram_sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success("Notification sent. Check Telegram on your phone and tap one of the buttons.")
        except Exception as e:
            st.error(f"Could not send the Telegram message: {e}")

    st.markdown('<div class="telegram-card"><strong>Step 3 — Read the button response</strong><br><span class="small">After tapping a button on your phone, return here and check for the response.</span></div>', unsafe_allow_html=True)
    if st.button("Check button response"):
        try:
            updates = recent_updates()
            st.session_state.telegram_updates = updates
            rows = callback_rows(updates)
            if rows:
                latest = rows[-1]
                st.success(f"Received response: {latest['response']}")
                st.json(latest)
            else:
                st.info("No button response received yet. Tap a button in Telegram, then try again.")
        except Exception as e:
            st.error(f"Could not read Telegram responses: {e}")

st.divider()
st.caption("From the CVC Cosmos · Turning movement into data")
