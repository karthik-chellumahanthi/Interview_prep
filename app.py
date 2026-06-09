import streamlit as st
import json
import random
import os
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

def evaluate_answer(answer, question):
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

    return score, feedback_level, matched_keywords

def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

MIC_HTML = """
<div style="padding:14px; border-radius:16px; background: rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.16); color:#eef4ff;">
  <div style="font-size:16px; font-weight:700; margin-bottom:10px;">Mic Answer Input</div>
  <div style="display:flex; gap:10px; align-items:center; margin-bottom:10px;">
    <button id="startBtn" style="padding:10px 16px; border:none; border-radius:10px; background:#4c8fff; color:#fff; cursor:pointer;">🎙 Start</button>
    <button id="stopBtn" style="padding:10px 16px; border:none; border-radius:10px; background:#a3d8ff; color:#001a38; cursor:pointer;" disabled>Stop</button>
  </div>
  <div id="status" style="font-size:14px; color:#d7e4ff;">Click Start and speak your answer clearly. The voice text will appear in the answer box.</div>
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
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    const parentTextarea = window.parent.document.querySelector('textarea[aria-label="Answer via Mic or typing"]');
    if (parentTextarea) {
      parentTextarea.value = transcript;
      const inputEvent = new Event('input', { bubbles: true });
      parentTextarea.dispatchEvent(inputEvent);
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

st.markdown("""
<style>
/* Hide the Streamlit header, menu, and deploy button */
[data-testid="stHeader"] { visibility: hidden; }
#MainMenu { visibility: hidden; }
header { visibility: hidden; }

html, body, [class*="css"]  {
    background: linear-gradient(180deg, #07162f 0%, #102549 45%, #192f58 100%);
    color: #eef4ff;
}
.stApp {
    background: transparent;
}
.main-title {
    text-align: center;
    font-size: 44px;
    font-weight: 800;
    color: #ffffff;
}
.sub-title {
    text-align: center;
    font-size: 18px;
    color: #cfd8ee;
}
.card, .question-card {
    padding: 24px;
    border-radius: 22px;
    background: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.16);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.18);
    margin-bottom: 18px;
}
.card {
    background: rgba(255, 255, 255, 0.09);
}
.question-card {
    background: linear-gradient(180deg, rgba(11, 41, 96, 0.92), rgba(20, 69, 143, 0.88));
    border-left: 6px solid #6db5ff;
}
.hero-card {
    padding: 32px;
    border-radius: 28px;
    background: linear-gradient(135deg, rgba(56, 120, 255, 0.95), rgba(77, 216, 255, 0.85));
    border: 1px solid rgba(255, 255, 255, 0.22);
    box-shadow: 0 28px 70px rgba(0, 44, 113, 0.28);
    margin-bottom: 24px;
    color: #ffffff;
}
.hero-title {
    font-size: 52px;
    font-weight: 900;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}
.hero-subtitle {
    font-size: 20px;
    color: rgba(255, 255, 255, 0.95);
}
.css-1emrehy.edgvbvh3 {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
}
button, .stButton>button {
    background: linear-gradient(90deg, #4c8fff, #69c4ff) !important;
    color: #001a38 !important;
    border: none !important;
    border-radius: 14px !important;
    box-shadow: 0 12px 28px rgba(0, 76, 158, 0.28) !important;
}
button:hover, .stButton>button:hover {
    transform: translateY(-1px);
}
textarea, input, .stTextInput>div>input, .stTextArea>div>textarea {
    background: rgba(255, 255, 255, 0.12) !important;
    color: #000000 !important;
    border: 2px solid rgba(76, 143, 255, 0.5) !important;
    font-size: 16px !important;
}
textarea::placeholder, input::placeholder {
    color: rgba(0, 0, 0, 0.5) !important;
}
label, .css-1pahdxg-control {
    color: #e0e7ff !important;
}
a, a:visited {
    color: #92c9ff;
}
</style>
<script>
document.addEventListener('keydown', function(event) {
    // Disable Streamlit's Ctrl+C (or Cmd+C on Mac) cache clear shortcut
    if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
        // Allow normal copy functionality, just prevent Streamlit's handler
        return true;
    }
});
</script>
""", unsafe_allow_html=True)

st.markdown("<div class='hero-card'><div class='hero-title'>🎤 PrepMate AI Interview Coach</div><div class='hero-subtitle'>Practice professional mock interviews with structured feedback, smart scoring, and role-targeted guidance.</div></div>", unsafe_allow_html=True)

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

            # If no questions found, try to generate with Gemini
            if len(filtered_questions) == 0:
                # Create cache key
                cache_key = f"{interview_type}_{domain}_{difficulty}"
                
                # Check if we already generated these questions
                if cache_key in st.session_state.generated_questions_cache:
                    filtered_questions = st.session_state.generated_questions_cache[cache_key]
                    st.info("✅ Using previously generated questions...")
                # Check if generation was already attempted and failed
                elif cache_key in st.session_state.generation_attempted:
                    st.error(f"❌ Could not generate questions. Reason: {st.session_state.generation_attempted[cache_key]}")
                    st.info("💡 Please try selecting a different domain or difficulty, or wait for your API quota to reset.")
                else:
                    # Only attempt generation once
                    st.info("📚 Generating custom questions using AI...")
                    try:
                        filtered_questions = generate_questions_with_gemini(
                            interview_type,
                            domain,
                            difficulty,
                            count=5
                        )
                        
                        # Cache the generated questions
                        if filtered_questions:
                            st.session_state.generated_questions_cache[cache_key] = filtered_questions
                            st.success("✅ Custom questions generated successfully!")
                        else:
                            st.session_state.generation_attempted[cache_key] = "No questions were generated"
                            st.error("❌ No questions could be generated.")
                            st.stop()
                    except Exception as e:
                        st.session_state.generation_attempted[cache_key] = str(e)
                        st.error(f"❌ Could not generate questions. Error: {str(e)}")
                        st.info("💡 Please try selecting a different domain or difficulty.")
                        st.stop()
                
                if len(filtered_questions) == 0 and cache_key not in st.session_state.generated_questions_cache:
                    st.error("❌ No questions found for this selection. Please choose another domain or difficulty.")
                    st.stop()

            selected_questions = random.sample(
                filtered_questions,
                min(5, len(filtered_questions))
            )

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
        st.write("Answer all 5 questions clearly. You'll receive feedback after completing all questions.")

        progress = (current_index) / total_questions
        st.progress(progress)
        st.caption(f"Question {min(current_index + 1, total_questions)} of {total_questions}")

        if current_index < total_questions:
            current_question = st.session_state.selected_questions[current_index]
            st.markdown(f"### {current_question['question_text']}")

            html(MIC_HTML, height=180)
            user_answer = st.text_area("Answer via Mic or typing", key=f"answer_{current_index}", height=180)

            if st.button("Next Question", use_container_width=True):
                if not user_answer.strip():
                    st.error("Please provide an answer before moving to the next question.")
                else:
                    st.session_state.answers.append({
                        "question": current_question["question_text"],
                        "answer": user_answer,
                        "question_obj": current_question
                    })
                    st.session_state.current_index += 1
                    st.rerun()

        else:
            # All questions answered - show evaluation
            st.success("✅ All Questions Completed! Processing your feedback...")
            st.write("\n**Your Answers with Detailed Feedback:**\n")
            
            st.session_state.scores = []
            for i, answer_data in enumerate(st.session_state.answers, start=1):
                question_obj = answer_data["question_obj"]
                user_answer = answer_data["answer"]
                
                score, level, matched_keywords = evaluate_answer(user_answer, question_obj)
                st.session_state.scores.append(score)
                
                st.markdown(f"---")
                st.markdown(f"### Question {i}: {answer_data['question']}")
                st.markdown(f"**Your Answer:** {user_answer}")
                
                st.success(f"✓ Score: {score}/10 - {level}")
                st.write(f"**Matched Keywords:** {', '.join(matched_keywords) if matched_keywords else 'No major keywords matched'}")
                st.write(f"**What was missing:** {question_obj['what_interviewer_is_looking_for']}")
                st.write(f"**Improved Sample Answer:** {question_obj['sample_strong_answer']}")
                st.write(f"**Common Mistakes to Avoid:** {question_obj['common_mistakes_to_avoid']}")

    with right:
        st.markdown("### Interview Summary")

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.write(f"**Progress:** {min(current_index, total_questions)}/{total_questions} Answered")
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