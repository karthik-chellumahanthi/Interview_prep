import streamlit as st
import json
import random
import os
import time
from streamlit.components.v1 import html
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini API
GOOGLE_API_KEY = os.getenv("google_api_key")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

st.set_page_config(
    page_title="PrepMate AI - Interview Coach",
    page_icon="🎤",
    layout="wide"
)

def load_questions():
    with open("questions.json", "r", encoding="utf-8") as file:
        return json.load(file)

def filter_questions(questions, interview_type, domain, difficulty):
    filtered = []

    for q in questions:
        if q["difficulty"] != difficulty:
            continue

        if interview_type == "HR":
            if q["category"] == "HR/Behavioral":
                filtered.append(q)

        elif interview_type == "Technical":
            if q["category"] in ["Technical", "Role-Specific"] and q["domain"] == domain:
                filtered.append(q)

        elif interview_type == "Both":
            if q["category"] == "HR/Behavioral" or q["domain"] == domain:
                filtered.append(q)

    return filtered

def generate_questions_with_gemini(interview_type, domain, difficulty, count=5):
    """Generate interview questions using Gemini API when questions not found"""
    if not GOOGLE_API_KEY:
        return []
    
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""Generate {count} professional interview questions for the following:
- Interview Type: {interview_type}
- Domain: {domain}
- Difficulty: {difficulty}

For each question, provide a JSON object with these fields:
- question_text: The interview question
- category: Either "HR/Behavioral" or "Technical" or "Role-Specific"
- domain: {domain}
- difficulty: {difficulty}
- keywords: List of 3-5 important keywords/concepts to look for in answer
- sample_strong_answer: An example of a good answer (2-3 sentences)
- what_interviewer_is_looking_for: What the interviewer expects
- common_mistakes_to_avoid: Common errors candidates make

Return ONLY a valid JSON array. Example format:
[
  {{
    "question_text": "Tell me about yourself",
    "category": "HR/Behavioral",
    "domain": "{domain}",
    "difficulty": "{difficulty}",
    "keywords": ["experience", "skills", "goals"],
    "sample_strong_answer": "I have 5 years of experience in...",
    "what_interviewer_is_looking_for": "Clear communication of relevant experience",
    "common_mistakes_to_avoid": "Don't recite your resume, be specific"
  }}
]"""
        
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Extract JSON from response
        try:
            # Find JSON array in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                questions = json.loads(json_str)
                return questions
        except json.JSONDecodeError:
            pass
    
    except Exception as e:
        st.warning(f"Could not generate questions with AI: {str(e)}")
    
    return []

def evaluate_answer_basic(answer, question):
    answer_lower = answer.lower()
    keywords = question.get("keywords", [])

    matched_keywords = [
        keyword for keyword in keywords
        if keyword.lower() in answer_lower
    ]

    word_count = len(answer.split())
    score = 0

    if word_count >= 30:
        score += 4
    elif word_count >= 20:
        score += 3
    elif word_count >= 10:
        score += 2
    elif word_count >= 5:
        score += 1

    score += len(matched_keywords) * 2
    score = min(score, 10)

    if word_count < 5:
        feedback_level = "Too Short"
    elif score <= 3:
        feedback_level = "Weak Answer"
    elif score <= 6:
        feedback_level = "Average Answer"
    else:
        feedback_level = "Good Answer"

    return score, feedback_level, f"Matched keywords: {', '.join(matched_keywords) if matched_keywords else 'None'}"

def evaluate_answer_with_gemini(answer, question):
    if not GOOGLE_API_KEY:
        return evaluate_answer_basic(answer, question)
        
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""Evaluate this interview answer.
Question: {question['question_text']}
Candidate's Answer: {answer}
Expected concepts: {', '.join(question.get('keywords', []))}

Provide your evaluation as a JSON object with:
- score: an integer from 0 to 10
- feedback: 2-3 sentences of specific, constructive feedback on what they did well and what to improve. Talk directly to the candidate (e.g. 'You did a good job explaining...').

Return ONLY valid JSON.
"""
        response = model.generate_content(prompt)
        start_idx = response.text.find('{')
        end_idx = response.text.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = response.text[start_idx:end_idx]
            result = json.loads(json_str)
            
            score = int(result.get('score', 0))
            feedback = result.get('feedback', 'No feedback provided.')
            
            if score <= 4:
                level = "Needs Improvement"
            elif score <= 7:
                level = "Average Answer"
            else:
                level = "Good Answer"
                
            return score, level, feedback
    except Exception as e:
        pass
        
    return evaluate_answer_basic(answer, question)

def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

MIC_HTML = """
<div style="padding:20px; border-radius:16px; background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%); border:1px solid rgba(139, 92, 246, 0.3); color:#F8FAFC; margin-bottom: 16px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.2);">
  <div style="font-size:16px; font-weight:700; margin-bottom:16px; color: #E2E8F0; display:flex; align-items:center; gap:8px;">
    <span style="font-size:20px;">🎤</span> Voice Answer
  </div>
  <div style="display:flex; gap:16px; align-items:center; margin-bottom:12px;">
    <button id="startBtn" style="padding:10px 24px; border:none; border-radius:10px; background: linear-gradient(135deg, #10B981 0%, #059669 100%); color:#fff; cursor:pointer; font-weight: 600; font-family: 'Inter', sans-serif; transition: all 0.3s; box-shadow: 0 4px 15px -3px rgba(16, 185, 129, 0.4); text-transform:uppercase; font-size:13px; letter-spacing:0.5px;">Start Recording</button>
    <button id="stopBtn" style="padding:10px 24px; border:none; border-radius:10px; background: linear-gradient(135deg, #EF4444 0%, #B91C1C 100%); color:#fff; border: none; cursor:pointer; font-weight: 600; font-family: 'Inter', sans-serif; transition: all 0.3s; box-shadow: 0 4px 15px -3px rgba(239, 68, 68, 0.4); text-transform:uppercase; font-size:13px; letter-spacing:0.5px;" disabled>Stop</button>
  </div>
  <div id="status" style="font-size:14px; color:#CBD5E1; font-style:italic;">Click Start and speak your answer clearly.</div>
</div>
<script>
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const status = document.getElementById('status');
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

if (!SpeechRecognition) {
  status.textContent = 'Speech recognition is not supported in this browser. Please type your answer manually.';
  startBtn.disabled = true;
} else {
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onresult = (event) => {
    let transcript = '';
    // Loop from 0 to get the entire history of the current recording session
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    
    const parentTextarea = window.parent.document.querySelector('textarea[aria-label="Answer via Mic or typing"]');
    if (parentTextarea) {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, "value").set;
      nativeInputValueSetter.call(parentTextarea, transcript);
      parentTextarea.dispatchEvent(new Event('input', { bubbles: true }));
    }
    status.textContent = 'Listening...';
  };

  recognition.onerror = (event) => {
    status.textContent = 'Microphone error: ' + event.error;
  };

  recognition.onend = () => {
    status.textContent = 'Recording stopped. Review the transcript and submit.';
    startBtn.disabled = false;
    stopBtn.disabled = true;
    
    const parentTextarea = window.parent.document.querySelector('textarea[aria-label="Answer via Mic or typing"]');
    if (parentTextarea) {
      // Force React to recognize the final state
      parentTextarea.focus();
      parentTextarea.dispatchEvent(new Event('change', { bubbles: true }));
      parentTextarea.blur();
    }
  };

  startBtn.onclick = () => {
    recognition.start();
    startBtn.disabled = true;
    stopBtn.disabled = false;
    status.textContent = 'Speak now...';
  };

  stopBtn.onclick = () => {
    recognition.stop();
  };
}
</script>
"""

if "started" not in st.session_state:
    st.session_state.started = False

if "chat" not in st.session_state:
    st.session_state.chat = []

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "scores" not in st.session_state:
    st.session_state.scores = []

if "answers" not in st.session_state:
    st.session_state.answers = []

if "generated_questions_cache" not in st.session_state:
    st.session_state.generated_questions_cache = {}

if "generation_attempted" not in st.session_state:
    st.session_state.generation_attempted = {}

if "question_start_time" not in st.session_state:
    st.session_state.question_start_time = None

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stHeader"] { visibility: hidden; }
#MainMenu { visibility: hidden; }
header { visibility: hidden; }

@keyframes gradientAnimation {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

@keyframes float {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-15px); }
    100% { transform: translateY(0px); }
}

@keyframes float-slow {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-8px); }
    100% { transform: translateY(0px); }
}

.stApp {
    background: linear-gradient(-45deg, #0f172a, #1e1b4b, #312e81, #020617);
    background-size: 400% 400%;
    animation: gradientAnimation 15s ease infinite;
    color: #F8FAFC;
    overflow-x: hidden;
}

/* Floating background orbs */
.floating-orb {
    position: fixed;
    border-radius: 50%;
    filter: blur(120px);
    z-index: 0;
    pointer-events: none;
    opacity: 0.6;
}
.orb-1 {
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(139,92,246,0.8) 0%, rgba(139,92,246,0) 70%);
    top: -100px;
    left: -100px;
    animation: float 10s ease-in-out infinite;
}
.orb-2 {
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(236,72,153,0.8) 0%, rgba(236,72,153,0) 70%);
    bottom: -150px;
    right: -150px;
    animation: float 14s ease-in-out infinite reverse;
}

/* Ensure content stays above orbs */
[data-testid="stAppViewContainer"] > .main {
    z-index: 1;
    position: relative;
}

/* Glowing cards */
.card, .question-card {
    padding: 28px;
    border-radius: 20px;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(16px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
    position: relative;
    overflow: hidden;
    margin-bottom: 24px;
    transition: all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    animation: float-slow 7s ease-in-out infinite;
}

.card:nth-child(even) {
    animation-delay: 1.5s;
}

.card:hover {
    transform: translateY(-8px) scale(1.02);
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 20px rgba(139, 92, 246, 0.2);
    border-color: rgba(139, 92, 246, 0.4);
    z-index: 10;
}

.card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899);
}

.hero-card {
    padding: 56px 32px;
    border-radius: 28px;
    background: linear-gradient(135deg, rgba(30, 27, 75, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
    border: 1px solid rgba(139, 92, 246, 0.3);
    margin-bottom: 40px;
    text-align: center;
    position: relative;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), inset 0 0 0 1px rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(20px);
    animation: float 6s ease-in-out infinite;
    transition: all 0.5s cubic-bezier(0.23, 1, 0.32, 1);
}

.hero-card:hover {
    transform: translateY(-5px) scale(1.02);
    box-shadow: 0 30px 60px rgba(0, 0, 0, 0.5), inset 0 0 0 1px rgba(255, 255, 255, 0.2), 0 0 30px rgba(236, 72, 153, 0.3);
    animation-play-state: paused;
}

.hero-title {
    font-size: 64px;
    font-weight: 900;
    background: linear-gradient(to right, #60A5FA, #C084FC, #F472B6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 20px;
    letter-spacing: -0.03em;
    text-shadow: 0 10px 30px rgba(192, 132, 252, 0.2);
}

.hero-subtitle {
    font-size: 22px;
    color: #E2E8F0;
    max-width: 700px;
    margin: 0 auto;
    line-height: 1.7;
    font-weight: 300;
}

/* Primary Button Styling */
div.stButton > button {
    background: linear-gradient(135deg, #4F46E5 0%, #EC4899 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.8rem 1.5rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.05em !important;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
    box-shadow: 0 4px 15px -3px rgba(236, 72, 153, 0.4) !important;
    text-transform: uppercase !important;
    font-size: 14px !important;
}

div.stButton > button:hover {
    transform: translateY(-6px) scale(1.03) !important;
    box-shadow: 0 20px 30px -5px rgba(236, 72, 153, 0.6) !important;
}

/* Secondary Button styling for skip/end */
div[data-testid="column"]:nth-child(2) div.stButton > button {
    background: linear-gradient(135deg, #475569 0%, #334155 100%) !important;
    box-shadow: 0 4px 15px -3px rgba(71, 85, 105, 0.4) !important;
}
div[data-testid="column"]:nth-child(2) div.stButton > button:hover {
    box-shadow: 0 20px 30px -5px rgba(71, 85, 105, 0.6) !important;
}

div[data-testid="column"]:nth-child(3) div.stButton > button {
    background: linear-gradient(135deg, #DC2626 0%, #991B1B 100%) !important;
    box-shadow: 0 4px 15px -3px rgba(220, 38, 38, 0.4) !important;
}
div[data-testid="column"]:nth-child(3) div.stButton > button:hover {
    box-shadow: 0 15px 25px -5px rgba(220, 38, 38, 0.5) !important;
}

textarea, input, .stTextInput>div>input, .stTextArea>div>textarea {
    background: rgba(15, 23, 42, 0.6) !important;
    color: #F8FAFC !important;
    border: 2px solid rgba(139, 92, 246, 0.2) !important;
    border-radius: 12px !important;
    font-size: 16px !important;
    padding: 16px !important;
    transition: all 0.3s ease !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.1) !important;
}

textarea:focus, input:focus, .stTextInput>div>input:focus, .stTextArea>div>textarea:focus {
    border-color: #A855F7 !important;
    box-shadow: 0 0 0 4px rgba(168, 85, 247, 0.2), inset 0 2px 4px rgba(0,0,0,0.1) !important;
}

/* Radio buttons & Checkboxes Container Styling */
[data-testid="stRadio"] > div[role="radiogroup"],
[data-testid="stCheckbox"] {
    background: linear-gradient(180deg, rgba(30, 41, 59, 0.5) 0%, rgba(15, 23, 42, 0.8) 100%) !important;
    padding: 16px 20px !important;
    border-radius: 16px !important;
    border: 1px solid rgba(139, 92, 246, 0.2) !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
}

/* Form labels */
.stRadio label > div, .stCheckbox label > div, p {
    color: #F1F5F9 !important;
}

hr {
    border-color: rgba(255, 255, 255, 0.1) !important;
    margin: 2.5em 0 !important;
}

/* Success/Info/Warning/Error boxes */
div[data-testid="stAlert"] {
    border-radius: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%) !important;
    backdrop-filter: blur(12px) !important;
    box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3) !important;
}

/* Metric styling */
[data-testid="stMetricValue"] > div {
    font-size: 2.5rem !important;
    font-weight: 800 !important;
    background: linear-gradient(135deg, #A855F7, #EC4899);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
[data-testid="stMetricLabel"] > div {
    font-size: 1.1rem !important;
    color: #CBD5E1 !important;
    font-weight: 500 !important;
}

/* Progress bar */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899) !important;
}

/* Typography tweaks */
h1, h2, h3, h4, h5, h6 {
    color: #F8FAFC !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}
</style>
<script>
document.addEventListener('keydown', function(event) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
        return true;
    }
});
</script>
""", unsafe_allow_html=True)

st.markdown("""
<div class="floating-orb orb-1"></div>
<div class="floating-orb orb-2"></div>
""", unsafe_allow_html=True)

st.markdown("<div class='hero-card'><div class='hero-title'>✨ PrepMate AI</div><div class='hero-subtitle'>Your professional interview coach. Experience realistic mock interviews with dynamic feedback, intelligent scoring, and beautiful insights.</div></div>", unsafe_allow_html=True)

st.divider()

try:
    questions = load_questions()
except FileNotFoundError:
    st.error("questions.json file not found. Keep questions.json in the same folder as app.py.")
    st.stop()

if not st.session_state.started:
    st.markdown("### Start Your Mock Interview")
    st.write("Select the interview type, domain, and difficulty level for a focused practice session.")

    main_col, info_col = st.columns([2, 1])

    with main_col:
        st.markdown("**Interview Type:**")
        interview_type = st.radio(
            "Select interview type",
            ["HR", "Technical", "Both"],
            horizontal=True,
            label_visibility="collapsed"
        )

        st.markdown("**Domain:**")
        domain = st.radio(
            "Select domain",
            [
                "HR",
                "CS",
                "Data Analytics",
                "Web Development",
                "Non-CS/Aptitude",
                "Marketing",
                "Finance",
                "Data Science"
            ],
            label_visibility="collapsed"
        )

        st.markdown("**Difficulty:**")
        difficulty = st.radio(
            "Select difficulty",
            ["Easy", "Medium", "Hard"],
            horizontal=True,
            label_visibility="collapsed"
        )

        st.markdown("---")
        st.info("Answer with confidence, clarity, and role-specific examples.")
        st.markdown("---")

        if st.button("Start Interview", use_container_width=True):
            filtered_questions = filter_questions(
                questions,
                interview_type,
                domain,
                difficulty
            )

            # If we don't have enough questions, try to generate the rest with Gemini
            if len(filtered_questions) < 15:
                needed = 15 - len(filtered_questions)
                
                # Create cache key
                cache_key = f"{interview_type}_{domain}_{difficulty}_{needed}"
                
                # Check if we already generated these questions
                if cache_key in st.session_state.generated_questions_cache:
                    filtered_questions.extend(st.session_state.generated_questions_cache[cache_key])
                    st.info("✅ Using some previously generated questions to reach 15...")
                # Check if generation was already attempted and failed
                elif cache_key in st.session_state.generation_attempted:
                    if len(filtered_questions) == 0:
                        st.error(f"❌ Could not generate questions. Reason: {st.session_state.generation_attempted[cache_key]}")
                        st.info("💡 Please try selecting a different domain or difficulty.")
                        st.stop()
                else:
                    # Only attempt generation once
                    if len(filtered_questions) == 0:
                        st.info("📚 Generating custom questions using AI...")
                    else:
                        st.info(f"📚 Found {len(filtered_questions)} questions. Generating {needed} more using AI to reach 15...")
                        
                    try:
                        new_questions = generate_questions_with_gemini(
                            interview_type,
                            domain,
                            difficulty,
                            count=needed
                        )
                        
                        # Cache the generated questions
                        if new_questions:
                            st.session_state.generated_questions_cache[cache_key] = new_questions
                            filtered_questions.extend(new_questions)
                            st.success("✅ Custom questions generated successfully!")
                        else:
                            st.session_state.generation_attempted[cache_key] = "No questions were generated"
                            if len(filtered_questions) == 0:
                                st.error("❌ No questions could be generated.")
                                st.stop()
                    except Exception as e:
                        st.session_state.generation_attempted[cache_key] = str(e)
                        if len(filtered_questions) == 0:
                            st.error(f"❌ Could not generate questions. Error: {str(e)}")
                            st.info("💡 Please try selecting a different domain or difficulty.")
                            st.stop()
                
                if len(filtered_questions) == 0:
                    st.error("❌ No questions found for this selection. Please choose another domain or difficulty.")
                    st.stop()

            # Ensure we have exactly 15 questions by reusing questions if necessary
            selected_questions = []
            if len(filtered_questions) >= 15:
                selected_questions = random.sample(filtered_questions, 15)
            else:
                selected_questions = list(filtered_questions)
                while len(selected_questions) < 15:
                    selected_questions.append(random.choice(filtered_questions))
                random.shuffle(selected_questions)

            st.session_state.started = True
            st.session_state.selected_questions = selected_questions
            st.session_state.current_index = 0
            st.session_state.scores = []
            st.session_state.answers = []
            st.session_state.chat = []

            first_question = selected_questions[0]["question_text"]
            st.session_state.chat.append({
                "role": "assistant",
                "message": f"Question 1: {first_question}"
            })

            st.rerun()
            st.session_state.answers = []
            st.session_state.chat = []

            first_question = selected_questions[0]["question_text"]
            st.session_state.chat.append({
                "role": "assistant",
                "message": f"Question 1: {first_question}"
            })

            st.rerun()

    with info_col:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("#### How it works")
        st.markdown(
            "- Answer in clear, complete sentences.\n"
            "- Use examples or short explanations.\n"
            "- Focus on skills, achievements, and goals.\n"
            "- Avoid one-word or generic responses."
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("#### Interview Tips")
        st.markdown(
            "- Mention what interviewer expects.\n"
            "- Keep it structured: situation, action, result.\n"
            "- Refer to the sample answer when needed.\n"
            "- Keep your tone professional and precise."
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("#### Ready for practice?")
        st.markdown("A professional mock interview experience starts with focused preparation and concise responses.")
        st.markdown("</div>", unsafe_allow_html=True)

else:
    total_questions = len(st.session_state.selected_questions)
    current_index = st.session_state.current_index

    left, right = st.columns([2, 1], gap="large")

    with left:
        st.markdown("### Interview Session")
        st.write("Answer all questions clearly. You'll receive comprehensive feedback after completing the interview.")

        answered_count = len(st.session_state.answers)
        progress = answered_count / total_questions
        st.progress(progress)
        
        if current_index < total_questions:
            st.caption(f"Question {answered_count + 1} of {total_questions}")
        else:
            st.caption(f"Completed {answered_count} of {total_questions} questions")

        if current_index < total_questions:
            current_question = st.session_state.selected_questions[current_index]
            st.markdown(f"### {current_question['question_text']}")

            if st.session_state.question_start_time is None:
                st.session_state.question_start_time = time.time()

            html(MIC_HTML, height=180)
            user_answer = st.text_area("Answer via Mic or typing", key=f"answer_{current_index}", height=180)

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Next Question", use_container_width=True):
                    if not user_answer.strip():
                        st.error("Please provide an answer before moving to the next question.")
                    else:
                        time_taken = time.time() - st.session_state.question_start_time
                        with st.spinner("🤖 AI is evaluating your answer..."):
                            score, level, ai_feedback = evaluate_answer_with_gemini(user_answer, current_question)
                            
                        st.session_state.answers.append({
                            "question": current_question["question_text"],
                            "answer": user_answer,
                            "question_obj": current_question,
                            "score": score,
                            "level": level,
                            "ai_feedback": ai_feedback,
                            "time_taken": time_taken,
                            "skipped": False
                        })
                        st.session_state.scores.append(score)
                        st.session_state.current_index += 1
                        st.session_state.question_start_time = None
                        st.rerun()

            with col2:
                if st.button("Skip Question", use_container_width=True):
                    time_taken = time.time() - st.session_state.question_start_time
                    st.session_state.answers.append({
                        "question": current_question["question_text"],
                        "answer": "Skipped",
                        "question_obj": current_question,
                        "score": 0,
                        "level": "Skipped",
                        "ai_feedback": "You chose to skip this question.",
                        "time_taken": time_taken,
                        "skipped": True
                    })
                    st.session_state.scores.append(0)
                    st.session_state.current_index += 1
                    st.session_state.question_start_time = None
                    st.rerun()

            with col3:
                if st.button("End Interview", use_container_width=True):
                    st.session_state.current_index = total_questions
                    st.session_state.question_start_time = None
                    st.rerun()

        else:
            # All questions answered - show evaluation
            st.success("✅ Interview Completed! Here is your detailed feedback.")
            st.write("\n**Your Answers and AI Feedback:**\n")
            
            for i, answer_data in enumerate(st.session_state.answers, start=1):
                question_obj = answer_data["question_obj"]
                user_answer = answer_data["answer"]
                score = answer_data["score"]
                level = answer_data["level"]
                time_taken = answer_data.get("time_taken", 0)
                
                st.markdown(f"---")
                st.markdown(f"### Question {i}: {answer_data['question']}")
                
                if answer_data.get("skipped", False):
                    st.warning("⚠️ You skipped this question.")
                else:
                    st.markdown(f"**Your Answer:** {user_answer}")
                    st.success(f"✓ Score: {score}/10 - {level}")
                    
                    time_str = f"{int(time_taken // 60)}m {int(time_taken % 60)}s"
                    if time_taken < 15:
                        st.warning(f"⏱️ Time taken: {time_str} (Answered very quickly. Try to elaborate more.)")
                    elif time_taken > 180:
                        st.warning(f"⏱️ Time taken: {time_str} (A bit too long. Try to be more concise.)")
                    else:
                        st.info(f"⏱️ Time taken: {time_str}")
                        
                    st.write(f"**🤖 AI Feedback:** {answer_data['ai_feedback']}")
                
                st.write(f"**What the interviewer expects:** {question_obj['what_interviewer_is_looking_for']}")
                st.write(f"**Improved Sample Answer:** {question_obj['sample_strong_answer']}")

            st.markdown("<br><br>", unsafe_allow_html=True)
            st.info("💡 Review your feedback and try again to improve your score!")
            if st.button("🔄 Start New Interview", key="restart_main_btn", use_container_width=True):
                reset_app()

    with right:
        st.markdown("### Interview Summary")

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        answered_count = len(st.session_state.answers)
        st.write(f"**Progress:** {answered_count}/{total_questions} Answered")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("#### Score Overview")

        if st.session_state.scores:
            for i, score in enumerate(st.session_state.scores, start=1):
                st.metric(f"Question {i}", f"{score}/10")

            average_score = sum(st.session_state.scores) / len(st.session_state.scores)
            st.success(f"Average Score: {average_score:.1f}/10")
        else:
            st.info("Scores will appear after completing all questions.")

        if current_index >= total_questions and st.session_state.scores:
            final_score = sum(st.session_state.scores) / len(st.session_state.scores)
            st.markdown("---")
            st.markdown("### Final Scorecard")
            st.metric("Overall Score", f"{final_score:.1f}/10")

            if final_score >= 8:
                st.success("🌟 Strong performance. Keep your answers precise and structured.")
            elif final_score >= 5:
                st.warning("📈 Solid start. Add clearer examples and stronger role alignment.")
            else:
                st.error("💪 More practice needed. Improve your structure and examples.")

            st.markdown("### Next Steps")
            st.write(
                "- Review the feedback for each question.\n"
                "- Make answers more structured and specific.\n"
                "- Include examples, outcomes, and role alignment."
            )

            st.markdown("---")
            if st.button("🔄 Restart Interview", use_container_width=True):
                reset_app()