import io
import json
import time
import requests
import streamlit as st
from datetime import datetime
from openai import OpenAI

# --------- Config / secrets ----------

TAVUS_API_KEY    = st.secrets["tavus"]["api_key"]
TAVUS_PERSONA_ID = st.secrets["tavus"]["persona_id"]
TAVUS_REPLICA_ID = st.secrets["tavus"]["replica_id"]
OPENAI_API_KEY   = st.secrets["openai"]["secret_key"] 

# Optional: override if Tavus changes the interactions route
TAVUS_INTERACTIONS_URL = st.secrets.get(
    "TAVUS_INTERACTIONS_URL",
    "https://tavusapi.com/v2/interactions/broadcast"
)

# --------- Helpers ----------
def create_conversation():
    """Create a real-time CVI conversation and return id + embed URL."""
    url = "https://tavusapi.com/v2/conversations"
    payload = {
        "persona_id": TAVUS_PERSONA_ID,
        "replica_id": TAVUS_REPLICA_ID,
        "conversation_name": f"Streamlit-{datetime.utcnow().isoformat(timespec='seconds')}Z"
        # You can also pass callback_url, conversational_context, etc.
    }
    r = requests.post(
        url, json=payload,
        headers={"x-api-key": TAVUS_API_KEY, "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return data["conversation_id"], data["conversation_url"]

def end_conversation(conversation_id: str):
    url = f"https://tavusapi.com/v2/conversations/{conversation_id}/end"
    requests.post(url, headers={"x-api-key": TAVUS_API_KEY}, timeout=15)

def broadcast_echo(conversation_id: str, text: str):
    """
    Tell the replica exactly what to say (Echo Interaction).
    If your account uses a different route, set TAVUS_INTERACTIONS_URL in secrets.
    """
    payload = {
        "message_type": "conversation",          # per Interactions Protocol
        "event_type": "conversation.echo",       # Echo Interaction
        "conversation_id": conversation_id,
        "properties": {"text": text}
    }
    r = requests.post(
        TAVUS_INTERACTIONS_URL,
        headers={"x-api-key": TAVUS_API_KEY, "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=30,
    )
    # If your tenant uses a different path, surface the error in the UI
    if r.status_code >= 400:
        st.error(f"Echo broadcast failed ({r.status_code}): {r.text}")

def openai_transcribe_wav(wav_bytes: bytes) -> str:
    """Transcribe mic audio with OpenAI Whisper."""
    url = "https://api.openai.com/v1/audio/transcriptions"
    files = {
        "file": ("audio.wav", wav_bytes, "audio/wav"),
    }
    data = {"model": "whisper-1"}  # simple & widely supported
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    r = requests.post(url, headers=headers, files=files, data=data, timeout=60)
    r.raise_for_status()
    return r.json()["text"]

def openai_chat(prompt: str, history: list[dict]) -> str:
    """Call ChatGPT (Chat Completions) with a short running history."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    messages = [{"role": "system", "content": "You are a concise, friendly assistant."}]
    messages += history
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "gpt-4o-mini",   # use any chat-capable model on your account
        "messages": messages,
        "temperature": 0.7,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# --------- UI ----------
st.set_page_config(page_title="Interactive Avatar (Tavus + ChatGPT)", layout="wide")
st.title("🎥 Tavus Interactive Avatar + ChatGPT (Streamlit)")

with st.sidebar:
    st.subheader("Session")
    start = st.button("Start / Restart Session", type="primary")
    stop = st.button("End Session")
    st.markdown("—")
    st.caption("Mic ▶️ Speak below, then send:")
    mic = st.audio_input("Push-to-talk", key="mic")  # native Streamlit widget
    text_fallback = st.chat_input("Or type your message…")

if "conv_id" not in st.session_state or start:
    # Start a new real-time call
    try:
        conv_id, conv_url = create_conversation()
        st.session_state["conv_id"] = conv_id
        st.session_state["conv_url"] = conv_url
        st.session_state.setdefault("chat", [])
        st.toast("Conversation started.")
    except Exception as e:
        st.error(f"Failed to create conversation: {e}")

if stop and st.session_state.get("conv_id"):
    end_conversation(st.session_state["conv_id"])
    for k in ("conv_id", "conv_url"):
        st.session_state.pop(k, None)
    st.toast("Conversation ended.")

left, right = st.columns([0.55, 0.45])

with left:
    st.subheader("Live Avatar")
    if st.session_state.get("conv_url"):
        # Embed the conversation room (WebRTC) – user will grant mic/cam in the iframe.
        st.components.v1.iframe(st.session_state["conv_url"], height=560)
    else:
        st.info("Start a session to get the live avatar embed.")

with right:
    st.subheader("Chat Log")
    for role, content in st.session_state.get("chat", []):
        st.chat_message(role).write(content)

    # 1) If mic audio provided, transcribe it
    user_text = None
    if mic is not None:
        try:
            user_text = openai_transcribe_wav(mic.getvalue())
        except Exception as e:
            st.error(f"Transcription failed: {e}")

    # 2) Or typed text
    if text_fallback:
        user_text = text_fallback

    # 3) Send to ChatGPT, then tell Tavus to speak the reply
    if user_text and st.session_state.get("conv_id"):
        st.session_state["chat"].append(("user", user_text))
        st.chat_message("user").write(user_text)

        try:
            reply = openai_chat(user_text, [
                {"role": r, "content": c} for r, c in st.session_state["chat"]
            ])
            st.session_state["chat"].append(("assistant", reply))
            st.chat_message("assistant").write(reply)

            # Make the avatar say exactly the ChatGPT text
            broadcast_echo(st.session_state["conv_id"], reply)
        except Exception as e:
            st.error(f"Chat or echo failed: {e}")

