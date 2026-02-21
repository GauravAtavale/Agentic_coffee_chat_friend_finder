"""
Coffee Chat Profile Matcher (Agentic data only)
================================================
Uses only profiles under Agentic_coffee_chat_friend_finder/data/:
  Anagha_Palandye.json, Gaurav_Atavale.json, Kanishkha_S.json, Nirbhay_R.json

For one profile ("you"), matches with all other profiles and produces a summary:
  1. What you can learn from the other person
  2. What they can learn from you
  3. A simulated conversation preview between both

Usage:
  python profile_matcher.py --user anagha_palandye   # You = Anagha, match with everyone else
  python profile_matcher.py --user gaurav_atavale    # You = Gaurav, match with everyone else
  python profile_matcher.py --user anagha_palandye --other gaurav_atavale  # Single pair
  python profile_matcher.py --list                   # List profiles

Requires: pip install anthropic rich; export ANTHROPIC_API_KEY="..."
"""

import os
import sys
import json
import argparse
import textwrap
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("❌  pip install anthropic")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.table import Table
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

BASE_DIR = Path(__file__).resolve().parent
AGENTIC_DATA_DIR = BASE_DIR / "Agentic_coffee_chat_friend_finder" / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

# Only these 4 files under agentic*/data
AGENTIC_PROFILE_FILES = [
    "Anagha_Palandye.json",
    "Gaurav_Atavale.json",
    "Kanishkha_S.json",
    "Nirbhay_R.json",
]

PROFILE_ALIASES = {
    "anagha": "anagha_palandye",
    "gaurav": "gaurav_atavale",
    "kanishkha": "kanishkha_s",
    "nirbhay": "nirbhay_r",
}


def _stem_to_key(stem: str) -> str:
    """Anagha_Palandye -> anagha_palandye, Kanishkha_S -> kanishkha_s."""
    return stem.replace(" ", "_").lower()


def _load_json(path: Path, default=None):
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _format_value(v, indent: int = 0) -> list[str]:
    """Format any value to markdown lines; no fields omitted."""
    prefix = "  " * indent
    lines = []
    if v is None:
        return [f"{prefix}-"]
    if isinstance(v, bool):
        return [f"{prefix}{v}"]
    if isinstance(v, (int, float, str)):
        return [f"{prefix}{v}"]
    if isinstance(v, list):
        for i, item in enumerate(v):
            if isinstance(item, dict):
                lines.append(f"{prefix}- **Entry {i + 1}:**")
                lines.extend(_format_value(item, indent + 1))
            elif isinstance(item, list):
                lines.extend(_format_value(item, indent))
            else:
                lines.append(f"{prefix}- {item}")
        return lines
    if isinstance(v, dict):
        for k, val in v.items():
            label = k.replace("_", " ").replace("-", " ").title()
            if isinstance(val, (dict, list)) and val:
                lines.append(f"{prefix}**{label}:**")
                lines.extend(_format_value(val, indent + 1))
            else:
                lines.append(f"{prefix}**{label}:** {val}")
        return lines
    return [f"{prefix}{v}"]


def build_profile_summary(profile: dict) -> str:
    """Full profile (agentic only) as markdown."""
    name = (profile.get("profile") or {}).get("fullName") or (profile.get("name")) or "Unknown"
    lines = [f"# {name}\n", "\n## Profile (full)\n"]
    lines.extend(_format_value(profile, 0))
    return "\n".join(lines).replace("\n\n\n", "\n\n")


def load_profiles() -> dict[str, dict]:
    """Load only the 4 Agentic data files; each profile = full JSON (no LinkedIn/GitHub)."""
    profiles = {}
    for filename in AGENTIC_PROFILE_FILES:
        path = AGENTIC_DATA_DIR / filename
        raw = _load_json(path)
        if raw is None:
            continue
        if isinstance(raw, list) and len(raw) > 0:
            data = raw[0]
        elif isinstance(raw, dict):
            data = raw
        else:
            continue
        key = _stem_to_key(path.stem)
        name = (data.get("profile") or {}).get("fullName") or data.get("name") or key.replace("_", " ").title()
        profiles[key] = {"name": name, "agentic": data}
    return profiles


def _resolve_key(key: str, profiles: dict) -> str:
    key = key.strip().lower()
    if key in profiles:
        return key
    if key in PROFILE_ALIASES:
        c = PROFILE_ALIASES[key]
        if c in profiles:
            return c
    return key


def call_claude(system: str, user_prompt: str, max_tokens: int = 4096) -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌  ANTHROPIC_API_KEY not set (e.g. in .env).")
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return msg.content[0].text


def generate_match_summary(user_profile: dict, other_profile: dict) -> str:
    """One summary with: what you can learn from them, what they learn from you, conversation preview."""
    user_summary = build_profile_summary(user_profile["agentic"])
    other_summary = build_profile_summary(other_profile["agentic"])
    user_name = user_profile["name"]
    other_name = other_profile["name"]

    system = textwrap.dedent("""\
        You are an expert coffee-chat facilitator. Given two person profiles (from a social app),
        produce a single Markdown document with exactly THREE sections. Be specific and use details
        from the profiles (interests, professional background, values, communication style, etc.).
        Use clean Markdown headings and bullets.""")

    prompt = textwrap.dedent(f"""\
        ## Your profile (YOU)
        {user_summary}

        ---

        ## Other person's profile (THEM)
        {other_summary}

        ---

        Write ONE document with these three sections:

        ### 1. What you can learn from them
        Based on THEIR profile, list 4–6 specific things YOU could learn or gain from this person
        (skills, perspective, interests, experience). Be concrete.

        ### 2. What they can learn from you
        Based on YOUR profile, list 4–6 specific things THEY could learn or gain from you.
        Be concrete.

        ### 3. Simulated conversation preview
        Write a short, realistic coffee-chat conversation (10–14 exchanges) between you and them.
        Use their actual names. Format as:
        **{user_name}:** ...
        **{other_name}:** ...
        Make it warm and specific to their profiles (shared interests, professional overlap, values).""")

    return call_claude(system, prompt, max_tokens=4096)


def display_rich(title: str, content: str, style: str = "cyan"):
    if HAS_RICH:
        Console(width=100).print()
        Console(width=100).print(Panel(Markdown(content), title=title, border_style=style, padding=(1, 2)))
        Console(width=100).print()
    else:
        print(f"\n{'='*80}\n  {title}\n{'='*80}\n{content}\n{'='*80}\n")


def save_output(filename: str, content: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(
        description="☕ Profile match (Agentic data only): one profile with all others",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          python profile_matcher.py --user anagha_palandye     # Anagha vs everyone
          python profile_matcher.py --user gaurav              # Gaurav vs everyone
          python profile_matcher.py --user anagha --other gaurav   # Single pair
          python profile_matcher.py --list
          python profile_matcher.py --user anagha --save       # Save each summary to outputs/
        """)
    )
    parser.add_argument("--user", default="anagha_palandye", help="Your profile (you match with others)")
    parser.add_argument("--other", default=None, help="If set, only match with this one profile")
    parser.add_argument("--list", action="store_true", help="List profiles")
    parser.add_argument("--save", action="store_true", help="Save summaries to outputs/")
    args = parser.parse_args()

    profiles = load_profiles()
    if not profiles:
        print("❌ No profiles found under Agentic_coffee_chat_friend_finder/data/")
        print("   Expected: Anagha_Palandye.json, Gaurav_Atavale.json, Kanishkha_S.json, Nirbhay_R.json")
        sys.exit(1)

    user_key = _resolve_key(args.user, profiles)
    if user_key not in profiles:
        print(f"❌ Profile '{args.user}' not found. Use --list.")
        sys.exit(1)

    if args.list:
        print("\n📋 Profiles (Agentic data only):")
        print("-" * 50)
        for key in sorted(profiles.keys()):
            name = profiles[key]["name"]
            print(f"  • {key:20s} → {name}")
        print(f"\n  Use: --user <key> to match that profile with all others (or --other <key> for one pair).\n")
        return

    # Who to match with
    if args.other:
        other_key = _resolve_key(args.other, profiles)
        if other_key not in profiles:
            print(f"❌ Profile '{args.other}' not found. Use --list.")
            sys.exit(1)
        if user_key == other_key:
            print("❌ --user and --other must be different.")
            sys.exit(1)
        others = [other_key]
    else:
        others = [k for k in profiles if k != user_key]
        if not others:
            print("❌ No other profiles to match with.")
            sys.exit(1)

    user_profile = profiles[user_key]
    user_name = user_profile["name"]

    if HAS_RICH:
        Console(width=100).print(Panel(
            f"[bold]☕ Profile match: [cyan]{user_name}[/cyan] with {len(others)} other(s)[/bold]",
            border_style="green", padding=(1, 2)
        ))
    else:
        print(f"\n☕ Profile match: {user_name} with {', '.join(others)}\n")

    for other_key in others:
        other_profile = profiles[other_key]
        other_name = other_profile["name"]
        print(f"🔍 Matching {user_name} ↔ {other_name}...")
        summary = generate_match_summary(user_profile, other_profile)
        display_rich(f"Summary: {user_name} ↔ {other_name}", summary, style="green")
        if args.save:
            path = save_output(f"match_{user_key}_{other_key}.md", summary)
            print(f"✅ Saved: {path}")

    if HAS_RICH and len(others) > 1:
        tips = Table(box=box.ROUNDED, title="💡 Next steps", show_header=False, border_style="yellow")
        tips.add_column(style="bold yellow", width=4)
        tips.add_column(style="white")
        tips.add_row("1.", "Use --save to write each summary to outputs/")
        tips.add_row("2.", "Use --other <key> to match with a single person only")
        Console(width=100).print(tips)
        Console(width=100).print()


if __name__ == "__main__":
    main()
