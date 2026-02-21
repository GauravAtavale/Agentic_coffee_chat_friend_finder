#!/usr/bin/env python3
"""
Start the Agentic Social web server (world_chat UI + simulation stream).
Run from repo root: python backend/run_web.py
Or from backend: python run_web.py
Server runs at http://localhost:8001
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

from server import main

if __name__ == "__main__":
    main()
