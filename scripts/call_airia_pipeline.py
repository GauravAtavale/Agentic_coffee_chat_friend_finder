#!/usr/bin/env python3
"""
Call Airia Pipeline Execution API.
Uses AIRIA_API_KEY from environment or config/.env.

Usage:
  python scripts/call_airia_pipeline.py
  python scripts/call_airia_pipeline.py --user-input "Your prompt here"
  python scripts/call_airia_pipeline.py --user-input "Hello" --async-output
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Load .env from repo root or config
REPO_ROOT = Path(__file__).resolve().parent.parent
for env_path in [REPO_ROOT / "config" / ".env", REPO_ROOT / ".env"]:
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            break
        except ImportError:
            break

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

AIRIA_PIPELINE_URL = "https://api.airia.ai/v2/PipelineExecution/86bb5ef8-4810-448e-b0ef-78eb822b79fd"


def main():
    parser = argparse.ArgumentParser(description="Call Airia Pipeline Execution API")
    parser.add_argument(
        "--user-input",
        default="Example user input",
        help="User input to send (default: Example user input)",
    )
    parser.add_argument(
        "--async-output",
        action="store_true",
        help="Set asyncOutput to true (default: false)",
    )
    parser.add_argument(
        "--url",
        default=AIRIA_PIPELINE_URL,
        help="Pipeline execution URL",
    )
    args = parser.parse_args()

    api_key = os.environ.get("AIRIA_API_KEY", "").strip()
    if not api_key:
        print("Error: AIRIA_API_KEY not set. Add it to config/.env or export it.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "userInput": args.user_input,
        "asyncOutput": args.async_output,
    }

    try:
        r = requests.post(args.url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        print(json.dumps(r.json(), indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        if hasattr(e, "response") and e.response is not None:
            try:
                print(e.response.text, file=sys.stderr)
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
