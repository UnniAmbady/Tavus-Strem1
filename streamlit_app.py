import requests
import streamlit as st
from datetime import datetime

# ========== Config / secrets ==========
# .streamlit/secrets.toml
TAVUS_API_KEY    = st.secrets["tavus"]["api_key"]
TAVUS_PERSONA_ID = st.secrets["tavus"]["persona_id"]
TAVUS_REPLICA_ID = st.secrets["tavus"]["replica_id"]

# ========== Tavus helpers ==========
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

# ========== Page setup ==========
st.set_page_config(page_title="Interactive Avatar", page_icon="🎥", layout="centered")

# Session
ss = st.session_state
ss.setdefault("conv_id", None)
ss.setdefault("conv_url", None)

# ========== Styles ==========
st.markdown(
    """
    <style>
      .app-wrapper { max-width: 480px; margin: 0 auto; }
      .video-stack { width: 100%; }
      .slot {
        width: 100%;
        height: 42vh;                 /* two equal blocks fit on one phone screen */
        max-height: 360px;             /* cap for bigger phones */
        background: #000;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 14px rgba(0,0,0,0.25);
      }
      .btn-row { display: flex; gap: 10px; width: 100%; margin-top: 2px; }
      .btn-row > div { flex: 1; }

      /* Compact, light colors */
      .btn-start button, .btn-join button {
        padding: 6px 10px !important;
        font-size: 14px !important;
        line-height: 1.1 !important;
        border-radius: 10px !important;
        border: none !important;
      }
      .btn-start button { background: #ffc9c9 !important; color: #7a0000 !important; }  /* light red */
      .btn-join  button { background: #c8f7d0 !important; color: #0c5c2a !important; }  /* light green */

      @media (max-width: 600px){
        header[data-testid="stHeader"] { height: 0; min-height: 0; }
        header[data-testid="stHeader"] * { display: none; }
        .block-container { padding-top: 0 !important; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ========== UI ==========
st.markdown('<div class="app-wrapper">', unsafe_allow_html=True)
st.title("Interactive Avatar")

# Static guidance (no modal)
st.info(
    "Permissions needed\n\nPlease allow **Microphone** access to continue. "
    "We will then ask for **Camera** (optional).",
    icon="🔐",
)

# Buttons (enabled by default)
st.markdown('<div class="btn-row">', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.markdown('<div class="btn-start">', unsafe_allow_html=True)
    start_clicked = st.button("Start", key="btn_start", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
with c2:
    st.markdown('<div class="btn-join">', unsafe_allow_html=True)
    join_clicked = st.button("Join", key="btn_join", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

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

# ========== Video stack ==========
st.markdown('<div class="video-stack">', unsafe_allow_html=True)

# Top: Avatar (Tavus)
st.markdown('<div class="slot">', unsafe_allow_html=True)
if ss.get("conv_url"):
    st.components.v1.iframe(ss["conv_url"], height=360, scrolling=False)
else:
    st.info("Tap Start or Join to begin the session.")
st.markdown("</div>", unsafe_allow_html=True)

# Bottom: User camera preview (silent attempt; black if blocked/denied)
st.markdown('<div class="slot" style="margin-top: 10px;">', unsafe_allow_html=True)
cam_html = """
<video id="me" autoplay playsinline muted style="width:100%; height:100%; object-fit: cover; background:#000;"></video>
<script>
(async () => {
  try {
    // Try to get video; if user denies or browser blocks, we simply keep black screen.
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    const v = document.getElementById('me');
    if (v) v.srcObject = stream;
  } catch (e) {
    // Keep black screen silently for prototype testing.
  }
})();
</script>
"""
st.components.v1.html(cam_html, height=360)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)  # .video-stack

# Optional End button
if ss.get("conv_id"):
    if st.button("End", use_container_width=True):
        end_conversation(ss["conv_id"])
        ss["conv_id"] = None
        ss["conv_url"] = None
        st.toast("Session ended.")

st.markdown("</div>", unsafe_allow_html=True)  # .app-wrapper
