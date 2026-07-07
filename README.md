<p align="center">
  <img src="https://img.shields.io/badge/📚-SehPaathi-667eea?style=for-the-badge&labelColor=0f0c29" alt="SehPaathi" />
</p>

<h1 align="center">SehPaathi — AI Document Analysis & Exam Planning Platform</h1>

<p align="center">
  <em>Upload. Analyse. Plan. Ace your exams — powered by Google Gemini.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat-square&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/Gemini_2.5_Flash_Lite-API-4285F4?style=flat-square&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Search-Grounding-34A853?style=flat-square&logo=googlesearchconsole&logoColor=white" />
  <img src="https://img.shields.io/badge/Gemini_Files_API-PDF_Pipeline-FBBC05?style=flat-square&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />
</p>

---

## 🧭 Overview

**SehPaathi** (_Hindi: सहपाठी — "classmate"_) is a production-grade AI-powered exam preparation platform that unifies three intelligent modules into a single, session-aware application:

| Module | Capability |
|--------|-----------|
| 💬 **Interactive Q&A** | Multi-turn conversational AI with Google Search grounding for real-time, factual answers on any academic topic |
| 📅 **Dynamic Study Planner** | Generates personalised, day-wise study schedules using a multi-step guided wizard — including meals, breaks, and exam-type strategies |
| 📄 **PDF Analyser** | Upload PDFs (local file or public URL) and conduct an interactive Q&A conversation directly against the document content |

All three modules share a **persistent session state architecture** while maintaining complete independence, enabling zero-context-bleed interactions and seamless module switching mid-conversation.

---

## ✨ Features

### 💬 Conversational Q&A with Google Search Grounding
- Multi-turn chat sessions powered by **Gemini 2.5 Flash Lite**
- Real-time factual grounding via the **Google Search** tool — no hallucinated answers on current-events or factual queries
- Streaming response rendering for a responsive, ChatGPT-like experience
- Full conversation history preserved across interactions within a session

### 📅 Intelligent Study Planner
- **Two-step guided wizard**: first collects exam count, then dynamically renders the exact number of input rows needed
- Supports **theory**, **MCQ**, and **practical** exam types with differentiated revision strategies
- Generates a realistic human schedule including breakfast, lunch, dinner, bathing, short/long breaks, and rest periods
- Automatically prioritises nearest exams and adjusts study focus based on inter-exam gaps
- **One-click download** of the generated plan as a `.txt` file

### 📄 PDF Analyser — Upload & Chat with Documents
- Dual-input support: **public URL** download or **local file upload**
- Automatic PDF download with chunked streaming (8 KB blocks) to avoid RAM spikes
- File size detection and adaptive upload path selection
- Robust **automatic state polling** pipeline for the Gemini Files API (see Engineering Highlights)
- Full multi-turn Q&A against the uploaded document with conversation history

### 🧠 Intent Detection Engine
- Keyword-based intent classifier routes user input to the correct module (`planner`, `pdf`, `qa`)
- Graceful fallback with clarification prompts for ambiguous inputs
- **Smart interrupt system**: users can switch modules mid-flow (e.g., ask a Q&A question while the planner is active) and seamlessly resume where they left off

---

## 🏗️ Engineering Highlights & Optimizations

### 1. Robust PDF Analysis Pipeline with Automatic State Polling

The PDF processing pipeline integrates with the **Gemini Files API**, which processes uploaded documents asynchronously — meaning the file is not immediately available for inference after upload. SehPaathi engineers around this with an **automatic state polling mechanism**:

```python
# Upload → Poll → Validate lifecycle
uploaded_file = client.files.upload(file=path)

# Automatic state polling — retry loop until ACTIVE or FAILED
while uploaded_file.state.name == "PROCESSING":
    time.sleep(2)                                       # Non-blocking 2s poll interval
    uploaded_file = client.files.get(name=uploaded_file.name)  # Re-fetch state from API

if uploaded_file.state.name == "FAILED":
    # Graceful error handling — reset state, clean up temp files
```

**Why this matters:**
- The Gemini Files API returns a `PROCESSING` state immediately after upload — naively passing this to `generate_content` would cause a hard API error
- The polling loop with exponential-backoff-style intervals (2s) ensures the application **never submits a query against an unprocessed file**
- Integrated fallback: if processing fails, the session state is fully reset and temporary files are cleaned up to prevent resource leaks

### 2. Persistent Session State Management Across Three Independent Modules

SehPaathi runs three fully independent AI modules — **Chat Q&A**, **Study Planner**, and **PDF Analyser** — each with its own session lifecycle. The core architectural challenge: **how do you maintain isolated state for each module while allowing seamless cross-module switching without context bleed?**

The solution is a **centralized session state dictionary** that cleanly partitions state per module:

```python
# Streamlit session state — persistent across reruns
defaults = {
    # ── Q&A Chat (independent session) ──
    "qa_messages": [],       # Conversation history
    "qa_chat":     None,     # Gemini chat object

    # ── Planner (multi-step wizard state) ──
    "planner_result":     None,   # Generated plan output
    "planner_exam_count": None,   # Wizard step tracker (None → step 1, int → step 2)

    # ── PDF Analyser (independent session) ──
    "pdf_uploaded_file": None,    # Gemini File reference
    "pdf_filename":      None,    # Display name
    "pdf_messages":      [],      # PDF-scoped conversation history
    "pdf_chat":          None,    # PDF-scoped Gemini chat object
}
```

**Key design decisions:**
- Each module owns its own `chat` session object — the Q&A chat and PDF chat are **completely independent Gemini sessions**, preventing document context from leaking into general Q&A responses
- The planner uses a **finite-state-machine pattern** (`planner_exam_count = None` → Step 1; `int` → Step 2; `planner_result != None` → display) enabling clean wizard-style progression
- The CLI agent (`main.py`) extends this further with an `agent_state` dictionary including `mode` and `waiting_for` fields, implementing a **stateful conversation router** that supports mid-flow module interruption and resumption

### 3. Streaming Response Architecture
- All AI responses use `send_message_stream()` for token-by-token delivery
- Collected via a `collect_stream()` utility that drains the generator into a single string for state persistence
- Eliminates the latency of waiting for full response generation before rendering

### 4. Resource Management & Cleanup
- Temporary PDF files (from URL downloads) are tracked in state and **automatically cleaned up** on session close or error
- Chunked download (`iter_content(chunk_size=8192)`) prevents memory spikes when downloading large PDFs from URLs
- Content-Type validation warns users when a URL may not point to a valid PDF before committing to the upload pipeline

### 5. Dual-Interface Architecture
The application ships with **two complete interfaces** for different use cases:

| Interface | File | Use Case |
|-----------|------|----------|
| **Web GUI** | `app.py` | Production-grade Streamlit web UI with custom CSS, glassmorphism design, and gradient theming |
| **CLI Agent** | `main.py` | Terminal-based conversational agent with stateful routing, interrupt handling, and real-time streaming |

Both interfaces share the same core AI logic and Gemini integration patterns, demonstrating clean separation of concerns between business logic and presentation layer.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend / UI** | Streamlit with custom CSS (Sora + JetBrains Mono fonts, glassmorphism, gradient themes) |
| **AI Engine** | Google Gemini 2.5 Flash Lite |
| **Document Processing** | Gemini Files API with automatic state polling |
| **Search Grounding** | Google Search Tool (via Gemini function calling) |
| **PDF Handling** | `requests` (chunked download), `tempfile` (secure temp storage) |
| **State Management** | Streamlit `session_state` + custom finite-state-machine patterns |
| **Configuration** | `python-dotenv` for environment variable management |

---

## 📁 Project Structure

```
SehPaathi/
├── app.py                  # Streamlit web application (production GUI)
├── main.py                 # CLI-based conversational agent
├── requirements.txt        # Python dependencies
├── .env                    # API key configuration (not committed)
├── .gitignore              # Git exclusions
├── .streamlit/
│   └── config.toml         # Streamlit theme configuration (dark mode)
└── README.md               # You are here
```

---

## 🚀 Local Setup

### Prerequisites

- **Python 3.10+** installed
- A **Google Gemini API key** ([Get one here](https://aistudio.google.com/apikey))

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/SehPaathi.git
cd SehPaathi
```

### 2. Create & Activate a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 5. Run the Application

**Option A — Web Interface (Recommended)**

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501` with the full GUI experience.

**Option B — CLI Agent**

```bash
python main.py
```

Launches the terminal-based conversational agent with all three modules accessible via natural language.

---

## 🖥️ Usage

### 💬 Chat Q&A
1. Navigate to the **Chat Q/A** tab
2. Type any academic question (e.g., _"Explain the OSI model"_)
3. Get streaming, Google-Search-grounded responses with full conversation context

### 📅 Study Planner
1. Navigate to the **Study Planner** tab
2. Enter the number of exams → fill in subject, date, and type for each
3. Set your daily study window (start / end time)
4. Click **Generate Plan** — download the result as a `.txt` file

### 📄 PDF Analyser
1. Navigate to the **PDF Analyser** tab
2. Paste a public PDF URL **or** upload a file from your device
3. Wait for the automatic processing pipeline to complete
4. Ask any question about the document — fully conversational, multi-turn

---

## 🙏 Acknowledgements

- [Google Gemini API](https://ai.google.dev/) — AI engine and document analysis
- [Streamlit](https://streamlit.io/) — rapid web UI framework
- [Google Fonts](https://fonts.google.com/) — Sora & JetBrains Mono typefaces

---

<p align="center">
  <strong>Built with ❤️ by <a href="https://github.com/<your-username>">@CoderNabh1</a></strong>
  <br />
  <em>Keep Studying — Keep Advancing 🚀</em>
</p>
