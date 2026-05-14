import os
import time
import datetime
import tempfile
import requests

from urllib.parse import urlparse

from dotenv import load_dotenv
from google import genai
from google.genai import types


# -------------------------------
# 🔐 Load API Key
# -------------------------------
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ GEMINI_API_KEY not found in .env file")

# -------------------------------
# 🤖 Create Client
# -------------------------------
client = genai.Client(api_key=api_key)

# Optional grounding tool
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# -------------------------------
# 🧠 System Instruction
# -------------------------------
sys_instr = """
You are SehPathi, an intelligent exam planning assistant.

Your responsibilities:
1. Help users create study plans based on exam dates
2. Summarize study material and answer questions
3. Answer subject-related questions clearly

Rules:
- Be structured and helpful
- Be concise but informative
- Guide the user step-by-step
- If user input is unclear, ask questions before answering
- Ask follow-up questions naturally
"""

# -------------------------------
# 💬 Chat Session
# -------------------------------
chat = client.chats.create(
    model="gemini-2.5-flash-lite",
    config=types.GenerateContentConfig(
        system_instruction=sys_instr,
        temperature=0.4,
        tools=[grounding_tool]
    )
)

# -------------------------------
# 🧠 GLOBAL STATE (NEW 🔥)
# -------------------------------
agent_state = {

    # Current active module
    "mode": None,

    # What info bot is waiting for
    "waiting_for": None,

    # Planner memory
    "planner": {
        "exam_count": None,
        "current_exam_index": 0,
        "exams": [],
        "study_start": None,
        "study_end": None
    },

    # PDF memory (future use)
    "pdf": {

    # Active uploaded PDF object
    "active_file": None,

    # Original filename
    "file_name": None,

    # small_pdf or large_pdf
    "upload_method": None,

    # Whether PDF conversation is active
    "conversation_active": False,
    
     "temp_path": None
    }
}


# -------------------------------
# 👋 Greeting
# -------------------------------
def greet_user():
    print("\n-----------------------------------------------------")
    print("👋 Hello, I am SehPathi — Your Exam Planning Assistant")
    print("-------------------------------------------------------\n")
    
    print("I can help you with:")
    print("📅 Date Sheet Planning")
    print("📄 PDF Summarization + Q/A")
    print("📚 Subject-related Questions\n")
    
    print("👉 Just tell me what you need.")
    print("Type 'endchat' anytime to exit.\n")

# -------------------------------
# 🧠 Intent Detection
# -------------------------------
def detect_intent(user_input):

    text = user_input.lower()
    
    # =====================================================
    # 📅 PLANNER KEYWORDS
    # =====================================================
    planner_keywords = [
        "plan",
        "schedule",
        "study plan",
        "datesheet",
        "date sheet",
        "timetable",
        "exam plan",
        "exam",
        "planning",
        "planner"
    ]

    # =====================================================
    # 📄 PDF KEYWORDS
    # =====================================================
    pdf_keywords = [
        "pdf",
        "document",
        "summary",
        "notes",
        "summarize",
        "whole"
    ]

    # =====================================================
    # 📚 Q/A KEYWORDS
    # =====================================================
    qa_keywords = [
        "what",
        "how",
        "why",
        "who",      # <-- Added
        "when",     # <-- Added
        "where",    # <-- Added
        "which",    # <-- Added
        "explain",
        "define",
        "difference",
        "tell",
        "about",
        "can you",  # <-- Added (e.g., "can you help me with...")
        "is there"  # <-- Added
    ]

    # Planner detection
    for word in planner_keywords:
        if word in text:
            return "planner"

    # PDF detection
    for word in pdf_keywords:
        if word in text:
            return "pdf"
        
    for word in qa_keywords:
        if word in text:
            return "qa"

    # Default fallback
    return "unclear"

# =========================================================
# 📤 STREAMING RESPONSE FUNCTION
# =========================================================
def stream_response(prompt):

    print("\nSehPathi: ", end="", flush=True)
    
    try:
            for chunk in chat.send_message_stream(prompt):
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    time.sleep(0.02)
            print("\n")
    except Exception as e:
        print(f"\n❌ Streaming Error: {e}")
    print("\n")

# =========================================================
# 🔄 RESET PLANNER STATE
# =========================================================
# Clears planner memory safely
# =========================================================
def reset_planner():

    agent_state["mode"] = None

    agent_state["waiting_for"] = None

    agent_state["planner"] = {

        "exam_count": None,
        "current_exam_index": 0,
        "exams": [],
        "study_start": None,
        "study_end": None
    }


# =========================================================
# 🧹 CLEANUP TEMP PDF
# =========================================================
def cleanup_temp_pdf():
    temp_path = agent_state["pdf"].get("temp_path")
    if temp_path and os.path.exists(temp_path):

        try:
            os.remove(temp_path)

        except Exception as e:
            print(f"SehPathi: Cleanup warning -> {e}")


# =========================================================
# 🔄 RESET PDF STATE
# =========================================================
def reset_pdf():
    cleanup_temp_pdf()
    agent_state["pdf"] = {

        "active_file": None,
        "file_name": None,
        "upload_method": None,
        "conversation_active": False,
        "temp_path": None
    }


# =========================================================
# 🌐 CHECK IF INPUT IS URL
# =========================================================
def is_url(text):

    try:

        result = urlparse(text)
        return all([result.scheme, result.netloc])

    except:
        return False


# =========================================================
# 📦 GET FILE SIZE
# =========================================================
def get_file_size_mb(path):

    size_bytes = os.path.getsize(path)
    return size_bytes / (1024 * 1024)


# =========================================================
# 🌐 DOWNLOAD PDF FROM URL
# =========================================================
def download_pdf(url):
    try:
        response = requests.get(url, stream = True)

        if response.status_code != 200:
            return None
        
        # BUG 5 FIX: Basic Content-Type Validation
        content_type = response.headers.get("Content-Type", "")
        if 'application/pdf' not in content_type.lower() and not url.lower().endswith('.pdf'):
            print("SehPathi: ⚠️ Warning: URL might not be a PDF.")
        
        # Create temp pdf file
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        )

        # BUG 3 FIX: Download in chunks to avoid RAM spikes
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)

        temp_file.close()
        return temp_file.name
    except Exception as e:
        print(f"SehPathi: ❌ Download error: {e}")
        return None


# =========================================================
# 📅 PLANNER MODULE
# =========================================================
def run_planner(user_input):
    planner = agent_state["planner"]

    # -----------------------------------------------------
    # STEP 1 → Ask number of exams
    # -----------------------------------------------------
    if agent_state["waiting_for"] is None:
        agent_state["mode"] = "planner"
        agent_state["waiting_for"] = "exam_count"
        print("\nSehPathi: How many exams do you have?\n")
        return

    # -----------------------------------------------------
    # STEP 2 → Receive exam count
    # -----------------------------------------------------
    if agent_state["waiting_for"] == "exam_count":
        try:
            planner["exam_count"] = int(user_input)
        except:
            print("SehPathi: Please enter a valid number.")
            return

        # 🔥 CHANGED: Ask for all details at once!
        agent_state["waiting_for"] = "exam_details"
        print("\nSehPathi: Enter details for Exam 1 (Format: Subject, Date, Type --> [theory, mcq, practical])")
        print("Example: Computer Networks, 25 May, theory\n")
        return

    # -----------------------------------------------------
    # STEP 3 → Receive ALL Exam Details (Collapsed)
    # -----------------------------------------------------
    if agent_state["waiting_for"] == "exam_details":
        
        # Split the user input by commas and remove extra spaces
        parts = [p.strip() for p in user_input.split(",")]

        # Safety check: Did they provide all 3 items?
        if len(parts) != 3:
            print("\nSehPathi: ⚠️ Please provide all 3 details separated by commas.")
            print("Example: Computer Networks, 25 May, theory\n")
            return

        # Save the exam
        exam = {
            "subject": parts[0],
            "date": parts[1],
            "type": parts[2].lower()
        }
        planner["exams"].append(exam)
        planner["current_exam_index"] += 1

        # More exams remaining
        if planner["current_exam_index"] < planner["exam_count"]:
            next_exam = planner["current_exam_index"] + 1
            print(f"\nSehPathi: Enter details for Exam {next_exam} (Format: Subject, Date, Type)\n")
            return

        # All exams completed
        else:
            agent_state["waiting_for"] = "study_start"
            print("\nSehPathi: Enter study start time (Example: 06:00 AM)\n")
            return

    # -----------------------------------------------------
    # STEP 4 → Study Start Time
    # -----------------------------------------------------
    if agent_state["waiting_for"] == "study_start":
        planner["study_start"] = user_input
        agent_state["waiting_for"] = "study_end"
        print("\nSehPathi: Enter study end time (Example: 11:00 PM)\n")
        return

    # -----------------------------------------------------
    # STEP 5 → Study End Time
    # -----------------------------------------------------
    if agent_state["waiting_for"] == "study_end":
        planner["study_end"] = user_input

        # =================================================
        # 🔥 GENERATE FINAL PLAN
        # =================================================
        exams = planner["exams"]
        
        # Grab the current year automatically
        current_year = datetime.date.today().year
        
        prompt = f"""
Create a detailed day-wise study plan for the year {current_year}.

Exams:
{exams}

Study Time:
{planner["study_start"]} to {planner["study_end"]}

CRITICAL RULES:
1. STRICT RULE: DO NOT ASK ANY FOLLOW-UP QUESTIONS. Generate the schedule immediately. 
2. If syllabus details are missing, ASSUME standard core topics for the given subjects.
3. If rest times are missing, use your best judgment to allocate healthy rest periods.

Rules:
1. Include:
- breakfast - 15 to 30 minutes
- lunch - 15 to 30 minutes
- dinner - 15 to 30 minutes
- bathing - 5 to 15 minutes
- breaks
- meals
- rest
- hygiene

2. Study blocks:
- 1.5 to 2 hour sessions
- 15 min breaks
- 30 min long breaks

3. Planning Logic:
- prioritize nearest exam
- if exam gap >3 days: shift focus strategically

4. Exam Strategy:
- MCQ → speed practice
- Theory → revision + concepts
- Practical → application + concepts

5. Day before exam:
- revision only

6. Exam day:
- light study only

Make realistic human schedule.
"""
        stream_response(prompt)

        # =================================================
        # 🔄 RESET STATE CLEANLY
        # =================================================
        reset_planner()
        
        
# -------------------------------
# 📄 PDF MODULE
# -------------------------------
def run_pdf_module(user_input):

    # -----------------------------------------------------
    # STEP 1 → START PDF MODE
    # -----------------------------------------------------
    if not agent_state["pdf"]["conversation_active"]:
        agent_state["mode"] = "pdf"
        agent_state["pdf"]["conversation_active"] = True

        print("\nSehPathi: 📄 Please provide:")
        print("1. PDF URL")
        print("OR")
        print("2. Local PDF Path\n")
        return

    # -----------------------------------------------------
    # STEP 2 → RECEIVE PDF
    # -----------------------------------------------------
    pdf_input = user_input.strip()
    pdf_path = None
    is_temporary = False

    # =====================================================
    # 🌐 URL CASE
    # =====================================================
    if is_url(pdf_input):
        print("\nSehPathi: 🌐 Downloading PDF from URL...\n")

        pdf_path = download_pdf(pdf_input)
        is_temporary = True # Mark for deletion later
        
        if pdf_path is None:
            print("SehPathi: ❌ Failed to download PDF.")
            reset_pdf()
            return

    # =====================================================
    # 💻 LOCAL PATH CASE
    # =====================================================
    else:
        if not os.path.exists(pdf_input):
            print("SehPathi: ❌ File path does not exist.")
            return
        if not pdf_input.lower().endswith(".pdf"):
            print("SehPathi: ❌ File is not a PDF.")
            return
        pdf_path = pdf_input

    # =====================================================
    # 📦 FILE SIZE CHECK
    # =====================================================
    try:
        file_size = get_file_size_mb(pdf_path)
    except Exception as e:
        print(f"SehPathi: ❌ Could not read file size -> {e}")
        reset_pdf()
        return
    
    print(f"SehPathi: 📦 PDF Size = {round(file_size, 2)} MB")
     # -----------------------------------------------------
    # UPLOAD PDF
    # -----------------------------------------------------
    try:

        if file_size < 20:

            print(f"SehPathi: ☁️ Uploading small PDF...")

            agent_state["pdf"]["upload_method"] = "small_pdf"

        else:

            print(f"SehPathi: ☁️ Uploading large PDF...")

            agent_state["pdf"]["upload_method"] = "large_pdf"

        uploaded_file = client.files.upload(
            file=pdf_path
        )

    except Exception as e:

        print(f"SehPathi: ❌ Upload failed -> {e}")

        reset_pdf()

        return

    # -----------------------------------------------------
    # WAIT FOR ACTIVE
    # -----------------------------------------------------
    print("SehPathi: ⏳ Processing PDF", end="", flush=True)

    try:

        while uploaded_file.state.name == "PROCESSING":

            print(".", end="", flush=True)

            time.sleep(2)

            uploaded_file = client.files.get(
                name=uploaded_file.name
            )

    except Exception as e:

        print(f"\nSehPathi: ❌ Processing error -> {e}")

        reset_pdf()

        return

    # -----------------------------------------------------
    # FAILED PROCESSING
    # -----------------------------------------------------
    if uploaded_file.state.name == "FAILED":

        print("\nSehPathi: ❌ Gemini failed to process PDF.")

        reset_pdf()

        return

    # -----------------------------------------------------
    # SAVE PDF STATE
    # -----------------------------------------------------
    agent_state["pdf"]["active_file"] = uploaded_file

    agent_state["pdf"]["file_name"] = os.path.basename(pdf_path)

    if is_temporary:
        agent_state["pdf"]["temp_path"] = pdf_path

    print("\nSehPathi: ✅ PDF processed successfully.")
    print("You can now ask questions about the PDF.\n")

# -------------------------------
# 📚 Q/A MODULE
# -------------------------------
def run_qa(user_input):
    print("SehPathi:📚 Here's your answer:--")
    
    for chunk in chat.send_message_stream(user_input):
        if chunk.text:
            print(chunk.text, end="", flush=True)
            time.sleep(0.02)
    print()


# -------------------------------
# 🤔 FALLBACK
# -------------------------------
def ask_clarification():
    print("SehPathi: 🤔 I didn't fully understand.")
    print("Do you want:")
    print("1. A study plan?")
    print("2. PDF summary?")
    print("3. Subject Q/A?\n")

# -------------------------------
# 🚀 START
# -------------------------------
greet_user()
print("--- (Type 'endchat' to leave) ---")


# -------------------------------
# 🔁 MAIN LOOP (UPDATED 🔥)
# -------------------------------
while True:
    uinput = input("User: ")

    # =====================================================
    # 🛑 GLOBAL EXIT COMMANDS
    # =====================================================
    if uinput.lower() in [

        "endchat",
        "exit",
        "quit"
    ]:
        reset_pdf()
        print("\nSehPathi: See you next time, Till then Keep Studying--Keep Advancing...\n")
        break

    try:

        # =================================================
        # 🛑 GLOBAL CANCEL COMMANDS
        # =================================================
        # Allows user to escape planner anytime
        # =================================================
        if uinput.lower() in [

            "cancel",
            "stop",
            "exit planner",
            "abort",
            "nevermind"
        ]:

            reset_planner()
            reset_pdf()
            print("\nSehPathi: Current planner task cancelled.\n")
            continue


        # =================================================
        # 📄 ACTIVE PDF CONVERSATION
        # =================================================
        if agent_state["pdf"]["conversation_active"]:
            # ✅ FIX: If file not yet uploaded, we're still in setup phase
            if agent_state["pdf"]["active_file"] is None:
                run_pdf_module(uinput)
                continue
            
            interrupt_intent = detect_intent(uinput)
            if interrupt_intent == "planner":
                print("\nSehPathi: ⏸ Switching to Planner. PDF session paused (type 'exit pdf' to close it).\n")
                run_planner(uinput)
                continue
            
            # ---------------------------------------------
            # Exit PDF mode
            # ---------------------------------------------
            if uinput.lower() in [
                "exit pdf",
                "close pdf",
                "stop pdf",
                "cancel",
                "quit",
                "end"
            ]:
                reset_pdf()
                print("\nSehPathi: 📄 PDF session ended.\n")
                continue

            # ---------------------------------------------
            # Ask questions on active PDF
            # ---------------------------------------------
            print("\nSehPathi: ", end="", flush=True)
            try:
                response = chat.send_message_stream(
                    [
                        agent_state["pdf"]["active_file"],
                        uinput
                    ]
                )

                for chunk in response:
                    if chunk.text:
                        print(chunk.text, end="", flush=True)
                        time.sleep(0.02)
            except Exception as e:

                print(f"\n❌ PDF Q/A Error -> {e}")

            print("\n")
            continue

        # =================================================
        # 📅 SMART PLANNER INTERRUPT SYSTEM
        # =================================================
        if agent_state["mode"] == "planner":

            # Detect fresh intent even during planner
            interrupt_intent = detect_intent(uinput)

            # -------------------------------------------------
            # 🧠 USER SWITCHED TOPIC
            # -------------------------------------------------
            if interrupt_intent in ["pdf", "qa"]:
                print("\nSehPathi: ⏸ Planner paused temporarily.\n")

                # OPTIONAL:
                # You can either:
                # 1. keep planner memory
                # 2. reset planner completely

                # CURRENTLY:
                # We KEEP memory for better UX

                if interrupt_intent == "pdf":
                    run_pdf_module(uinput)

                elif interrupt_intent == "qa":
                    run_qa(uinput)
                    
                # 🔥 NEW: Remind the user where they left off!
                print(f"SehPathi: 🔄 Resuming planner! I am still waiting for the {agent_state['waiting_for']}.")
                continue

            # -------------------------------------------------
            # 📅 OTHERWISE CONTINUE PLANNER
            # -------------------------------------------------
            run_planner(uinput)
            continue

                
        # =================================================
        # 🔍 DETECT INTENT
        # =================================================
        intent = detect_intent(uinput)

        # =================================================
        # 📅 PLANNER ROUTING
        # =================================================
        if intent == "planner":
            run_planner(uinput)

        # =================================================
        # 📄 PDF ROUTING
        # =================================================
        elif intent == "pdf":
            run_pdf_module(uinput)

        # =================================================
        # 📚 QA ROUTING
        # =================================================
        elif intent == "qa":
            run_qa(uinput)

        # =================================================
        # ❓ UNKNOWN INPUT
        # =================================================
        else:
            ask_clarification()
            
    except KeyboardInterrupt:
        print("\n\nSehPathi: Interrupted safely.")
        reset_pdf()
        break

    except Exception as e:
        print(f"\nAn error occurred: {e}\n")

# =========================================================
# 🏁 APPLICATION END
# =========================================================
print("\n-----------------------------------")
print("Response Ended")