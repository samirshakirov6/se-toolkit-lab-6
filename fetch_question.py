#!/usr/bin/env python3
"""Fetch and display eval question from autochecker API."""

import base64
import json
import os
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_file = Path(__file__).parent / ".env"
load_dotenv(env_file)

api_url = os.getenv("AUTOCHECKER_API_URL")
email = os.getenv("AUTOCHECKER_EMAIL")
password = os.getenv("AUTOCHECKER_PASSWORD")

if not all([api_url, email, password]):
    print("Missing credentials in .env file")
    exit(1)

# Build auth header
auth_bytes = f"{email}:{password}".encode()
auth_header = base64.b64encode(auth_bytes).decode()

# Fetch question
lab = "lab-06"
index = 6  # Question 7 (0-indexed)
url = f"{api_url}/api/eval/question?lab={lab}&index={index}"

req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth_header}"})

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        print(json.dumps(data, indent=2, ensure_ascii=False))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode()}")
except urllib.error.URLError as e:
    print(f"URL Error: {e.reason}")
