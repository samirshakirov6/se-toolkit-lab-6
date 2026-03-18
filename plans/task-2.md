# Task 2: The Documentation Agent — Implementation Plan

## Overview
Extend the agent from Task 1 to support tool-calling capabilities. The agent will have two tools (`read_file`, `list_files`) to navigate the project wiki and answer questions with proper source references.

## Tool Definitions

### read_file
**Purpose:** Read contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root

**Security:**
- Validate path does not contain `../` traversal
- Resolve to absolute path and verify it's within project directory
- Return error message if file doesn't exist or is outside bounds

**Returns:** File contents as string, or error message

### list_files
**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root

**Security:**
- Validate path does not contain `../` traversal
- Resolve to absolute path and verify it's within project directory
- Return error message if directory doesn't exist or is outside bounds

**Returns:** Newline-separated listing of entries

## Tool Schemas (OpenAI Function Calling)

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file from the project repository",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
        }
      },
      "required": ["path"]
    }
  }
}
```

```json
{
  "type": "function",
  "function": {
    "name": "list_files",
    "description": "List files and directories at a given path",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative directory path from project root (e.g., 'wiki')"
        }
      },
      "required": ["path"]
    }
  }
}
```

## Agentic Loop

### Algorithm

```
1. Initialize messages list with system + user message
2. Initialize tool_calls_history = []
3. Loop (max 10 iterations):
   a. Call LLM with messages + tool schemas
   b. If response has tool_calls:
      - For each tool_call:
        * Execute the tool
        * Append tool_call to tool_calls_history with result
        * Add tool_call and tool result to messages
      - Continue loop
   c. If response has text message (no tool calls):
      - Extract answer from message
      - Extract source from answer (file path + section anchor)
      - Break loop
4. Format output JSON with answer, source, tool_calls
```

### Message Flow

```
User: "How do you resolve a merge conflict?"
  ↓
LLM: [tool_call: list_files(path="wiki")]
  ↓
Agent: Execute list_files → ["git-workflow.md", ...]
  ↓
LLM: [tool_call: read_file(path="wiki/git-workflow.md")]
  ↓
Agent: Execute read_file → "# Git Workflow\n\n..."
  ↓
LLM: "To resolve a merge conflict... (source: wiki/git-workflow.md#resolving-merge-conflicts)"
  ↓
Output JSON
```

## System Prompt Strategy

The system prompt will instruct the LLM to:

1. **Use tools to find answers** in the wiki documentation
2. **Always include source references** (file path + section anchor)
3. **Use list_files first** to discover relevant files
4. **Use read_file** to read specific files
5. **Stop after finding the answer** — don't make unnecessary tool calls

Example system prompt:
```
You are a documentation assistant. Answer questions using the project wiki.

Tools available:
- list_files: List files in a directory
- read_file: Read a file's contents

Process:
1. Use list_files to discover wiki files
2. Use read_file to find the answer
3. Include the source reference (file path + section anchor) in your answer

Format your answer with the source at the end:
"Your answer here. (source: wiki/file.md#section-name)"
```

## Path Security

### Validation Rules

1. **No path traversal:**
   - Reject paths containing `..`
   - Reject absolute paths (starting with `/` or `C:\`)

2. **Within project bounds:**
   - Resolve path relative to project root
   - Verify resolved path starts with project root directory

3. **Error handling:**
   - Return clear error message for invalid paths
   - Don't expose internal path structure in errors

### Implementation

```python
def validate_path(relative_path: str, project_root: Path) -> Path:
    # Check for traversal
    if ".." in relative_path:
        raise ValueError("Path traversal not allowed")
    
    # Resolve absolute path
    absolute_path = (project_root / relative_path).resolve()
    
    # Verify within project
    if not str(absolute_path).startswith(str(project_root.resolve())):
        raise ValueError("Path outside project not allowed")
    
    return absolute_path
```

## Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

## Error Handling

- **Tool execution error:** Include error message in tool result, continue loop
- **LLM doesn't call tools:** Use response as answer, set source to "general"
- **Max iterations (10):** Stop and use whatever answer is available
- **Invalid path:** Return error message as tool result

## Testing Strategy

### Test 1: Merge Conflict Question
**Question:** "How do you resolve a merge conflict?"

**Expected:**
- `read_file` in tool_calls
- `wiki/git-workflow.md` in source
- Non-empty answer

### Test 2: Wiki Files Question
**Question:** "What files are in the wiki?"

**Expected:**
- `list_files` in tool_calls
- Non-empty tool_calls array
- Answer mentions wiki files

## Files to Modify

| File | Action | Purpose |
|------|--------|---------|
| `plans/task-2.md` | Create | This implementation plan |
| `agent.py` | Update | Add tools and agentic loop |
| `AGENT.md` | Update | Document tools and loop |
| `tests/test_agent_task1.py` | Update | Add 2 new tests |

## Acceptance Criteria Checklist

- [ ] `plans/task-2.md` exists with implementation plan
- [ ] `agent.py` defines `read_file` and `list_files` as tool schemas
- [ ] Agentic loop executes tool calls and feeds results back
- [ ] `tool_calls` in output is populated when tools are used
- [ ] `source` field correctly identifies wiki section
- [ ] Tools do not access files outside project directory
- [ ] `AGENT.md` documents tools and agentic loop
- [ ] 2 tool-calling regression tests exist and pass
- [ ] Git workflow followed (issue, branch, PR, partner approval, merge)
