import os
import sys
import copy
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator

# Ensure parent directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.workflow import Workflow, node, FunctionNode, JoinNode, START, Edge
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.models import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.apps import App, ResumabilityConfig
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, Field

from db.db_manager import DatabaseManager

logger = logging.getLogger("MockMentorAgent")

# Initialize database manager
db = DatabaseManager()

# Define Pydantic structures
class StartInput(BaseModel):
    session_id: str
    name: str
    domain: str
    mode: str
    jd_text: str
    resume_text: str

class ProfileAnalysis(BaseModel):
    matched_competencies: List[str] = Field(description="Key skills and competencies matched.")
    technical_gaps: List[str] = Field(description="List of technical/hard skill gaps.")
    behavioral_gaps: List[str] = Field(description="List of behavioral/soft skill gaps.")

class EvaluationResponse(BaseModel):
    score: int = Field(description="A score from 1 to 10 for the response quality.")
    feedback: str = Field(description="Actionable coaching feedback explaining what was good and how to improve.")
    weakness: str = Field(description="A single topic label describing the candidate's primary weakness in this response, or empty string if excellent.")

# Custom Fallback Model Wrapper
class FallbackGemini(Gemini):
    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        # Models to try in order of preference
        models_to_try = [self.model, "gemini-2.5-flash", "gemini-1.5-flash"]
        # Filter out duplicates
        unique_models = []
        for m in models_to_try:
            if m not in unique_models:
                unique_models.append(m)
        
        last_err = None
        for model_name in unique_models:
            try:
                req_copy = copy.copy(llm_request)
                req_copy.model = model_name
                async for response in super().generate_content_async(req_copy, stream):
                    yield response
                return
            except Exception as e:
                logger.warning(f"Model {model_name} call failed: {e}. Trying fallback...")
                last_err = e
        if last_err:
            raise last_err

# Helper to load skill instructions
def load_skill_instruction(skill_name: str) -> str:
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skill_path = os.path.join(base_path, "skills", skill_name, "SKILL.md")
    if os.path.exists(skill_path):
        with open(skill_path, "r") as f:
            # Strip YAML frontmatter if present
            content = f.read()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
            return content.strip()
    return ""

# 1. AnalyzeProfileNode (FunctionNode)
@node
def analyze_profile(ctx: Context, node_input: StartInput) -> Event:
    """Initializes user profile and reads past weaknesses from the database."""
    session_id = node_input.session_id
    name = node_input.name
    domain = node_input.domain
    mode = node_input.mode
    jd_text = node_input.jd_text
    resume_text = node_input.resume_text

    # Database updates
    user_id = db.get_or_create_user(name, domain)
    db.create_session(session_id, user_id, mode, jd_text, resume_text)
    
    # Read past weaknesses
    weakspots_list = db.get_user_weakspots(user_id)
    weakspot_topics = [w["topic"] for w in weakspots_list if w["rating"] < 7]

    # Save to session state
    state_updates = {
        "session_id": session_id,
        "user_id": user_id,
        "user_name": name,
        "domain": domain,
        "mode": mode,
        "jd_text": jd_text,
        "resume_text": resume_text,
        "current_index": 0,
        "total_questions": 10,
        "weakspots": weakspot_topics,
        "scores": [],
        "chat_history": []
    }

    # Pass data downstream
    return Event(output=node_input, state=state_updates)

# Instantiate LLM Agents
profile_matcher_agent = LlmAgent(
    name="profile_matcher",
    model=FallbackGemini(model="gemini-3.5-flash"),
    instruction=load_skill_instruction("resume_matcher") + "\nAnalyze the target JD and Resume, then return the structured profile analysis.",
    output_schema=ProfileAnalysis,
    output_key="profile_analysis"
)

generate_question_agent = LlmAgent(
    name="generate_question",
    model=FallbackGemini(model="gemini-3.5-flash"),
    instruction="""You are MockMentor, an expert AI Interview Coach.
Your goal is to generate one interview question at a time.
User Info:
- Name: {user_name}
- Target Domain: {domain}
- Interview Mode: {mode}
- Job Description: {jd_text}
- Resume: {resume_text}
- Identified Weaknesses: {weakspots}
- Current Question Index: {current_index} of {total_questions}

Guidelines:
- Generate exactly one relevant question. Do not include any other text, feedback, or markdown headers. Just return the raw question.
- If Mode is 'TECHNICAL', ask a technical/domain-specific question.
- If Mode is 'BEHAVIORAL', ask a STAR behavioral question.
- If Mode is 'FULL', alternate between technical and behavioral questions.
- Adapt the question complexity to target any identified weaknesses first.
- Make the question professional and aligned with the Job Description.""",
    output_key="current_question"
)

# 2. AskQuestionNode (FunctionNode)
# Set rerun_on_resume=False so that when the workflow resumes, the user's message is treated as the output of this node.
@node(rerun_on_resume=False)
async def ask_question(ctx: Context, node_input: str) -> AsyncGenerator[Event, None]:
    """Presents the question to the candidate and pauses for input."""
    current_index = ctx.state.get("current_index", 0)
    
    # 1. Output question to UI
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=node_input)]))
    
    # 2. Request user response
    yield RequestInput(interrupt_id=f"question_{current_index}", message=node_input)

# Helper node to capture the candidate's answer into state
@node
def save_user_answer(ctx: Context, node_input: str) -> Event:
    return Event(output=node_input, state={"current_answer": node_input})

evaluate_response_agent = LlmAgent(
    name="evaluate_response",
    model=FallbackGemini(model="gemini-3.5-flash"),
    instruction=load_skill_instruction("behavioral_evaluator") + """
You are the Interview Coach.
Evaluate the candidate's response to the question.
Question: {current_question}
Candidate's Answer: {current_answer}
Domain: {domain}
Mode: {mode}

Guidelines:
- Score the response from 1 to 10.
- Provide constructive, actionable feedback.
- If there is an area of weakness or room for improvement, identify it as a specific topic label. If none, leave it empty.
- If Mode is 'BEHAVIORAL' or if the question is behavioral, strictly use the STAR methodology instructions to grade.
""",
    output_schema=EvaluationResponse,
    output_key="current_evaluation"
)

# 3. UpdateMemoryNode (FunctionNode)
@node
def update_memory(ctx: Context, node_input: dict) -> Event:
    """Saves the answer and evaluation to database history, updates weakspots, and routes the loop."""
    session_id = ctx.state["session_id"]
    user_id = ctx.state["user_id"]
    question = ctx.state["current_question"]
    answer = ctx.state["current_answer"]
    
    score = node_input.get("score", 5)
    feedback = node_input.get("feedback", "No feedback provided.")
    weakness = node_input.get("weakness", "").strip()

    # Save to SQLite database
    db.save_question_history(session_id, question, answer, score, feedback, weakness)
    if weakness:
        db.update_user_weakspots(user_id, weakness, score)

    # Update session history in state
    chat_history = ctx.state.get("chat_history", [])
    chat_history.append({
        "question": question,
        "answer": answer,
        "score": score,
        "feedback": feedback,
        "weakness": weakness
    })
    
    scores = ctx.state.get("scores", [])
    scores.append(score)

    next_index = ctx.state.get("current_index", 0) + 1
    finished = next_index >= ctx.state.get("total_questions", 10)

    state_updates = {
        "current_index": next_index,
        "chat_history": chat_history,
        "scores": scores
    }

    if finished:
        return Event(output="complete", route="complete", state=state_updates)
    else:
        return Event(output="continue", route="continue", state=state_updates)

# Define Workflow Graph Edges
edges = [
    (START, analyze_profile),
    (analyze_profile, profile_matcher_agent),
    (profile_matcher_agent, generate_question_agent),
    
    # Interview Loop
    (generate_question_agent, ask_question),
    (ask_question, save_user_answer),
    (save_user_answer, evaluate_response_agent),
    (evaluate_response_agent, update_memory),
    
    # Conditional route to repeat the loop
    Edge(from_node=update_memory, to_node=generate_question_agent, route="continue")
]

# Build root agent
root_agent = Workflow(
    name="coach_agent",
    edges=edges,
    input_schema=StartInput,
    rerun_on_resume=True
)

# App wrapping with human-in-the-loop support enabled
app = App(
    name="coach_app",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True)
)
