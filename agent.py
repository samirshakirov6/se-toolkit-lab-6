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
    """Load configuration from .env.agent.secret file."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    
    if not env_file.exists():
        print(f"Error: Environment file not found: {env_file}", file=sys.stderr)
        sys.exit(1)
    
    load_dotenv(env_file)
    
    config = {
        "api_key": os.getenv("LLM_API_KEY"),
        "api_base": os.getenv("LLM_API_BASE"),
        "model": os.getenv("LLM_MODEL"),
    }
    
    missing = [key for key, value in config.items() if not value]
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    
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
    }
]


def execute_tool(tool_name: str, args: dict, project_root: Path) -> str:
    """
    Execute a tool and return the result.
    
    Args:
        tool_name: Name of the tool to execute
        args: Tool arguments
        project_root: Project root directory
        
    Returns:
        Tool result as string
    """
    print(f"Executing tool: {tool_name}({args})", file=sys.stderr)
    
    if tool_name == "read_file":
        return read_file(args.get("path", ""), project_root)
    elif tool_name == "list_files":
        return list_files(args.get("path", ""), project_root)
    else:
        return f"Error: Unknown tool: {tool_name}"


def extract_source_from_answer(answer: str) -> str:
    """
    Extract source reference from the LLM answer.
    
    Looks for patterns like:
    - (source: wiki/file.md#section)
    - source: wiki/file.md#section
    - wiki/file.md#section
    
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
        "max_tokens": 1500,
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
    system_prompt = """You are a documentation assistant for a software engineering project.
Answer questions using the project wiki documentation.

You have access to these tools:
- list_files(path): List files and directories at a path
- read_file(path): Read the contents of a file

Process to answer questions:
1. Use list_files to discover relevant wiki files
2. Use read_file to read specific files and find the answer
3. Include a source reference in your answer using this format: (source: wiki/file.md#section-name)
4. If the answer spans multiple sections, cite the most relevant one
5. Once you have the answer, respond with the final answer including the source

Be concise and accurate. Always cite your sources."""

    # Initialize messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
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
                result = execute_tool(tool_name, tool_args, project_root)
                
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
        source = extract_source_from_answer(answer)
        
        # Clean up answer (remove source citation from text if present)
        import re
        clean_answer = re.sub(r'\s*\(source:\s*[^\)]+\)', '', answer).strip()
        
        return clean_answer, source, tool_calls_history
    
    # Max tool calls reached
    print(f"Max tool calls ({MAX_TOOL_CALLS}) reached", file=sys.stderr)
    
    # Try to get an answer from the last response
    if assistant_message.content:
        answer = assistant_message.content
        source = extract_source_from_answer(answer)
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
        print("Error: Question cannot be empty", file=sys.stderr)
        sys.exit(1)
    
    try:
        config = load_config()
        answer, source, tool_calls = run_agentic_loop(args.question, config)
        response = format_response(answer, source, tool_calls)
        
        # Output JSON to stdout (single line, ensure ASCII for Windows compatibility)
        # Use sys.stdout.buffer for proper Unicode handling
        import io
        sys.stdout.reconfigure(encoding='utf-8')
        print(json.dumps(response, ensure_ascii=False))
        
        sys.exit(0)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
