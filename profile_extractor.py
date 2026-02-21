#!/usr/bin/env python3
"""
Simple profile extractor using Claude API (with web search).
No backend needed - just set ANTHROPIC_API_KEY and run this script.
"""

import base64
import datetime
import json
import os
import re
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # optional: pip install python-dotenv

# Set in .env or in your environment
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_VERSION = "2023-06-01"
# Optional: GitHub token raises rate limit from 60/hr to 5000/hr (create at https://github.com/settings/tokens)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
# Optional: ScrapeCreators API for LinkedIn (real profile data; get key at https://scrapecreators.com). If set, used instead of Claude.
SCRAPECREATORS_API_KEY = os.environ.get("SCRAPECREATORS_API_KEY")


def _username_from_github_url(url: str) -> str:
    """Extract username from GitHub URL (e.g. https://github.com/palandyeanagha -> palandyeanagha)."""
    url = url.rstrip("/")
    if "/" in url:
        return url.split("/")[-1]
    return url


# GitHub REST API: https://docs.github.com/en/rest/users?apiVersion=2022-11-28
GITHUB_API_VERSION = "2022-11-28"


def _github_headers():
    """Headers for GitHub API; use GITHUB_TOKEN if set to avoid rate limits (60 vs 5000/hr)."""
    h = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _fetch_readme_summary(owner: str, repo_name: str, headers: dict, max_chars: int = 500) -> str | None:
    """Fetch README for a repo and return a short summary (first max_chars of content). Returns None if no README."""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo_name}/readme",
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        content_b64 = data.get("content")
        if not content_b64:
            return None
        raw = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        # Strip markdown headers/images and collapse whitespace for a readable summary
        summary = raw.replace("\r\n", "\n").strip()
        summary = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", summary)  # remove images
        summary = re.sub(r"^#+\s*", "", summary, flags=re.MULTILINE)
        summary = re.sub(r"\n{2,}", "\n\n", summary).strip()
        if len(summary) > max_chars:
            summary = summary[: max_chars].rsplit(maxsplit=1)[0] + "…"
        return summary if summary else None
    except Exception:
        return None


def extract_github_via_api(github_url: str) -> dict:
    """Extract GitHub profile using the official GitHub API (no API key needed for public data)."""
    username = _username_from_github_url(github_url)
    print(f"\n🔍 Fetching GitHub profile via API: {username}")
    print("⏳ Please wait...\n")

    headers = _github_headers()
    resp = requests.get(
        f"https://api.github.com/users/{username}",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 404:
        raise ValueError(f"GitHub user not found: {username}")
    if resp.status_code == 403:
        msg = resp.json().get("message", resp.text) if resp.text else "Forbidden"
        if "rate limit" in msg.lower():
            raise ValueError(
                "GitHub API rate limit exceeded. Add GITHUB_TOKEN to .env (create at https://github.com/settings/tokens) for 5000 req/hr."
            )
    resp.raise_for_status()
    user = resp.json()

    # Fetch all repos (paginate)
    repos = []
    page = 1
    per_page = 100
    while True:
        repos_resp = requests.get(
            f"https://api.github.com/users/{username}/repos",
            params={"sort": "updated", "per_page": per_page, "page": page},
            headers=headers,
            timeout=30,
        )
        if repos_resp.status_code != 200:
            break
        chunk = repos_resp.json()
        if not chunk:
            break
        repos.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1

    def _repo_details(r, readme_summary=None):
        out = {
            "name": r.get("name"),
            "fullName": r.get("full_name"),
            "description": r.get("description") or "",
            "url": r.get("html_url"),
            "cloneUrl": r.get("clone_url"),
            "language": r.get("language") or "",
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "openIssues": r.get("open_issues_count", 0),
            "size": r.get("size"),
            "defaultBranch": r.get("default_branch"),
            "isFork": r.get("fork", False),
            "isArchived": r.get("archived", False),
            "createdAt": r.get("created_at"),
            "updatedAt": r.get("updated_at"),
            "pushedAt": r.get("pushed_at"),
            "topics": r.get("topics") or [],
            "homepage": r.get("homepage") or "",
            "license": r.get("license", {}).get("key") if r.get("license") else None,
            "visibility": r.get("visibility", "public"),
        }
        out["readmeSummary"] = readme_summary  # None if no README or fetch failed
        return out

    # Top languages from repos
    lang_counts = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    top_languages = [k for k, _ in sorted(lang_counts.items(), key=lambda x: -x[1])[:5]]

    # All repos with full details + README summary per repo
    public_repos = [r for r in repos if not r.get("private")]
    repositories = []
    for r in public_repos:
        owner = r.get("owner", {}).get("login", username)
        readme_summary = _fetch_readme_summary(owner, r.get("name", ""), headers)
        repositories.append(_repo_details(r, readme_summary))

    # Top repos by stars (summary, same shape as before)
    top_repos = sorted(
        public_repos,
        key=lambda x: x.get("stargazers_count", 0),
        reverse=True,
    )[:10]

    profile_data = {
        "name": user.get("name") or "",
        "username": user.get("login", username),
        "bio": user.get("bio") or "",
        "location": user.get("location") or "",
        "company": user.get("company") or "",
        "email": user.get("email") or "",
        "followers": user.get("followers"),
        "following": user.get("following"),
        "publicRepos": user.get("public_repos"),
        "topLanguages": top_languages,
        "repositories": repositories,
        "topRepositories": [
            {
                "name": r.get("name"),
                "description": r.get("description") or "",
                "language": r.get("language") or "",
                "stars": r.get("stargazers_count", 0),
            }
            for r in top_repos
        ],
        "skills": top_languages,
        "interests": [],
    }
    print("✅ GitHub data fetched successfully!")
    return profile_data


def _call_claude(prompt: str) -> dict:
    """Call Claude API with web search tool. Returns parsed JSON from response text."""
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. "
            "Set it in your environment: export ANTHROPIC_API_KEY='your-key'"
        )

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 3000,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    # Extract text content (model may also return tool_use blocks)
    text_content = ""
    if "content" in data:
        for item in data["content"]:
            if item.get("type") == "text":
                text_content += item.get("text", "")

    if not text_content.strip():
        raise ValueError(
            "No text in API response (model may have returned only tool_use). "
            "Try again or use a request without the web_search tool."
        )

    # Clean and parse JSON
    clean_json = text_content.replace("```json", "").replace("```", "").strip()
    start = clean_json.find("{")
    end = clean_json.rfind("}") + 1
    if start != -1 and end != 0:
        clean_json = clean_json[start:end]
    return json.loads(clean_json)


def extract_github(github_url: str) -> dict:
    """Extract GitHub profile data."""
    print(f"\n🔍 Extracting GitHub profile: {github_url}")
    print("⏳ Please wait 10-15 seconds...\n")

    prompt = f"""{github_url}

Search for this GitHub profile and extract ALL information.

Return ONLY a JSON object (no markdown, no explanation) with this structure:
{{
  "name": "full name",
  "username": "github username",
  "bio": "bio/description",
  "location": "location",
  "company": "company",
  "email": "email if public",
  "followers": "number",
  "following": "number",
  "publicRepos": "number",
  "topLanguages": ["language1", "language2", "language3"],
  "topRepositories": [
    {{"name": "repo", "description": "desc", "language": "lang", "stars": "count"}}
  ],
  "skills": ["skill1", "skill2"],
  "interests": ["interest1", "interest2"]
}}

Return ONLY valid JSON."""

    profile_data = _call_claude(prompt)
    print("✅ GitHub data extracted successfully!")
    return profile_data


def extract_linkedin(linkedin_url: str) -> dict:
    """Extract LinkedIn profile data using Claude with web search."""
    print(f"\n🔍 Extracting LinkedIn profile: {linkedin_url}")
    print("⏳ Please wait 10-15 seconds...\n")

    prompt = f"""Your task: find this LinkedIn profile and extract its data into a single JSON object.

Profile URL: {linkedin_url}

Instructions:
1. Use web search to find this LinkedIn profile. Search for the URL and also for the person's name + "LinkedIn" to find profile snippets, previews, and any cached or indexed text.
2. Prefer the most recent or current information when you see multiple versions (e.g. updated headline over older one).
3. Extract every field you can find. If a field is not available, use empty string "" or empty array [] — do not invent data.
4. Headline = the professional tagline that appears directly under the name on LinkedIn (e.g. "Data Scientist at X | ML Engineer").
5. About = the full "About" or "About me" section — the paragraph(s) the person wrote describing themselves. Include the complete text.
6. currentPosition = their current or most recent job (title, company, start date, short description).
7. education = list of schools/universities with degree, field, and year.
8. experience = list of past/current roles with title, company, duration, and description.
9. skills = list of skills listed or endorsed on the profile.
10. industry = their industry if shown.

Return ONLY a valid JSON object (no markdown code fence, no extra text) with exactly this structure:
{{
  "name": "full name",
  "headline": "professional headline under their name",
  "location": "city, region or country",
  "about": "full About/About me section text",
  "currentPosition": {{
    "title": "job title",
    "company": "company name",
    "startDate": "start date or Present",
    "description": "short role description"
  }},
  "education": [
    {{"school": "institution name", "degree": "degree", "field": "field of study", "year": "year or Present"}}
  ],
  "experience": [
    {{"title": "job title", "company": "company", "duration": "duration", "description": "description"}}
  ],
  "skills": ["skill1", "skill2"],
  "industry": "industry",
  "summary": "brief professional summary in 1-2 sentences, or same as about if that's all you have"
}}

Return ONLY valid JSON."""

    profile_data = _call_claude(prompt)
    print("✅ LinkedIn data extracted successfully!")
    return profile_data


# Override file for LinkedIn: paste your current headline & About me so exported data is up to date.
# LinkedIn has no public API; we only get whatever is in search/cache, which can be stale.
LINKEDIN_OVERRIDE_FILE = "linkedin_override.json"


def _apply_linkedin_override(linkedin_data: dict) -> dict:
    """If linkedin_override.json exists, merge headline and about (and optional summary) into profile."""
    if not linkedin_data or not os.path.isfile(LINKEDIN_OVERRIDE_FILE):
        return linkedin_data
    try:
        with open(LINKEDIN_OVERRIDE_FILE, encoding="utf-8") as f:
            override = json.load(f)
        for key in ("headline", "about", "summary"):
            if key in override and override[key] is not None:
                linkedin_data[key] = override[key]
        print("✅ Applied headline/about from linkedin_override.json")
    except Exception as e:
        print(f"⚠️ Could not load {LINKEDIN_OVERRIDE_FILE}: {e}")
    return linkedin_data


def extract_both(
    github_url: str | None = None,
    linkedin_url: str | None = None,
    linkedin_override: bool = True,
) -> dict:
    """Extract both GitHub and LinkedIn profiles. Optionally apply linkedin_override.json for current headline/about."""
    results = {
        "github": None,
        "linkedin": None,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    if github_url:
        try:
            results["github"] = extract_github_via_api(github_url)
        except Exception as e:
            print(f"❌ GitHub extraction failed: {e}")

    if linkedin_url:
        try:
            results["linkedin"] = extract_linkedin(linkedin_url)
            if linkedin_override:
                results["linkedin"] = _apply_linkedin_override(results["linkedin"])
        except Exception as e:
            print(f"❌ LinkedIn extraction failed: {e}")

    return results


def _normalize_linkedin_url(url: str) -> str:
    """Ensure LinkedIn URL has https."""
    url = url.strip()
    if url and not url.startswith("http"):
        url = "https://" + url
    return url


# Canonical GitHub profile keys so all saved profiles have the same shape (fill missing with blank).
GITHUB_TOP_KEYS = (
    "name", "username", "bio", "location", "company", "email",
    "followers", "following", "publicRepos", "topLanguages",
    "repositories", "topRepositories", "skills", "interests",
)
GITHUB_REPO_KEYS = (
    "name", "fullName", "description", "url", "cloneUrl", "language",
    "stars", "forks", "openIssues", "size", "defaultBranch", "isFork", "isArchived",
    "createdAt", "updatedAt", "pushedAt", "topics", "homepage", "license",
    "visibility", "readmeSummary",
)
GITHUB_TOP_REPO_KEYS = ("name", "description", "language", "stars")


def normalize_github_profile(data: dict | None) -> dict:
    """Ensure profile has all canonical keys; fill missing with '' or [] or 0 or None so Anagha/Gaurav match."""
    if not data:
        data = {}
    out = {}
    for k in GITHUB_TOP_KEYS:
        v = data.get(k)
        if v is None and k in ("followers", "following", "publicRepos"):
            out[k] = 0
        elif v is None and k in ("topLanguages", "repositories", "topRepositories", "skills", "interests"):
            out[k] = []
        elif v is None:
            out[k] = "" if k != "email" else ""
        else:
            out[k] = v
    # Normalize each repository to have all repo keys
    repos = out.get("repositories") or []
    out["repositories"] = []
    for r in repos:
        nr = {}
        for key in GITHUB_REPO_KEYS:
            val = r.get(key)
            if val is not None:
                nr[key] = val
            elif key == "topics":
                nr[key] = []
            elif key in ("stars", "forks", "openIssues", "size"):
                nr[key] = 0
            elif key == "readmeSummary":
                nr[key] = None
            else:
                nr[key] = ""
        out["repositories"].append(nr)
    # Normalize topRepositories items
    top = out.get("topRepositories") or []
    out["topRepositories"] = []
    for t in top:
        nt = {}
        for k in GITHUB_TOP_REPO_KEYS:
            val = t.get(k)
            nt[k] = val if val is not None else (0 if k == "stars" else "")
        out["topRepositories"].append(nt)
    return out


# ==================== USAGE ====================

if __name__ == "__main__":
    GITHUB_ANAGHA_URL = "https://github.com/palandyeanagha"
    GITHUB_GAURAV_URL = "https://github.com/gauravatavale"  # set to Gaurav's GitHub if different
    LINKEDIN_URL = _normalize_linkedin_url("www.linkedin.com/in/anagha-palandye")

    # Fetch GitHub for both Anagha and Gaurav so both files have the same keys
    github_anagha = None
    github_gaurav = None
    try:
        github_anagha = extract_github_via_api(GITHUB_ANAGHA_URL)
    except Exception as e:
        print(f"❌ GitHub (Anagha) failed: {e}")
    try:
        github_gaurav = extract_github_via_api(GITHUB_GAURAV_URL)
    except Exception as e:
        print(f"❌ GitHub (Gaurav) failed: {e}")

    github_anagha_norm = normalize_github_profile(github_anagha)
    github_gaurav_norm = normalize_github_profile(github_gaurav)

    if github_anagha_norm.get("username"):
        with open("github_profile_anagha.json", "w", encoding="utf-8") as f:
            json.dump(github_anagha_norm, f, indent=2)
        print("💾 Saved github_profile_anagha.json (normalized keys)")

    if github_gaurav_norm.get("username"):
        with open("github_profile_gaurav.json", "w", encoding="utf-8") as f:
            json.dump(github_gaurav_norm, f, indent=2)
        print("💾 Saved github_profile_gaurav.json (normalized keys)")

    # LinkedIn for Anagha + combined profile (reuse Anagha GitHub already fetched)
    all_data = {"github": github_anagha, "linkedin": None, "timestamp": datetime.datetime.now().isoformat()}
    try:
        all_data["linkedin"] = extract_linkedin(LINKEDIN_URL)
        all_data["linkedin"] = _apply_linkedin_override(all_data["linkedin"])
    except Exception as e:
        print(f"❌ LinkedIn extraction failed: {e}")

    if all_data["github"]:
        with open("github_profile.json", "w", encoding="utf-8") as f:
            json.dump(normalize_github_profile(all_data["github"]), f, indent=2)
        print("💾 Saved github_profile.json")
    if all_data["linkedin"]:
        with open("linkedin_profile.json", "w", encoding="utf-8") as f:
            json.dump(all_data["linkedin"], f, indent=2)
        print("💾 Saved linkedin_profile.json")
    with open("profile_combined.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2)
    print("💾 Saved profile_combined.json")
