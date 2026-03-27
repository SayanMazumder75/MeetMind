"""
app.py — Streamlit dashboard for AI Meeting Notes.

Run with:
    streamlit run dashboard/app.py
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from core.config import config
from core.session import MeetingSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title=config.APP_NAME,
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @keyframes pulse { 0%{opacity:1} 50%{opacity:0.4} 100%{opacity:1} }
    .recording-dot {
        display:inline-block; width:12px; height:12px;
        background:#e53e3e; border-radius:50%;
        animation:pulse 1.2s ease-in-out infinite; margin-right:8px;
    }
    .recording-badge {
        background:#fff5f5; border:1px solid #fc8181; border-radius:8px;
        padding:8px 14px; color:#c53030; font-weight:600; font-size:14px;
        display:inline-flex; align-items:center;
    }
    .chunk-card {
        background:#f8f9fa; border-left:3px solid #4a7fe5;
        padding:8px 12px; margin-bottom:6px;
        border-radius:0 6px 6px 0; font-size:14px;
    }
    .chunk-timestamp { font-size:11px; color:#888; margin-bottom:2px; }
    .chunk-speaker   { font-weight:600; color:#4a7fe5; }
    .chunk-text      { color:#333; line-height:1.5; }
    .lang-badge {
        display:inline-block; font-size:10px; padding:1px 6px;
        border-radius:4px; background:#e9d8fd; color:#553c9a;
        font-weight:600; margin-left:6px; vertical-align:middle;
    }
    .action-item {
        background:#fffbeb; border-left:3px solid #f6ad55;
        padding:6px 12px; margin-bottom:4px;
        border-radius:0; font-size:13px; color:#744210;
    }
    .key-point {
        background:#ebf8ff; border-left:3px solid #63b3ed;
        padding:6px 12px; margin-bottom:4px;
        border-radius:0; font-size:13px; color:#2c5282;
    }
    .summary-box {
        background:#f0fff4; border:1px solid #9ae6b4; border-radius:8px;
        padding:16px; font-size:14px; line-height:1.7; color:#276749;
    }
    .stat-card {
        background:white; border:1px solid #e2e8f0;
        border-radius:8px; padding:16px; text-align:center;
    }
    .stat-value { font-size:28px; font-weight:700; color:#2d3748; }
    .stat-label { font-size:12px; color:#718096; margin-top:4px; }
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "meeting_session":  None,
        "is_recording":     False,
        "session_id":       None,
        "last_chunk_count": 0,
        "meeting_title":    f"Meeting {datetime.now().strftime('%d %b %Y')}",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_state()


# ── Page renderer functions (defined before any calls below) ───────────────────

def _render_welcome():
    st.title("🎙️ AI Meeting Notes")
    st.markdown("""
Welcome! Press **▶ Start Recording** in the sidebar to begin.

This app will:
- Capture audio from Google Meet (via VB-Cable or PulseAudio)
- Transcribe speech in real-time using Whisper
- Generate a summary, action items and key points automatically
- Let you export notes to PDF, Word or Google Docs

---
""")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**Step 1 — Set up audio**\n\nInstall VB-Cable (Windows) or configure PulseAudio loopback (Linux) to route Google Meet audio into the app.")
    with col2:
        st.info("**Step 2 — Configure**\n\nChoose your speech engine (Whisper recommended for offline use) and summarizer in the sidebar settings.")
    with col3:
        st.info("**Step 3 — Record**\n\nClick Start Recording before or during a meeting. The live transcript and summary update automatically.")


def _render_transcript_panel(chunks):
    st.subheader("📝 Live Transcript")

    if not chunks:
        st.caption("Transcript will appear here as you speak…")
        return

    search = st.text_input("🔍 Search transcript", placeholder="Type to search…")

    transcript_html = ""
    for chunk in reversed(chunks):
        if search and search.lower() not in chunk.text.lower():
            continue
        highlighted = chunk.text
        if search:
            highlighted = highlighted.replace(search, f"<mark>{search}</mark>")
        lang = getattr(chunk, "detected_lang", "en")
        lang_badge = f"""<span class="lang-badge">{lang.upper()}</span>""" if lang and lang != "en" else ""
        transcript_html += f"""
        <div class="chunk-card">
            <div class="chunk-timestamp">{chunk.time_label}{lang_badge}</div>
            <span class="chunk-speaker">{chunk.speaker}</span>
            <span class="chunk-text"> {highlighted}</span>
        </div>"""

    st.markdown(
        f'<div style="max-height:520px;overflow-y:auto;">{transcript_html}</div>',
        unsafe_allow_html=True,
    )

    full_text = "\n".join(f"[{c.time_label}] {c.speaker}: {c.text}" for c in chunks)
    st.download_button(
        "📋 Download transcript",
        data=full_text,
        file_name=f"transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
    )


def _render_summary_panel(summary, chunks, session):
    st.subheader("📋 Meeting Summary")

    if summary:
        st.markdown(f'<div class="summary-box">{summary.summary}</div>', unsafe_allow_html=True)
        st.write("")

        if summary.action_items:
            st.markdown("**✅ Action Items**")
            for item in summary.action_items:
                st.markdown(f'<div class="action-item">→ {item}</div>', unsafe_allow_html=True)
            st.write("")

        if summary.key_points:
            st.markdown("**💡 Key Points**")
            for point in summary.key_points:
                st.markdown(f'<div class="key-point">• {point}</div>', unsafe_allow_html=True)
            st.write("")

        if summary.highlights:
            st.markdown("**✨ Highlights**")
            for h in summary.highlights:
                st.markdown(f"> *{h}*")
    else:
        if chunks:
            st.info("Summary generating… (requires ~20+ words of transcript)")
        else:
            st.caption("Summary will appear here once there is enough transcript.")

    if session and chunks:
        topics = session.get_topics()
        if topics:
            st.markdown("**🏷️ Topics Detected**")
            st.write(" · ".join(f"`{t}`" for t in topics[:8]))

    st.write("")
    st.markdown("**📤 Export Notes**")

    session_id = (
        session.session_id if session
        else st.session_state.get("loaded_session_id", "unknown")
    )

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("📄 PDF", use_container_width=True):
            with st.spinner("Generating PDF…"):
                from exports.export_pdf import export_to_pdf
                path = export_to_pdf(
                    session_id=session_id,
                    transcript=chunks,
                    summary=summary,
                    meeting_title=st.session_state.meeting_title,
                )
            with open(path, "rb") as f:
                st.download_button(
                    "⬇ Download PDF", data=f,
                    file_name=path.name, mime="application/pdf",
                )

    with col_b:
        if st.button("📝 Word", use_container_width=True):
            with st.spinner("Generating DOCX…"):
                from exports.export_docx import export_to_docx
                path = export_to_docx(
                    session_id=session_id,
                    transcript=chunks,
                    summary=summary,
                    meeting_title=st.session_state.meeting_title,
                )
            with open(path, "rb") as f:
                st.download_button(
                    "⬇ Download DOCX", data=f,
                    file_name=path.name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )

    with col_c:
        if st.button("📊 Google Docs", use_container_width=True):
            with st.spinner("Exporting to Google Docs…"):
                try:
                    from exports.export_google_docs import export_to_google_docs
                    url = export_to_google_docs(
                        session_id=session_id,
                        transcript=chunks,
                        summary=summary,
                        meeting_title=st.session_state.meeting_title,
                    )
                    if url:
                        st.success(f"[Open in Google Docs]({url})")
                    else:
                        st.error("Failed — check GOOGLE_CREDENTIALS_PATH in .env")
                except Exception as e:
                    st.error(f"Error: {e}")


def _render_live_session():
    session: MeetingSession = st.session_state.meeting_session
    if not session:
        return

    chunks  = session.transcript.get_all()
    summary = session.get_summary()
    dur_sec = int(session.get_duration())

    st.title(f"🎙️ {st.session_state.meeting_title}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="stat-value">{dur_sec//60:02d}:{dur_sec%60:02d}</div><div class="stat-label">Duration</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="stat-value">{len(chunks)}</div><div class="stat-label">Transcript chunks</div></div>', unsafe_allow_html=True)
    with col3:
        words = sum(len(c.text.split()) for c in chunks)
        st.markdown(f'<div class="stat-card"><div class="stat-value">{words}</div><div class="stat-label">Words spoken</div></div>', unsafe_allow_html=True)
    with col4:
        speakers = len(set(c.speaker for c in chunks))
        st.markdown(f'<div class="stat-card"><div class="stat-value">{speakers}</div><div class="stat-label">Speakers</div></div>', unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([1, 1], gap="large")
    with left:
        _render_summary_panel(summary, chunks, session)
    with right:
        _render_transcript_panel(chunks)


def _render_past_session(session_id: str):
    data = MeetingSession.load_session(session_id)
    if not data:
        st.error(f"Session {session_id} not found.")
        return

    from core.transcriber import TranscriptChunk
    from core.summarizer import MeetingSummary

    chunks = [
        TranscriptChunk(
            text=c["text"],
            timestamp=c["timestamp"],
            speaker=c.get("speaker", "Unknown"),
            confidence=c.get("confidence", 1.0),
        )
        for c in data.get("transcript", [])
    ]

    summary = None
    if data.get("summary"):
        s = data["summary"]
        summary = MeetingSummary(
            summary=s.get("summary", ""),
            action_items=s.get("action_items", []),
            key_points=s.get("key_points", []),
            highlights=s.get("highlights", []),
            word_count=s.get("word_count", 0),
            model_used=s.get("model_used", ""),
        )

    st.title(f"📂 Past Session — {session_id}")
    dt  = data.get("started_at", "")[:16].replace("T", " ")
    dur = int(data.get("duration_sec", 0))
    st.caption(f"Recorded: {dt}  |  Duration: {dur//60}m {dur%60}s  |  {len(chunks)} chunks")

    if st.button("← Back to live view"):
        del st.session_state["loaded_session_id"]
        st.rerun()

    st.write("")
    left, right = st.columns([1, 1], gap="large")
    with left:
        _render_summary_panel(summary, chunks, session=None)
    with right:
        _render_transcript_panel(chunks)


# ── Auto-refresh while recording ───────────────────────────────────────────────

if st.session_state.is_recording:
    st_autorefresh(interval=3000, key="live_refresh")


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎙️ AI Meeting Notes")
    st.markdown("---")

    st.session_state.meeting_title = st.text_input(
        "Meeting title",
        value=st.session_state.meeting_title,
        disabled=st.session_state.is_recording,
    )

    with st.expander("⚙️ Engine Settings", expanded=False):
        speech_engine = st.selectbox(
            "Speech engine",
            ["whisper", "assemblyai", "google"],
            index=0,
            disabled=st.session_state.is_recording,
        )
        summarizer = st.selectbox(
            "Summarizer",
            ["transformers", "openai", "claude"],
            index=0,
            disabled=st.session_state.is_recording,
        )
        if speech_engine == "whisper":
            st.selectbox(
                "Whisper model",
                ["tiny", "base", "small", "medium", "large"],
                index=1,
                help="Larger = more accurate but slower",
                disabled=st.session_state.is_recording,
            )

    st.markdown("---")

    if not st.session_state.is_recording:
        if st.button("▶ Start Recording", use_container_width=True, type="primary"):
            session = MeetingSession(
                speech_engine=speech_engine,
                summarizer_engine=summarizer,
            )
            session.start()
            st.session_state.meeting_session = session
            st.session_state.is_recording    = True
            st.session_state.session_id      = session.session_id
            st.rerun()
    else:
        st.markdown(
            '<div class="recording-badge"><span class="recording-dot"></span>Recording…</div>',
            unsafe_allow_html=True,
        )
        st.write("")
        if st.button("⏹ Stop Recording", use_container_width=True):
            session = st.session_state.get("meeting_session")

            if session:
                try:
                    with st.spinner("Finalizing session…"):
                        session.stop()

                except Exception as e:
                    st.error(f"Error while stopping: {e}")

            # Always reset state (even if error happens)
            st.session_state.is_recording = False
            st.session_state.meeting_session = session

            st.rerun()

    # Speaker rename panel
    if st.session_state.meeting_session:
        session = st.session_state.meeting_session
        speakers = session._transcriber.get_speakers() if session._transcriber else []
        if speakers:
            st.markdown("---")
            st.markdown("### Rename Speakers")
            st.caption("Type a real name to replace Speaker 1, Speaker 2, etc.")
            for spk in speakers:
                new_name = st.text_input(spk, value=spk, key=f"rename_{spk}")
                if new_name and new_name != spk:
                    session._transcriber.rename_speaker(spk, new_name)
                    for chunk in session.transcript.get_all():
                        if chunk.speaker == spk:
                            chunk.speaker = new_name
                    st.rerun()

    st.markdown("---")
    st.markdown("### 📂 Past Sessions")
    sessions = MeetingSession.list_sessions()
    if not sessions:
        st.caption("No sessions yet.")
    else:
        for s in sessions[:10]:
            dt   = s["started_at"][:16].replace("T", " ") if s["started_at"] else "?"
            mins = int(s["duration"] / 60)
            if st.button(f"{dt} ({mins}m)", key=f"sess_{s['session_id']}", use_container_width=True):
                st.session_state.loaded_session_id = s["session_id"]
                st.rerun()


# ── Main area routing — all functions are defined above, safe to call ──────────

loaded_session_id = st.session_state.get("loaded_session_id")

if loaded_session_id and not st.session_state.is_recording:
    _render_past_session(loaded_session_id)
elif st.session_state.is_recording or st.session_state.meeting_session:
    _render_live_session()
else:
    _render_welcome()
