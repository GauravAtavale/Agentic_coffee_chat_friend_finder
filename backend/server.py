"""
Web server for Agentic Social: world_chat UI. Runs run.py on startup
and streams new lines from data/conversational_history.txt to the UI.
"""
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


@app.get("/health")
async def health():
    return {"status": "ok"}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


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
    args = parser.parse_args()
    if args.free_port:
        _free_port(8002)
    _PORT = _available_port(8002)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=_PORT)


if __name__ == "__main__":
    main()
