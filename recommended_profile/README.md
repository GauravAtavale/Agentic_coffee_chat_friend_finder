# Recommended Profile + Let's Meet (standalone)

Standalone page that shows a recommended friend’s profile (from a match `.md` file) and, after **Let's meet**, a calendar of available slots.

## How to run

From the **repo root** (`Agentic_coffee_chat_friend_finder/`):

```bash
python -m http.server 8000
```

Then open: **http://localhost:8000/recommended_profile/**

Optional query params:

- `?viewer=anagha_palandye&recommended=gaurav_atavale` — loads `outputs/match_anagha_palandye_gaurav_atavale.md` and `outputs/available_slots_anagha_palandye_gaurav_atavale.json`. Defaults are the same if omitted.

## Flow

1. **Profile** — Renders the match guide (what you can learn from them, what they can learn from you, conversation preview).
2. **Let's meet** — Reveals the calendar section.
3. **Calendar** — Month grid; dates with availability are clickable. Click a date to see time slots, pick one, then **Confirm meet**.

If the page is opened as a file or `outputs/` isn’t served, embedded sample data (Anagha ↔ Gaurav) is used so the page still works.

## Integration later

- Serve `recommended_profile/` and `outputs/` from `run_web` (e.g. static mounts or routes).
- Replace the **Confirm meet** alert with an API call to book the chosen slot.
