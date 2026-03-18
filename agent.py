#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer' and 'tool_calls' fields to stdout.
    All debug/progress output goes to stderr.
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

import os


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


def call_llm(question: str, config: dict) -> str:
    """Call the LLM and return the answer."""
    print(f"Sending question to LLM: {question}", file=sys.stderr)
    print(f"Using model: {config['model']}", file=sys.stderr)
    print(f"API endpoint: {config['api_base']}", file=sys.stderr)
    
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["api_base"],
    )
    
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Provide clear, concise answers to questions."
            },
            {
                "role": "user",
                "content": question
            }
        ],
        max_tokens=1000,
        temperature=0.7,
    )
    
    answer = response.choices[0].message.content
    print(f"Received answer from LLM", file=sys.stderr)
    
    return answer


def format_response(answer: str) -> dict:
    """Format the response as JSON with required fields."""
    return {
        "answer": answer,
        "tool_calls": []
    }


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Agent CLI - Ask questions to an LLM"
    )
    parser.add_argument(
        "question",
        type=str,
        help="The question to ask the LLM"
    )
    
    args = parser.parse_args()
    
    if not args.question.strip():
        print("Error: Question cannot be empty", file=sys.stderr)
        sys.exit(1)
    
    try:
        config = load_config()
        answer = call_llm(args.question, config)
        response = format_response(answer)
        
        # Output JSON to stdout (single line)
        print(json.dumps(response, ensure_ascii=False))
        
        sys.exit(0)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
