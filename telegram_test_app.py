import json
import requests
import streamlit as st

st.set_page_config(page_title="TABS Telegram Test", page_icon="💬", layout="centered")

TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")


def api(method, payload=None):
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from Streamlit Secrets.")
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    if method == "getUpdates":
        response = requests.get(url, params=payload or {}, timeout=30)
    else:
        response = requests.post(url, json=payload or {}, timeout=30)
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "Telegram API error"))
    return body.get("result", [])


def updates():
    return api("getUpdates", {
        "limit": 100,
        "timeout": 0,
        "allowed_updates": json.dumps(["message", "callback_query"]),
    })


def private_chats(items):
    chats = {}
    for item in items:
        callback = item.get("callback_query") or {}
        message = item.get("message") or callback.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") != "private" or "id" not in chat:
            continue
        user = (item.get("message") or {}).get("from") or callback.get("from") or {}
        name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])).strip()
        chats[str(chat["id"])] = name or user.get("username") or str(chat["id"])
    return chats


st.title("TABS Telegram Test")
st.write("Standalone proof of concept for interactive participant notifications.")

if not TOKEN:
    st.error("Telegram bot token is not configured.")
    st.stop()

if st.button("1. Find Telegram chats", type="primary"):
    try:
        st.session_state.tg_updates = updates()
    except Exception as exc:
        st.error(str(exc))

items = st.session_state.get("tg_updates", [])
chats = private_chats(items)

if chats:
    chat_id = st.selectbox("Private chat", list(chats), format_func=lambda value: chats[value])
    st.session_state.tg_chat_id = chat_id
    st.success(f"Found: {chats[chat_id]}")
else:
    chat_id = st.session_state.get("tg_chat_id")

if chat_id:
    message = st.text_area(
        "Message",
        "TABS Activity test: This is your first automated activity notification.",
    )
    if st.button("2. Send test notification", type="primary"):
        keyboard = {
            "inline_keyboard": [[
                {"text": "👍 Got it", "callback_data": "got_it"},
                {"text": "⏰ Remind me later", "callback_data": "remind_me_later"},
            ]]
        }
        try:
            api("sendMessage", {
                "chat_id": chat_id,
                "text": message,
                "reply_markup": keyboard,
            })
            st.success("Sent. Tap a button in Telegram on your phone.")
        except Exception as exc:
            st.error(str(exc))

    if st.button("3. Check button response"):
        try:
            latest = updates()
            callbacks = [x["callback_query"] for x in latest if x.get("callback_query")]
            if callbacks:
                callback = callbacks[-1]
                st.success(f"Received: {callback.get('data')}")
                st.write({
                    "response": callback.get("data"),
                    "user": (callback.get("from") or {}).get("first_name"),
                    "chat_id": ((callback.get("message") or {}).get("chat") or {}).get("id"),
                })
            else:
                st.info("No button response yet.")
        except Exception as exc:
            st.error(str(exc))
