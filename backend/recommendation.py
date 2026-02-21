#!/usr/bin/env python3
"""
Generate coffee-chat recommendations for Gaurav_Atavale from conversation history.
Reads config/recommendation_sys_prompt.txt and data/conversational_history.txt,
calls the primary/fallback model, and outputs JSON recommendations with likelihood scores.

Run from repo root: python backend/recommendation.py
Or from backend: python recommendation.py
"""
import json
import os
import re
import sys
from pathlib import Path

# Paths
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"
HISTORY_FILE = DATA_DIR / "conversational_history.txt"
PROMPT_FILE = CONFIG_DIR / "recommendation_sys_prompt.txt"
RECOMMENDATIONS_OUTPUT = DATA_DIR / "recommendations.json"


def load_prompt() -> str:
    """Load the recommendation system prompt from config."""
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")
    return PROMPT_FILE.read_text(encoding="utf-8").strip()


def load_conversation_history(turns: int = 50) -> str:
    """Load and format conversation history from conversational_history.txt."""
    if not HISTORY_FILE.exists():
        return "No conversation history found."
    lines = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                role = entry.get("role", "Unknown")
                content = entry.get("content", "")
                lines.append(f"{role}: {content}")
            except json.JSONDecodeError:
                continue
    # Last N turns
    lines = lines[-turns:] if len(lines) > turns else lines
    return "\n".join(lines) if lines else "No conversation history found."


def get_recommendations(profile_user: str):
    """
    Generate coffee-chat recommendations for the given profile user.
    profile_user: e.g. 'Gaurav_Atavale', 'Anagha_Palandye'. Replaces <user> in the prompt.
    Returns dict with 'recommendations' array; raises on error.
    """
    if BACKEND_DIR not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    import utils

    raw_prompt = load_prompt()
    prompt = raw_prompt.replace("<user>", profile_user)
    history = load_conversation_history()
    user_message = (
        f"Use the following conversation history to generate coffee chat recommendations for {profile_user}.\n\n"
        "Conversation history:\n"
        "---\n"
        f"{history}\n"
        "---\n\n"
        "Output only the JSON object with the 'recommendations' array as specified in your instructions."
    )

    try:
        response = utils.agent_sim(utils.PRIMARY_MODEL, prompt, user_message)
    except Exception:
        response = utils.agent_sim(utils.FALLBACK_MODEL, prompt, user_message)

    result = extract_json(response)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RECOMMENDATIONS_OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def extract_json(text: str) -> dict:
    """Extract JSON from model output, optionally inside ```json ... ```."""
    text = text.strip()
    # Try raw parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try to find {...} in the text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError("Could not extract valid JSON from model output.")


def main():
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(BACKEND_DIR)
    import utils

    prompt = load_prompt()
    history = load_conversation_history()
    try:
        result = get_recommendations("Gaurav_Atavale")
        print(f"Saved to {RECOMMENDATIONS_OUTPUT}", file=sys.stderr)
        print(json.dumps(result, indent=2))
        return result
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
