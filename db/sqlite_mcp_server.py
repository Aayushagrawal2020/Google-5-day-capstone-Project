import os
import sys
from mcp.server.fastmcp import FastMCP

# Ensure the parent directory is in PYTHONPATH so db.db_manager can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.db_manager import DatabaseManager

# Initialize FastMCP server
mcp = FastMCP("MockMentor Database")

# Initialize database manager
db = DatabaseManager()

@mcp.tool()
def get_session_details(session_id: str) -> dict:
    """Retrieves session details and metadata (user_id, user_name, domain, mode, jd_text, resume_text) for a given session ID.
    
    Args:
        session_id: The UUID of the session.
    """
    session = db.get_session(session_id)
    return session or {}

@mcp.tool()
def get_user_weakspots(user_id: int) -> list:
    """Gets the weakness profile (topic, rating, times_tested) for a candidate by user_id.
    
    Args:
        user_id: The integer ID of the user.
    """
    return db.get_user_weakspots(user_id)

@mcp.tool()
def update_user_weakspot(user_id: int, topic: str, score: int) -> str:
    """Updates or inserts a weak spot topic rating for a candidate.
    
    Args:
        user_id: The integer ID of the user.
        topic: The weakness topic/skill area (e.g. 'STAR structure application').
        score: The rating/score from the latest question (1 to 10).
    """
    db.update_user_weakspots(user_id, topic, score)
    return f"Weakspot '{topic}' updated successfully for user {user_id}."

@mcp.tool()
def save_interview_question(
    session_id: str,
    question: str,
    answer: str,
    score: int,
    feedback: str,
    weaknesses: str
) -> str:
    """Saves a question-answer evaluation instance into the session history.
    
    Args:
        session_id: The UUID of the session.
        question: The interview question asked.
        answer: The candidate's response.
        score: The evaluation score (1 to 10).
        feedback: Actions and critiques feedback from the coach.
        weaknesses: Commas-separated list of identified weaknesses for this response.
    """
    db.save_question_history(session_id, question, answer, score, feedback, weaknesses)
    return "Question history saved successfully."

if __name__ == "__main__":
    mcp.run()
