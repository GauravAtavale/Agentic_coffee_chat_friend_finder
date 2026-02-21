"""
Web server for Agentic Social: world_chat UI. Runs run.py on startup
and streams new lines from data/conversational_history.txt to the UI.
"""
import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# Set by main() before uvicorn runs; used in startup() to print UI URL
_PORT: int = 8002


def _available_port(start: int = 8002, max_tries: int = 10) -> int:
    """Return the first port in [start, start+max_tries) that is free to bind."""
    for i in range(max_tries):
        port = start + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
                return port
        except OSError:
            continue
    return start  # fallback, uvicorn will fail with clear error


def _free_port(port: int = 8002) -> None:
    """Kill any process listening on the given port."""
    try:
        out = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            for pid in out.stdout.strip().split():
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except (ProcessLookupError, ValueError, PermissionError):
                    pass
            time.sleep(2)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

# Load .env so subprocess run.py inherits ANTHROPIC_API_KEY, GROQ_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / "config" / ".env")  # config/.env first (primary API keys)
    load_dotenv(BASE_DIR / ".env")
    load_dotenv(BASE_DIR.parent / ".env")
except ImportError:
    pass

# Paths relative to repo root
REPO_ROOT = BASE_DIR.parent
DATA_DIR = REPO_ROOT / "data"
FRONTEND_DIR = REPO_ROOT / "frontend"
CONFIG_DIR = REPO_ROOT / "config"

# Channel -> history filename (under data/)
CHANNEL_FILES = {
    "world": "conversational_history.txt",
    "finance": "finance_convers_history.txt",
    "technology": "tech_convers_history.txt",
    "healthcare": "healthcare_convers_history.txt",
    "architecture": "architecture_convers_history.txt",
    "computer_science": "computer_science_convers_history.txt",
    "human": "human_convers_history.txt",
}

def _history_file_for_channel(channel: str) -> Path:
    """Resolve channel to absolute path of its history file; default to world if unknown."""
    filename = CHANNEL_FILES.get(channel, CHANNEL_FILES["world"])
    return (DATA_DIR / filename).resolve()

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Agentic Social – world_chat")

# One run.py process per channel (world, finance, technology, healthcare, architecture, computer_science)
SIMULATION_CHANNELS = [c for c in CHANNEL_FILES if c != "human"]
_run_processes: dict = {}


def _load_history(history_path: Path):
    """Return list of {role, content, timestamp} from the given history file."""
    if not history_path.exists():
        return []
    out = []
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    timestamp = entry.get("timestamp")
                    if not timestamp:
                        from datetime import datetime, timedelta
                        base_time = datetime.utcnow() - timedelta(seconds=len(lines) * 3)
                        timestamp = (base_time + timedelta(seconds=i * 3)).isoformat() + "Z"
                    out.append({
                        "role": entry.get("role", ""),
                        "content": entry.get("content", ""),
                        "timestamp": timestamp
                    })
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def _stream_new_lines(history_path: Path):
    """Generator: poll history_path and yield SSE only for new lines (since connection)."""
    try:
        if history_path.exists():
            with open(history_path, "r", encoding="utf-8") as f:
                last_count = sum(1 for ln in f if ln.strip())
        else:
            last_count = 0
    except OSError:
        last_count = 0
    while True:
        try:
            if history_path.exists():
                with open(history_path, "r", encoding="utf-8") as f:
                    lines = [ln.strip() for ln in f if ln.strip()]
                for i in range(last_count, len(lines)):
                    try:
                        entry = json.loads(lines[i])
                        from datetime import datetime
                        timestamp = entry.get("timestamp") or datetime.utcnow().isoformat() + "Z"
                        ev = {
                            "type": "message",
                            "role": entry.get("role", ""),
                            "content": entry.get("content", ""),
                            "timestamp": timestamp
                        }
                        yield f"data: {json.dumps(ev)}\n\n"
                    except json.JSONDecodeError:
                        pass
                last_count = len(lines)
        except OSError:
            pass
        time.sleep(0.5)


@app.get("/")
async def serve_index():
    """Serve the main UI (world_chat)."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return {"error": "Frontend files not found."}
    return FileResponse(
        index_path,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/history")
async def api_history(channel: str = "world"):
    """Return full conversation history for the given channel (world, finance, technology, healthcare, architecture, computer_science, human)."""
    path = _history_file_for_channel(channel)
    messages = _load_history(path)
    return JSONResponse(
        content={"messages": messages},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/history/stream")
async def api_history_stream(channel: str = "world"):
    """SSE: emit new messages as they are appended to the channel's history file."""
    path = _history_file_for_channel(channel)

    def gen():
        for chunk in _stream_new_lines(path):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/api/history/human")
async def api_human_message(request: Request):
    """Append a human user message to human_convers_history.txt and return it."""
    try:
        body = await request.json()
        content = (body.get("content") or body.get("text") or "").strip()
        if not content:
            return {"ok": False, "error": "content required"}
        path = _history_file_for_channel("human")
        path.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        entry = {
            "role": "Human",
            "content": content,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        line = json.dumps(entry) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
        return {"ok": True, "message": entry}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Profile display name -> internal user id for recommendation API
PROFILE_USER_IDS = {
    "Gaurav": "Gaurav_Atavale",
    "Anagha": "Anagha_Palandye",
    "Kanishkha": "Kanishkha_S",
    "Nirbhay": "Nirbhay_R",
}


def _run_recommendations_sync(profile_user_id: str):
    """Run blocking get_recommendations in a way safe for async."""
    from recommendation import get_recommendations
    return get_recommendations(profile_user_id)


@app.get("/api/recommendations")
async def api_get_recommendations():
    """Return last saved recommendations from data/recommendations.json (for quick display or fallback)."""
    rec_file = DATA_DIR / "recommendations.json"
    if not rec_file.exists():
        return {"recommendations": []}
    try:
        data = json.loads(rec_file.read_text(encoding="utf-8"))
        return data
    except Exception:
        return {"recommendations": []}


@app.post("/api/recommendations")
async def api_recommendations(request: Request):
    """Generate coffee-chat recommendations for the selected profile. Body: { \"user\": \"Gaurav\" } or internal id."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    profile = (body.get("user") or "").strip() or "Gaurav"
    profile_user_id = PROFILE_USER_IDS.get(profile) or profile
    try:
        result = await asyncio.to_thread(_run_recommendations_sync, profile_user_id)
        return result
    except Exception as e:
        return JSONResponse(content={"error": str(e), "recommendations": []}, status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok"}


AIRIA_PIPELINE_URL = "https://api.airia.ai/v2/PipelineExecution/86bb5ef8-4810-448e-b0ef-78eb822b79fd"
EMAIL_IDS_PATH = DATA_DIR / "email_ids.json"


def _key_to_persona_name(key: str) -> str:
    """Convert key (e.g. anagha_palandye) to persona name (e.g. Anagha_Palandye)."""
    if not key or not key.strip():
        return ""
    parts = key.strip().lower().split("_")
    return "_".join(p.capitalize() for p in parts)


def _load_email_ids() -> dict:
    """Load data/email_ids.json; return dict of persona name -> email (supports array or single object)."""
    if not EMAIL_IDS_PATH.exists():
        return {}
    try:
        data = json.loads(EMAIL_IDS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return dict(data[0])
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _email_for_key(key: str) -> str | None:
    """Resolve key (e.g. anagha_palandye) to email from data/email_ids.json, then persona JSON fallback."""
    if not key or not key.strip():
        return None
    persona_name = _key_to_persona_name(key)
    email_ids = _load_email_ids()
    email = email_ids.get(persona_name)
    if email:
        return email
    # Case-insensitive match (e.g. Kanishkha_s in JSON vs Kanishkha_S from key)
    persona_lower = persona_name.lower()
    for name, addr in email_ids.items():
        if name.lower() == persona_lower:
            return addr
    # Try without last segment for names like Nirbhay_R -> Nirbhay
    if "_" in persona_name:
        short = persona_name.rsplit("_", 1)[0]
        email = email_ids.get(short)
        if email:
            return email
    return _email_for_recommended_key(key)


def _format_date_ymd(ymd: str) -> str:
    """Convert YYYY-MM-DD to e.g. February 21, 2026."""
    if not ymd or len(ymd) < 10:
        return ymd
    try:
        y, m, d = int(ymd[:4]), int(ymd[5:7]), int(ymd[8:10])
        from datetime import date
        dt = date(y, m, d)
        return dt.strftime("%B %d, %Y")
    except (ValueError, TypeError):
        return ymd


# Eastern Time (New York): EST is UTC-5. Pipeline/Calendar often treat prompt time as UTC,
# so we convert Eastern -> UTC and send UTC in the prompt so the event shows at the right local time.
EST_UTC_OFFSET_HOURS = 5


def _format_time_hm(hm: str, include_tz: bool = True) -> str:
    """Format HH:MM (24h) as Eastern time, then convert to UTC and return UTC time for the prompt.
    The UI sends times in Eastern; the pipeline creates at the time we send. Sending UTC ensures
    the created event displays as the selected Eastern time (e.g. 6 PM Eastern)."""
    if not hm or ":" not in hm:
        return hm
    try:
        part = hm.strip().split(":")
        h, m = int(part[0]), int(part[1]) if len(part) > 1 else 0
        if h < 0 or h > 23 or m < 0 or m > 59:
            return hm
        # Treat input as Eastern; convert to UTC for the prompt so calendar shows correct Eastern time
        h_utc = (h + EST_UTC_OFFSET_HOURS) % 24
        if h_utc == 0:
            s = f"12:{m:02d} AM"
        elif h_utc < 12:
            s = f"{h_utc}:{m:02d} AM"
        elif h_utc == 12:
            s = f"12:{m:02d} PM"
        else:
            s = f"{h_utc - 12}:{m:02d} PM"
        if include_tz:
            s += " UTC (create the event at this UTC time; it will display as the selected time in Eastern Time, New York)"
        return s
    except (ValueError, TypeError, IndexError):
        return hm


def _build_meet_prompt(
    title: str,
    date: str,
    time: str,
    location: str = "",
    description: str = "",
    attendees: str = "",
    organizer: str = "",
    status: str = "Confirmed",
) -> str:
    """Build the userInput prompt string for Airia create-meet pipeline. Time is sent in UTC so the event displays correctly in Eastern (New York)."""
    parts = [
        "Create a Google Calendar invite with the following details. The Time field is in UTC; create the event at that exact UTC time so it shows correctly for attendees in Eastern Time (New York).",
        f"Send from (organizer): {organizer}",
        f"Title: {title}",
        f"Date: {date}",
        f"Time: {time}",
    ]
    if location:
        parts.append(f"Location: {location}")
    if description:
        parts.append(f"Description: {description}")
    if attendees:
        parts.append(f"Attendee(s): {attendees}")
    if status:
        parts.append(f"Status: {status}")
    return ". ".join(parts)


def _email_for_recommended_key(key: str) -> str | None:
    """Resolve recommended_key (e.g. anagha_palandye) to email from data/Anagha_Palandye.json."""
    if not key or not key.strip():
        return None
    # anagha_palandye -> Anagha_Palandye
    parts = key.strip().lower().split("_")
    persona_name = "_".join(p.capitalize() for p in parts)
    path = DATA_DIR / f"{persona_name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data and isinstance(data[0], dict):
            profile = data[0].get("profile") or {}
            return profile.get("email") or None
        if isinstance(data, dict):
            # Top-level email (flat persona) or nested profile.email
            if data.get("email"):
                return data["email"]
            profile = data.get("profile") or {}
            if isinstance(profile, dict) and profile.get("email"):
                return profile["email"]
    except (json.JSONDecodeError, OSError):
        pass
    return None


@app.post("/api/create-meet")
async def api_create_meet(request: Request):
    """Create a Google Meet/Calendar invite via Airia pipeline. Body: title, date, time, viewer_key? (profile selected in UI = organizer/from email, from data/email_ids.json), recommended_key? (attendee), location?, description?, attendee?."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    title = (body.get("title") or "Coffee chat").strip()
    date_ymd = (body.get("date_ymd") or "").strip()
    time_hm = (body.get("time_hm") or "").strip()
    date_str = (body.get("date") or "").strip()
    time_str = (body.get("time") or "").strip()
    if date_ymd and time_hm:
        date_str = _format_date_ymd(date_ymd)
        time_str = _format_time_hm(time_hm)
    location = (body.get("location") or "Virtual").strip()
    description = (body.get("description") or "Coffee chat").strip()
    recommended_key = (body.get("recommended_key") or "").strip()
    viewer_key = (body.get("viewer_key") or "").strip()
    if not date_str or not time_str:
        return JSONResponse(
            content={"ok": False, "error": "date and time are required (send date_ymd and time_hm from the UI)"},
            status_code=400,
        )
    # Organizer = email of the profile selected in UI (viewer); from data/email_ids.json
    organizer = (body.get("organizer") or "").strip()
    if not organizer and viewer_key:
        organizer = _email_for_key(viewer_key) or ""
    if not organizer:
        return JSONResponse(
            content={
                "ok": False,
                "error": "Could not determine organizer email. Ensure the selected profile has an email in data/email_ids.json and that viewer_key is sent.",
            },
            status_code=400,
        )
    # Participants = both viewer (profile selected) and recommended (person clicked in slider)
    viewer_email = _email_for_key(viewer_key) or _email_for_recommended_key(viewer_key) if viewer_key else ""
    recommended_email = _email_for_key(recommended_key) or _email_for_recommended_key(recommended_key) if recommended_key else ""
    attendees_list = [e for e in (viewer_email, recommended_email) if e]
    if not attendees_list:
        attendees_list = [organizer]
    attendees_str = ", ".join(attendees_list)
    user_input = _build_meet_prompt(
        title=title,
        date=date_str,
        time=time_str,
        location=location,
        description=description,
        attendees=attendees_str,
        organizer=organizer,
    )
    api_key = os.environ.get("AIRIA_API_KEY", "").strip()
    if not api_key:
        return JSONResponse(
            content={"ok": False, "error": "AIRIA_API_KEY not configured"},
            status_code=503,
        )
    try:
        import requests
    except ImportError:
        return JSONResponse(
            content={"ok": False, "error": "requests not installed"},
            status_code=503,
        )
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {"userInput": user_input, "asyncOutput": False}
    try:
        r = requests.post(AIRIA_PIPELINE_URL, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        result = r.json()
        return JSONResponse(content={"ok": True, "message": "Meet created", "response": result})
    except requests.exceptions.RequestException as e:
        err_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                err_msg = e.response.text or err_msg
            except Exception:
                pass
        return JSONResponse(
            content={"ok": False, "error": err_msg},
            status_code=502,
        )


# Serve recommended_profile UI (must be before mount so route takes precedence)
RECOMMENDED_PROFILE_DIR = REPO_ROOT / "recommended_profile"
_recommended_profile_index = RECOMMENDED_PROFILE_DIR / "index.html"


@app.get("/recommended_profile")
@app.get("/recommended_profile/")
async def serve_recommended_profile():
    """Serve the recommended profile page (viewer/recommended via query params)."""
    if not _recommended_profile_index.exists():
        return JSONResponse(content={"detail": "Not Found"}, status_code=404)
    return FileResponse(
        _recommended_profile_index,
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
# Mount static assets under /recommended_profile/ (e.g. /recommended_profile/foo.js) - index is served by route above
if RECOMMENDED_PROFILE_DIR.exists():
    app.mount("/recommended_profile", StaticFiles(directory=str(RECOMMENDED_PROFILE_DIR), html=True), name="recommended_profile")
if DATA_DIR.exists():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")
OUTPUTS_DIR = REPO_ROOT / "outputs"
if OUTPUTS_DIR.exists():
    app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")
PROFILE_PICTURES_DIR = REPO_ROOT / "profile_pictures"
PROFILE_PICTURES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/profile_pictures", StaticFiles(directory=str(PROFILE_PICTURES_DIR)), name="profile_pictures")


def _ensure_history_file_exists(channel: str):
    """Ensure the channel's history file exists with at least one line so run.py can read last speaker."""
    path = _history_file_for_channel(channel)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"role": "Gaurav", "content": "Conversation started."}\n')
        print(f"Created seed line for channel: {channel}")


def _start_run_py_for_channel(channel: str):
    """Start run.py for one channel in the background (bidding + agents write to that channel's history file)."""
    global _run_processes
    if channel in _run_processes and _run_processes[channel].poll() is None:
        return
    run_py = BASE_DIR / "run.py"
    if not run_py.exists():
        print("Warning: run.py not found, skipping auto-start")
        return
    _ensure_history_file_exists(channel)
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, str(run_py), "--channel", channel],
        cwd=str(BASE_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    _run_processes[channel] = proc

    def log_stderr():
        if proc.stderr:
            for line in iter(proc.stderr.readline, ""):
                if line:
                    sys.stderr.write("[run.py %s] " % channel + line.decode("utf-8", errors="replace"))
            proc.stderr.close()

    t = threading.Thread(target=log_stderr, daemon=True)
    t.start()
    print("Started run.py for channel '%s' (PID %s)." % (channel, proc.pid))


@app.on_event("startup")
async def startup():
    global _PORT
    for ch in SIMULATION_CHANNELS:
        _start_run_py_for_channel(ch)
    print("Agentic Social – world_chat")
    print(f"  UI: http://localhost{'' if _PORT == 80 else ':' + str(_PORT)}")
    print("  One run.py per tab (world, finance, technology, healthcare, architecture, computer_science); each stream updates its tab.")


def main():
    global _PORT
    import argparse
    parser = argparse.ArgumentParser(description="Agentic Social world_chat server")
    parser.add_argument("--free-port", action="store_true", help="Kill process on port 8002 before starting")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: first free from 8002)")
    args = parser.parse_args()
    if args.free_port:
        _free_port(8002)
    _PORT = args.port if args.port is not None else _available_port(8002)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=_PORT)


if __name__ == "__main__":
    main()
