import json
import requests
import streamlit as st
from datetime import datetime

# ===================== Config / secrets =====================
# Expect these in .streamlit/secrets.toml

TAVUS_API_KEY    = st.secrets["tavus"]["api_key"]
TAVUS_PERSONA_ID = st.secrets["tavus"]["persona_id"]
TAVUS_REPLICA_ID = st.secrets["tavus"]["replica_id"]

TAVUS_INTERACTIONS_URL = st.secrets.get(
    "TAVUS_INTERACTIONS_URL",
    "https://tavusapi.com/v2/interactions/broadcast"
)

# ===================== API helpers =====================
def create_conversation():
    url = "https://tavusapi.com/v2/conversations"
    payload = {
        "persona_id": TAVUS_PERSONA_ID,
        "replica_id": TAVUS_REPLICA_ID,
        "conversation_name": f"Streamlit-{datetime.utcnow().isoformat(timespec='seconds')}Z"
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

# Session defaults
ss = st.session_state
ss.setdefault("mic_granted", False)
ss.setdefault("cam_granted", False)
ss.setdefault("permission_checked", False)
ss.setdefault("conv_id", None)
ss.setdefault("conv_url", None)

# Reflect query params (set by the permission popup JS)
qp = st.query_params
if qp:
    if "mic" in qp:
        ss.mic_granted = qp.get("mic") == "granted"
    if "cam" in qp:
        ss.cam_granted = qp.get("cam") == "granted"
    if "checked" in qp:
        ss.permission_checked = qp.get("checked") == "1"

# ===================== Styles =====================
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

      /* Compact, light-colored buttons */
      .btn-start button, .btn-join button {
        padding: 6px 10px !important;
        font-size: 14px !important;
        line-height: 1.1 !important;
        border-radius: 10px !important;
        border: none !important;
      }
      .btn-start button { background: #ffc9c9 !important; color: #7a0000 !important; }  /* light red */
      .btn-join  button { background: #c8f7d0 !important; color: #0c5c2a !important; }  /* light green */

      .disabled button { filter: grayscale(100%); opacity: 0.55; pointer-events: none; }

      /* Hide Streamlit chrome on small screens for more room */
      @media (max-width: 600px){
        header[data-testid="stHeader"] { height: 0; min-height: 0; }
        header[data-testid="stHeader"] * { display: none; }
        .block-container { padding-top: 0 !important; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===================== Title =====================
st.markdown('<div class="app-wrapper">', unsafe_allow_html=True)
st.title("Interactive Avatar")

# ===================== Permission popup =====================
# Shows once until permissions are checked; then remains hidden.
# On click:
#   1) Ask MIC; if denied => mic=denied, checked=1; reload (buttons disabled)
#   2) If MIC granted, ask CAM; regardless => cam=granted|denied, checked=1; reload
permission_popup_html = """
<div id="perm-modal" style="
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 9999;
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;">
  <div style="background: white; width: 92%; max-width: 360px; padding: 18px 16px; border-radius: 12px;">
    <h3 style="margin: 0 0 8px 0;">Permissions needed</h3>
    <p style="margin: 0 0 10px 0;">Please allow <b>Microphone</b> access to continue. We will then ask for <b>Camera</b> (optional).</p>
    <button id="go" style="width:100%; padding: 10px 12px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;">
      Continue
    </button>
  </div>
</div>
<script>
(function(){
  const modal = document.getElementById('perm-modal');
  const btn = document.getElementById('go');
  if (!btn) return;

  btn.onclick = async () => {
    // Hide the modal immediately so it doesn't visually "stick"
    if (modal) modal.style.display = 'none';

    let mic = 'denied', cam = 'denied';

    // Request Microphone
    try {
      await navigator.mediaDevices.getUserMedia({audio: true});
      mic = 'granted';
    } catch(e) {
      mic = 'denied';
    }

    // If MIC granted, try camera next (optional)
    if (mic === 'granted') {
      try {
        const s = await navigator.mediaDevices.getUserMedia({video: true});
        s.getTracks().forEach(t => t.stop());
        cam = 'granted';
      } catch(e) {
        cam = 'denied';
      }
    }

    // Update the URL query params and reload so Streamlit picks up state
    const url = new URL(window.location.href);
    url.searchParams.set('mic', mic);
    url.searchParams.set('cam', cam);
    url.searchParams.set('checked', '1');
    window.location.assign(url.toString());  // ensures a full rerun
  };
})();
</script>
"""

if not ss.permission_checked:
    st.components.v1.html(permission_popup_html, height=220)

# ===================== Buttons =====================
st.markdown('<div class="btn-row">', unsafe_allow_html=True)

col_start, col_join = st.columns(2)
with col_start:
    start_disabled = not ss.mic_granted
    start_classes = "btn-start" + (" disabled" if start_disabled else "")
    st.markdown(f'<div class="{start_classes}">', unsafe_allow_html=True)
    start_clicked = st.button("Start", key="btn_start", disabled=start_disabled, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_join:
    join_disabled = not ss.mic_granted
    join_classes = "btn-join" + (" disabled" if join_disabled else "")
    st.markdown(f'<div class="{join_classes}">', unsafe_allow_html=True)
    join_clicked = st.button("Join", key="btn_join", disabled=join_disabled, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ===================== Start / Join handlers =====================
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

# ===================== Video stack =====================
st.markdown('<div class="video-stack">', unsafe_allow_html=True)

# Top: Avatar
st.markdown('<div class="slot">', unsafe_allow_html=True)
if ss.get("conv_url"):
    st.components.v1.iframe(ss["conv_url"], height=360, scrolling=False)
else:
    st.info("Tap Start or Join to begin the session.")
st.markdown('</div>', unsafe_allow_html=True)

# Bottom: User video (or black)
st.markdown('<div class="slot" style="margin-top: 10px;">', unsafe_allow_html=True)
if ss.cam_granted:
    cam_html = """
    <video id="me" autoplay playsinline muted style="width:100%; height:100%; object-fit: cover; background:#000;"></video>
    <script>
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({video:true, audio:false});
        const v = document.getElementById('me');
        if (v) v.srcObject = stream;
      } catch (e) {
        /* leave black screen if camera later denied */
      }
    })();
    </script>
    """
    st.components.v1.html(cam_html, height=360)
else:
    st.markdown('<div style="width:100%; height:100%; background:#000;"></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)  # .video-stack

# Optional End button
if ss.get("conv_id"):
    if st.button("End", use_container_width=True):
        end_conversation(ss["conv_id"])
        ss["conv_id"] = None
        ss["conv_url"] = None
        st.toast("Session ended.")

st.markdown('</div>', unsafe_allow_html=True)  # .app-wrapper
