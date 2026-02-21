import json
import os
import re
from pathlib import Path

# Paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = REPO_ROOT / "data" / "conversational_history.txt"
CONFIG_DIR = REPO_ROOT / "config"

# Load .env for API keys
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / "config" / ".env")
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

import anthropic
from groq import Groq


def read_recent_history(turns=10):
    if not HISTORY_FILE.exists():
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
        recent_history = [json.loads(line) for line in lines[-turns:] if line.strip()]  # Last 'turns' turns
    return recent_history


# def format_history_as_string(turns = 10):
#     formatted_string = ""
    
#     with open("../conversational_history.txt", "r", encoding="utf-8") as f:
#         lines = f.readlines()[-turns:]        
#         for line in lines:
#             entry = json.loads(line)
#             # Format: "Agent1: Hello\n"
#             formatted_string += f"{entry['role'].capitalize()}: {entry['content']}\n"
            
#     return formatted_string
def format_history_as_string(turns=10):
    formatted_string = ""
    
    try:
        if not HISTORY_FILE.exists():
            return "No history found."
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Take the last N lines
            lines = lines[-turns:]
            
            for line in lines:
                # 1. Strip whitespace
                line = line.strip()
                
                # 2. Skip if empty
                if not line:
                    continue
                
                try:
                    entry = json.loads(line)
                    role = entry.get('role', 'Unknown').capitalize()
                    content = entry.get('content', '')
                    formatted_string += f"{role}: {content}\n"
                except json.JSONDecodeError:
                    print(f"Skipping invalid JSON line: {line}")
                    continue
                    
    except FileNotFoundError:
        return "No history found."
            
    return formatted_string



def _get_anthropic_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it to config/.env or repo root .env")
    return key


def _get_groq_key():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise ValueError("GROQ_API_KEY not set. Add it to config/.env or repo root .env")
    return key


def agent_sim(model_LLM, plan_sys_prompt, user_query):
    if model_LLM.split("-")[0] == 'claude':
        client = anthropic.Anthropic(api_key=_get_anthropic_key())    
        response = client.messages.create(
            model=model_LLM,
            max_tokens=2048,
            temperature=1.0,  # Claude supports temperature
            system=plan_sys_prompt,  # System prompt goes here (not in messages)
            messages=[
                {
                    "role": "user",
                    "content": user_query
                }
            ]
        )
        return response.content[0].text

    elif model_LLM.split("-")[0] in ['llama', 'meta']:
        client = Groq(api_key=_get_groq_key())
        completion = client.chat.completions.create(
            model= model_LLM, #"llama-3.1-8b-instant", #"llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": plan_sys_prompt  # Your system prompt here
                },
                {
                "role": "user",
                "content": user_query          
                },
            ],
            temperature=1,
            max_completion_tokens=1024,
            top_p=1,
            stream=True,
            stop=None
        )

        response_content = ""
        for chunk in completion:
            chunk_content = chunk.choices[0].delta.content or ""
            response_content += chunk_content
            # print(chunk_content, end="")  # Optional: Still print to console if you want to see it live
        return response_content

def generate_bid_score_each_user(person_name, credits_left, model_LLM):
    """
    Generate bid score for a persona. Reads persona prompt and bidding prompt from config/.
    """
    persona_prompt_path = CONFIG_DIR / f"{person_name}_persona_prompt.txt"
    if not persona_prompt_path.exists():
        raise FileNotFoundError(f"Persona prompt not found: {persona_prompt_path}")
    with open(persona_prompt_path, "r", encoding="utf-8") as f:
        persona_prompt = f.read()
    
    conversation_hist_format = format_history_as_string(turns=10)
    
    bidding_prompt_path = CONFIG_DIR / "bidding_sys_prompt.txt"
    if not bidding_prompt_path.exists():
        raise FileNotFoundError(f"Bidding prompt not found: {bidding_prompt_path}")
    with open(bidding_prompt_path, "r", encoding="utf-8") as f:
        bidding_system_prompt = f.read()
    
    bidding_system_prompt = bidding_system_prompt.replace("||", str(credits_left[person_name]))
    
    # bidding_system_prompt = bidding_system_prompt + "\n\n" + "Persona: " + persona_prompt + "\n\n" + "Conversation History: \n" + conversation_hist_format
    plan_sys_prompt = bidding_system_prompt
    user_query = "Persona: " + persona_prompt + "\n\n" + "Conversation History: \n" + conversation_hist_format

    history = []
    history.append({"role": "user", "content": bidding_system_prompt})
    bid_score = agent_sim(model_LLM, plan_sys_prompt, user_query) #conversation(history)        
    # bid_scores[person_name] = bid_score

    return bid_score

    # bid_scores = {}
    # for person_name, person_role in person_role_dict.items():
    #     with open(f"{person_name}_persona_prompt.txt", "r") as f:
    #         persona_prompt = f.read()
        
    #     conversation_hist_format = format_history_as_string(turns = 10)
        
    #     with open(f"bidding_sys_prompt.txt", "r") as f:
    #         bidding_system_prompt = f.read()
        
    #     bidding_system_prompt = bidding_system_prompt.replace("||", str(credits_left[person_name]))
        
    #     # bidding_system_prompt = bidding_system_prompt + "\n\n" + "Persona: " + persona_prompt + "\n\n" + "Conversation History: \n" + conversation_hist_format
    #     plan_sys_prompt = bidding_system_prompt
    #     user_query = "Persona: " + persona_prompt + "\n\n" + "Conversation History: \n" + conversation_hist_format

    #     history = []
    #     history.append({"role": "user", "content": bidding_system_prompt})
    #     bid_score = agent_sim(model_LLM, plan_sys_prompt, user_query) #conversation(history)        
    #     bid_scores[person_name] = bid_score

    # return bid_scores
