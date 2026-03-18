# Task 1: Call an LLM from Code — Implementation Plan

## Overview
Build a CLI program (`agent.py`) that takes a question as a command-line argument, sends it to an LLM, and returns a structured JSON answer.

## LLM Provider and Model

### Provider: Qwen Code API (self-hosted on VM)
- **Why Qwen Code API:**
  - 1000 free requests per day
  - Works from Russia without restrictions
  - No credit card required
  - OpenAI-compatible API endpoint
  - Already deployed on our VM (port 42005)

### Model: `coder-model` (Qwen 3.5 Plus)
- Strong tool-calling capabilities (will be used in Task 2-3)
- Good balance of speed and quality
- Recommended in the task description

## Architecture

### Components

1. **Environment Loading**
   - Read `.env.agent.secret` using `python-dotenv`
   - Extract: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`

2. **Argument Parsing**
   - Use `argparse` to get the question from command line
   - Validate that a question was provided

3. **LLM Client**
   - Use `openai` Python library (compatible with Qwen Code API)
   - Configure with custom base URL and API key
   - Send chat completion request with system + user message

4. **Response Processing**
   - Extract answer from LLM response
   - Format as JSON: `{"answer": "...", "tool_calls": []}`
   - `tool_calls` is empty for this task (will be populated in Task 2)

5. **Output**
   - JSON to stdout (single line)
   - All debug/progress logs to stderr
   - Exit code 0 on success

### Data Flow

```
Command line argument (question)
    ↓
agent.py parses argument
    ↓
Load environment variables from .env.agent.secret
    ↓
Create OpenAI client with custom base URL
    ↓
Send request to LLM_API_BASE/chat/completions
    ↓
Receive response from LLM
    ↓
Format as JSON with answer and tool_calls
    ↓
Output JSON to stdout
```

## Error Handling

- Missing question argument → print error to stderr, exit code 1
- Missing environment variables → print error to stderr, exit code 1
- API request failure → print error to stderr, exit code 1
- Timeout (>60 seconds) → let the test framework handle it

## Testing Strategy

### Single Regression Test
- Run `agent.py` as subprocess with a test question
- Parse stdout as JSON
- Verify:
  - `answer` field exists and is a non-empty string
  - `tool_calls` field exists and is an array

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `plans/task-1.md` | Create | This implementation plan |
| `agent.py` | Create | Main CLI agent |
| `.env.agent.secret` | Create | LLM credentials (gitignored) |
| `AGENT.md` | Create | Architecture documentation |
| `tests/test_agent_task1.py` | Create | Regression test |

## Dependencies

Add to `pyproject.toml` (if not already present):
- `openai` — OpenAI-compatible API client
- `python-dotenv` — Environment variable loading

## Acceptance Criteria Checklist

- [ ] `plans/task-1.md` exists with implementation plan
- [ ] `agent.py` exists in project root
- [ ] `uv run agent.py "..."` outputs valid JSON with `answer` and `tool_calls`
- [ ] API key stored in `.env.agent.secret` (not hardcoded)
- [ ] `AGENT.md` documents the solution architecture
- [ ] 1 regression test exists and passes
- [ ] Git workflow followed (issue, branch, PR, partner approval, merge)
