# Agent Architecture Documentation

## Overview

This project implements a CLI agent (`agent.py`) that connects to an LLM and returns structured JSON answers. The agent serves as the foundation for a more advanced agentic system with tool-calling capabilities (to be implemented in Tasks 2-3).

## LLM Provider

### Qwen Code API (Self-hosted on VM)

**Why Qwen Code API:**
- 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- OpenAI-compatible API endpoint
- Already deployed on our VM

**Configuration:**
- **Endpoint:** `http://10.93.25.231:42005/v1`
- **Model:** `coder-model` (Qwen 3.5 Plus)
- **API Key:** Stored in `.env.agent.secret`

### Alternative Providers

The agent supports any OpenAI-compatible API. To switch providers:

1. Update `.env.agent.secret`:
   ```
   LLM_API_BASE=https://openrouter.ai/api/v1
   LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
   ```

2. Set your API key:
   ```
   LLM_API_KEY=your-openrouter-key
   ```

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                      agent.py                               │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │ Argument    │  │ LLM Client   │  │ Response        │    │
│  │ Parser      │→ │ (OpenAI)     │→ │ Formatter       │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
│         ↑                ↑                     │            │
│         │                │                     │            │
│  ┌──────┴────────┐ ┌────┴──────────┐  ┌──────┴────────┐   │
│  │ Command Line  │ │ .env.agent    │  │ JSON Output   │   │
│  │ Arguments     │ │ .secret       │  │ (stdout)      │   │
│  └───────────────┘ └───────────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
                    ┌─────────────────┐
                    │ Qwen Code API   │
                    │ (on VM:42005)   │
                    └─────────────────┘
```

### Data Flow

1. **Input:** User provides a question as a command-line argument
2. **Configuration:** Agent loads API credentials from `.env.agent.secret`
3. **Request:** Agent sends the question to the LLM via OpenAI-compatible API
4. **Response:** LLM returns an answer
5. **Output:** Agent formats the response as JSON and prints to stdout

### Output Format

```json
{
  "answer": "Representational State Transfer.",
  "tool_calls": []
}
```

**Fields:**
- `answer` (string): The LLM's response to the question
- `tool_calls` (array): Empty for Task 1, will contain tool invocations in Task 2-3

## Usage

### Basic Usage

```bash
# Run with a question
uv run agent.py "What does REST stand for?"

# Example output:
# {"answer": "Representational State Transfer.", "tool_calls": []}
```

### Exit Codes

- `0`: Success
- `1`: Error (missing arguments, configuration, API failure)

### Output Streams

- **stdout:** JSON response only (for parsing by other tools)
- **stderr:** Debug/progress messages

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for LLM provider | `my-secret-key` |
| `LLM_API_BASE` | Base URL of LLM API | `http://10.93.25.231:42005/v1` |
| `LLM_MODEL` | Model name to use | `coder-model` |

### File Structure

```
.
├── agent.py              # Main CLI agent
├── .env.agent.secret     # LLM credentials (gitignored)
├── .env.agent.example    # Example configuration
├── AGENT.md              # This documentation
├── plans/
│   └── task-1.md         # Implementation plan
└── tests/
    └── test_agent_task1.py  # Regression tests
```

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run specific test
uv run pytest tests/test_agent_task1.py -v
```

### Test Coverage

The regression test verifies:
- Agent runs successfully with a question
- Output is valid JSON
- `answer` field exists and is non-empty
- `tool_calls` field exists and is an array

## Dependencies

| Package | Purpose |
|---------|---------|
| `openai` | OpenAI-compatible API client |
| `python-dotenv` | Environment variable loading |
| `pydantic` | Data validation (for future tasks) |

## Future Enhancements (Tasks 2-3)

- **Task 2:** Add tool-calling capabilities
  - Define tools (file read, API query, etc.)
  - Parse tool calls from LLM response
  - Execute tools and return results

- **Task 3:** Implement agentic loop
  - Multi-turn conversation support
  - Tool result feedback to LLM
  - Final answer synthesis

## Troubleshooting

### "Environment file not found"

Ensure `.env.agent.secret` exists in the project root:
```bash
cp .env.agent.example .env.agent.secret
# Edit with your credentials
```

### "Missing environment variables"

Check that all required variables are set in `.env.agent.secret`:
```
LLM_API_KEY=your-key
LLM_API_BASE=http://10.93.25.231:42005/v1
LLM_MODEL=coder-model
```

### API connection errors

1. Verify VM is accessible: `ping 10.93.25.231`
2. Check Qwen API is running: `curl http://10.93.25.231:42005/health`
3. Ensure firewall allows port 42005

### Timeout (>60 seconds)

- The test framework enforces a 60-second timeout
- If LLM is slow, check VM resources and network connectivity
