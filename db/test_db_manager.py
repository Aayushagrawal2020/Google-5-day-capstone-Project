import os
import pytest
import tempfile
from db.db_manager import DatabaseManager

@pytest.fixture
def temp_db():
    # Create a temporary file for the database
    db_fd, db_path = tempfile.mkstemp()
    yield db_path
    os.close(db_fd)
    os.unlink(db_path)

def test_db_operations(temp_db):
    db = DatabaseManager(temp_db)
    
    # 1. Test get_or_create_user
    user_id = db.get_or_create_user("John Doe", "Software Engineer")
    assert user_id == 1
    
    # Retrieve again, should return the same ID
    user_id_again = db.get_or_create_user("John Doe", "Software Engineer")
    assert user_id_again == 1
    
    # 2. Test create_session and get_session
    session_id = "test-session-uuid"
    db.create_session(session_id, user_id, "FULL", "JD text here", "Resume text here")
    
    session = db.get_session(session_id)
    assert session is not None
    assert session["user_name"] == "John Doe"
    assert session["domain"] == "Software Engineer"
    assert session["mode"] == "FULL"
    assert session["jd_text"] == "JD text here"
    assert session["resume_text"] == "Resume text here"

    # 3. Test save_question_history and get_session_history
    db.save_question_history(
        session_id,
        "What is your experience?",
        "I have 3 years of Python experience.",
        8,
        "Good response.",
        "None"
    )
    
    history = db.get_session_history(session_id)
    assert len(history) == 1
    assert history[0]["question"] == "What is your experience?"
    assert history[0]["score"] == 8
    
    # 4. Test weakspots updates
    db.update_user_weakspots(user_id, "STAR structure", 5)
    weakspots = db.get_user_weakspots(user_id)
    assert len(weakspots) == 1
    assert weakspots[0]["topic"] == "STAR structure"
    assert weakspots[0]["rating"] == 5
    assert weakspots[0]["times_tested"] == 1
    
    # Test updating weak spot rating
    db.update_user_weakspots(user_id, "STAR structure", 7)
    weakspots_updated = db.get_user_weakspots(user_id)
    assert len(weakspots_updated) == 1
    # Weighted average: (5 * 1 + 7) / 2 = 6
    assert weakspots_updated[0]["rating"] == 6
    assert weakspots_updated[0]["times_tested"] == 2
