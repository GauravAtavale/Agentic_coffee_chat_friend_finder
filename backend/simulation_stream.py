"""
Streaming version of the run.py simulation for the web UI.
Yields SSE-style events (message_start, message_end, done, error) so the server can stream to the client.
Uses the same utils and agent scripts as run.py.
"""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
HISTORY_FILE = REPO_ROOT / "data" / "conversational_history.txt"
CONFIG_DIR = REPO_ROOT / "config"

# Same as run.py
PERSON_ROLE = {
    "Gaurav_Atavale": "Gaurav",
    "Anagha_Palandye": "Anagha",
    "Kanishkha_S": "Kanishkha",
    "Nirbhay_R": "Nirbhay",
}
ROLE_PERSON = {v: k for k, v in PERSON_ROLE.items()}
FILE_NAMES = {
    "Gaurav_Atavale": BACKEND_DIR / "agent_Gaurav.py",
    "Anagha_Palandye": BACKEND_DIR / "agent_Anagha.py",
    "Kanishkha_S": BACKEND_DIR / "agent_Kanishkha.py",
    "Nirbhay_R": BACKEND_DIR / "agent_Nirbhay.py",
}
INITIAL_CREDITS = 100
BID_MODEL_PRIMARY = "claude-3-5-sonnet-20240620"
BID_MODEL_FALLBACK = "llama-3.1-8b-instant"


def _ensure_history_file():
    """Ensure history file exists with at least one line so we can derive init_person."""
    if not HISTORY_FILE.exists() or HISTORY_FILE.stat().st_size == 0:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        first_person = list(PERSON_ROLE.keys())[0]
        role = PERSON_ROLE[first_person]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps({"role": role, "content": "Conversation started."}) + "\n")


def _read_last_speaker():
    """Return (person_key, credits_dict) for current state."""
    _ensure_history_file()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return list(PERSON_ROLE.keys())[0], {k: INITIAL_CREDITS for k in PERSON_ROLE}
    try:
        last = json.loads(lines[-1].strip())
        role = last.get("role", "").strip()
        init_person = ROLE_PERSON.get(role)
    except (json.JSONDecodeError, TypeError):
        init_person = None
    if init_person is None:
        init_person = list(PERSON_ROLE.keys())[0]
    credits = {k: INITIAL_CREDITS for k in PERSON_ROLE}
    return init_person, credits


def _read_last_message_line():
    """Read the last line of the history file (the message just appended by an agent)."""
    if not HISTORY_FILE.exists():
        return None, None
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return None, None
    try:
        entry = json.loads(lines[-1].strip())
        return entry.get("role"), entry.get("content", "")
    except (json.JSONDecodeError, TypeError):
        return None, None


def run_simulation_stream(max_rounds=15, pause_seconds=0):
    """
    Generator that runs the bidding simulation and yields SSE-style dicts.
    Each yield is a dict with 'type' and other fields; the server will serialize as "data: {json}\n\n".
    Uses existing utils and exec(agent_*.py).
    """
    import time
    import utils

    orig_cwd = os.getcwd()
    try:
        os.chdir(BACKEND_DIR)
    except OSError:
        yield {"type": "error", "detail": "Could not change to backend directory"}
        return

    try:
        init_person, credits_left = _read_last_speaker()
        round_count = 0

        while round_count < max_rounds and any(credits_left[k] > 0 for k in credits_left):
            random_numbers = {}
            for key in PERSON_ROLE:
                if credits_left[key] > 0:
                    try:
                        llm_bid = utils.generate_bid_score_each_user(key, credits_left, BID_MODEL_PRIMARY)
                        random_numbers[key] = int(0.01 * float(json.loads(llm_bid)["score"]) * credits_left[key])
                    except Exception:
                        try:
                            llm_bid = utils.generate_bid_score_each_user(key, credits_left, BID_MODEL_FALLBACK)
                            random_numbers[key] = int(0.01 * float(json.loads(llm_bid)["score"]) * credits_left[key])
                        except Exception:
                            random_numbers[key] = 0
                else:
                    random_numbers[key] = 0

            if all(v == 0 for v in random_numbers.values()):
                break

            selected_person = max(random_numbers, key=random_numbers.get)
            winning_bid = random_numbers[selected_person]

            if winning_bid > 0 and selected_person != init_person:
                credits_left[selected_person] = max(0, credits_left[selected_person] - winning_bid)
                role = PERSON_ROLE[selected_person]
                agent_script = FILE_NAMES.get(selected_person)
                if not agent_script or not agent_script.exists():
                    round_count += 1
                    continue
                yield {"type": "message_start", "speaker": role}
                try:
                    with open(agent_script, "r") as f:
                        exec(f.read(), {"REPO_ROOT": REPO_ROOT, "HISTORY_FILE": HISTORY_FILE, "__file__": str(agent_script)})
                except Exception as e:
                    yield {"type": "message_end", "speaker": role, "text": f"[Error: {e}]"}
                else:
                    _, text = _read_last_message_line()
                    yield {"type": "message_end", "speaker": role, "text": text or "(no response)"}
                init_person = selected_person
                round_count += 1
                if pause_seconds > 0 and round_count < max_rounds:
                    time.sleep(pause_seconds)
            elif selected_person == init_person:
                second = max((k for k in random_numbers if k != selected_person), key=random_numbers.get, default=None)
                if second is not None and random_numbers[second] > 0:
                    selected_person = second
                    winning_bid = random_numbers[selected_person]
                    credits_left[selected_person] = max(0, credits_left[selected_person] - winning_bid)
                    role = PERSON_ROLE[selected_person]
                    agent_script = FILE_NAMES.get(selected_person)
                    if agent_script and agent_script.exists():
                        yield {"type": "message_start", "speaker": role}
                        try:
                            with open(agent_script, "r") as f:
                                exec(f.read(), {"REPO_ROOT": REPO_ROOT, "HISTORY_FILE": HISTORY_FILE, "__file__": str(agent_script)})
                        except Exception as e:
                            yield {"type": "message_end", "speaker": role, "text": f"[Error: {e}]"}
                        else:
                            _, text = _read_last_message_line()
                            yield {"type": "message_end", "speaker": role, "text": text or "(no response)"}
                        init_person = selected_person
                        round_count += 1
                        if pause_seconds > 0 and round_count < max_rounds:
                            time.sleep(pause_seconds)
                else:
                    round_count += 1
            else:
                round_count += 1

        yield {"type": "done"}
    except Exception as e:
        yield {"type": "error", "detail": str(e)}
    finally:
        os.chdir(orig_cwd)
