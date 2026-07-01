import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pypdf
import io

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockMentorAPI")

app = FastAPI(
    title="MockMentor API",
    description="Backend API for MockMentor - Agentic AI Interview Coach",
    version="0.1.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Check if we should run in mock mode
GEMINI_API_KEY_EXISTS = bool(os.getenv("GEMINI_API_KEY"))
MOCK_MODE = os.getenv("MOCK_MODE", "True").lower() in ("true", "1", "yes")

if not GEMINI_API_KEY_EXISTS:
    logger.warning("GEMINI_API_KEY not found in environment. Defaulting to Mock Mode.")
    MOCK_MODE = True
else:
    logger.info("GEMINI_API_KEY detected. Agent operations will use the ADK 2.0 Workflow.")

# Import ADK runners and agent if in active mode
runner = None
if not MOCK_MODE:
    try:
        from google.adk.runners import InMemoryRunner
        from google.genai import types
        from agent.coach_agent import app as agent_app, StartInput, db
        runner = InMemoryRunner(app=agent_app)
        logger.info("ADK Runner successfully initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize ADK Runner: {e}. Falling back to Mock Mode.")
        MOCK_MODE = True

async def get_session_by_id(session_id: str):
    if runner is not None:
        resp = await runner.session_service.list_sessions(app_name="coach_app")
        for s in resp.sessions:
            if s.id == session_id:
                return s
    return None


# Import database manager for analytics logging (in non-mock mode)
db_manager = None
if not MOCK_MODE:
    from db.db_manager import DatabaseManager
    db_manager = DatabaseManager()
else:
    # Minimal db import for demo fallback if needed
    try:
        from db.db_manager import DatabaseManager
        db_manager = DatabaseManager()
    except Exception:
        db_manager = None

# In-memory session store (used when DATABASE or AGENT is in mock mode)
MOCK_SESSIONS: Dict[str, Dict[str, Any]] = {}

# Mock questions database based on domain
MOCK_QUESTIONS = {
    "software": [
        "Can you describe a challenging technical problem you solved in a previous project? Please explain the problem, your approach, and the final impact.",
        "How do you approach designing a system for scalability and high availability? For example, when would you choose caching or microservices?",
        "Tell me about a time you had a technical disagreement with a team member. How did you present your case, and what was the resolution?",
        "How do you ensure code quality and safety in your deployment pipeline? Discuss your experience with CI/CD and automated testing.",
        "Based on the Job Description and your Resume, what do you think is your biggest technical gap for this role, and how are you working to bridge it?",
        "How do you handle managing database transactions and ensuring data consistency in a distributed system?",
        "Describe a scenario where you had to optimize a slow SQL query or backend service. What tools did you use and what was the outcome?",
        "What is your approach to handling security vulnerabilities, such as SQL injection or cross-site scripting, in your code?",
        "Tell me about a time you had to learn a new framework or programming language quickly for a project. How did you manage it?",
        "How do you balance technical debt against the need to deliver new features quickly?"
    ],
    "marketing": [
        "Tell me about a successful marketing campaign you led. What were the key performance indicators (KPIs) and the final return on investment (ROI)?",
        "How do you approach identifying and segments target audiences for a new product launch?",
        "Describe a campaign that did not meet its targets. What went wrong, what did you learn, and how did you apply that to future projects?",
        "How do you adapt your marketing strategy to search engine algorithm updates or changing social media platform policies?",
        "What key strength from your resume do you believe will have the greatest impact on our marketing team's current goals?",
        "How do you utilize A/B testing to optimize landing pages and email campaign conversion rates?",
        "Can you share an experience where you had to collaborate with a product/engineering team to implement marketing analytics or tracking?",
        "What tools and metrics do you rely on to measure customer acquisition cost (CAC) and customer lifetime value (LTV)?",
        "Describe a time when you had to manage a tight marketing budget. How did you allocate resources to maximize ROI?",
        "How do you maintain brand consistency across different channels, such as social media, email, and content marketing?"
    ],
    "general": [
        "Could you introduce yourself and walk me through why you are interested in this specific role?",
        "Describe a situation where you had to work with a teammate who had a very different working style. How did you ensure collaboration was successful?",
        "How do you manage your workload and prioritize tasks when you have multiple competing deadlines?",
        "Tell me about a time when you received constructive feedback that was difficult to hear. How did you react, and what actions did you take?",
        "How does this position align with your long-term career goals and professional development?",
        "Describe a time when you took the initiative to solve a problem that wasn't explicitly your responsibility.",
        "How do you handle stress and stay motivated during high-pressure periods or tight deadlines?",
        "Tell me about a project you worked on where the requirements changed midway. How did you adapt?",
        "What is your process for making an important decision when you don't have all the information you need?",
        "Can you share an example of a goal you set for yourself and how you went about achieving it?"
    ]
}

def extract_text_from_pdf(file_stream) -> str:
    """Helper to extract text from a PDF binary stream."""
    try:
        reader = pypdf.PdfReader(file_stream)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to parse PDF: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to parse the PDF file. Please ensure it is not corrupted."
        )

@app.post("/api/session/start")
async def start_session(
    name: str = Form(...),
    domain: str = Form(...),
    mode: str = Form(...),  # 'FULL', 'BEHAVIORAL', 'TECHNICAL'
    jd_text: str = Form(...),
    resume_file: Optional[UploadFile] = File(None),
    resume_text: Optional[str] = Form(None)
):
    session_id = str(uuid.uuid4())
    parsed_resume = ""

    # Handle resume upload
    if resume_file and resume_file.filename:
        filename = resume_file.filename.lower()
        if filename.endswith(".pdf"):
            file_bytes = await resume_file.read()
            parsed_resume = extract_text_from_pdf(io.BytesIO(file_bytes))
        elif filename.endswith(".txt"):
            content = await resume_file.read()
            parsed_resume = content.decode("utf-8", errors="ignore")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Please upload a PDF or TXT file."
            )
    elif resume_text:
        parsed_resume = resume_text.strip()
    else:
        parsed_resume = "No resume provided."

    # If running in real ADK mode
    if not MOCK_MODE and runner is not None:
        try:
            from agent.coach_agent import StartInput
            from google.genai import types

            # Create ADK Session
            await runner.session_service.create_session(
                app_name="coach_app",
                user_id=name,
                session_id=session_id
            )

            start_input = StartInput(
                session_id=session_id,
                name=name,
                domain=domain,
                mode=mode,
                jd_text=jd_text,
                resume_text=parsed_resume
            )

            # Trigger ADK first question generation
            first_question = None
            async for event in runner.run_async(
                user_id=name,
                session_id=session_id,
                new_message=start_input
            ):
                if event.content and event.content.parts:
                    first_question = event.content.parts[0].text

            if not first_question:
                session_obj = await runner.session_service.get_session(
                    app_name="coach_app",
                    user_id=name,
                    session_id=session_id
                )
                first_question = session_obj.state.get("current_question", "Could you introduce yourself?") if session_obj else "Could you introduce yourself?"

            return {
                "session_id": session_id,
                "user_name": name,
                "first_question": first_question,
                "total_questions": 10
            }
        except Exception as e:
            logger.error(f"ADK session start failed: {e}. Falling back to mock session.")

    # Determine question domain (Mock Mode fallback)
    domain_key = "general"
    lower_domain = domain.lower()
    if "software" in lower_domain or "engineer" in lower_domain or "tech" in lower_domain or "developer" in lower_domain:
        domain_key = "software"
    elif "market" in lower_domain or "sales" in lower_domain or "growth" in lower_domain:
        domain_key = "marketing"

    questions_list = MOCK_QUESTIONS.get(domain_key, MOCK_QUESTIONS["general"])
    first_question = questions_list[0]

    MOCK_SESSIONS[session_id] = {
        "user_name": name,
        "domain": domain,
        "mode": mode,
        "jd_text": jd_text,
        "resume_text": parsed_resume,
        "domain_key": domain_key,
        "current_index": 0,
        "questions_list": questions_list,
        "chat_history": [],
        "scores": [],
        "weakspots": {},
        "skills_loaded": ["resume_matcher"]
    }

    logger.info(f"Mock Session {session_id} started for user {name} in domain {domain}")

    return {
        "session_id": session_id,
        "user_name": name,
        "first_question": first_question,
        "total_questions": len(questions_list)
    }

@app.post("/api/session/chat")
async def chat_step(
    session_id: str = Form(...),
    user_answer: str = Form(...)
):
    # Check if session exists in real ADK mode
    if not MOCK_MODE and runner is not None:
        try:
            from google.genai import types

            session_obj = await get_session_by_id(session_id)
            if session_obj:
                state = session_obj.state
                user_name = state.get("user_name", "User")
                
                # Resume runner with the user answer
                async for event in runner.run_async(
                    user_id=user_name,
                    session_id=session_id,
                    new_message=user_answer
                ):
                    pass

                # Retrieve evaluation details from updated state
                updated_session = await runner.session_service.get_session(
                    app_name="coach_app",
                    user_id=user_name,
                    session_id=session_id
                )
                updated_state = updated_session.state if updated_session else {}
                chat_history = updated_state.get("chat_history", [])
                
                feedback = "Good response."
                score = 7
                if chat_history:
                    last_eval = chat_history[-1]
                    score = last_eval.get("score", 7)
                    feedback = last_eval.get("feedback", "")

                next_index = updated_state.get("current_index", 0)
                total_q = updated_state.get("total_questions", 10)
                finished = next_index >= total_q

                next_question = None
                if not finished:
                    next_question = updated_state.get("current_question")

                # Query user weakspots from database
                user_id = updated_state.get("user_id", 0)
                weakspots_list = db_manager.get_user_weakspots(user_id) if db_manager else []
                weakspots = [w["topic"] for w in weakspots_list]

                return {
                    "question": next_question,
                    "feedback": feedback,
                    "score": score,
                    "finished": finished,
                    "weakspots": weakspots
                }
        except Exception as e:
            logger.error(f"ADK chat step failed: {e}. Falling back to mock session.")

    # Mock Mode evaluation fallback
    if session_id not in MOCK_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found."
        )

    session = MOCK_SESSIONS[session_id]
    current_index = session["current_index"]
    questions_list = session["questions_list"]

    if current_index >= len(questions_list):
        return {
            "question": None,
            "feedback": "Interview already completed.",
            "score": None,
            "finished": True,
            "weakspots": list(session["weakspots"].keys())
        }

    answer_len = len(user_answer.strip())
    if answer_len < 30:
        score = 3
        feedback = "Your answer was very brief. Try using the STAR method (Situation, Task, Action, Result) to provide context and details."
        weakness = "STAR structure application"
    elif answer_len < 100:
        score = 6
        feedback = "Good start, but you could provide more specific metrics and explain the exact actions you took."
        weakness = "Detailing actions and metrics"
    else:
        score = 8
        feedback = "Strong response! You provided a detailed explanation. To improve further, ensure you highlight the direct business impact of your work."
        weakness = "Impact quantification"

    session["chat_history"].append({
        "question": questions_list[current_index],
        "answer": user_answer,
        "score": score,
        "feedback": feedback,
        "weakness": weakness
    })
    session["scores"].append(score)
    
    if weakness in session["weakspots"]:
        session["weakspots"][weakness]["times_tested"] += 1
        session["weakspots"][weakness]["rating"] = min(10, session["weakspots"][weakness]["rating"] + 1)
    else:
        session["weakspots"][weakness] = {
            "rating": score,
            "times_tested": 1
        }

    session["current_index"] += 1
    next_index = session["current_index"]
    
    finished = next_index >= len(questions_list)
    next_question = None if finished else questions_list[next_index]

    return {
        "question": next_question,
        "feedback": feedback,
        "score": score,
        "finished": finished,
        "weakspots": list(session["weakspots"].keys())
    }

@app.get("/api/session/analytics")
async def get_analytics(session_id: str):
    # Check if session exists in DB (for real ADK sessions)
    if db_manager:
        session = db_manager.get_session(session_id)
        if session:
            history = db_manager.get_session_history(session_id)
            weakspots = db_manager.get_user_weakspots(session["user_id"])

            scores = [h["score"] for h in history if h["score"] is not None]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            # Adjust competencies slightly based on actual scores
            technical = 7
            communication = 8
            problem_solving = 6
            star_struct = 5
            culture_fit = 8

            if scores:
                overall_avg = sum(scores) / len(scores)
                technical = min(10, int(overall_avg + 1))
                communication = min(10, int(overall_avg))
                problem_solving = min(10, int(overall_avg - 1))

            return {
                "user_name": session["user_name"],
                "domain": session["domain"],
                "average_score": round(avg_score, 1),
                "competency_scores": {
                    "Technical Knowledge": technical,
                    "Communication": communication,
                    "Problem Solving": problem_solving,
                    "STAR Structuring": star_struct,
                    "Culture Fit": culture_fit
                },
                "weakspots": [
                    {"topic": w["topic"], "rating": w["rating"], "times_tested": w["times_tested"]}
                    for w in weakspots
                ],
                "history": [
                    {"question": h["question"], "score": h["score"], "feedback": h["feedback"]}
                    for h in history
                ]
            }

    # Mock Mode fallback
    if session_id not in MOCK_SESSIONS:
        # Generate dummy data for dashboard demo
        return {
            "user_name": "Demo Candidate",
            "domain": "Software Engineering",
            "average_score": 7.2,
            "competency_scores": {
                "Technical Knowledge": 8,
                "Communication": 7,
                "Problem Solving": 6,
                "STAR Structuring": 5,
                "Culture Fit": 9
            },
            "weakspots": [
                {"topic": "STAR Structuring", "rating": 5, "times_tested": 3},
                {"topic": "System Design: Caching", "rating": 4, "times_tested": 2},
                {"topic": "Quantifying Impact", "rating": 6, "times_tested": 2}
            ],
            "history": [
                {"question": "Can you describe a challenging technical problem you solved?", "score": 6, "feedback": "Provide more details on implementation."},
                {"question": "How do you approach designing a system for scalability?", "score": 5, "feedback": "Missed talking about database read replicas."},
                {"question": "Tell me about a time you had a technical disagreement.", "score": 8, "feedback": "Excellent conflict resolution explanation."},
                {"question": "How do you ensure code quality in your pipeline?", "score": 7, "feedback": "Good description of testing."},
                {"question": "What is your biggest technical gap?", "score": 9, "feedback": "Very honest and shows growth mindset."},
                {"question": "How do you manage database transactions in distributed environments?", "score": 7, "feedback": "Good knowledge of ACID properties, but review saga patterns."},
                {"question": "Describe a scenario where you optimized a slow query.", "score": 8, "feedback": "Excellent use of indexes and execution plans."},
                {"question": "What is your approach to code security?", "score": 6, "feedback": "Explain more about static analysis tools."},
                {"question": "Tell me about learning a new tool quickly.", "score": 9, "feedback": "Outstanding speed and adaptability demonstrated."},
                {"question": "How do you balance technical debt?", "score": 8, "feedback": "Pragmatic trade-off analysis."}
            ]
        }

    session = MOCK_SESSIONS[session_id]
    scores = session["scores"]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    weakspots_list = []
    for topic, stats in session["weakspots"].items():
        weakspots_list.append({
            "topic": topic,
            "rating": stats["rating"],
            "times_tested": stats["times_tested"]
        })

    technical = 7
    communication = 8
    problem_solving = 6
    star_struct = 5
    culture_fit = 8

    if scores:
        overall_avg = sum(scores) / len(scores)
        technical = min(10, int(overall_avg + 1))
        communication = min(10, int(overall_avg))
        problem_solving = min(10, int(overall_avg - 1))

    return {
        "user_name": session["user_name"],
        "domain": session["domain"],
        "average_score": round(avg_score, 1),
        "competency_scores": {
            "Technical Knowledge": technical,
            "Communication": communication,
            "Problem Solving": problem_solving,
            "STAR Structuring": star_struct,
            "Culture Fit": culture_fit
        },
        "weakspots": weakspots_list,
        "history": [
            {
                "question": h["question"],
                "score": h["score"],
                "feedback": h["feedback"]
            } for h in session["chat_history"]
        ]
    }

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

@app.get("/")
async def read_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "MockMentor Frontend under construction. Static files directory mounted at /static."}

app.mount("/static", StaticFiles(directory=static_dir), name="static")
