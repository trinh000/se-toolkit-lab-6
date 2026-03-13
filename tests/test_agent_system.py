import json
import subprocess
import pytest

def run_agent(question):
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        check=True
    )
    return json.loads(result.stdout)

def test_agent_backend_framework():
    """
    Test that the agent can identify the backend framework (FastAPI).
    It should likely read pyproject.toml or a similar file.
    """
    question = "What Python web framework does the backend use?"
    output = run_agent(question)
    
    # Check for expected fields
    assert "answer" in output
    assert "tool_calls" in output
    
    # Check tool calls: read_file should be used
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "read_file" in tool_names
    
    # Check answer
    assert "FastAPI" in output["answer"]

def test_agent_database_count():
    """
    Test that the agent can count items in the database.
    It should use the query_api tool.
    """
    question = "How many items are in the database?"
    output = run_agent(question)
    
    # Check for expected fields
    assert "answer" in output
    assert "tool_calls" in output
    
    # Check tool calls: query_api should be used
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "query_api" in tool_names
    
    # Verify query_api arguments
    query_call = next(tc for tc in output["tool_calls"] if tc["tool"] == "query_api")
    assert "/items/" in query_call["args"]["path"]
    assert query_call["args"]["method"].upper() == "GET"
    
    # Check that a number is in the answer
    assert any(char.isdigit() for char in output["answer"])
