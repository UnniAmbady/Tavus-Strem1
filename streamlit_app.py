# streamlit_app.py — Version 2 (Avatar + ChatGPT)

import os, io, json, time, base64, tempfile, requests
from datetime import datetime
import streamlit as st
from openai import OpenAI
import openai  # for exception types

# ===================== Config / secrets =====================
# .streamlit/secrets.toml (examples)
# [tavus]
# api_key     = "..."
# persona_id  = "..."
# replica_id  = "..."
# interactions_url = "https://tavusapi.com/v2/interactions/broadcast"
#
# [openai]
# secret_key  = "..."

TAVUS_API_KEY    = st.secrets["tavus"]["api_key"]
TAVUS_PERSONA_ID = st.secrets["tavus"]["persona_id"]
TAVUS_REPLICA_ID = st.secrets["tavus"]["replica_id"]

# Accept both flat and nested spellings for the interactions URL
def _get_interactions_url():
    if "tavus" in st.secrets and "interactions_url" in st.secrets["tavus"]:
        return st.secrets["tavus"]["interactions_url"]
    return (
        st.secrets.get("interactions_url")
        or st.secrets.get("TAVUS_INTERACTIONS_URL")
        or "https://tavusapi.com/v2/interactions/broadcast"
    )

TAVUS_INTERACTIONS_URL = _get_interactions_url()

OPENAI_API_KEY   = st.secrets["openai"]["secret_key"]

# Writable location for your log
TRANSCRIPT_FILE = os.path.join(tempfile.gettempdir(), "conversation.txt")


# ===================== OpenAI client & helpers =====================
def get_openai_client():
    if not OPENAI_API_KEY:
        raise RuntimeError("OpenAI API key missing in secrets.")
    return OpenAI(api_key=OPENAI_API_KEY)

client = get_openai_client()

def validate_openai():
    try:
        _ = client.models.list()
    except openai.AuthenticationError:
        raise RuntimeError("OpenAI auth failed: invalid/revoked key.")
    except openai.RateLimitError:
        raise RuntimeError("OpenAI rate limit / quota exceeded.")
    except Exception as e:
        raise RuntimeError(f"OpenAI check failed: {e}")

def openai_transcribe_wav(wav_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp.write(wav_bytes); tmp.flush()
        try:
            t = client.audio.transcriptions.create(model="whisper-1", file=open(tmp.name, "rb"))
            return t.text
        except openai.AuthenticationError:
            raise RuntimeError("OpenAI auth failed during transcription.")
        except openai.RateLimitError:
            raise RuntimeError("OpenAI quota exceeded during transcription.")
        except Exception as e:
            raise RuntimeError(f"Transcription error: {e}")

def openai_chat_reply(prompt: str, history: list[dict]) -> str:
    messages = [{"role": "system", "content": "You are a concise, friendly assistant."}]
    messages += history
    messages.append({"role": "user", "content": prompt})
    try:
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=messages, temperature=0.6)
        return resp.choices[0].message.content
    except openai.AuthenticationError:
        raise RuntimeError("OpenAI auth failed during chat.")
    except openai.RateLimitError:
        raise RuntimeError("OpenAI quota exceeded during chat.")
    except Exception as e:
        raise RuntimeError(f"Chat error: {e}")


# ===================== Tavus helpers =====================
def create_conversation():
    url = "https://tavusapi.com/v2/conversations"
    payload = {
        "persona_id": TAVUS_PERSONA_ID,
        "replica_id": TAVUS_REPLICA_ID,
        "conversation_name": f"Streamlit-{datetime.utcnow().isoformat(timespec='seconds')}Z",
    }
    r = requests.post(
        url, json=payload,
        headers={"x-api-key": TAVUS_API_KEY, "Content-Type": "application/json"},
        timeout=30,
    )
    if r.status_code == 429:
        raise RuntimeError("Tavus quota/rate limit exceeded while creating conversation (HTTP 429).")
    if r.status_code in (401, 403):
        raise RuntimeError("Tavus auth failed while creating conversation.")
    r.raise_for_status()
    data = r.json()
    return data["conversation_id"], data["conversation_url"]

def end_conversation(conversation_id: str):
    try:
        url = f"https://tavusapi.com/v2/conversations/{conversation_id}/end"
        requests.post(url, headers={"x-api-key": TAVUS_API_KEY}, timeout=15)
    except Exception:
        pass

def broadcast_echo(conversation_id: str, text: str):
    payload = {
        "message_type": "conversation",
        "event_type": "conversation.echo",
        "conversation_id": conversation_id,
        "properties": {"text": text},
    }
    r = requests.post(
        TAVUS_INTERACTIONS_URL,
        headers={"x-api-key": TAVUS_API_KEY, "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=30,
    )
    if r.status_code == 429:
        raise RuntimeError("Tavus quota/rate limit exceeded when speaking (HTTP 429).")
    if r.status_code in (401, 403):
        raise RuntimeError("Tavus auth failed when broadcasting echo.")
    if r.status_code >= 400:
        raise RuntimeError(f"Echo failed ({r.status_code}): {r.text}")


# ===================== Logging stubs (as requested) =====================
def _append(role, text):
    os.makedirs(os.path.dirname(TRANSCRIPT_FILE), exist_ok=True)
    with open(TRANSCRIPT_FILE, "a", encoding="utf-8") as f:
        ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        f.write(f"[{ts}] {role.upper()}: {text.strip()}\n")

def process_input(s: str) -> str:
    _append("input", s)
    return s.strip()

def process_output(s: str) -> str:
    _append("output", s)
    return s.strip()


# ===================== Page (keeps your working V1 layout) =====================
st.set_page_config(page_title="Interactive Avatar", page_icon="🎥", layout="centered")

# Session state
ss = st.session_state
ss.setdefault("conv_id", None)
ss.setdefault("conv_url", None)
ss.setdefault("chat", [])
ss.setdefault("boot_nonce", 0)

# ---- Styles copied from your V1 (minor tweaks only) ----
st.markdown(
    """
    <style>
      :root{ --rad:12px; --gap:12px; }
      .app-wrapper { max-width: 480px; margin: 0 auto; }
      .btn-row{ display:flex; align-items:center; justify-content:center; gap:var(--gap); margin:8px 0 12px 0; }
      .btn-chip{ display:inline-flex; }
      .btn-chip button{ padding:6px 14px !important; font-size:15px !important; line-height:1.1 !important;
                        border-radius:999px !important; border:1px solid rgba(0,0,0,0.08) !important; min-width:96px; }
      .btn-start button{ background:#ffe3e3 !important; color:#6d0000 !important; }
      .room-frame{ width:100%; border:0; border-radius:var(--rad); box-shadow:0 4px 14px rgba(0,0,0,0.22);
                   overflow:hidden; display:block; aspect-ratio:16/9; height:auto; }
      .below-room-spacer{ height:max(16px, env(safe-area-inset-bottom, 0px)); }
      @media (max-width:600px){
        header[data-testid="stHeader"] { height:0; min-height:0; }
        header[data-testid="stHeader"] * { display:none; }
        .block-container { padding-top:6px !important; }
        .room-frame{ aspect-ratio:auto; height:calc(56vh - env(safe-area-inset-top, 0px)); max-height:420px; margin-bottom:10px; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="app-wrapper">', unsafe_allow_html=True)
st.title("Interactive Avatar")

st.info(
    "Please allow **Microphone** (required) and **Camera** (optional, for the room) when prompted.",
    icon="🔐",
)

# ---- Button row (like V1) ----
st.markdown('<div class="btn-row">', unsafe_allow_html=True)
st.markdown('<div class="btn-chip btn-start">', unsafe_allow_html=True)
start_clicked = st.button("Start", key="btn_start")
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Start handler
if start_clicked:
    # Validate OpenAI quickly so Send & Speak won’t surprise the user later
    try:
        validate_openai()
    except Exception as e:
        st.error(str(e))
        st.stop()

    # End any previous session, then create a new Tavus conversation
    if ss.get("conv_id"):
        end_conversation(ss["conv_id"])
    try:
        conv_id, conv_url = create_conversation()
        ss["conv_id"], ss["conv_url"] = conv_id, conv_url
        ss["boot_nonce"] = time.time()   # used only for cache-busting if you decide to append as query
        st.toast("Session started.")
    except Exception as e:
        st.error(f"Failed to start: {e}")
        st.stop()

# ---- Room (exactly like your V1 embed pattern; no key= anywhere) ----
if ss.get("conv_url"):
    # Use the working embed approach from V1
    st.components.v1.html(
        f'<iframe src="{ss["conv_url"]}" class="room-frame" '
        'allow="camera; microphone; clipboard-read; clipboard-write"></iframe>',
        height=540,   # desktop; CSS will adjust on phones
    )
    st.markdown('<div class="below-room-spacer"></div>', unsafe_allow_html=True)
else:
    st.info("Tap Start to begin the session.")

# ---- Chat controls (push-to-talk + optional text) ----
col1, col2 = st.columns(2)
with col1:
    mic_blob = st.audio_input("Hold to record, then release", key="mic_in")
with col2:
    text_fallback = st.text_input("Type a message (optional)", "")

send_clicked = st.button("Send & Speak", type="primary", use_container_width=True)

# ---- End button ----
if ss.get("conv_id"):
    if st.button("End", use_container_width=True):
        end_conversation(ss["conv_id"])
        ss["conv_id"] = None
        ss["conv_url"] = None
        st.toast("Session ended.")

# ---- Log utilities ----
with st.expander("Conversation Log"):
    btns = st.columns(2)
    with btns[0]:
        if st.button("Open Log"):
            if os.path.exists(TRANSCRIPT_FILE):
                with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
                    st.code(f.read()[-4000:] or "(empty)", language="text")
            else:
                st.info("No conversation.txt yet.")
    with btns[1]:
        if st.button("Clear Log"):
            try:
                if os.path.exists(TRANSCRIPT_FILE):
                    os.remove(TRANSCRIPT_FILE)
                st.success("Cleared conversation.txt")
            except Exception as e:
                st.error(f"Could not clear log: {e}")

# ===================== Conversation pipeline =====================
def run_pipeline(user_text: str):
    """ASR (if recorded) -> process_input -> GPT -> process_output -> Tavus speak."""
    # 1) preprocessing/log
    inp = process_input(user_text)

    # 2) GPT with simple rolling memory
    history = [{"role": r, "content": c} for (r, c) in ss.get("chat", [])]
    reply = openai_chat_reply(inp, history)
    out = process_output(reply)

    # 3) update UI history
    ss["chat"].append(("user", inp))
    st.chat_message("user").write(inp)
    ss["chat"].append(("assistant", out))
    st.chat_message("assistant").write(out)

    # 4) make the avatar speak exactly that text
    if ss.get("conv_id"):
        try:
            broadcast_echo(ss["conv_id"], out)
        except Exception as e:
            st.error(str(e))
    else:
        st.warning("No active Tavus conversation. Tap Start to open a session.")

if send_clicked:
    # Prefer audio -> Whisper; otherwise use typed text
    text = None
    if mic_blob is not None:
        try:
            text = openai_transcribe_wav(mic_blob.getvalue())
        except Exception as e:
            st.error(str(e))
    if not text and text_fallback.strip():
        text = text_fallback.strip()

    if not text:
        st.warning("Please record audio or type a message.")
    else:
        try:
            run_pipeline(text)
        except Exception as e:
            st.error(str(e))

st.markdown("</div>", unsafe_allow_html=True)  # .app-wrapper

