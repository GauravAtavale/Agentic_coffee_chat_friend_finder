#!/usr/bin/env python3
"""
Create a Google Calendar meet invite via Airia pipeline.
Takes event fields as CLI arguments and builds the prompt for the API.

Uses AIRIA_API_KEY from environment or config/.env.

Usage:
  python scripts/create_meet.py --title "Meet up" --date "February 21, 2026" --time "6:00 PM – 7:00 PM (UTC)" --attendee anaghapalandye@gmail.com
  python scripts/create_meet.py --title "Meet up" --date "Feb 21 2026" --time "6-7 PM" --location Virtual --description "Let's meet" --attendee anaghapalandye@gmail.com
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


def build_prompt(
    title: str,
    date: str,
    time: str,
    location: str,
    description: str,
    attendee: str,
    status: str,
) -> str:
    """Build the userInput prompt string from event fields."""
    parts = [
        "Create a Google Calendar invite with the following details:",
        f"Title: {title}",
        f"Date: {date}",
        f"Time: {time}",
    ]
    if location:
        parts.append(f"Location: {location}")
    if description:
        parts.append(f"Description: {description}")
    parts.append(f"Attendee(s): {attendee}")
    if status:
        parts.append(f"Status: {status}")
    return ". ".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Create a Google Calendar meet invite via Airia pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--title", default="Meet up", help="Event title")
    parser.add_argument("--date", default="February 21, 2026", help="Event date")
    parser.add_argument(
        "--time",
        default="6:00 PM – 7:00 PM (UTC)",
        help="Event time range",
    )
    parser.add_argument(
        "--location",
        default="Virtual",
        help="Location (e.g. Virtual or address)",
    )
    parser.add_argument(
        "--description",
        default="Let's meet",
        help="Event description",
    )
    parser.add_argument(
        "--attendee",
        default="anaghapalandye@gmail.com",
        help="Attendee email(s); comma-separated for multiple",
    )
    parser.add_argument(
        "--status",
        default="Confirmed",
        help="Event status (e.g. Confirmed)",
    )
    parser.add_argument(
        "--async-output",
        action="store_true",
        help="Use async pipeline output",
    )
    parser.add_argument(
        "--url",
        default=AIRIA_PIPELINE_URL,
        help="Airia pipeline execution URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompt only, do not call API",
    )
    args = parser.parse_args()

    user_input = build_prompt(
        title=args.title,
        date=args.date,
        time=args.time,
        location=args.location or "",
        description=args.description or "",
        attendee=args.attendee,
        status=args.status or "",
    )

    if args.dry_run:
        print("Prompt that would be sent:")
        print(user_input)
        return

    api_key = os.environ.get("AIRIA_API_KEY", "").strip()
    if not api_key:
        print("Error: AIRIA_API_KEY not set. Add it to config/.env or export it.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "userInput": user_input,
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
