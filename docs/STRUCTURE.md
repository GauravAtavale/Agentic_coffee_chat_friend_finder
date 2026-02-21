# Repository Structure

This document describes the reorganized structure of the Agentic Social repository.

## Directory Layout

```
Agentic_social/
├── backend/              # Backend server and simulation logic
│   ├── server.py        # FastAPI web server (world_chat UI)
│   ├── run.py           # Main simulation loop (bidding + agents)
│   ├── run_web.py       # Entry point to start web server
│   ├── utils.py         # LLM helpers (Anthropic, Groq)
│   ├── simulation_stream.py  # Streaming simulation for web
│   ├── agent_*.py       # Individual persona scripts (4 files)
│   ├── basic_agent.py   # Legacy agent implementation
│   ├── persona_prompt_builder.py  # Utility to build prompts
│   └── requirements.txt # Backend dependencies
│
├── frontend/            # Web UI (static files)
│   ├── index.html       # world_chat interface
│   ├── app.js           # SSE client for live updates
│   └── styles.css       # Styling
│
├── scripts/             # Utility scripts
│   ├── run_questions.py # Voice interview (ElevenLabs TTS/STT)
│   └── run_old_personal_builder.py  # Legacy simulation
│
├── config/              # Configuration files
│   ├── sys_prompt.txt   # System prompt for agents
│   ├── bidding_sys_prompt.txt  # Bidding prompt template
│   ├── *_persona_prompt.txt    # Per-persona prompts (4 files)
│   └── .env.example     # Environment variables template
│
├── data/                # Data files
│   ├── conversational_history.txt  # Conversation log (one JSON per line)
│   ├── *_*.json         # Persona data files (4 files)
│   └── old_convo.txt    # Legacy conversation
│
├── docs/                # Documentation
│   ├── README.md        # Original project README
│   ├── README_WEB.md    # Web UI documentation
│   ├── QUESTIONS.md     # Interview questions
│   ├── STRUCTURE.md     # This file
│   └── *.ipynb          # Jupyter notebooks
│
├── requirements.txt     # Root-level Python dependencies
├── .gitignore          # Git ignore rules
└── README.md           # Main project README
```

## Key Changes from Previous Structure

### Before
- `Personal_builder/` contained everything (server, agents, static files, config, data)
- `backend/` did not exist
- Root-level files mixed with code

### After
- **`backend/`**: All server and simulation code
- **`frontend/`**: Static web UI files
- **`scripts/`**: Utility scripts (voice interview, etc.)
- **`config/`**: Configuration files (prompts, .env examples)
- **`data/`**: Data files (conversation history, persona JSONs)
- **`docs/`**: All documentation

## Path Updates

All code has been updated to use the new structure:

- **History file**: `data/conversational_history.txt` (was `../conversational_history.txt`)
- **Config files**: `config/*.txt` (was `./*.txt` in Personal_builder)
- **Frontend**: `frontend/` (was `Personal_builder/static/`)
- **Server**: `backend/server.py` (was `Personal_builder/server.py`)

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Set API keys in config/.env
# ANTHROPIC_API_KEY=...
# GROQ_API_KEY=...

# Run web server
python backend/run_web.py --free-port

# Or run CLI simulation
cd backend
python run.py
```

## Notes

- The `backup_old/` folder is preserved and untouched.
- All import paths have been updated to use the new structure.
- Environment variables are loaded from `config/.env` or repo root `.env`.
