"""
Regression tests for agent.py (Task 1 & Task 2).

These tests verify that agent.py:
- Runs successfully with a question
- Outputs valid JSON
- Contains required fields (answer, source, tool_calls)
- Uses tools correctly (Task 2)
"""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str, project_root: Path) -> dict:
    """Helper to run agent.py and parse JSON response."""
    agent_path = project_root / "agent.py"
    
    result = subprocess.run(
        ["uv", "run", str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(project_root),
    )
    
    # Print stderr for debugging
    if result.stderr:
        print(f"stderr: {result.stderr}", file=sys.stderr)
    
    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"
    
    # Parse stdout as JSON
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
    
    return json.loads(json_line)


def test_agent_returns_valid_json():
    """Test that agent.py returns valid JSON with required fields (Task 1)."""
    project_root = Path(__file__).parent.parent
    
    # Test question
    question = "What is 2 + 2?"
    
    response = run_agent(question, project_root)
    
    # Verify 'answer' field exists and is non-empty
    assert "answer" in response, "Missing 'answer' field in response"
    assert isinstance(response["answer"], str), "'answer' must be a string"
    assert len(response["answer"].strip()) > 0, "'answer' cannot be empty"
    
    # Verify 'source' field exists (Task 2)
    assert "source" in response, "Missing 'source' field in response"
    assert isinstance(response["source"], str), "'source' must be a string"
    
    # Verify 'tool_calls' field exists and is an array
    assert "tool_calls" in response, "Missing 'tool_calls' field in response"
    assert isinstance(response["tool_calls"], list), "'tool_calls' must be an array"
    
    print(f"✓ Test passed: answer='{response['answer'][:50]}...'")


def test_merge_conflict_question():
    """Test that agent uses read_file to answer merge conflict question (Task 2)."""
    project_root = Path(__file__).parent.parent
    
    # Test question about merge conflicts
    question = "How do you resolve a merge conflict?"
    
    response = run_agent(question, project_root)
    
    # Verify answer exists
    assert "answer" in response, "Missing 'answer' field"
    assert len(response["answer"].strip()) > 0, "'answer' cannot be empty"
    
    # Verify source exists and contains wiki reference
    assert "source" in response, "Missing 'source' field"
    assert "wiki/" in response["source"] or response["source"] == "general", \
        f"Source should reference wiki file, got: {response['source']}"
    
    # Verify tool_calls is not empty
    assert "tool_calls" in response, "Missing 'tool_calls' field"
    assert isinstance(response["tool_calls"], list), "'tool_calls' must be an array"
    assert len(response["tool_calls"]) > 0, "Expected tool calls for wiki question"
    
    # Verify read_file was used
    tool_names = [tc.get("tool") for tc in response["tool_calls"]]
    assert "read_file" in tool_names, f"Expected read_file in tool_calls, got: {tool_names}"
    
    # Verify source contains wiki file path
    if response["source"] != "general":
        assert "wiki/" in response["source"] and ".md" in response["source"], \
            f"Source should be wiki file reference, got: {response['source']}"
    
    print(f"✓ Test passed: answer='{response['answer'][:50]}...', source='{response['source']}'")


def test_wiki_files_question():
    """Test that agent uses list_files to answer wiki files question (Task 2)."""
    project_root = Path(__file__).parent.parent
    
    # Test question about wiki files
    question = "What files are in the wiki?"
    
    response = run_agent(question, project_root)
    
    # Verify answer exists
    assert "answer" in response, "Missing 'answer' field"
    assert len(response["answer"].strip()) > 0, "'answer' cannot be empty"
    
    # Verify source exists
    assert "source" in response, "Missing 'source' field"
    
    # Verify tool_calls is not empty
    assert "tool_calls" in response, "Missing 'tool_calls' field"
    assert isinstance(response["tool_calls"], list), "'tool_calls' must be an array"
    assert len(response["tool_calls"]) > 0, "Expected tool calls for wiki question"
    
    # Verify list_files was used
    tool_names = [tc.get("tool") for tc in response["tool_calls"]]
    assert "list_files" in tool_names, f"Expected list_files in tool_calls, got: {tool_names}"
    
    # Verify tool call has correct structure
    list_files_call = next((tc for tc in response["tool_calls"] if tc.get("tool") == "list_files"), None)
    assert list_files_call is not None, "list_files call not found"
    assert "args" in list_files_call, "list_files missing 'args' field"
    assert "result" in list_files_call, "list_files missing 'result' field"
    assert list_files_call["args"].get("path") == "wiki", \
        f"list_files should have path='wiki', got: {list_files_call['args']}"
    
    print(f"✓ Test passed: answer='{response['answer'][:50]}...', tool_calls={len(response['tool_calls'])}")


def test_framework_question():
    """Test that agent uses read_file to answer framework question (Task 3)."""
    project_root = Path(__file__).parent.parent
    
    # Test question about backend framework
    question = "What Python web framework does this project's backend use?"
    
    response = run_agent(question, project_root)
    
    # Verify answer exists
    assert "answer" in response, "Missing 'answer' field"
    assert len(response["answer"].strip()) > 0, "'answer' cannot be empty"
    
    # Verify answer contains FastAPI
    answer_lower = response["answer"].lower()
    assert "fastapi" in answer_lower, f"Expected 'FastAPI' in answer, got: {response['answer'][:100]}"
    
    # Verify tool_calls is not empty
    assert "tool_calls" in response, "Missing 'tool_calls' field"
    assert isinstance(response["tool_calls"], list), "'tool_calls' must be an array"
    assert len(response["tool_calls"]) > 0, "Expected tool calls for framework question"
    
    # Verify read_file was used
    tool_names = [tc.get("tool") for tc in response["tool_calls"]]
    assert "read_file" in tool_names, f"Expected read_file in tool_calls, got: {tool_names}"
    
    print(f"✓ Test passed: answer='{response['answer'][:50]}...', source='{response.get('source', 'N/A')}'")


def test_item_count_question():
    """Test that agent uses query_api to answer item count question (Task 3)."""
    project_root = Path(__file__).parent.parent
    
    # Test question about item count
    question = "How many items are currently stored in the database?"
    
    response = run_agent(question, project_root)
    
    # Verify answer exists
    assert "answer" in response, "Missing 'answer' field"
    assert len(response["answer"].strip()) > 0, "'answer' cannot be empty"
    
    # Verify answer contains a number
    import re
    numbers = re.findall(r'\d+', response["answer"])
    assert len(numbers) > 0, f"Expected a number in answer, got: {response['answer']}"
    
    # Verify tool_calls is not empty
    assert "tool_calls" in response, "Missing 'tool_calls' field"
    assert isinstance(response["tool_calls"], list), "'tool_calls' must be an array"
    assert len(response["tool_calls"]) > 0, "Expected tool calls for item count question"
    
    # Verify query_api was used
    tool_names = [tc.get("tool") for tc in response["tool_calls"]]
    assert "query_api" in tool_names, f"Expected query_api in tool_calls, got: {tool_names}"
    
    # Verify query_api call has correct structure
    query_api_call = next((tc for tc in response["tool_calls"] if tc.get("tool") == "query_api"), None)
    assert query_api_call is not None, "query_api call not found"
    assert "args" in query_api_call, "query_api missing 'args' field"
    assert "result" in query_api_call, "query_api missing 'result' field"
    assert query_api_call["args"].get("method") == "GET", \
        f"query_api should have method='GET', got: {query_api_call['args']}"
    assert "/items/" in query_api_call["args"].get("path", ""), \
        f"query_api should have path='/items/', got: {query_api_call['args']}"
    
    print(f"✓ Test passed: answer='{response['answer'][:50]}...', tool_calls={len(response['tool_calls'])}")


if __name__ == "__main__":
    print("Running Task 1 test...")
    test_agent_returns_valid_json()
    
    print("\nRunning Task 2 tests...")
    test_merge_conflict_question()
    test_wiki_files_question()
    
    print("\nRunning Task 3 tests...")
    test_framework_question()
    test_item_count_question()
    
    print("\nAll tests passed!")
