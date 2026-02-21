# Personal_builder Web UI

This folder now includes a **web app** that uses the same workflow as `run.py` (bidding simulation) with a browser UI.

## What was added (only in Personal_builder)

- **`server.py`** – FastAPI app: serves the UI and exposes `/api/history` and `/api/simulation/stream`.
- **`simulation_stream.py`** – Runs the same bidding loop as `run.py` but yields SSE events so the server can stream messages to the client.
- **`run_web.py`** – Entry point to start the web server (port 8001).
- **`static/`** – Frontend (same style as the backend app):
  - `index.html` – Single-page UI: sidebar (personas), conversation area, “Load history” and “Start simulation”.
  - `app.js` – Fetches history and consumes the simulation SSE stream.
  - `styles.css` – Matches the backend’s purple gradient and chat layout.
- **`requirements.txt`** – Dependencies for the web server and existing scripts (fastapi, uvicorn, anthropic, groq).

The **backend** folder is unchanged. Backend and Personal_builder remain separate.

## How to run the web app

From the **repo root**:

```bash
pip install -r Personal_builder/requirements.txt
python Personal_builder/run_web.py
```

Or from **Personal_builder**:

```bash
pip install -r requirements.txt
python run_web.py
```

Then open **http://localhost:8001**.

### API keys (fix 401 "invalid x-api-key")

The simulation uses **Anthropic** (Claude) and **Groq** (LLaMA). Keys are read from the environment (no hardcoded keys).

1. Create **`Personal_builder/.env`** (or put keys in repo root **`.env`**):
   ```bash
   ANTHROPIC_API_KEY=your_anthropic_key_here
   GROQ_API_KEY=your_groq_key_here
   ```
2. Get keys:
   - Anthropic: https://console.anthropic.com/
   - Groq: https://console.groq.com/keys

If you see **401 "invalid x-api-key"** when running the **backend** app (e.g. Profile voice interview or transcribe), that is **ElevenLabs**. Set **`ELEVENLABS_API_KEY`** in **`backend/.env`** (see backend README).

- **Load history** – Loads `conversational_history.txt` (from the parent of Personal_builder, i.e. repo root) and displays it.
- **Start simulation** – Runs the bidding loop and streams each new message in real time (same logic as `run.py`).

## CLI vs web

- **`run.py`** – Original CLI: run from `Personal_builder/` with `../conversational_history.txt` in the parent directory. Runs until everyone is out of credits.
- **Web** – Same simulation, streamed over SSE so the UI updates as each persona speaks. Uses the same history file and agent scripts.
