import json
import requests
import streamlit as st
from datetime import datetime

# ============ Config / secrets ============
TAVUS_API_KEY    = st.secrets["tavus"]["api_key"]
TAVUS_PERSONA_ID = st.secrets["tavus"]["persona_id"]
TAVUS_REPLICA_ID = st.secrets["tavus"]["replica_id"]

# Optional: override if Tavus changes the interactions route
TAVUS_INTERACTIONS_URL = st.secrets.get(
    "TAVUS_INTERACTIONS_URL",
    "https://tavusapi.com/v2/interactions/broadcast"
)

# ============ API helpers ============
def create_conversation():
    """Create a real-time CVI conversation and return id + embed URL."""
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
    url = f"https://tavusapi.com/v2/conversations/{conversation_id}/end"
    requests.post(url, headers={"x-api-key": TAVUS_API_KEY}, timeout=15)

def broadcast_echo(conversation_id: str, text: str):
    """Optional: If you later want to drive the avatar to say exact text."""
    payload = {
        "message_type": "conversation",
        "event_type": "conversation.echo",
        "conversation_id": conversation_id,
        "properties": {"text": text}
    }
    r = requests.post(
        TAVUS_INTERACTIONS_URL,
        headers={"x-api-key": TAVUS_API_KEY, "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=30,
    )
    if r.status_code >= 400:
        st.error(f"Echo broadcast failed ({r.status_code}): {r.text}")

# ============ Page setup ============
st.set_page_config(page_title="Interactive Avatar", page_icon="🎥", layout="centered")

# Session defaults
ss = st.session_state
ss.setdefault("mic_granted", False)
ss.setdefault("cam_granted", False)
ss.setdefault("conv_id", None)
ss.setdefault("conv_url", None)
ss.setdefault("permission_checked", False)

# Read permission flags if set via query params by the popup component
qp = st.query_params
if "mic" in qp:
    ss.mic_granted = qp.get("mic", "") == "granted"
if "cam" in qp:
    ss.cam_granted = qp.get("cam", "") == "granted"
if "checked" in qp:
    ss.permission_checked = qp.get("checked", "") == "1"

# ============ Title ============
st.markdown(
    """
    <style>
      /* Keep everything comfortably mobile-friendly */
      .app-wrapper { max-width: 480px; margin: 0 auto; }
      .video-stack { width: 100%; }
      .slot {
        width: 100%;
        height: 42vh;               /* two equal blocks fit in one phone screen */
        max-height: 360px;           /* cap on larger phones */
        background: #000;            /* black if no video */
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 14px rgba(0,0,0,0.25);
      }
      .btn-row { display: flex; gap: 12px; width: 100%; }
      .btn-row > div { flex: 1; }
      .btn-start button { background: #d40000 !important; color: #fff !important; border: none !important; }
      .btn-join  button { background: #12a150 !important; color: #fff !important; border: none !important; }
      .disabled button { filter: grayscale(100%); opacity: 0.6; pointer-events: none; }
      /* Hide Streamlit's top-toolbar on small screens for more room */
      @media (max-width: 600px){
        header[data-testid="stHeader"] { height: 0; min-height: 0; }
        header[data-testid="stHeader"] * { display: none; }
        .block-container { padding-top: 0 !important; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="app-wrapper">', unsafe_allow_html=True)
st.title("Interactive Avatar")

# ============ Permission popup (JS) ============
# This component shows a modal-like popup, asks for mic first, then camera.
# It writes results back through URL query parameters and reloads the page.
permission_popup_html = """
<div id="perm-modal" style="
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 9999;
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;">
  <div style="background: white; width: 92%; max-width: 360px; padding: 18px 16px; border-radius: 12px;">
    <h3 style="margin: 0 0 8px 0;">Permissions needed</h3>
    <p style="margin: 0 0 10px 0;">To continue, please allow <b>Microphone</b> access. We'll then ask for <b>Camera</b> access (optional).</p>
    <button id="go" style="width:100%; padding: 10px 12px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;">
      Continue
    </button>
  </div>
</div>
<script>
(async () => {
  const btn = document.getElementById('go');
  if (!btn) return;
  btn.onclick = async () => {
    let mic = 'denied', cam = 'denied';
    try {
      // Ask MIC first
      await navigator.mediaDevices.getUserMedia({audio: true});
      mic = 'granted';
    } catch (e) {
      mic = 'denied';
    }
    if (mic === 'granted') {
      // Then ask CAM
      try {
        const s = await navigator.mediaDevices.getUserMedia({video: true});
        // Stop tracks immediately; we only needed permission probe here.
        s.getTracks().forEach(t => t.stop());
        cam = 'granted';
      } catch (e) {
        cam = 'denied';
      }
    }

    // Write query params and reload
    const url = new URL(window.location.href);
    url.searchParams.set('mic', mic);
    url.searchParams.set('cam', cam);
    url.searchParams.set('checked', '1');
    window.location.replace(url.toString());
  };
})();
</script>
"""

# ============ Controls ============
# Buttons are disabled if mic permission not granted (as requested).
btn_container = st.container()
with btn_container:
    st.markdown('<div class="btn-row">', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        start_disabled = not ss.mic_granted
        start_classes = "btn-start" + (" disabled" if start_disabled else "")
        st.markdown(f'<div class="{start_classes}">', unsafe_allow_html=True)
        start_clicked = st.button("Start", key="btn_start", disabled=start_disabled, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        join_disabled = not ss.mic_granted
        join_classes = "btn-join" + (" disabled" if join_disabled else "")
        st.markdown(f'<div class="{join_classes}">', unsafe_allow_html=True)
        join_clicked = st.button("Join", key="btn_join", disabled=join_disabled, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# If user hasn’t checked permissions yet (first load or they dismissed), show popup.
if not ss.permission_checked:
    st.components.v1.html(permission_popup_html, height=180)

# Handle Start/Join
if start_clicked:
    # (Re)start conversation
    try:
        if ss.conv_id:
            end_conversation(ss.conv_id)
    except Exception:
        pass
    try:
        conv_id, conv_url = create_conversation()
        ss.conv_id = conv_id
        ss.conv_url = conv_url
        st.toast("Session started.")
    except Exception as e:
        st.error(f"Failed to create conversation: {e}")

if join_clicked and not ss.conv_url:
    # If Join pressed before a session exists, create one implicitly
    try:
        conv_id, conv_url = create_conversation()
        ss.conv_id = conv_id
        ss.conv_url = conv_url
        st.toast("Joined session.")
    except Exception as e:
        st.error(f"Failed to join/create conversation: {e}")

# ============ Video stack ============
# Top: Avatar (Tavus room) — always shown once session exists
# Bottom: User camera if granted; otherwise black screen.
top = st.container()
bottom = st.container()

with top:
    st.markdown('<div class="video-stack">', unsafe_allow_html=True)
    st.markdown('<div class="slot">', unsafe_allow_html=True)
    if ss.conv_url:
        # Embed the Tavus conversation room (WebRTC).
        # Permissions will also be requested inside the iframe by the room itself.
        st.components.v1.iframe(ss.conv_url, height=360, scrolling=False)
    else:
        st.info("Tap Start or Join to begin the session.")
    st.markdown('</div>', unsafe_allow_html=True)

with bottom:
    st.markdown('<div class="slot" style="margin-top: 10px;">', unsafe_allow_html=True)
    if ss.cam_granted:
        # Lightweight inline camera preview (client-side only)
        cam_html = """
        <video id="me" autoplay playsinline muted style="width:100%; height:100%; object-fit: cover; background:#000;"></video>
        <script>
        (async () => {
          try {
            const stream = await navigator.mediaDevices.getUserMedia({video:true, audio:false});
            const v = document.getElementById('me');
            if (v) v.srcObject = stream;
          } catch (e) {
            // If user revokes afterward, keep black screen.
          }
        })();
        </script>
        """
        st.components.v1.html(cam_html, height=360)
    else:
        # Black box reserved for user video (per requirement)
        st.markdown(
            '<div style="width:100%; height:100%; background:#000;"></div>',
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Optional: small footer actions
end_col = st.container()
with end_col:
    if ss.conv_id and st.button("End", use_container_width=True):
        try:
            end_conversation(ss.conv_id)
        except Exception:
            pass
        for k in ("conv_id", "conv_url"):
            ss.pop(k, None)
        st.toast("Session ended.")

st.markdown('</div>', unsafe_allow_html=True)
