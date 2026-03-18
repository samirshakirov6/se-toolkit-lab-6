# Agent Architecture Documentation

## Overview

This project implements a CLI agent (`agent.py`) that connects to an LLM and returns structured JSON answers. The agent has tool-calling capabilities to navigate the project wiki and answer questions with proper source references.

**Current capabilities (Task 2):**
- Two tools: `read_file`, `list_files`
- Agentic loop with max 10 tool calls
- Source extraction from answers

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

## Tools

The agent has two tools for navigating the project wiki:

### read_file

**Purpose:** Read the contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Security:**
- Validates path does not contain `../` traversal
- Verifies resolved path is within project directory
- Returns error message if file doesn't exist or is outside bounds

**Example:**
```json
{"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "# Git Workflow\n..."}
```

### list_files

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Security:**
- Validates path does not contain `../` traversal
- Verifies resolved path is within project directory
- Returns error message if directory doesn't exist or is outside bounds

**Example:**
```json
{"tool": "list_files", "args": {"path": "wiki"}, "result": "git-workflow.md\ngit.md\n..."}
```

## Agentic Loop

### Algorithm

```
1. Initialize messages with system + user prompt
2. Initialize tool_calls_history = []
3. Loop (max 10 iterations):
   a. Call LLM with messages + tool schemas
   b. If LLM returns tool_calls:
      - Execute each tool
      - Record tool call with result
      - Add tool_call and result to messages
      - Continue loop
   c. If LLM returns text message:
      - Extract answer and source
      - Break loop
4. Output JSON with answer, source, tool_calls
```

### Message Flow

```
User Question
    ↓
┌──────────────────────────────────────┐
│  LLM (with tool schemas)             │
└──────────────────────────────────────┘
    ↓
Has tool_calls?
    ├─ Yes → Execute tools → Add results to messages → Back to LLM
    └─ No  → Extract answer + source → Output JSON
```

### System Prompt Strategy

The system prompt instructs the LLM to:

1. **Use tools to find answers** in the wiki documentation
2. **Always include source references** (file path + section anchor)
3. **Use list_files first** to discover relevant files
4. **Use read_file** to read specific files
5. **Stop after finding the answer**

Example:
```
You are a documentation assistant for a software engineering project.
Answer questions using the project wiki documentation.

You have access to these tools:
- list_files(path): List files and directories at a path
- read_file(path): Read the contents of a file

Process to answer questions:
1. Use list_files to discover relevant wiki files
2. Use read_file to read specific files and find the answer
3. Include a source reference in your answer using this format: (source: wiki/file.md#section-name)
```

## Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-vscode.md#resolve-a-merge-conflict",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\ngit.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-vscode.md"},
      "result": "# Git in VS Code\n\n..."
    }
  ]
}
```

**Fields:**
- `answer` (string): The LLM's response to the question
- `source` (string): Wiki section reference (file path + section anchor)
- `tool_calls` (array): All tool calls made during the agentic loop

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
