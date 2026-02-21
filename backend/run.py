"""
Final flow of Agentic Social Simulation.
Supports per-channel conversations: run with --channel finance (or world, technology, healthcare, architecture, computer_science).
"""
import argparse
import json
import re
import sys
from pathlib import Path
import utils

# Paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"

# Channel -> history filename (must match server.CHANNEL_FILES)
CHANNEL_FILES = {
    "world": "conversational_history.txt",
    "finance": "finance_convers_history.txt",
    "technology": "tech_convers_history.txt",
    "healthcare": "healthcare_convers_history.txt",
    "architecture": "architecture_convers_history.txt",
    "computer_science": "computer_science_convers_history.txt",
}

def _parse_args():
    p = argparse.ArgumentParser(description="Run agent simulation for a channel")
    p.add_argument("--channel", default="world", help="Channel name (world, finance, technology, healthcare, architecture, computer_science)")
    return p.parse_args()

def _history_file_for_channel(channel: str) -> Path:
    filename = CHANNEL_FILES.get(channel, CHANNEL_FILES["world"])
    return (DATA_DIR / filename).resolve()

def _ensure_channel_has_seed(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"role": "Gaurav", "content": "Conversation started."}\n')

# Parse channel and set history file for this process (and for utils)
_args = _parse_args()
_channel = _args.channel
HISTORY_FILE = _history_file_for_channel(_channel)
utils.HISTORY_FILE = HISTORY_FILE
_ensure_channel_has_seed(HISTORY_FILE)

# Mock data for testing
person_role_dict = {
    "Gaurav_Atavale": "Gaurav",
    "Anagha_Palandye": "Anagha",
    "Kanishkha_S": "Kanishkha",
    "Nirbhay_R": "Nirbhay"
    }
role_person_dict = {v: k for k, v in person_role_dict.items()}

file_names_dict = {
    "Gaurav_Atavale": BACKEND_DIR / "agent_Gaurav.py",
    "Anagha_Palandye": BACKEND_DIR / "agent_Anagha.py",
    "Kanishkha_S": BACKEND_DIR / "agent_Kanishkha.py",
    "Nirbhay_R": BACKEND_DIR / "agent_Nirbhay.py"
    }

# Loop until NO ONE has credits left (everyone is 0)
# Run iterations of the simulation
with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    lines = [ln.strip() for ln in f.readlines() if ln.strip()]
if not lines:
    init_person = list(person_role_dict.keys())[0]
else:
    try:
        last_entry = json.loads(lines[-1])
        last_role = last_entry.get("role")
        if not last_role or last_role not in role_person_dict:
            init_person = list(person_role_dict.keys())[0]
            print(f"[run.py channel={_channel}] Role '{last_role}' not in dict, using {init_person}")
        else:
            init_person = role_person_dict[last_role]
    except (json.JSONDecodeError, KeyError) as e:
        init_person = list(person_role_dict.keys())[0]
        print(f"[run.py channel={_channel}] Parse error, using {init_person}. Error: {e}") 

credits_left = {key: 100 for key in person_role_dict.keys()}
print(f"[run.py channel={_channel}] Started. History file: {HISTORY_FILE}", file=sys.stderr, flush=True)

while any(credits_left[key] > 0 for key in credits_left):
    
    # FIX: Generate random bid ONLY if credits > 0, else bid is 0
    random_numbers = {}
    for key in person_role_dict:
        if credits_left[key] > 0:
            try:
                llm_bid_score = utils.generate_bid_score_each_user(key, credits_left, utils.PRIMARY_MODEL)
                random_numbers[key] = int(0.01 * float(json.loads(llm_bid_score)["score"]) * credits_left[key])
                print("primary model worked. Bid score:", random_numbers[key])
            except Exception:
                llm_bid_score = utils.generate_bid_score_each_user(key, credits_left, utils.FALLBACK_MODEL)
                random_numbers[key] = int(0.01 * float(json.loads(llm_bid_score)["score"]) * credits_left[key])
                print("fallback model worked. Bid score:", random_numbers[key])
        else:
            random_numbers[key] = 0  # Can't bid if no credits


    # Check if everyone is out of credits (bids are all 0) to avoid infinite loop or errors
    if all(val == 0 for val in random_numbers.values()):
        break

    # Select winner
    selected_person = max(random_numbers, key=random_numbers.get)
    winning_bid = random_numbers[selected_person]

    # Deduct credits
    if winning_bid > 0 and selected_person != init_person:
        # Only deduct if they actually bid something
        credits_left[selected_person] = max(0, credits_left[selected_person] - winning_bid)
        print(f"{selected_person} wins with bid {winning_bid} and will chat now.", "Credits left:", credits_left) 
        agent_script = file_names_dict[selected_person]
        if not agent_script.exists():
            print(f"Warning: Agent script not found: {agent_script}")
            continue
        with open(agent_script, "r") as f:
            exec(f.read(), {"REPO_ROOT": REPO_ROOT, "HISTORY_FILE": HISTORY_FILE, "__file__": str(agent_script)})
        init_person = selected_person
    elif selected_person == init_person:
        # second highest value from random_numbers dict
        second_highest_person = max((k for k in random_numbers if k != selected_person), key=random_numbers.get)
        selected_person = second_highest_person
        winning_bid = random_numbers[selected_person]
        credits_left[selected_person] = max(0, credits_left[selected_person] - winning_bid)
        print(f"{selected_person} wins with bid {winning_bid} and will chat now.", "Credits left:", credits_left) 
        agent_script = file_names_dict[selected_person]
        if not agent_script.exists():
            print(f"Warning: Agent script not found: {agent_script}")
            continue
        with open(agent_script, "r") as f:
            exec(f.read(), {"REPO_ROOT": REPO_ROOT, "HISTORY_FILE": HISTORY_FILE, "__file__": str(agent_script)})
        init_person = selected_person        
    else:
        print("No valid bids this round.")
        continue
        
    # time.sleep(3)

print("Game Over. Final Credits:", credits_left)