"""
Regression tests for agent.py (Task 1).

These tests verify that agent.py:
- Runs successfully with a question
- Outputs valid JSON
- Contains required 'answer' and 'tool_calls' fields
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_returns_valid_json():
    """Test that agent.py returns valid JSON with required fields."""
    # Path to agent.py in project root
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"
    
    # Test question
    question = "What is 2 + 2?"
    
    # Run agent.py as subprocess using uv from PATH
    result = subprocess.run(
        ["uv", "run", str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(project_root),
    )
    
    # Print stderr for debugging
    if result.stderr:
        print(f"stderr: {result.stderr}", file=sys.stderr)
    
    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"
    
    # Parse stdout as JSON
    # Filter out any non-JSON lines from stdout
    stdout_lines = result.stdout.strip().split('\n')
    json_line = None
    
    for line in stdout_lines:
        try:
            json.loads(line)
            json_line = line
            break
        except json.JSONDecodeError:
            continue
    
    assert json_line is not None, f"No valid JSON found in stdout: {result.stdout}"
    
    response = json.loads(json_line)
    
    # Verify 'answer' field exists and is non-empty
    assert "answer" in response, "Missing 'answer' field in response"
    assert isinstance(response["answer"], str), "'answer' must be a string"
    assert len(response["answer"].strip()) > 0, "'answer' cannot be empty"
    
    # Verify 'tool_calls' field exists and is an array
    assert "tool_calls" in response, "Missing 'tool_calls' field in response"
    assert isinstance(response["tool_calls"], list), "'tool_calls' must be an array"
    
    print(f"✓ Test passed: answer='{response['answer'][:50]}...'")


if __name__ == "__main__":
    test_agent_returns_valid_json()
    print("All tests passed!")
