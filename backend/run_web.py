#!/usr/bin/env python3
"""
Start the Agentic Social web server (world_chat UI + simulation stream).
Run from repo root: python backend/run_web.py
Or from backend: python run_web.py
Server runs at http://localhost:8002
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

# Load config/.env first so GROQ_API_KEY and ANTHROPIC_API_KEY are available
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / "config" / ".env")
except ImportError:
    pass

from server import main

if __name__ == "__main__":
    main()
