"""
app.py — AI Meeting Notes Dashboard (Premium Redesign)

Run with:
    streamlit run dashboard/app.py
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from audio_recorder_streamlit import audio_recorder
import tempfile

from streamlit_autorefresh import st_autorefresh

from core.config import config
from core.session import MeetingSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title=config.APP_NAME,
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ========== Session state ==========
def init_state():
    defaults = {
        "meeting_session": None,
        "is_recording": False,
        "session_id": None,
        "last_chunk_count": 0,
        "meeting_title": f"Meeting {datetime.now().strftime('%d %b %Y')}",
        "dark_mode": True,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_state()


# ========== PREMIUM THEME ==========
def inject_theme():
    dark = st.session_state.get("dark_mode", True)

    if dark:
        bg            = "#080c14"
        bg2           = "#0d1220"
        surface       = "#111827"
        surface2      = "#1a2236"
        border        = "#1e2d45"
        border2       = "#243352"
        text          = "#e8eef8"
        text2         = "#6b7fa3"
        text3         = "#3d5070"
        accent        = "#4f8ef7"
        accent2       = "#3a7ae8"
        accent_glow   = "rgba(79,142,247,0.18)"
        accent_glow2  = "rgba(79,142,247,0.08)"
        green         = "#34d399"
        green_bg      = "rgba(52,211,153,0.07)"
        green_bd      = "rgba(52,211,153,0.2)"
        amber         = "#fbbf24"
        amber_bg      = "rgba(251,191,36,0.07)"
        amber_bd      = "rgba(251,191,36,0.22)"
        blue_bg       = "rgba(79,142,247,0.07)"
        blue_bd       = "rgba(79,142,247,0.22)"
        header_bg     = "rgba(8,12,20,0.92)"
        shadow        = "rgba(0,0,0,0.6)"
        shadow2       = "rgba(0,0,0,0.3)"
        rec_color     = "#f87171"
        rec_bg        = "rgba(248,113,113,0.1)"
        badge_bg      = "rgba(79,142,247,0.12)"
        scrollbar_bg  = "#111827"
        scrollbar_th  = "#1e2d45"
    else:
        bg            = "#f0f4ff"
        bg2           = "#e4eaf8"
        surface       = "#ffffff"
        surface2      = "#f7f9ff"
        border        = "#dde4f5"
        border2       = "#c8d3ee"
        text          = "#0f1729"
        text2         = "#5a6b8c"
        text3         = "#9aaabf"
        accent        = "#2563eb"
        accent2       = "#1d4ed8"
        accent_glow   = "rgba(37,99,235,0.14)"
        accent_glow2  = "rgba(37,99,235,0.06)"
        green         = "#059669"
        green_bg      = "rgba(5,150,105,0.06)"
        green_bd      = "rgba(5,150,105,0.2)"
        amber         = "#d97706"
        amber_bg      = "rgba(217,119,6,0.06)"
        amber_bd      = "rgba(217,119,6,0.22)"
        blue_bg       = "rgba(37,99,235,0.06)"
        blue_bd       = "rgba(37,99,235,0.2)"
        header_bg     = "rgba(240,244,255,0.94)"
        shadow        = "rgba(15,23,41,0.1)"
        shadow2       = "rgba(15,23,41,0.06)"
        rec_color     = "#dc2626"
        rec_bg        = "rgba(220,38,38,0.08)"
        badge_bg      = "rgba(37,99,235,0.1)"
        scrollbar_bg  = "#f0f4ff"
        scrollbar_th  = "#c8d3ee"

    css = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ─── GLOBAL RESET & BASE ─── */
    *, *::before, *::after {{
        box-sizing: border-box;
        font-family: 'Sora', sans-serif !important;
    }}
    code, pre, kbd, .stCode {{
        font-family: 'JetBrains Mono', monospace !important;
    }}

    /* ─── NUCLEAR BG OVERRIDE ─── */
    html, body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="block-container"],
    .main, .appview-container {{
        background: {bg} !important;
        background-color: {bg} !important;
        color: {text} !important;
    }}

    /* ─── HIDE STREAMLIT CHROME ─── */
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    footer, #MainMenu,
    [data-testid="stDecoration"] {{
        display: none !important;
    }}

    /* ─── SCROLLBAR ─── */
    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: {scrollbar_bg}; }}
    ::-webkit-scrollbar-thumb {{ background: {scrollbar_th}; border-radius: 10px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {border2}; }}

    /* ─── TEXT UNIVERSALS ─── */
    p, span, div, li, td, th, label,
    h1, h2, h3, h4, h5, h6,
    .stMarkdown, .stMarkdown p, .stMarkdown span,
    .stMarkdown li, .stMarkdown strong,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] strong,
    [data-testid="stText"],
    .stCaption,
    [data-testid="stCaptionContainer"] p {{
        color: {text} !important;
    }}
    small, .stCaption p, [data-testid="stCaptionContainer"] p {{
        color: {text2} !important;
    }}

    h1 {{
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.03em !important;
        line-height: 1.2 !important;
    }}
    h2 {{
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
    }}
    h3 {{
        font-size: 0.92rem !important;
        font-weight: 600 !important;
    }}

    /* ─── TOP BAR FIX ─── */
    [data-testid="stMainBlockContainer"],
    [data-testid="block-container"] {{
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 1440px !important;
    }}

    div[data-testid="stHorizontalBlock"]:first-of-type {{
        position: sticky;
        top: 0.75rem;
        z-index: 1000;
        background: {header_bg};
        backdrop-filter: blur(24px) saturate(180%);
        -webkit-backdrop-filter: blur(24px) saturate(180%);
        border: 1px solid {border};
        box-shadow: 0 8px 32px {shadow2};
        border-radius: 16px;
        padding: 0.75rem;
        margin-bottom: 1.25rem;
    }}

    div[data-testid="stHorizontalBlock"]:first-of-type .stButton button {{
        height: 38px !important;
        border-radius: 10px !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        white-space: nowrap !important;
        letter-spacing: 0.01em !important;
        padding: 0 14px !important;
    }}
    div[data-testid="stHorizontalBlock"]:first-of-type .stTextInput input {{
        height: 38px !important;
        border-radius: 10px !important;
        font-size: 0.85rem !important;
        padding: 0 12px !important;
    }}
    div[data-testid="stHorizontalBlock"]:first-of-type [data-baseweb="select"] > div {{
        min-height: 38px !important;
        border-radius: 10px !important;
    }}

    /* ─── STAT CARDS ─── */
    .stat-card {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 16px;
        padding: 1.1rem 0.75rem;
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
        box-shadow: 0 2px 12px {shadow2};
        position: relative;
        overflow: hidden;
    }}
    .stat-card::before {{
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, {accent_glow2} 0%, transparent 60%);
        pointer-events: none;
    }}
    .stat-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 12px 32px {shadow};
        border-color: {border2};
    }}
    .stat-value {{
        font-size: 1.9rem;
        font-weight: 800;
        color: {text} !important;
        line-height: 1;
        letter-spacing: -0.04em;
    }}
    .stat-label {{
        font-size: 0.58rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: {text2} !important;
        margin-top: 6px;
        font-weight: 600;
    }}
    .stat-accent {{
        width: 28px;
        height: 2px;
        background: {accent};
        margin: 6px auto 0;
        border-radius: 2px;
        opacity: 0.6;
    }}

    /* ─── TRANSCRIPT CARDS ─── */
    .chunk-card {{
        background: {surface};
        border: 1px solid {border};
        border-left: 2px solid {accent};
        padding: 0.65rem 1rem 0.65rem 0.9rem;
        margin-bottom: 0.4rem;
        border-radius: 0 12px 12px 0;
        box-shadow: 0 1px 6px {shadow2};
        transition: box-shadow 0.15s ease, border-left-color 0.15s ease;
    }}
    .chunk-card:hover {{
        box-shadow: 0 4px 16px {shadow};
        border-left-color: {green};
    }}
    .chunk-timestamp {{
        font-size: 0.62rem;
        color: {text3} !important;
        margin-bottom: 4px;
        font-family: 'JetBrains Mono', monospace !important;
        letter-spacing: 0.04em;
    }}
    .chunk-speaker {{
        font-weight: 700;
        color: {accent} !important;
        font-size: 0.8rem;
        letter-spacing: 0.01em;
    }}
    .chunk-text {{
        color: {text} !important;
        line-height: 1.6;
        font-size: 0.84rem;
        font-weight: 400;
    }}
    mark {{
        background: {accent_glow};
        color: {accent} !important;
        border-radius: 3px;
        padding: 0 2px;
    }}

    /* ─── SUMMARY / ACTION / KEYPOINT BOXES ─── */
    .summary-box {{
        background: {green_bg};
        border: 1px solid {green_bd};
        border-radius: 14px;
        padding: 1.1rem 1.2rem;
        color: {green} !important;
        line-height: 1.7;
        font-size: 0.875rem;
        font-weight: 400;
    }}
    .action-item {{
        background: {amber_bg};
        border: 1px solid {amber_bd};
        border-left: 2px solid {amber};
        padding: 0.5rem 0.9rem;
        margin-bottom: 0.38rem;
        border-radius: 0 10px 10px 0;
        font-size: 0.84rem;
        color: {text} !important;
        transition: background 0.15s;
    }}
    .action-item:hover {{ background: rgba(251,191,36,0.12); }}
    .key-point {{
        background: {blue_bg};
        border: 1px solid {blue_bd};
        border-left: 2px solid {accent};
        padding: 0.5rem 0.9rem;
        margin-bottom: 0.38rem;
        border-radius: 0 10px 10px 0;
        font-size: 0.84rem;
        color: {text} !important;
        transition: background 0.15s;
    }}
    .key-point:hover {{ background: rgba(79,142,247,0.12); }}

    /* ─── RECORDING BADGE ─── */
    .recording-badge {{
        background: {rec_bg};
        border: 1px solid {rec_color}33;
        border-radius: 40px;
        padding: 0.22rem 0.9rem;
        font-weight: 600;
        color: {rec_color} !important;
        display: inline-flex;
        align-items: center;
        gap: 7px;
        font-size: 0.78rem;
        letter-spacing: 0.04em;
        white-space: nowrap;
    }}
    .recording-dot {{
        width: 7px;
        height: 7px;
        background: {rec_color};
        border-radius: 50%;
        flex-shrink: 0;
        animation: rec-pulse 1.2s ease-in-out infinite;
    }}
    @keyframes rec-pulse {{
        0%, 100% {{ opacity: 1; transform: scale(1); box-shadow: 0 0 0 0 {rec_color}44; }}
        50% {{ opacity: 0.3; transform: scale(0.75); box-shadow: 0 0 0 4px transparent; }}
    }}

    /* ─── LANG BADGE ─── */
    .lang-badge {{
        display: inline-block;
        background: {badge_bg};
        color: {accent} !important;
        border-radius: 4px;
        padding: 1px 5px;
        font-size: 0.58rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        margin-left: 6px;
        font-family: 'JetBrains Mono', monospace !important;
        vertical-align: middle;
    }}

    /* ─── INPUTS ─── */
    [data-testid="stTextInput"] input {{
        background: {surface} !important;
        color: {text} !important;
        border: 1px solid {border} !important;
        border-radius: 10px !important;
        font-size: 0.875rem !important;
        transition: border-color 0.15s, box-shadow 0.15s !important;
    }}
    [data-testid="stTextInput"] input:focus {{
        border-color: {accent} !important;
        box-shadow: 0 0 0 3px {accent_glow} !important;
        outline: none !important;
    }}
    [data-testid="stTextInput"] input::placeholder {{
        color: {text3} !important;
    }}

    /* ─── SELECTBOX ─── */
    [data-baseweb="select"] > div {{
        background: {surface} !important;
        border-color: {border} !important;
        border-radius: 10px !important;
        color: {text} !important;
    }}
    [data-baseweb="select"] svg {{
        fill: {text2} !important;
    }}
    [data-baseweb="popover"] {{
        background: {surface2} !important;
        border: 1px solid {border} !important;
        border-radius: 12px !important;
        box-shadow: 0 8px 32px {shadow} !important;
    }}
    [data-baseweb="menu"] li {{
        background: transparent !important;
        color: {text} !important;
        font-size: 0.85rem !important;
    }}
    [data-baseweb="menu"] li:hover {{
        background: {accent_glow2} !important;
    }}

    /* ─── BUTTONS ─── */
    .stButton > button {{
        background: {surface} !important;
        color: {text} !important;
        border: 1px solid {border} !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        letter-spacing: 0.01em !important;
        transition: all 0.15s ease !important;
    }}
    .stButton > button:hover {{
        background: {surface2} !important;
        border-color: {accent} !important;
        box-shadow: 0 0 0 3px {accent_glow} !important;
        transform: translateY(-1px) !important;
    }}
    .stButton > button[kind="primary"] {{
        background: {accent} !important;
        color: #ffffff !important;
        border: none !important;
        box-shadow: 0 4px 14px {accent_glow} !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        background: {accent2} !important;
        box-shadow: 0 6px 20px {accent_glow} !important;
    }}

    /* ─── DOWNLOAD BUTTON ─── */
    .stDownloadButton > button {{
        background: {green_bg} !important;
        color: {green} !important;
        border: 1px solid {green_bd} !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }}
    .stDownloadButton > button:hover {{
        box-shadow: 0 0 0 3px {green_bd} !important;
    }}

    /* ─── POPOVER ─── */
    [data-testid="stPopover"] > div {{
        background: {surface2} !important;
        border: 1px solid {border} !important;
        border-radius: 14px !important;
        box-shadow: 0 12px 40px {shadow} !important;
        padding: 1rem !important;
    }}

    /* ─── INFO / ALERT ─── */
    .stAlert {{
        background: {surface} !important;
        border: 1px solid {border} !important;
        border-radius: 12px !important;
        color: {text} !important;
    }}

    /* ─── SECTION DIVIDERS ─── */
    hr {{
        border: none !important;
        border-top: 1px solid {border} !important;
        margin: 1.2rem 0 !important;
    }}

    /* ─── SPINNER ─── */
    .stSpinner > div {{
        border-top-color: {accent} !important;
    }}

    /* ─── SUBHEADER STYLE ─── */
    .section-header {{
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 0.9rem;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid {border};
    }}
    .section-header-text {{
        font-size: 0.88rem;
        font-weight: 700;
        color: {text} !important;
        letter-spacing: -0.01em;
    }}

    /* ─── WELCOME CARD ─── */
    .welcome-hero {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 24px;
        padding: 2.5rem 2rem;
        text-align: center;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 24px {shadow2};
    }}
    .welcome-hero::before {{
        content: '';
        position: absolute;
        top: -60px;
        left: 50%;
        transform: translateX(-50%);
        width: 300px;
        height: 200px;
        background: radial-gradient(ellipse, {accent_glow} 0%, transparent 70%);
        pointer-events: none;
    }}
    .welcome-icon {{
        font-size: 2.8rem;
        margin-bottom: 0.7rem;
        display: block;
        position: relative;
    }}

    /* ─── STEP CARDS ─── */
    .step-card {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 16px;
        padding: 1.3rem 1.1rem;
        height: 100%;
        position: relative;
        overflow: hidden;
        transition: border-color 0.2s, box-shadow 0.2s;
        box-shadow: 0 2px 10px {shadow2};
    }}
    .step-card:hover {{
        border-color: {border2};
        box-shadow: 0 8px 28px {shadow};
    }}
    .step-num {{
        width: 28px;
        height: 28px;
        background: {accent};
        color: #fff;
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.78rem;
        font-weight: 800;
        margin-bottom: 0.8rem;
        box-shadow: 0 4px 10px {accent_glow};
    }}
    .step-icon {{ font-size: 1.5rem; margin-bottom: 0.5rem; display: block; }}
    .step-title {{
        font-weight: 700;
        font-size: 0.88rem;
        margin-bottom: 0.4rem;
        color: {text} !important;
        letter-spacing: -0.01em;
    }}
    .step-desc {{
        font-size: 0.78rem;
        color: {text2} !important;
        line-height: 1.55;
    }}

    /* ─── TOGGLE ─── */
    [data-testid="stToggle"] label {{
        color: {text2} !important;
        font-size: 0.8rem !important;
    }}

    /* ─── COLUMN GAP FIX ─── */
    [data-testid="stHorizontalBlock"] {{
        gap: 0.75rem !important;
        align-items: center !important;
    }}

    /* ─── BLOCKQUOTE ─── */
    blockquote {{
        border-left: 2px solid {accent} !important;
        background: {blue_bg} !important;
        border-radius: 0 8px 8px 0 !important;
        padding: 0.5rem 0.9rem !important;
        margin: 0.3rem 0 !important;
        font-size: 0.84rem !important;
        font-style: italic !important;
        color: {text2} !important;
    }}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


inject_theme()


# ========== Helper functions ==========
def _render_welcome():
    dark = st.session_state.get("dark_mode", True)
    sub_color = "#6b7fa3" if dark else "#5a6b8c"

    st.markdown(f"""
    <div class="welcome-hero">
        <span class="welcome-icon">🎙️</span>
        <h1 style="margin:0 0 0.5rem;letter-spacing:-0.03em;">AI Meeting Notes</h1>
        <p style="color:{sub_color};font-size:0.9rem;line-height:1.6;margin:0;">
            Real‑time transcription · AI summaries · Multi-language support<br>
            Hit <strong>▶ Start Recording</strong> in the top bar to begin.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="medium")
    steps = [
        ("1", "🔊", "Audio Routing", "Install VB‑Cable or configure PulseAudio loopback to capture system audio."),
        ("2", "📝", "Live Notes", "Transcription and meeting summary appear automatically while the session runs."),
        ("3", "▶", "Start Recording", "Hit Start Recording — transcript and summary appear live as you speak."),
    ]
    for col, (num, icon, title, desc) in zip([col1, col2, col3], steps):
        with col:
            st.markdown(f"""
            <div class="step-card">
                <div class="step-num">{num}</div>
                <span class="step-icon">{icon}</span>
                <div class="step-title">{title}</div>
                <div class="step-desc">{desc}</div>
            </div>
            """, unsafe_allow_html=True)


def _render_transcript_panel(chunks):
    st.markdown('<div class="section-header"><span class="section-header-text">📝 Live Transcript</span></div>', unsafe_allow_html=True)
    if not chunks:
        st.caption("Transcript will appear here once recording starts…")
        return
    search = st.text_input("Search transcript", placeholder="🔍 Search…", label_visibility="collapsed")
    html_parts = []
    for chunk in reversed(chunks):
        if search and search.lower() not in chunk.text.lower():
            continue
        text = chunk.text.replace(search, f"<mark>{search}</mark>") if search else chunk.text
        lang = getattr(chunk, "detected_lang", "en")
        badge = f"<span class='lang-badge'>{lang.upper()}</span>" if lang != "en" else ""
        html_parts.append(f"""
        <div class="chunk-card">
            <div class="chunk-timestamp">{chunk.time_label}{badge}</div>
            <span class="chunk-speaker">{chunk.speaker}</span>
            <span class="chunk-text"> — {text}</span>
        </div>""")
    scroll_html = f'<div style="max-height:500px;overflow-y:auto;padding-right:3px;">{"".join(html_parts)}</div>'
    st.markdown(scroll_html, unsafe_allow_html=True)
    full = "\n".join(f"[{c.time_label}] {c.speaker}: {c.text}" for c in chunks)
    st.download_button(
        "📋 Download transcript (.txt)",
        data=full,
        file_name=f"transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        use_container_width=True
    )


def _render_summary_panel(summary, chunks, session):
    st.markdown('<div class="section-header"><span class="section-header-text">📋 Meeting Summary</span></div>', unsafe_allow_html=True)
    if summary:
        st.markdown(f'<div class="summary-box">{summary.summary}</div>', unsafe_allow_html=True)
        if summary.action_items:
            st.markdown("<br>**✅ Action Items**", unsafe_allow_html=True)
            for item in summary.action_items:
                st.markdown(f'<div class="action-item">→ {item}</div>', unsafe_allow_html=True)
        if summary.key_points:
            st.markdown("<br>**💡 Key Points**", unsafe_allow_html=True)
            for point in summary.key_points:
                st.markdown(f'<div class="key-point">• {point}</div>', unsafe_allow_html=True)
        if summary.highlights:
            st.markdown("<br>**✨ Highlights**", unsafe_allow_html=True)
            for h in summary.highlights:
                st.markdown(f"> *{h}*")
    else:
        st.info("Generating summary… (needs ~20+ words)" if chunks else "Summary will appear here once recording starts.")

    if session and chunks:
        topics = getattr(session, "get_topics", lambda: [])()
        if topics:
            st.markdown("<br>**🏷️ Topics Detected**", unsafe_allow_html=True)
            st.write(" · ".join(f"`{t}`" for t in topics[:8]))

    st.markdown("---")
    st.markdown("**📤 Export Notes**")
    sid = session.session_id if session else st.session_state.get("loaded_session_id", "unknown")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("📄 PDF", use_container_width=True):
            try:
                from exports.export_pdf import export_to_pdf
                with st.spinner("Generating PDF…"):
                    path = export_to_pdf(sid, chunks, summary, st.session_state.meeting_title)
                    with open(path, "rb") as f:
                        st.download_button("⬇ Download PDF", data=f, file_name=path.name, mime="application/pdf")
            except ImportError:
                st.error("PDF export module not available")
    with c2:
        if st.button("📝 Word", use_container_width=True):
            try:
                from exports.export_docx import export_to_docx
                with st.spinner("Generating DOCX…"):
                    path = export_to_docx(sid, chunks, summary, st.session_state.meeting_title)
                    with open(path, "rb") as f:
                        st.download_button("⬇ Download DOCX", data=f, file_name=path.name)
            except ImportError:
                st.error("DOCX export module not available")
    with c3:
        if st.button("📊 Google Docs", use_container_width=True):
            try:
                from exports.export_google_docs import export_to_google_docs
                with st.spinner("Exporting…"):
                    url = export_to_google_docs(sid, chunks, summary, st.session_state.meeting_title)
                    if url:
                        st.success(f"[Open in Google Docs]({url})")
                    else:
                        st.error("Check GOOGLE_CREDENTIALS_PATH in .env")
            except ImportError:
                st.error("Google Docs export module not available")


def _render_live_session():
    session = st.session_state.meeting_session
    if not session:
        return
    chunks = session.transcript.get_all()
    summary = session.get_summary()
    dur = int(session.get_duration())

    st.title(f"🎙️ {st.session_state.meeting_title}")

    c1, c2, c3, c4 = st.columns(4)
    stats = [
        (f"{dur//60:02d}:{dur%60:02d}", "Duration"),
        (str(len(chunks)), "Chunks"),
        (str(sum(len(c.text.split()) for c in chunks)), "Words"),
        (str(len(set(c.speaker for c in chunks))), "Speakers"),
    ]
    for col, (val, label) in zip([c1, c2, c3, c4], stats):
        with col:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{val}</div>
                <div class="stat-label">{label}</div>
                <div class="stat-accent"></div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
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
        TranscriptChunk(c["text"], c["timestamp"], c.get("speaker", "Unknown"), c.get("confidence", 1.0))
        for c in data.get("transcript", [])
    ]
    summary = None
    if data.get("summary"):
        s = data["summary"]
        summary = MeetingSummary(
            s.get("summary", ""),
            s.get("action_items", []),
            s.get("key_points", []),
            s.get("highlights", []),
            s.get("word_count", 0),
            s.get("model_used", "")
        )
    dt = data.get("started_at", "")[:16].replace("T", " ")
    dur = int(data.get("duration_sec", 0))
    st.title(f"📂 {session_id}")
    st.caption(f"Recorded: {dt}  ·  Duration: {dur//60}m {dur%60}s  ·  {len(chunks)} chunks")
    if st.button("← Back to live view"):
        del st.session_state["loaded_session_id"]
        st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        _render_summary_panel(summary, chunks, None)
    with right:
        _render_transcript_panel(chunks)


# ========== Auto-refresh while recording ==========
if st.session_state.is_recording:
    st_autorefresh(interval=3000, key="live_refresh")


# ========== Top bar ==========
def top_bar():
    speech_engine = "whisper"
    summarizer = "transformers"

    with st.container():
        cols = st.columns([0.6, 4.0, 2.0, 1.8, 2.4, 0.65])

        with cols[0]:
            if st.button("←", help="Go back"):
                st.markdown('<script>window.history.back();</script>', unsafe_allow_html=True)

        with cols[1]:
            st.session_state.meeting_title = st.text_input(
                "title",
                value=st.session_state.meeting_title,
                disabled=st.session_state.is_recording,
                label_visibility="collapsed",
                placeholder="Meeting title…"
            )

        with cols[2]:

            st.markdown(
                """
                <div style="
                    text-align:center;
                    padding:8px;
                    border-radius:12px;
                    background:#111827;
                    border:1px solid #1e293b;
                    margin-bottom:10px;
                ">
                🎤 Browser Recording
                </div>
                """,
                unsafe_allow_html=True
            )

            audio_bytes = audio_recorder(
                text="",
                recording_color="#ef4444",
                neutral_color="#3b82f6",
                icon_name="microphone",
                icon_size="2x",
            )

            if audio_bytes:

                st.success("Recording completed!")

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".wav"
                ) as tmp_file:

                    tmp_file.write(audio_bytes)

                    audio_path = tmp_file.name

                try:

                    if st.session_state.meeting_session is None:

                        sess = MeetingSession(
                            speech_engine,
                            summarizer
                        )

                        st.session_state.meeting_session = sess

                    sess = st.session_state.meeting_session

                    with st.spinner("Transcribing audio..."):

                        transcript_result = (
                            sess.transcriber.transcribe_file(audio_path)
                        )

                    if transcript_result:

                        for chunk in transcript_result:

                            sess.transcript.add(chunk)

                    with st.spinner("Generating summary..."):

                        sess.generate_summary()

                    st.success("Summary generated!")

                    st.rerun()

                except Exception as e:

                    st.error(f"Error: {e}")

        with cols[3]:
            sess = st.session_state.meeting_session
            if sess and not st.session_state.is_recording:
                chunks = sess.transcript.get_all() if hasattr(sess, 'transcript') else []
                speakers = sorted(set(c.speaker for c in chunks)) if chunks else []
                if speakers:
                    with st.popover("🏷️ Speakers"):
                        for spk in speakers:
                            new = st.text_input(spk, value=spk, key=f"rename_{spk}")
                            if new and new != spk:
                                for ch in sess.transcript.get_all():
                                    if ch.speaker == spk:
                                        ch.speaker = new
                                st.rerun()
                else:
                    st.caption("No speakers yet")
            else:
                st.caption("—")

        with cols[4]:
            sessions = MeetingSession.list_sessions()
            if sessions:
                opts = {
                    f"{s['started_at'][:16]} ({s['duration']//60}m)": s['session_id']
                    for s in sessions[:10]
                }
                sel = st.selectbox(
                    "Past sessions",
                    list(opts.keys()),
                    index=None,
                    placeholder="📂 Past sessions",
                    label_visibility="collapsed"
                )
                if sel:
                    st.session_state.loaded_session_id = opts[sel]
                    st.rerun()
            else:
                st.caption("No past sessions")

        with cols[5]:
            dark = st.toggle("🌙", value=st.session_state.dark_mode, help="Dark mode")
            if dark != st.session_state.dark_mode:
                st.session_state.dark_mode = dark
                st.rerun()


# ========== Main ==========
top_bar()

loaded = st.session_state.get("loaded_session_id")
if loaded and not st.session_state.is_recording:
    _render_past_session(loaded)
elif st.session_state.is_recording or st.session_state.meeting_session:
    _render_live_session()
else:
    _render_welcome()