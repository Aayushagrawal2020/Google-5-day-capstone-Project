import pytest
from fastapi.testclient import TestClient
from frontend.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    # Should redirect or serve static file response (in this test, static dir is mounted but empty or has files, returns 200)
    assert response.status_code == 200

def test_session_start_and_flow():
    # 1. Test Session Start
    start_data = {
        "name": "Jane Doe",
        "domain": "Software Developer",
        "mode": "FULL",
        "jd_text": "Looking for a Software Engineer proficient in Python.",
        "resume_text": "Jane Doe - Python engineer with 3 years of experience."
    }
    
    response = client.post("/api/session/start", data=start_data)
    assert response.status_code == 200
    res_json = response.json()
    assert "session_id" in res_json
    assert res_json["user_name"] == "Jane Doe"
    assert "first_question" in res_json
    
    session_id = res_json["session_id"]
    
    # 2. Test Session Chat Step
    chat_data = {
        "session_id": session_id,
        "user_answer": "I have used Python for web development and automated testing for three years."
    }
    response = client.post("/api/session/chat", data=chat_data)
    assert response.status_code == 200
    chat_json = response.json()
    assert "score" in chat_json
    assert "feedback" in chat_json
    assert "finished" in chat_json
    
    # 3. Test Session Analytics
    response = client.get(f"/api/session/analytics?session_id={session_id}")
    assert response.status_code == 200
    analytics_json = response.json()
    assert analytics_json["user_name"] == "Jane Doe"
    assert "average_score" in analytics_json
    assert "competency_scores" in analytics_json

def test_analytics_demo_mode():
    response = client.get("/api/session/analytics?session_id=latest")
    assert response.status_code == 200
    analytics_json = response.json()
    assert analytics_json["user_name"] == "Demo Candidate"
    assert "competency_scores" in analytics_json
