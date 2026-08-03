"""
Computes account-wide stats (public, non-fork repos) -- repo count, commits,
stars, total lines of code, and a language-percentage breakdown -- and writes
them as a plain-text terminal block into README.md between the
STATS:START / STATS:END markers. No third-party dependencies, stdlib only.
"""

import json
import os
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

USERNAME = os.environ.get("GH_USERNAME", "vikasranax")
TOKEN = os.environ.get("GH_TOKEN")
API = "https://api.github.com"
README_PATH = "README.md"

BAR_WIDTH = 20        # characters wide for each language bar
TOP_N_LANGUAGES = 8   # show top N languages, group the rest as "Other"


def gh_request(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USERNAME,
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_repos():
    """All public, non-fork repos owned by the user."""
    repos, page = [], 1
    while True:
        url = f"{API}/users/{USERNAME}/repos?type=owner&per_page=100&page={page}"
        batch = gh_request(url)
        if not batch:
            break
        repos.extend(r for r in batch if not r.get("fork"))
        if len(batch) < 100:
            break
        page += 1
    return repos


def get_total_commits():
    """Total commits authored by the user, across all public repos on GitHub."""
    url = f"{API}/search/commits?q=author:{USERNAME}"
    data = gh_request(url, accept="application/vnd.github.cloak-preview+json")
    return data.get("total_count", 0)


def get_total_loc(repos):
    """Shallow-clones each repo and sums 'code' lines via cloc."""
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for repo in repos:
            dest = os.path.join(tmp, repo["name"])
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", "--quiet",
                     repo["clone_url"], dest],
                    check=True, timeout=120,
                )
            except Exception:
                continue

            try:
                result = subprocess.run(
                    ["cloc", "--json", dest],
                    check=True, capture_output=True, text=True, timeout=120,
                )
                report = json.loads(result.stdout)
                total += report.get("SUM", {}).get("code", 0)
            except Exception:
                continue
    return total


def get_language_breakdown(repos):
    """
    Sums bytes-per-language across all repos (GitHub's own language
    detection, via the /languages endpoint) and returns a sorted list of
    (language, percentage) tuples.
    """
    totals = {}
    for repo in repos:
        try:
            langs = gh_request(f"{API}/repos/{USERNAME}/{repo['name']}/languages")
        except Exception:
            continue
        for lang, byte_count in langs.items():
            totals[lang] = totals.get(lang, 0) + byte_count

    grand_total = sum(totals.values())
    if grand_total == 0:
        return []

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    breakdown = [(lang, (count / grand_total) * 100) for lang, count in ranked]

    if len(breakdown) > TOP_N_LANGUAGES:
        top = breakdown[:TOP_N_LANGUAGES]
        other_pct = sum(pct for _, pct in breakdown[TOP_N_LANGUAGES:])
        top.append(("Other", other_pct))
        breakdown = top

    return breakdown


def format_ist_datetime():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    suffix = "th" if 11 <= (now.day % 100) <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(now.day % 10, "th")
    return f"{now.day}{suffix} {now.strftime('%B %Y')} {now.strftime('%H:%M')} IST"


def stat_line(prefix, label, value, total_width=66):
    content = f"{label}: "
    dots_needed = max(3, total_width - len(content) - len(str(value)))
    dots = "." * dots_needed
    return f"{prefix} {content}{dots}  {value}"


def render_block(stats, languages):
    lines = [
        "# GITHUB STATS -------------------------------------------------------",
        stat_line("!", "Repos", stats["REPOS"]),           # ! = orange/amber highlight
        stat_line(" ", "Commits", stats["COMMITS"]),       # no prefix = default color
        stat_line(" ", "Stars", stats["STARS"]),
        stat_line("+", "Lines of code", stats["LOC"]),     # + = green
        " ",
        "# LANGUAGES ------------------------------------------------------------",
    ]

    if languages:
        for lang, pct in languages:
            lines.append(stat_line(" ", lang, f"{pct:.1f}%"))
    else:
        lines.append("  (no data)")

    lines.append(" ")
    lines.append(f"  last sync: {stats['UPDATED']}")

    return "```diff\n" + "\n".join(lines) + "\n```"


def update_readme(block):
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if "<!-- STATS:START -->" not in content or "<!-- STATS:END -->" not in content:
        raise RuntimeError(
            "STATS:START / STATS:END markers not found in README.md — "
            "the script has nowhere to insert stats. Check that both "
            "'<!-- STATS:START -->' and '<!-- STATS:END -->' exist exactly "
            "as written, on their own, somewhere in README.md."
        )

    new_content, count = re.subn(
        r"(<!-- STATS:START -->)(.*?)(<!-- STATS:END -->)",
        lambda m: f"{m.group(1)}\n{block}\n{m.group(3)}",
        content,
        flags=re.DOTALL,
    )

    if count == 0:
        raise RuntimeError(
            "Markers were found but regex substitution matched 0 times — "
            "check marker formatting/ordering in README.md."
        )

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    repos = get_repos()
    stats = {
        "REPOS": len(repos),
        "COMMITS": f"{get_total_commits():,}",
        "STARS": f"{sum(r.get('stargazers_count', 0) for r in repos):,}",
        "LOC": f"{get_total_loc(repos):,}",
        "UPDATED": format_ist_datetime(),
    }
    languages = get_language_breakdown(repos)
    block = render_block(stats, languages)
    update_readme(block)
    print("Updated README with:\n" + block)


if __name__ == "__main__":
    main()
