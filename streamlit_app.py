import requests
import streamlit as st
from datetime import datetime

# ===================== Config / secrets =====================
# .streamlit/secrets.toml
TAVUS_API_KEY    = st.secrets["tavus"]["api_key"]
TAVUS_PERSONA_ID = st.secrets["tavus"]["persona_id"]
TAVUS_REPLICA_ID = st.secrets["tavus"]["replica_id"]

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
    r.raise_for_status()
    data = r.json()
    return data["conversation_id"], data["conversation_url"]

def end_conversation(conversation_id: str):
    try:
        url = f"https://tavusapi.com/v2/conversations/{conversation_id}/end"
        requests.post(url, headers={"x-api-key": TAVUS_API_KEY}, timeout=15)
    except Exception:
        pass

# ===================== Page setup =====================
st.set_page_config(page_title="Interactive Avatar", page_icon="🎥", layout="centered")

ss = st.session_state
ss.setdefault("conv_id", None)
ss.setdefault("conv_url", None)

# ===================== Styles =====================
st.markdown(
    """
    <style>
      :root{
        /* soft radii + spacing that work on phones */
        --rad: 12px;
        --gap: 12px;
      }

      .app-wrapper { max-width: 480px; margin: 0 auto; }

      /* ---- Buttons row: tiny, centered left/right ---- */
      .btn-row{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--gap);
        margin: 8px 0 12px 0;
      }
      .btn-chip { display: inline-flex; }

      /* Make Streamlit buttons look like compact "chips" */
      .btn-chip button{
        padding: 6px 14px !important;      /* small, just enough for text */
        font-size: 15px !important;
        line-height: 1.1 !important;
        border-radius: 999px !important;    /* pill */
        border: 1px solid rgba(0,0,0,0.08) !important;
        min-width: 96px;                    /* keeps both readable */
      }
      .btn-start button { background: #ffe3e3 !important; color: #6d0000 !important; } /* light red */
      .btn-join  button { background: #dbffe6 !important; color: #0c5c2a  !important; } /* light green */

      /* ---- Video container (Tavus room) ----
         - Use aspect-ratio on desktop
         - On small phones, use a vh-based height so controls fit */
      .room-frame{
        width: 100%;
        border: 0;
        border-radius: var(--rad);
        box-shadow: 0 4px 14px rgba(0,0,0,0.22);
        overflow: hidden;
        display: block;
        aspect-ratio: 16/9;        /* nice on desktop */
        height: auto;
      }

      /* Spacing below the iframe so the page UI never crowds the room's own control bar */
      .below-room-spacer{
        height: max(16px, env(safe-area-inset-bottom, 0px));
      }

      /* ---- Mobile tuning ---- */
      @media (max-width: 600px){
        header[data-testid="stHeader"] { height: 0; min-height: 0; }
        header[data-testid="stHeader"] * { display: none; }
        .block-container { padding-top: 6px !important; }

        /* Use a fixed vh height for the iframe on phones so nothing feels cramped.
           Leave extra space so the room's bottom controls are fully visible. */
        .room-frame{
          aspect-ratio: auto;
          height: calc(56vh - env(safe-area-inset-top, 0px));
          max-height: 420px;
          margin-bottom: 10px;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===================== UI =====================
st.markdown('<div class="app-wrapper">', unsafe_allow_html=True)
st.title("Interactive Avatar")

# Static info (no popup)
st.info(
    "Permissions needed\n\nPlease allow **Microphone** access to continue. "
    "We will then ask for **Camera** (optional).",
    icon="🔐",
)

# Small centered buttons (chip style)
st.markdown('<div class="btn-row">', unsafe_allow_html=True)
st.markdown('<div class="btn-chip btn-start">', unsafe_allow_html=True)
start_clicked = st.button("Start", key="btn_start")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="btn-chip btn-join">', unsafe_allow_html=True)
join_clicked = st.button("Join", key="btn_join")
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)  # end .btn-row

# Handlers
if start_clicked:
    if ss.get("conv_id"):
        end_conversation(ss["conv_id"])
    try:
        conv_id, conv_url = create_conversation()
        ss["conv_id"], ss["conv_url"] = conv_id, conv_url
        st.toast("Session started.")
    except Exception as e:
        st.error(f"Failed to start: {e}")

if join_clicked and not ss.get("conv_url"):
    try:
        conv_id, conv_url = create_conversation()
        ss["conv_id"], ss["conv_url"] = conv_id, conv_url
        st.toast("Joined session.")
    except Exception as e:
        st.error(f"Failed to join: {e}")

# ===================== Single video area (Tavus room only) =====================
if ss.get("conv_url"):
    st.components.v1.html(
        f'<iframe src="{ss["conv_url"]}" class="room-frame" '
        'allow="camera; microphone; clipboard-read; clipboard-write"></iframe>',
        height=540,   # desktop; overridden by CSS on phones
    )
    # Spacer to guarantee the page UI sits below the room's own control bar on phones
    st.markdown('<div class="below-room-spacer"></div>', unsafe_allow_html=True)
else:
    st.info("Tap Start or Join to begin the session.")

# End button (single, centered)
if ss.get("conv_id"):
    if st.button("End", use_container_width=True):
        end_conversation(ss["conv_id"])
        ss["conv_id"] = None
        ss["conv_url"] = None
        st.toast("Session ended.")

st.markdown("</div>", unsafe_allow_html=True)  # .app-wrapper
