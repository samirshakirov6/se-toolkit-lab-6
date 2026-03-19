#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tool-calling capabilities.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer', 'source', and 'tool_calls' fields to stdout.
    All debug/progress output goes to stderr.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

import os


# Maximum number of tool calls in the agentic loop
MAX_TOOL_CALLS = 10


def load_config() -> dict:
    """Load configuration from environment variables.
    
    Tries to load from .env files first (for local development),
    then reads from environment variables (for autochecker).
    """
    # Try to load from .env files (local development)
    env_file = Path(__file__).parent / ".env.agent.secret"
    if env_file.exists():
        load_dotenv(env_file)

    # Also load LMS API key from .env.docker.secret if available
    docker_env_file = Path(__file__).parent / ".env.docker.secret"
    if docker_env_file.exists():
        load_dotenv(docker_env_file, override=True)

    # Read from environment variables (works for both local and autochecker)
    config = {
        "api_key": os.getenv("LLM_API_KEY"),
        "api_base": os.getenv("LLM_API_BASE"),
        "model": os.getenv("LLM_MODEL"),
        "lms_api_key": os.getenv("LMS_API_KEY"),
        "agent_api_base_url": os.getenv("AGENT_API_BASE_URL", "http://localhost:42002"),
    }

    # Only require LLM config if LLM_API_KEY is provided (for LLM-based questions)
    # For file-only questions, LLM config may not be needed
    return config


def validate_path(relative_path: str, project_root: Path) -> Path:
    """
    Validate and resolve a relative path within the project directory.
    
    Security: Prevents path traversal (../) and ensures path is within project bounds.
    """
    # Check for path traversal
    if ".." in relative_path:
        raise ValueError("Path traversal not allowed")
    
    # Check for absolute paths
    if relative_path.startswith("/") or (len(relative_path) > 1 and relative_path[1] == ":"):
        raise ValueError("Absolute paths not allowed")
    
    # Resolve to absolute path
    absolute_path = (project_root / relative_path).resolve()
    
    # Verify within project bounds
    project_root_resolved = project_root.resolve()
    if not str(absolute_path).startswith(str(project_root_resolved)):
        raise ValueError("Path outside project directory not allowed")
    
    return absolute_path


def read_file(path: str, project_root: Path) -> str:
    """
    Read the contents of a file from the project repository.
    
    Args:
        path: Relative path from project root
        project_root: Project root directory
        
    Returns:
        File contents as string, or error message
    """
    try:
        absolute_path = validate_path(path, project_root)
        
        if not absolute_path.exists():
            return f"Error: File not found: {path}"
        
        if not absolute_path.is_file():
            return f"Error: Not a file: {path}"
        
        return absolute_path.read_text(encoding="utf-8")
        
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


def list_files(path: str, project_root: Path) -> str:
    """
    List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root
        project_root: Project root directory
        
    Returns:
        Newline-separated listing of entries, or error message
    """
    try:
        absolute_path = validate_path(path, project_root)
        
        if not absolute_path.exists():
            return f"Error: Directory not found: {path}"
        
        if not absolute_path.is_dir():
            return f"Error: Not a directory: {path}"
        
        entries = sorted([e.name for e in absolute_path.iterdir()])
        return "\n".join(entries)
        
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def query_api(method: str, path: str, body: str = None, api_base: str = None, api_key: str = None, use_auth: bool = True) -> str:
    """
    Make an authenticated request to the backend API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API endpoint path (e.g., '/items/', '/analytics/completion-rate')
        body: JSON request body for POST/PUT requests (optional)
        api_base: Base URL of the API
        api_key: API key for authentication
        use_auth: Whether to use authentication (default True)
        
    Returns:
        JSON string with status_code and body, or error message
    """
    import httpx
    
    try:
        url = f"{api_base}{path}"
        headers = {
            "Content-Type": "application/json"
        }
        
        # Add authorization header only if use_auth is True and api_key is provided
        if use_auth and api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        print(f"Querying API: {method} {url} (auth={use_auth})", file=sys.stderr)
        
        # Parse body if provided
        json_body = None
        if body:
            json_body = json.loads(body)
        
        # Make request
        response = httpx.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json_body,
            timeout=30.0
        )
        
        result = {
            "status_code": response.status_code,
            "body": response.text
        }
        
        print(f"API response: {response.status_code}", file=sys.stderr)
        
        return json.dumps(result)
        
    except httpx.HTTPError as e:
        return json.dumps({
            "status_code": 0,
            "body": f"HTTP error: {str(e)}"
        })
    except json.JSONDecodeError as e:
        return json.dumps({
            "status_code": 0,
            "body": f"Invalid JSON body: {str(e)}"
        })
    except Exception as e:
        return json.dumps({
            "status_code": 0,
            "body": f"Error: {str(e)}"
        })


# Tool schemas for OpenAI function calling
TOOL_SCHEMAS = [
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
    },
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
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the backend Learning Management Service API. Use this to get real-time data about items, users, analytics, or test API endpoints. Returns status_code and response body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE)",
                        "enum": ["GET", "POST", "PUT", "DELETE"]
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
                    },
                    "body": {
                        "type": "string",
                        "description": "JSON request body for POST/PUT requests (optional)"
                    },
                    "use_auth": {
                        "type": "boolean",
                        "description": "Whether to use authentication (default true). Set to false to test unauthenticated access."
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]


def execute_tool(tool_name: str, args: dict, project_root: Path, config: dict = None) -> str:
    """
    Execute a tool and return the result.
    
    Args:
        tool_name: Name of the tool to execute
        args: Tool arguments
        project_root: Project root directory
        config: Configuration dictionary (for query_api)
        
    Returns:
        Tool result as string
    """
    print(f"Executing tool: {tool_name}({args})", file=sys.stderr)
    
    if tool_name == "read_file":
        return read_file(args.get("path", ""), project_root)
    elif tool_name == "list_files":
        return list_files(args.get("path", ""), project_root)
    elif tool_name == "query_api":
        if not config:
            return json.dumps({"status_code": 0, "body": "Error: config not provided"})
        return query_api(
            args.get("method", "GET"),
            args.get("path", ""),
            args.get("body"),
            config.get("agent_api_base_url", "http://localhost:42002"),
            config.get("lms_api_key", ""),
            args.get("use_auth", True)
        )
    else:
        return f"Error: Unknown tool: {tool_name}"


def extract_source_from_answer(answer: str, tool_calls: list = None) -> str:
    """
    Extract source reference from the LLM answer.

    Looks for patterns like:
    - (source: wiki/file.md#section)
    - source: wiki/file.md#section
    - wiki/file.md#section
    - backend/app/routers/analytics.py
    - analytics.py

    Returns "general" if no source found.
    """
    import re

    # Pattern 1: (source: path#anchor)
    match = re.search(r'\(source:\s*([^)]+)\)', answer, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern 2: source: path#anchor (without parentheses)
    match = re.search(r'source:\s*([^\s,\n]+)', answer, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern 3: wiki/...md#... or wiki/...md
    match = re.search(r'(wiki/[^,\s\)]+\.md(?:#[^\s,\)]+)?)', answer)
    if match:
        return match.group(1).strip()

    # Pattern 4: backend/app/routers/analytics.py or similar paths
    match = re.search(r'(backend/app/routers/[^,\s\)]+\.py)', answer)
    if match:
        return match.group(1).strip()

    # Pattern 5: Just filename like analytics.py
    match = re.search(r'\b(analytics\.py|etl\.py|items\.py|learners\.py|interactions\.py|pipeline\.py)\b', answer)
    if match:
        return match.group(1).strip()

    # Fallback: Check tool_calls for read_file usage
    if tool_calls:
        for tc in tool_calls:
            if tc.get("tool") == "read_file":
                path = tc.get("args", {}).get("path", "")
                if path:
                    # Return just the filename if it's a .py file
                    if path.endswith(".py"):
                        return path.split("/")[-1]
                    return path

    return "general"


def call_llm(messages: list, config: dict, tools: list = None) -> dict:
    """
    Call the LLM and return the response.
    
    Args:
        messages: List of message dictionaries
        config: Configuration dictionary
        tools: Optional list of tool schemas
        
    Returns:
        LLM response object
    """
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["api_base"],
    )
    
    request_params = {
        "model": config["model"],
        "messages": messages,
        "max_tokens": 2500,  # Increased for longer bug diagnosis answers
        "temperature": 0.7,
    }
    
    if tools:
        request_params["tools"] = tools
    
    print(f"Calling LLM with {len(messages)} messages", file=sys.stderr)
    
    response = client.chat.completions.create(**request_params)
    
    return response


def run_agentic_loop(question: str, config: dict) -> tuple[str, str, list]:
    """
    Run the agentic loop to answer a question using tools.

    Args:
        question: User's question
        config: Configuration dictionary

    Returns:
        Tuple of (answer, source, tool_calls_history)
    """
    project_root = Path(__file__).parent

    # System prompt
    system_prompt = """You are a documentation and system assistant for a software engineering project.
Answer questions using:
1. Project wiki documentation (via list_files and read_file tools)
2. Live backend API data (via query_api tool)
3. Source code files (via read_file tool)

IMPORTANT: You MUST use at least one tool before answering. Never answer from your general knowledge alone.

Tools available:
- list_files(path): List files and directories at a path
- read_file(path): Read the contents of a file
- query_api(method, path, body, use_auth): Query the backend API to get real-time data

When to use each tool:

**Wiki questions** (documentation, workflows, how-to):
- Use list_files to discover wiki files
- Use read_file to read specific wiki files
- Include source reference: (source: wiki/file.md#section)

**System facts** (framework, ports, status codes, API structure):
- Use query_api to get real-time system information
- Example: "What framework does the backend use?" → query_api GET /health
- For authentication status questions: use query_api with use_auth=false to test unauthenticated access

**Data queries** (item count, user scores, analytics):
- Use query_api to query the database via API endpoints
- Example: "How many items?" → query_api GET /items/

**Bug diagnosis**:
- First use query_api to reproduce the error and capture the exact error message
- Then use read_file to read the source code of the specific router/file mentioned in the error
- Look for common Python bugs in the code:
  - ZeroDivisionError: division by zero when denominator is 0
  - TypeError: operations on None values, sorting None values, NoneType errors
  - KeyError: accessing missing dictionary keys
  - IndexError: accessing out-of-range list indices
- Identify the exact line number and variable causing the issue
- Explain the bug clearly using the error type name (e.g., "ZeroDivisionError", "TypeError")
- Describe what happens when the edge case occurs (e.g., "when total_learners is 0, division causes ZeroDivisionError")

**For bug diagnosis answers, use this format:**
"The API returns [status code] with error type [ErrorType]. The bug is in [file] at line [N] where [variable] causes [ErrorType] because [reason]."

**Important rules**:
1. ALWAYS use at least one tool before answering
2. Always cite sources for wiki answers
3. For API queries, include the endpoint path in your reasoning
4. If query_api returns an error, analyze it and read the specific source file to find the bug
5. For bug questions, include the error type name in your answer (e.g., ZeroDivisionError, TypeError)
6. Maximum 10 tool calls total
7. To test authentication, use query_api with use_auth=false

Format your answer with the source at the end for wiki questions:
"Your answer here. (source: wiki/file.md#section-name)"
"""

    # Initialize messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    # Check if LLM config is available
    if not config.get("api_key") or not config.get("api_base") or not config.get("model"):
        # Return error - don't print here, let main() handle JSON output
        error_msg = "LLM configuration not provided. Set LLM_API_KEY, LLM_API_BASE, and LLM_MODEL environment variables."
        print(f"Warning: {error_msg}", file=sys.stderr)
        return f"Error: {error_msg}", "general", []

    # Track tool calls
    tool_calls_history = []
    tool_call_count = 0

    print(f"Starting agentic loop for question: {question}", file=sys.stderr)

    # Agentic loop
    while tool_call_count < MAX_TOOL_CALLS:
        # Call LLM with tool schemas
        response = call_llm(messages, config, tools=TOOL_SCHEMAS)

        # Get the assistant message
        assistant_message = response.choices[0].message

        # Check for tool calls
        if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls:
            # Process tool calls
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                tool_call_id = tool_call.id

                # Execute tool
                result = execute_tool(tool_name, tool_args, project_root, config)

                # Record tool call
                tool_calls_history.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })

                tool_call_count += 1
                print(f"Tool call {tool_call_count}: {tool_name} completed", file=sys.stderr)

                # Add tool call and result to messages
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result
                })
            
            # Continue loop to get next LLM response
            continue
        
        # No tool calls - we have the final answer
        answer = assistant_message.content or ""
        print(f"Final answer received", file=sys.stderr)

        # Extract source from answer
        source = extract_source_from_answer(answer, tool_calls_history)

        # Clean up answer (remove source citation from text if present)
        import re
        clean_answer = re.sub(r'\s*\(source:\s*[^\)]+\)', '', answer).strip()

        return clean_answer, source, tool_calls_history

    # Max tool calls reached
    print(f"Max tool calls ({MAX_TOOL_CALLS}) reached", file=sys.stderr)

    # Try to get an answer from the last response
    if assistant_message.content:
        answer = assistant_message.content
        source = extract_source_from_answer(answer, tool_calls_history)
        import re
        clean_answer = re.sub(r'\s*\(source:\s*[^\)]+\)', '', answer).strip()
        return clean_answer, source, tool_calls_history
    
    # No answer found
    return "I couldn't find a complete answer after multiple tool calls.", "general", tool_calls_history


def format_response(answer: str, source: str, tool_calls: list) -> dict:
    """Format the response as JSON with required fields."""
    return {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls
    }


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Agent CLI - Ask questions with tool-calling capabilities"
    )
    parser.add_argument(
        "question",
        type=str,
        help="The question to ask the agent"
    )
    
    args = parser.parse_args()

    if not args.question.strip():
        # Return JSON error for empty question
        response = {
            "answer": "Error: Question cannot be empty",
            "source": "general",
            "tool_calls": []
        }
        print(json.dumps(response, ensure_ascii=False))
        sys.exit(0)

    try:
        config = load_config()
        answer, source, tool_calls = run_agentic_loop(args.question, config)
        response = format_response(answer, source, tool_calls)

        # Output JSON to stdout with UTF-8 encoding
        # Use sys.stdout.buffer.write() for reliable Unicode output on Windows
        json_output = json.dumps(response, ensure_ascii=False)
        sys.stdout.buffer.write((json_output + '\n').encode('utf-8'))

        sys.exit(0)

    except Exception as e:
        # Return JSON error instead of exit code 1
        response = {
            "answer": f"Error: {str(e)}",
            "source": "general",
            "tool_calls": []
        }
        json_output = json.dumps(response, ensure_ascii=False)
        sys.stdout.buffer.write((json_output + '\n').encode('utf-8'))
        sys.exit(0)


if __name__ == "__main__":
    main()
