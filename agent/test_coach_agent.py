import pytest
from agent.coach_agent import root_agent, app

def test_workflow_structure():
    assert root_agent.name == "coach_agent"
    assert app.name == "coach_app"
    assert app.resumability_config.is_resumable is True
