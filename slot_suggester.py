"""
Coffee Chat – Suggest available slots for two people
====================================================
Uses availability/*.json (recurring weekly rules and/or explicit slots) to find
when both people are free, then suggests 1-hour coffee chat slots.

Usage:
  python slot_suggester.py --user anagha --other gaurav
  python slot_suggester.py --user anagha_palandye --other gaurav_atavale --days 14
  python slot_suggester.py --user anagha --other gaurav --save     # Save slots JSON for calendar UI
  python slot_suggester.py --user anagha --other gaurav --book 0   # Create .ics for first slot
  python slot_suggester.py --list

Availability files: availability/<profile_key>.json
See availability/README.md for format (recurring + optional explicit slots).
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
AVAILABILITY_DIR = BASE_DIR / "availability"
OUTPUT_DIR = BASE_DIR / "outputs"

PROFILE_ALIASES = {
    "anagha": "anagha_palandye",
    "gaurav": "gaurav_atavale",
    "kanishkha": "kanishkha_s",
    "nirbhay": "nirbhay_r",
}

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_TO_WEEKDAY = {d: i for i, d in enumerate(DAY_NAMES)}  # mon=0, ..., sun=6


def _resolve_key(key: str, keys: set) -> str:
    key = key.strip().lower()
    if key in keys:
        return key
    return PROFILE_ALIASES.get(key, key)


def _load_availability(profile_key: str) -> dict | None:
    path = AVAILABILITY_DIR / f"{profile_key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_time(s: str):
    """Parse 'HH:MM' -> (hour, minute)."""
    parts = s.strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return h, m


def _recurring_to_slots(recurring: list, from_date: datetime, days_ahead: int, slot_minutes: int = 30) -> set[datetime]:
    """Generate slot start datetimes from recurring rules. Slots are slot_minutes long."""
    slots = set()
    for rule in recurring:
        days = rule.get("days") or []
        start_str = rule.get("start") or "09:00"
        end_str = rule.get("end") or "17:00"
        sh, sm = _parse_time(start_str)
        eh, em = _parse_time(end_str)
        start_minutes = sh * 60 + sm
        end_minutes = eh * 60 + em

        weekday_set = {DAY_TO_WEEKDAY[d.lower()] for d in days if d.lower() in DAY_TO_WEEKDAY}

        for d in range(days_ahead):
            dt = from_date + timedelta(days=d)
            if dt.weekday() not in weekday_set:
                continue
            # Generate slots this day from start to end
            for m in range(start_minutes, end_minutes, slot_minutes):
                slot_start = dt.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0)
                if m + slot_minutes <= end_minutes:
                    slots.add(slot_start)
    return slots


def _explicit_slots(slot_strings: list) -> set[datetime]:
    out = set()
    for s in slot_strings:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            out.add(dt)
        except Exception:
            pass
    return out


def get_available_slots(profile_key: str, from_date: datetime, days_ahead: int, slot_minutes: int = 30) -> set[datetime]:
    """All available slot starts for this profile in the window."""
    data = _load_availability(profile_key)
    if not data:
        return set()

    slots = set()

    recurring = data.get("recurring") or []
    slots |= _recurring_to_slots(recurring, from_date, days_ahead, slot_minutes)

    explicit = data.get("slots") or []
    for s in explicit:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            if from_date <= dt < from_date + timedelta(days=days_ahead):
                slots.add(dt)
        except Exception:
            pass

    return slots


def suggest_slots(user_key: str, other_key: str, days_ahead: int = 14, slot_minutes: int = 30) -> list[datetime]:
    """Slots when both are available, sorted by datetime."""
    from_dt = datetime.now().replace(second=0, microsecond=0)
    user_slots = get_available_slots(user_key, from_dt, days_ahead, slot_minutes)
    other_slots = get_available_slots(other_key, from_dt, days_ahead, slot_minutes)
    common = user_slots & other_slots
    return sorted(common)


def write_ics(slot_start: datetime, duration_minutes: int, user_name: str, other_name: str, path: Path) -> None:
    """Write a single .ics calendar event for the coffee chat."""
    slot_end = slot_start + timedelta(minutes=duration_minutes)
    # ICS format: UTC or local without Z for compatibility
    def fmt(d: datetime) -> str:
        return d.strftime("%Y%m%dT%H%M%S")

    uid = f"coffee-chat-{slot_start.isoformat()}@profile-matcher"
    body = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Coffee Chat Slot Suggester//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{fmt(datetime.now())}
DTSTART:{fmt(slot_start)}
DTEND:{fmt(slot_end)}
SUMMARY:Coffee Chat – {user_name} & {other_name}
DESCRIPTION:Suggested slot from profile matcher.
END:VEVENT
END:VCALENDAR
"""
    path.write_text(body, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Suggest available coffee chat slots for two people",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python slot_suggester.py --user anagha --other gaurav
  python slot_suggester.py --user anagha --other gaurav --days 7
  python slot_suggester.py --user anagha --other gaurav --book 0
  python slot_suggester.py --list
        """,
    )
    parser.add_argument("--user", required=False, help="Your profile key (e.g. anagha_palandye or anagha)")
    parser.add_argument("--other", required=False, help="Other person's profile key")
    parser.add_argument("--days", type=int, default=14, help="Look ahead days (default 14)")
    parser.add_argument("--duration", type=int, default=30, help="Slot duration in minutes (default 30)")
    parser.add_argument("--list", action="store_true", help="List profiles that have availability files")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save suggested slots to outputs/ as JSON (for calendar UI)",
    )
    parser.add_argument(
        "--book",
        type=int,
        metavar="INDEX",
        default=None,
        help="Create .ics calendar event for the slot at this index (0-based)",
    )
    args = parser.parse_args()

    if args.list:
        if not AVAILABILITY_DIR.exists():
            print("No availability/ directory found.")
            return
        files = sorted(AVAILABILITY_DIR.glob("*.json"))
        print("\n📅 Profiles with availability:")
        for f in files:
            if f.name.startswith(".") or f.name.lower() == "readme.md":
                continue
            key = f.stem
            print(f"  • {key}")
        print(f"\n  Edit files in {AVAILABILITY_DIR}/ to set recurring or explicit slots.\n")
        return

    if not args.user or not args.other:
        parser.error("--user and --other are required (or use --list)")

    all_keys = {p.stem for p in AVAILABILITY_DIR.glob("*.json") if p.suffix == ".json"}
    user_key = _resolve_key(args.user, all_keys)
    other_key = _resolve_key(args.other, all_keys)

    if user_key not in all_keys:
        print(f"❌ No availability file for '{args.user}'. Add availability/{user_key}.json or use --list.")
        return
    if other_key not in all_keys:
        print(f"❌ No availability file for '{args.other}'. Add availability/{other_key}.json or use --list.")
        return

    slots = suggest_slots(user_key, other_key, days_ahead=args.days, slot_minutes=args.duration)

    if not slots:
        print(f"\n☕ No overlapping slots in the next {args.days} days for {user_key} and {other_key}.")
        print("   Update availability/*.json to add more free times.\n")
        return

    print(f"\n☕ Suggested coffee chat slots ({user_key} ↔ {other_key}, next {args.days} days):\n")
    for i, dt in enumerate(slots):
        print(f"  {i}. {dt.strftime('%a %Y-%m-%d %H:%M')}")

    if args.save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = {
            "user": user_key,
            "other": other_key,
            "duration_minutes": args.duration,
            "days_ahead": args.days,
            "slots": [dt.strftime("%Y-%m-%dT%H:%M") for dt in slots],
        }
        path = OUTPUT_DIR / f"available_slots_{user_key}_{other_key}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\n💾 Saved to {path} (use in calendar UI)")

    if args.book is not None:
        if args.book < 0 or args.book >= len(slots):
            print(f"\n❌ --book index must be 0 to {len(slots) - 1}.")
            return
        chosen = slots[args.book]
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ics_path = OUTPUT_DIR / f"coffee_chat_{user_key}_{other_key}_{chosen.strftime('%Y%m%d_%H%M')}.ics"
        write_ics(chosen, args.duration, user_key.replace("_", " ").title(), other_key.replace("_", " ").title(), ics_path)
        print(f"\n✅ Calendar event saved: {ics_path}")
        print("   Import into Google Calendar / Outlook / Apple Calendar.\n")
    else:
        print(f"\n💡 To create a calendar event for a slot: --book <index> (e.g. --book 0)\n")


if __name__ == "__main__":
    main()
