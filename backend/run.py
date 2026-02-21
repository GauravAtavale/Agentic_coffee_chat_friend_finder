"""
Final flow of Agentic Social Simulation:
"""
import random
import time
import re
import json
from pathlib import Path
import utils

# Paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = REPO_ROOT / "data" / "conversational_history.txt"
BACKEND_DIR = Path(__file__).resolve().parent

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
# init_person = "Gaurav_Atavale"
if not HISTORY_FILE.exists():
    raise FileNotFoundError(f"History file not found: {HISTORY_FILE}")
with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    lines = [ln.strip() for ln in f.readlines() if ln.strip()]  # Filter empty lines
if not lines:
    raise ValueError("History file is empty")
try:
    last_entry = json.loads(lines[-1])
    last_role = last_entry.get('role')
    if not last_role or last_role not in role_person_dict:
        # Default to first person if role not found
        init_person = list(person_role_dict.keys())[0]
        print(f"Warning: Role '{last_role}' not found in role_person_dict. Using default: {init_person}")
    else:
        init_person = role_person_dict[last_role]
except (json.JSONDecodeError, KeyError) as e:
    # Default to first person if parsing fails
    init_person = list(person_role_dict.keys())[0]
    print(f"Warning: Could not parse last line or find role. Using default: {init_person}. Error: {e}") 

credits_left = {key: 100 for key in person_role_dict.keys()}

# print("Initial credits:", credits_left)

while any(credits_left[key] > 0 for key in credits_left):
    
    # FIX: Generate random bid ONLY if credits > 0, else bid is 0
    random_numbers = {}
    for key in person_role_dict:
        if credits_left[key] > 0:
            try:
                # generate_bid_score_each_user outputs percentage likelihood. It has to be scaled by credit left. 
                llm_bid_score = utils.generate_bid_score_each_user(key, credits_left, "claude-3-5-sonnet-20240620")                
                random_numbers[key] = int(0.01 * float(json.loads(llm_bid_score)["score"]) * credits_left[key])  # Scale bid by credits left
                print("claude model worked. Bid score:", random_numbers[key])
            except:
                # generate_bid_score_each_user outputs percentage likelihood. It has to be scaled by credit left.
                llm_bid_score = utils.generate_bid_score_each_user(key, credits_left, "llama-3.1-8b-instant")
                random_numbers[key] = int(0.01 * float(json.loads(llm_bid_score)["score"]) * credits_left[key])
                print("llama model worked. Bid score:", random_numbers[key])
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