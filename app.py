"""
SehPaathi — Exam Planning Assistant
Streamlit GUI  |  Place this file in the same folder as main.py
Run: streamlit run app.py
"""

import os
import time
import datetime
import tempfile
import requests
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ─────────────────────────────────────────────
# ⚙️  PAGE CONFIG  (must be FIRST st call)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="SehPaathi — Exam Assistant",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# 🎨  CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Sora', sans-serif;
}

/* ── App background ── */
.stApp {
    background: linear-gradient(135deg, #0f0c29 0%, #1a1040 50%, #24243e 100%);
    min-height: 100vh;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.04);
    border-right: 1px solid rgba(255,255,255,0.08);
}

/* ── Hero banner ── */
.hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 24px;
    text-align: center;
}
.hero h1 { color: #fff; font-size: 2.2rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
.hero p  { color: rgba(255,255,255,0.82); margin: 6px 0 0; font-size: 1rem; }

/* ── Tab bar ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.05);
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 8px;
    color: rgba(255,255,255,0.6);
    font-weight: 500;
    padding: 8px 20px;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    color: #fff !important;
}

/* ── Chat bubbles ── */
.bubble-user {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff;
    border-radius: 18px 18px 4px 18px;
    padding: 12px 16px;
    margin: 6px 0 6px 40px;
    font-size: 0.95rem;
    line-height: 1.5;
    word-wrap: break-word;
}
.bubble-bot {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    color: rgba(255,255,255,0.9);
    border-radius: 18px 18px 18px 4px;
    padding: 12px 16px;
    margin: 6px 40px 6px 0;
    font-size: 0.95rem;
    line-height: 1.6;
    word-wrap: break-word;
}
.bubble-bot pre, .bubble-user pre {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    background: rgba(0,0,0,0.25);
    padding: 8px 12px;
    border-radius: 8px;
    overflow-x: auto;
}
.label-user { font-size: 0.72rem; color: rgba(255,255,255,0.4); margin-bottom: 2px; text-align: right; }
.label-bot  { font-size: 0.72rem; color: rgba(255,255,255,0.4); margin-bottom: 2px; }

/* ── Cards ── */
.info-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 12px;
    color: rgba(255,255,255,0.85);
}
.info-card h4 { margin: 0 0 6px; color: #a78bfa; font-size: 0.95rem; }
.info-card p  { margin: 0; font-size: 0.88rem; }

/* ── Inputs & buttons ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 10px !important;
    color: #fff !important;
}
.stButton > button {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 10px 24px;
    font-weight: 600;
    font-family: 'Sora', sans-serif;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }

/* ── Success / error overrides ── */
.stSuccess { border-radius: 10px; }
.stError   { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 🔐  GEMINI CLIENT (cached across reruns)
# ─────────────────────────────────────────────
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

@st.cache_resource
def build_client():
    if not api_key:
        st.error("❌ GEMINI_API_KEY not found. Add it to your .env file.")
        st.stop()
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1beta")
    )

client = build_client()

SYS_INSTR = """
You are SehPathi, an intelligent exam planning assistant.

Your responsibilities:
1. Help users create study plans based on exam dates
2. Summarize study material and answer questions
3. Answer subject-related questions clearly

Rules:
- Be structured and helpful
- Be concise but informative
- Guide the user step-by-step
- If user input is unclear, ask follow-up questions before answering
"""

# ─────────────────────────────────────────────
# 🧠  SESSION STATE INIT
# ─────────────────────────────────────────────
def init_state():
    defaults = {
        # ── Q&A chat ──
        "qa_messages": [],
        "qa_chat":     None,

        # ── Planner ──
        "planner_result":     None,
        "planner_exam_count": None,   # None → step 1 (ask count)  |  int → step 2 (fill rows)

        # ── PDF ──
        "pdf_uploaded_file": None,
        "pdf_filename":      None,
        "pdf_messages":      [],
        "pdf_chat":          None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ─────────────────────────────────────────────
# 🤖  HELPERS
# ─────────────────────────────────────────────
def get_chat_session(key: str):
    """Return (or lazily create) a Gemini chat session stored in session state."""
    if st.session_state[key] is None:
        grounding = types.Tool(google_search=types.GoogleSearch())
        st.session_state[key] = client.chats.create(
            model="gemini-2.5-flash-lite",
            config=types.GenerateContentConfig(
                system_instruction=SYS_INSTR,
                temperature=0.9,
                tools=[grounding],
            ),
        )
    return st.session_state[key]


def collect_stream(stream) -> str:
    """Drain a streaming response into one string."""
    parts = []
    for chunk in stream:
        if chunk.text:
            parts.append(chunk.text)
    return "".join(parts)


def render_chat(messages: list):
    """Render a list of {'role': 'user'|'bot', 'text': str} dicts."""
    for msg in messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="label-user">You</div><div class="bubble-user">{msg["text"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="label-bot">SehPaathi 📚</div><div class="bubble-bot">{msg["text"]}</div>', unsafe_allow_html=True)


def is_url(text: str) -> bool:
    try:
        r = urlparse(text)
        return all([r.scheme, r.netloc])
    except Exception:
        return False


def download_pdf_from_url(url: str) -> str | None:
    try:
        resp = requests.get(url, stream=True, timeout=30)
        if resp.status_code != 200:
            return None
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                tmp.write(chunk)
        tmp.close()
        return tmp.name
    except Exception as e:
        st.error(f"Download error: {e}")
        return None


def upload_pdf_to_gemini(path: str):
    """Upload a local PDF path to Gemini Files API and wait until ACTIVE."""
    uploaded = client.files.upload(file=path)
    # Poll until no longer PROCESSING
    with st.spinner("⏳ Processing PDF…"):
        for _ in range(60):          # max ~2 min
            if uploaded.state.name != "PROCESSING":
                break
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
    if uploaded.state.name == "FAILED":
        st.error("❌ Gemini failed to process the PDF.")
        return None
    return uploaded


# ─────────────────────────────────────────────
# 🏠  HERO + SIDEBAR
# ─────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>📚 SehPaathi</h1>
  <p>Your intelligent exam planning assistant — study smarter, not harder.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧭 Navigation")
    st.markdown("Use the **tabs** in the main panel to switch between:")
    st.markdown("- 💬 **Chat Q/A** — ask anything subject-related")
    st.markdown("- 📅 **Study Planner** — get a personalised day-wise schedule")
    st.markdown("- 📄 **PDF Analyser** — upload a PDF and chat with it")

    st.divider()
    st.markdown("### ℹ️ About")
    st.markdown("SehPaathi is powered by **Gemini 2.5 Flash Lite** with Google Search grounding.")

    if st.button("🗑️ Reset All Sessions"):
        for key in ["qa_messages", "qa_chat", "planner_result",
                    "pdf_uploaded_file", "pdf_filename", "pdf_messages", "pdf_chat"]:
            st.session_state[key] = None if key.endswith("chat") or key.endswith("file") or key == "planner_result" else []
        st.success("All sessions cleared!")
        st.rerun()

# ─────────────────────────────────────────────
# 📑  TABS
# ─────────────────────────────────────────────
tab_qa, tab_planner, tab_pdf = st.tabs(["💬 Chat Q/A", "📅 Study Planner", "📄 PDF Analyser"])


# ══════════════════════════════════════════════
# 💬  TAB 1 — Q/A CHAT
# ══════════════════════════════════════════════
with tab_qa:
    st.markdown("#### Ask anything about your subjects")
    st.caption("General knowledge, concept explanations, definitions, comparisons — SehPaathi has you covered.")

    render_chat(st.session_state.qa_messages)

    with st.form("qa_form", clear_on_submit=True):
        col1, col2 = st.columns([5, 1])
        with col1:
            user_q = st.text_input("Your question", placeholder="e.g. Explain the OSI model…", label_visibility="collapsed")
        with col2:
            send = st.form_submit_button("Send →")

    if send and user_q.strip():
        st.session_state.qa_messages.append({"role": "user", "text": user_q})
        chat_session = get_chat_session("qa_chat")
        with st.spinner("Thinking…"):
            response_text = collect_stream(chat_session.send_message_stream(user_q))
        st.session_state.qa_messages.append({"role": "bot", "text": response_text})
        st.rerun()

    if st.session_state.qa_messages:
        if st.button("🗑️ Clear chat", key="clear_qa"):
            st.session_state.qa_messages = []
            st.session_state.qa_chat = None
            st.rerun()


# ══════════════════════════════════════════════
# 📅  TAB 2 — STUDY PLANNER
# ══════════════════════════════════════════════
with tab_planner:
    st.markdown("#### Generate a day-wise study schedule")
    st.caption("Tell SehPaathi how many exams you have — it will ask for the details of each one.")

    # ── Show result if already generated ──────────────────
    if st.session_state.planner_result:
        st.divider()
        st.markdown("### 📋 Your Study Plan")
        st.markdown(
            f'<div class="bubble-bot">{st.session_state.planner_result}</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download Plan (.txt)",
            data=st.session_state.planner_result,
            file_name="study_plan.txt",
            mime="text/plain",
        )
        if st.button("🔄 Plan Again", key="reset_planner"):
            st.session_state.planner_result     = None
            st.session_state.planner_exam_count = None
            st.rerun()

    # ── STEP 1 — Ask how many exams ───────────────────────
    elif st.session_state.planner_exam_count is None:
        with st.form("planner_step1"):
            st.markdown("**Step 1 of 2 — How many exams do you have?**")
            count_input = st.number_input(
                "Number of exams",
                min_value=1, max_value=20, value=3, step=1,
                help="You can enter between 1 and 20 exams.",
            )
            confirm = st.form_submit_button("Confirm →")

        if confirm:
            st.session_state.planner_exam_count = int(count_input)
            st.rerun()

    # ── STEP 2 — Fill details for N exams ─────────────────
    else:
        n = st.session_state.planner_exam_count

        # Small "change count" escape hatch
        col_hdr, col_esc = st.columns([5, 1])
        with col_hdr:
            st.markdown(f"**Step 2 of 2 — Enter details for your {n} exam{'s' if n > 1 else ''}**")
        with col_esc:
            if st.button("✏️ Change count"):
                st.session_state.planner_exam_count = None
                st.rerun()

        with st.form("planner_step2"):
            # Study window
            st.markdown("**⏰ Study Window**")
            c1, c2 = st.columns(2)
            with c1:
                study_start = st.text_input("Start time", value="06:00 AM", placeholder="e.g. 06:00 AM")
            with c2:
                study_end = st.text_input("End time", value="11:00 PM", placeholder="e.g. 11:00 PM")

            st.divider()

            # Header row
            hc = st.columns([3, 2, 2])
            hc[0].markdown("**Subject**")
            hc[1].markdown("**Exam Date**")
            hc[2].markdown("**Type**")

            # Exactly N rows
            exam_rows = []
            for i in range(1, n + 1):
                cols = st.columns([3, 2, 2])
                subj  = cols[0].text_input(f"subject_{i}",  key=f"subj_{i}",  placeholder=f"Exam {i} subject",  label_visibility="collapsed")
                date  = cols[1].text_input(f"date_{i}",     key=f"date_{i}",  placeholder="e.g. 25 May",         label_visibility="collapsed")
                etype = cols[2].selectbox(f"type_{i}",      ["theory", "mcq", "practical"], key=f"type_{i}",     label_visibility="collapsed")
                exam_rows.append((subj, date, etype))

            generate = st.form_submit_button("🚀 Generate Plan")

        if generate:
            exams = [{"subject": s, "date": d, "type": t} for s, d, t in exam_rows if s.strip() and d.strip()]
            missing = n - len(exams)
            if missing > 0:
                st.warning(f"⚠️ {missing} exam row{'s' if missing > 1 else ''} {'are' if missing > 1 else 'is'} incomplete. Please fill in all {n} exams.")
            else:
                prompt = f"""
Create a detailed day-wise study plan for the year {datetime.date.today().year}.

Exams:
{exams}

Study Time: {study_start} to {study_end}

RULES:
1. Generate the schedule immediately — no follow-up questions.
2. If syllabus details are missing, assume standard core topics for the subjects.
3. Include: breakfast (15–30 min), lunch (15–30 min), dinner (15–30 min),
   bathing (5–15 min), breaks, meals, rest, and hygiene.
4. Study blocks: 1.5–2 hour sessions, 15 min short breaks, 30 min long breaks.
5. Prioritise nearest exam first.
6. MCQ → speed practice | Theory → revision + concepts | Practical → application.
7. Day before exam: revision only. Exam day: light study only.

Make it a realistic human schedule.
"""
                with st.spinner("📅 Building your personalised plan…"):
                    chat_tmp = client.chats.create(
                        model="gemini-2.5-flash-lite",
                        config=types.GenerateContentConfig(
                            system_instruction=SYS_INSTR,
                            temperature=0.85,
                        ),
                    )
                    result = collect_stream(chat_tmp.send_message_stream(prompt))
                st.session_state.planner_result = result
                st.rerun()


# ══════════════════════════════════════════════
# 📄  TAB 3 — PDF ANALYSER
# ══════════════════════════════════════════════
with tab_pdf:
    st.markdown("#### Upload a PDF and chat with it")
    st.caption("Paste a public PDF URL **or** upload a file from your device (≤ 50 MB recommended).")

    # ── Upload controls (shown only if no PDF is active) ──
    if st.session_state.pdf_uploaded_file is None:
        col_url, col_or, col_file = st.columns([4, 0.4, 4])

        with col_url:
            pdf_url = st.text_input("🌐 PDF URL", placeholder="https://example.com/notes.pdf")
            url_btn = st.button("Upload from URL")

        with col_or:
            st.markdown("<br><br><div style='text-align:center;color:rgba(255,255,255,0.4)'>or</div>", unsafe_allow_html=True)

        with col_file:
            uploaded_file = st.file_uploader("💾 Local PDF", type=["pdf"])
            file_btn = st.button("Upload File")

        # ── Handle URL upload ──
        if url_btn and pdf_url.strip():
            if not is_url(pdf_url.strip()):
                st.error("❌ That doesn't look like a valid URL.")
            else:
                with st.spinner("🌐 Downloading…"):
                    tmp_path = download_pdf_from_url(pdf_url.strip())
                if tmp_path:
                    gemini_file = upload_pdf_to_gemini(tmp_path)
                    os.remove(tmp_path)
                    if gemini_file:
                        st.session_state.pdf_uploaded_file = gemini_file
                        st.session_state.pdf_filename      = pdf_url.split("/")[-1] or "document.pdf"
                        st.session_state.pdf_messages      = [{"role": "bot", "text": "✅ PDF ready! Ask me anything about it."}]
                        st.rerun()

        # ── Handle local file upload ──
        if file_btn and uploaded_file is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name
            gemini_file = upload_pdf_to_gemini(tmp_path)
            os.remove(tmp_path)
            if gemini_file:
                st.session_state.pdf_uploaded_file = gemini_file
                st.session_state.pdf_filename      = uploaded_file.name
                st.session_state.pdf_messages      = [{"role": "bot", "text": f"✅ **{uploaded_file.name}** ready! Ask me anything about it."}]
                st.rerun()

    # ── Active PDF session ──
    else:
        col_info, col_close = st.columns([5, 1])
        with col_info:
            st.success(f"📄 Active: **{st.session_state.pdf_filename}**")
        with col_close:
            if st.button("✖ Close PDF"):
                st.session_state.pdf_uploaded_file = None
                st.session_state.pdf_filename      = None
                st.session_state.pdf_messages      = []
                st.session_state.pdf_chat          = None
                st.rerun()

        render_chat(st.session_state.pdf_messages)

        with st.form("pdf_form", clear_on_submit=True):
            col_q, col_s = st.columns([5, 1])
            with col_q:
                pdf_question = st.text_input("Ask about the PDF", placeholder="e.g. Summarise chapter 2…", label_visibility="collapsed")
            with col_s:
                ask_btn = st.form_submit_button("Ask →")

        if ask_btn and pdf_question.strip():
            st.session_state.pdf_messages.append({"role": "user", "text": pdf_question})
            pdf_chat = get_chat_session("pdf_chat")
            with st.spinner("Reading PDF…"):
                response = pdf_chat.send_message_stream(
                    [st.session_state.pdf_uploaded_file, pdf_question]
                )
                answer = collect_stream(response)
            st.session_state.pdf_messages.append({"role": "bot", "text": answer})
            st.rerun()

# ─────────────────────────────────────────────
# 🦶  FOOTER
# ─────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; margin-top:40px; color:rgba(255,255,255,0.25); font-size:0.8rem;">
  SehPaathi · Built with Streamlit + Gemini · Keep Studying — Keep Advancing 🚀
</div>
""", unsafe_allow_html=True)
