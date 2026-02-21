import re
import json
from pathlib import Path
import utils

# Get paths from globals if set by run.py, otherwise compute
REPO_ROOT = globals().get("REPO_ROOT", Path(__file__).resolve().parent.parent)
HISTORY_FILE = globals().get("HISTORY_FILE", REPO_ROOT / "data" / "conversational_history.txt")
CONFIG_DIR = REPO_ROOT / "config"

init_model = "claude-sonnet-4-5-20250929"
fallback_model = "llama-3.1-8b-instant"

# ================================== Get System Prompt ==================================

person_name = "Anagha_Palandye"
person_role_dict = {
    "Gaurav_Atavale": "Gaurav",
    "Anagha_Palandye": "Anagha",
    "Kanishkha_S": "Kanishkha",
    "Nirbhay_R": "Nirbhay"
    }
role = person_role_dict[person_name]

sys_prompt_path = CONFIG_DIR / "sys_prompt.txt"
persona_prompt_path = CONFIG_DIR / f"{person_name}_persona_prompt.txt"

with open(sys_prompt_path, "r", encoding="utf-8") as f:
    action_prompt = f.read()

with open(persona_prompt_path, "r", encoding="utf-8") as f:
    persona_prompt = f.read()

sys_prompt = persona_prompt + action_prompt

# ================================== Get conversation history ==================================
conversation_hist_format = utils.format_history_as_string(turns=10)

try:
    agent_resp = utils.agent_sim(init_model, sys_prompt, conversation_hist_format)
except:
    agent_resp = utils.agent_sim(fallback_model, sys_prompt, conversation_hist_format)

# Clean response 
agent_resp = re.sub(r"^[^:\n]+\s*:\s*", "", agent_resp, count=1)

# Create the JSON object
log_entry = json.dumps({"role": role, "content": agent_resp})

# Append to file
with open(HISTORY_FILE, "a", encoding="utf-8") as f:
    f.write(log_entry + "\n")
