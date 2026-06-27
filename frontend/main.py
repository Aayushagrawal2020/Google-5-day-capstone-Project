import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pypdf

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

# In-memory session store (used when DATABASE or AGENT is in mock mode)
MOCK_SESSIONS: Dict[str, Dict[str, Any]] = {}

# Mock questions database based on domain
MOCK_QUESTIONS = {
    "software": [
        "Can you describe a challenging technical problem you solved in a previous project? Please explain the problem, your approach, and the final impact.",
        "How do you approach designing a system for scalability and high availability? For example, when would you choose caching or microservices?",
        "Tell me about a time you had a technical disagreement with a team member. How did you present your case, and what was the resolution?",
        "How do you ensure code quality and safety in your deployment pipeline? Discuss your experience with CI/CD and automated testing.",
        "Based on the Job Description and your Resume, what do you think is your biggest technical gap for this role, and how are you working to bridge it?"
    ],
    "marketing": [
        "Tell me about a successful marketing campaign you led. What were the key performance indicators (KPIs) and the final return on investment (ROI)?",
        "How do you approach identifying and segments target audiences for a new product launch?",
        "Describe a campaign that did not meet its targets. What went wrong, what did you learn, and how did you apply that to future projects?",
        "How do you adapt your marketing strategy to search engine algorithm updates or changing social media platform policies?",
        "What key strength from your resume do you believe will have the greatest impact on our marketing team's current goals?"
    ],
    "general": [
        "Could you introduce yourself and walk me through why you are interested in this specific role?",
        "Describe a situation where you had to work with a teammate who had a very different working style. How did you ensure collaboration was successful?",
        "How do you manage your workload and prioritize tasks when you have multiple competing deadlines?",
        "Tell me about a time when you received constructive feedback that was difficult to hear. How did you react, and what actions did you take?",
        "How does this position align with your long-term career goals and professional development?"
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
    if resume_file:
        filename = resume_file.filename.lower()
        if filename.endswith(".pdf"):
            parsed_resume = extract_text_from_pdf(resume_file.file)
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

    # Determine question domain
    domain_key = "general"
    lower_domain = domain.lower()
    if "software" in lower_domain or "engineer" in lower_domain or "tech" in lower_domain or "developer" in lower_domain:
        domain_key = "software"
    elif "market" in lower_domain or "sales" in lower_domain or "growth" in lower_domain:
        domain_key = "marketing"

    # Select the first question
    questions_list = MOCK_QUESTIONS.get(domain_key, MOCK_QUESTIONS["general"])
    first_question = questions_list[0]

    # Store session state
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

    logger.info(f"Session {session_id} started for user {name} in domain {domain}")

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

    # Evaluate the user's answer
    # Simple heuristic-based evaluation for mock mode
    answer_len = len(user_answer.strip())
    
    # Calculate score (1-10) based on answer length and keyword density as a mockup
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

    # Save to history
    session["chat_history"].append({
        "question": questions_list[current_index],
        "answer": user_answer,
        "score": score,
        "feedback": feedback,
        "weakness": weakness
    })
    session["scores"].append(score)
    
    # Update weakspot frequency
    if weakness in session["weakspots"]:
        session["weakspots"][weakness]["times_tested"] += 1
        # Rating increases slightly if they did better, but stays weak for demo purposes
        session["weakspots"][weakness]["rating"] = min(10, session["weakspots"][weakness]["rating"] + 1)
    else:
        session["weakspots"][weakness] = {
            "rating": score,
            "times_tested": 1
        }

    # Advance index
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
    if session_id not in MOCK_SESSIONS:
        # Generate dummy data if session_id is "latest" or not found for dashboard demo purposes
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
                {"question": "What is your biggest technical gap?", "score": 9, "feedback": "Very honest and shows growth mindset."}
            ]
        }

    session = MOCK_SESSIONS[session_id]
    scores = session["scores"]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    # Map in-memory weakspots to output format
    weakspots_list = []
    for topic, stats in session["weakspots"].items():
        weakspots_list.append({
            "topic": topic,
            "rating": stats["rating"],
            "times_tested": stats["times_tested"]
        })

    # Competency score mapping based on session history
    technical = 7
    communication = 8
    problem_solving = 6
    star_struct = 5
    culture_fit = 8

    # Adjust competencies slightly based on actual scores
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

# Mount static files and serve index.html
# Create static directory if it doesn't exist
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Direct match for index.html at root
@app.get("/")
async def read_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "MockMentor Frontend under construction. Static files directory mounted at /static."}

# Mount other static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")
