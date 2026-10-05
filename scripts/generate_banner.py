#!/usr/bin/env python3
"""
Cinematic ink-wash GitHub profile banner generator.

Generates assets/github-banner-<theme>.svg for each selected theme with:
  - ACCURATE lines of code  (shallow-clones each repo, counts real lines)
  - ACCURATE commit counts  (git rev-list on the default branch)
  - Live language breakdown from the GitHub API, shown as bar charts
  - Last-updated timestamp rendered in IST (UTC+5:30)

Themes: temple (sunset ruins) | marble (turquoise agate) | saltflats (dusk)
"""
import os
import sys
import json
import math
import shutil
import subprocess
import tempfile
import datetime
import urllib.request
from pathlib import Path

# ============================================================================
#  👤  CONFIG — EDIT HERE
# ----------------------------------------------------------------------------
#  1) Your GitHub username (env var GITHUB_USERNAME overrides this value,
#     which is how the workflow passes it in):
USERNAME = os.environ.get("GITHUB_USERNAME", "vikasranax")  # ← EDIT THIS

#  2) Which banners to generate (delete the ones you don't want):
THEMES = ["saltflats"]

#  3) Misc options:
TOKEN           = os.environ.get("GITHUB_TOKEN", "")  # auto-set in Actions
INCLUDE_FORKS   = False   # forks inflate your commit / LOC stats
TOP_LANGUAGES   = 6       # languages shown in the breakdown
REQUEST_TIMEOUT = 30
OUT_DIR         = Path("assets")
# ============================================================================


# ----------------------------------------------------------------------------
# Language colors (GitHub linguist palette)
# ----------------------------------------------------------------------------
LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "HTML": "#e34c26",
    "CSS": "#563d7c", "Python": "#3776ab", "C++": "#f34b7d",
    "Java": "#b07219", "Dockerfile": "#384d54", "Shell": "#89e051",
    "Go": "#00add8", "Rust": "#dea584", "Ruby": "#cc342d",
    "PHP": "#4f5d95", "Swift": "#ffac45", "Kotlin": "#a97bff",
    "C": "#555555", "C#": "#178600", "Vue": "#41b883", "Svelte": "#ff3e00",
    "Dart": "#00b4ab", "SCSS": "#c6538c", "Lua": "#000080",
}

# Data / config formats excluded from BOTH the language breakdown and LOC,
# matching GitHub linguist's treatment of non-code files.
SKIP_LANGS = {
    "Markdown", "JSON", "YAML", "TOML", "TeX", "BitBake",
    "Batchfile", "PowerShell", "Jupyter Notebook",
}

CODE_EXTS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".c", ".h", ".cpp", ".cxx", ".cc", ".hpp", ".hh",
    ".cs", ".java", ".kt", ".kts", ".swift", ".go", ".rs",
    ".rb", ".php", ".m", ".mm", ".scala", ".sh", ".bash", ".zsh",
    ".pl", ".pm", ".r", ".lua", ".sql", ".vue", ".svelte", ".astro",
    ".groovy", ".dart", ".ex", ".exs", ".erl", ".hrl", ".fs", ".fsx",
    ".vb", "asm", ".sol", ".tf", ".mk",
}
SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "pipfile.lock", "cargo.lock", "composer.lock", "gemfile.lock",
    "go.sum", "go.mod",
}


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def ordinal_suffix(day):
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_ist_now():
    utc = datetime.datetime.now(datetime.timezone.utc)
    ist = utc + datetime.timedelta(hours=5, minutes=30)
    return ist.strftime(f"%d{ordinal_suffix(ist.day)} %B %Y · %I:%M %p IST")


def api_call(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", f"{USERNAME}-banner-generator")
    if TOKEN:
        req.add_header("Authorization", f"token {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"API error for {url}: {e}", file=sys.stderr)
        return []


def fetch_repos():
    repos = []
    page = 1
    while page <= 10:
        data = api_call(
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&sort=updated"
        )
        if not isinstance(data, list) or not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos


# ----------------------------------------------------------------------------
# ACCURATE stats: shallow-clone each repo, count real lines + real commits
# ----------------------------------------------------------------------------
def is_code_file(path_bytes):
    p = path_bytes.decode("utf-8", "ignore")
    low = p.lower()
    name = low.rsplit("/", 1)[-1]
    if name in SKIP_FILENAMES:
        return False
    if name.endswith((".min.js", ".min.css", ".min.mjs")):
        return False
    if low.startswith("vendor/") or "/vendor/" in low:
        return False
    if name in ("makefile", "gnumakefile", "dockerfile"):
        return True
    for ext in CODE_EXTS:
        if low.endswith(ext):
            return True
    return False


def count_lines(path):
    try:
        if path.stat().st_size > 1_000_000:      # skip huge generated files
            return 0
        data = path.read_bytes()
    except OSError:
        return 0
    if b"\0" in data[:8192]:                      # binary safety check
        return 0
    n = data.count(b"\n")
    if data and not data.endswith(b"\n"):
        n += 1
    return n


def clone_and_measure(repo_full_name, dest):
    """Returns (loc, commits) measured from a real checkout, or (0, 0)."""
    if TOKEN:
        url = f"https://x-access-token:{TOKEN}@github.com/{repo_full_name}.git"
    else:
        url = f"https://github.com/{repo_full_name}.git"
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
            check=True, timeout=300,
        )
    except Exception as e:
        print(f"clone failed for {repo_full_name}: {e}", file=sys.stderr)
        return 0, 0
    loc = 0
    try:
        listed = subprocess.run(
            ["git", "-C", str(dest), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
        for f in listed.split(b"\0"):
            if f and is_code_file(f):
                loc += count_lines(dest / f.decode("utf-8", "ignore"))
        commits = int(subprocess.run(
            ["git", "-C", str(dest), "rev-list", "--count", "HEAD"],
            capture_output=True, check=True,
        ).stdout.strip())
    except Exception as e:
        print(f"measure failed for {repo_full_name}: {e}", file=sys.stderr)
        return loc, 0
    return loc, commits


def fetch_stats():
    user = api_call(f"https://api.github.com/users/{USERNAME}")
    repos = fetch_repos()

    lang_bytes = {}
    total_bytes = 0
    stars = 0
    total_commits = 0
    total_loc = 0

    tmp = Path(tempfile.mkdtemp(prefix="banner-repos-"))
    try:
        for r in repos:
            if r.get("fork") and not INCLUDE_FORKS:
                continue
            stars += r.get("stargazers_count", 0)
            full = r.get("full_name", f"{USERNAME}/{r['name']}")
            loc, commits = clone_and_measure(full, tmp / r["name"])
            total_loc += loc
            total_commits += commits

            langs = api_call(r.get("languages_url", ""))
            if isinstance(langs, dict):
                for lang, b in langs.items():
                    if lang in SKIP_LANGS:
                        continue
                    lang_bytes[lang] = lang_bytes.get(lang, 0) + b
                    total_bytes += b
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    top = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:TOP_LANGUAGES]
    denom = total_bytes or 1
    languages = [(lang, round(b / denom * 100, 1)) for lang, b in top]

    return {
        "repos": len([r for r in repos if INCLUDE_FORKS or not r.get("fork")]),
        "stars": stars,
        "commits": total_commits,
        "loc": total_loc,
        "loc_str": f"{total_loc:,}",
        "languages": languages,
        "name": (user or {}).get("name") or USERNAME,
    }


# ----------------------------------------------------------------------------
# Theme palettes (text colors adapt to each background)
# ----------------------------------------------------------------------------
THEME_STYLE = {
    "temple": {
        "head": "#241a10", "text": "#3a2c1e", "sub": "#5a4632",
        "line": "#8a7256", "card": "#ffffff", "card_op": "0.45",
        "card_text": "#241a10", "card_sub": "#5a4632", "track": "#e6d6bc",
        "scrim": "#fff3e2", "scrim_op": "0.28",
    },
    "marble": {
        "head": "#f4fcfc", "text": "#e8f7f8", "sub": "#c8ecee",
        "line": "#9fd8dc", "card": "#ffffff", "card_op": "0.55",
        "card_text": "#083139", "card_sub": "#2a6a73", "track": "#cdeef0",
        "scrim": "#052e36", "scrim_op": "0.42",
    },
    "saltflats": {
        "head": "#f2f7fb", "text": "#dbe9f4", "sub": "#a9c4da",
        "line": "#4f7191", "card": "#0a1c34", "card_op": "0.55",
        "card_text": "#eef5fb", "card_sub": "#a9c4da", "track": "#3a5f88",
        "scrim": "#050f20", "scrim_op": "0.35",
    },
}


# ----------------------------------------------------------------------------
# Background artwork — pure SVG (gradients + paths, no filters needed)
# ----------------------------------------------------------------------------
def _puff(gid, color, op):
    return (f"<radialGradient id='{gid}' cx='0.5' cy='0.5' r='0.5'>"
            f"<stop offset='0' stop-color='{color}' stop-opacity='{op}'/>"
            f"<stop offset='0.55' stop-color='{color}' stop-opacity='{op*0.55:.2f}'/>"
            f"<stop offset='1' stop-color='{color}' stop-opacity='0'/></radialGradient>")


def _tower(cx, base_y, w, h, main, dark, light):
    parts = []
    n = 7
    for i in range(n):
        t = i / (n - 1)
        tw = w * (1 - 0.82 * t**1.35)
        th = h / n
        y = base_y - i * th
        parts.append(f"<rect x='{cx-tw/2:.1f}' y='{y-th:.1f}' width='{tw:.1f}' height='{th:.1f}' fill='{main}'/>")
        parts.append(f"<rect x='{cx-tw/2:.1f}' y='{y-th:.1f}' width='{tw*0.32:.1f}' height='{th:.1f}' fill='{dark}'/>")
        parts.append(f"<rect x='{cx-tw/2:.1f}' y='{y-th:.1f}' width='{tw:.1f}' height='{max(th*0.12,1.5):.1f}' fill='{light}'/>")
        for k in (1, 2):
            yy = y - th + th * k / 3
            parts.append(f"<line x1='{cx-tw/2:.1f}' y1='{yy:.1f}' x2='{cx+tw/2:.1f}' y2='{yy:.1f}' stroke='{dark}' stroke-width='0.8' opacity='0.5'/>")
    top_w = w * 0.18
    parts.append(f"<rect x='{cx-top_w/2:.1f}' y='{base_y-h-h*0.06:.1f}' width='{top_w:.1f}' height='{h*0.08:.1f}' rx='{top_w*0.4:.1f}' fill='{main}'/>")
    return "".join(parts)


def _lion(x, y, s, fill):
    return (f"<g transform='translate({x},{y}) scale({s})' fill='{fill}'>"
            "<rect x='-14' y='-8' width='28' height='14' rx='3'/>"
            "<rect x='-16' y='4' width='32' height='5'/>"
            "<path d='M -8 -8 L -6 -26 Q -6 -34 0 -36 Q 8 -34 8 -24 L 6 -8 Z'/>"
            "<circle cx='1' cy='-30' r='4.5'/></g>")


def bg_temple():
    defs, body = [], []
    cloud_specs = [
        ("c1", "#38285c", 0.9, [(200, 70, 250, 42), (330, 55, 160, 30), (90, 88, 150, 26)]),
        ("c2", "#45306b", 0.85, [(500, 42, 270, 30), (640, 60, 170, 24)]),
        ("c3", "#38285c", 0.9, [(1000, 62, 300, 40), (1120, 90, 170, 26)]),
        ("c4", "#d97a74", 0.55, [(830, 120, 250, 32), (940, 138, 150, 22)]),
        ("c5", "#e8876f", 0.6, [(310, 150, 260, 34), (410, 168, 150, 22)]),
        ("c6", "#eda06e", 0.5, [(680, 170, 300, 34), (800, 188, 170, 22)]),
        ("c7", "#e8876f", 0.5, [(1060, 190, 240, 30)]),
        ("c8", "#f0aa6d", 0.45, [(110, 220, 230, 28)]),
        ("c9", "#f7bf7d", 0.4, [(540, 235, 290, 26)]),
        ("c10", "#f6c08a", 0.6, [(400, 112, 110, 9), (930, 152, 130, 10), (150, 182, 120, 9)]),
    ]
    for gid, col, op, els in cloud_specs:
        defs.append(_puff(gid, col, op))
        for cx, cy, w, h in els:
            body.append(f"<ellipse cx='{cx}' cy='{cy}' rx='{w}' ry='{h}' fill='url(#{gid})'/>")

    body.append("<path d='M0 455 Q 190 425 400 447 T 850 440 T 1200 450 L1200 640 L0 640 Z' fill='#5e3a63' opacity='0.5'/>")
    body.append("<rect x='-20' y='560' width='1240' height='85' fill='url(#basefade)'/>")
    body.append("<rect x='-20' y='556' width='1240' height='7' fill='#d99a63'/>")
    body.append("<rect x='0' y='580' width='1200' height='14' fill='#6e4128'/>")
    body.append("<rect x='0' y='580' width='1200' height='4' fill='#c98a5a'/>")
    body.append("<rect x='0' y='606' width='1200' height='16' fill='#5d3722'/>")
    body.append("<rect x='0' y='606' width='1200' height='4' fill='#b5764a'/>")
    # central staircase
    body.append("<g><rect x='530' y='562' width='150' height='80' fill='#7c4a2c'/>"
                "<rect x='530' y='562' width='150' height='5' fill='#d99a63'/>"
                "<rect x='541' y='574' width='128' height='7' fill='#a5683f'/>"
                "<rect x='552' y='586' width='106' height='7' fill='#a5683f'/>"
                "<rect x='563' y='598' width='84' height='7' fill='#a5683f'/>"
                "<rect x='574' y='610' width='62' height='7' fill='#a5683f'/>"
                "<rect x='585' y='622' width='40' height='20' fill='#a5683f'/></g>")
    body.append("<path d='M530 562 L518 640 L530 640 Z' fill='#5d3722'/>")
    body.append("<path d='M680 562 L692 640 L680 640 Z' fill='#5d3722'/>")
    # sanctuary
    body.append("<rect x='440' y='540' width='330' height='24' fill='url(#stone)'/>")
    body.append("<rect x='440' y='540' width='330' height='4' fill='#e0a76b'/>")
    body.append(_tower(605, 542, 200, 235, "#b5764a", "#7c4a2c", "#e0a76b"))
    body.append("<rect x='587' y='492' width='36' height='52' fill='#2c1a30'/>")
    body.append("<rect x='583' y='485' width='44' height='9' fill='#e0a76b'/>")
    body.append("<rect x='583' y='485' width='44' height='3' fill='#f2c088'/>")
    body.append("<rect x='508' y='512' width='20' height='30' fill='#4a2c3a'/>")
    body.append("<rect x='684' y='512' width='20' height='30' fill='#4a2c3a'/>")
    # side towers
    body.append("<rect x='60' y='580' width='240' height='18' fill='url(#stone)'/>")
    body.append(_tower(180, 580, 125, 175, "#a5683f", "#6e4128", "#d99a63"))
    body.append("<rect x='168' y='552' width='24' height='30' fill='#241428'/>")
    body.append(_lion(285, 580, 1.1, "#4e2e1c"))
    body.append("<rect x='900' y='582' width='250' height='18' fill='url(#stone)'/>")
    body.append(_tower(1025, 582, 135, 180, "#a5683f", "#6e4128", "#d99a63"))
    body.append("<rect x='1013' y='554' width='24' height='30' fill='#241428'/>")
    body.append(_lion(925, 582, 1.1, "#4e2e1c"))
    body.append(_tower(390, 570, 78, 100, "#8f5a38", "#5d3722", "#c98a5a"))
    body.append("<g fill='#4d6b35' opacity='0.9'>"
                "<path d='M320 580 q3 -14 6 0 q3 -10 6 0 q-2 4 -6 4 q-4 0 -6 -4 Z'/>"
                "<path d='M860 582 q3 -14 6 0 q3 -10 6 0 q-2 4 -6 4 q-4 0 -6 -4 Z'/></g>")
    # birds
    body.append("<g stroke='#3a2a24' stroke-width='2' fill='none' opacity='0.7'>"
                "<path d='M760 220 q7 -8 14 0 q7 -8 14 0'/>"
                "<path d='M810 200 q6 -7 12 0 q6 -7 12 0'/>"
                "<path d='M715 245 q5 -6 10 0 q5 -6 10 0'/></g>")

    defs.append("<linearGradient id='sky' x1='0' y1='0' x2='0' y2='1'>"
                "<stop offset='0' stop-color='#2e1f4e'/><stop offset='0.28' stop-color='#5b3a6e'/>"
                "<stop offset='0.52' stop-color='#a3557a'/><stop offset='0.72' stop-color='#e07a63'/>"
                "<stop offset='0.9' stop-color='#f2a95f'/><stop offset='1' stop-color='#f7c47a'/></linearGradient>")
    defs.append(_puff("sunglow", "#ffcf94", 0.85))
    defs.append(_puff("wash", "#ffb37a", 0.5))
    defs.append("<linearGradient id='stone' x1='0' y1='0' x2='0' y2='1'>"
                "<stop offset='0' stop-color='#c98a5a'/><stop offset='0.55' stop-color='#a5683f'/>"
                "<stop offset='1' stop-color='#7c4a2c'/></linearGradient>")
    defs.append("<linearGradient id='basefade' x1='0' y1='0' x2='0' y2='1'>"
                "<stop offset='0' stop-color='#8a5433'/><stop offset='1' stop-color='#4e2e1c'/></linearGradient>")

    sky = "<rect width='1200' height='640' fill='url(#sky)'/>"
    sun = "<ellipse cx='760' cy='240' rx='640' ry='260' fill='url(#sunglow)'/>"
    wash = "<ellipse cx='600' cy='300' rx='620' ry='220' fill='url(#wash)'/>"
    return "".join(defs), sky + sun + "".join(body) + wash


def _meander(x0, y0, x1, y1, wiggle, n=14):
    import random
    pts = []
    for i in range(n + 1):
        t = i / n
        x = x0 + (x1 - x0) * t + random.uniform(-wiggle, wiggle)
        y = y0 + (y1 - y0) * t + random.uniform(-wiggle, wiggle) * 0.5
        pts.append((x, y))
    d = f"M {pts[0][0]:.0f} {pts[0][1]:.0f} "
    for i in range(1, n + 1):
        p, c = pts[i - 1], pts[i]
        d += f"Q {p[0]:.0f} {p[1]:.0f} {(p[0]+c[0])/2:.0f} {(p[1]+c[1])/2:.0f} "
    return d


def bg_marble():
    import random
    random.seed(42)
    defs, body = [], []

    blob_cols = ["#ffffff", "#d8f0f2", "#0f6f7e", "#1d8894",
                 "#5c2f47", "#123f52", "#9fd4d8", "#0a5f70"]
    for i, col in enumerate(blob_cols):
        defs.append(_puff(f"b{i}", col, 0.42))
    random.seed(7)
    for _ in range(34):
        gid = f"b{random.randint(0, 7)}"
        x, y = random.randint(-80, 1280), random.randint(-60, 700)
        rx, ry = random.randint(70, 250), random.randint(50, 160)
        body.append(f"<ellipse cx='{x}' cy='{y}' rx='{rx}' ry='{ry}' fill='url(#{gid})'/>")

    def vein(d, stroke, w, op):
        return (f"<path d='{d}' fill='none' stroke='{stroke}' stroke-width='{w}' "
                f"opacity='{op}' stroke-linecap='round'/>")

    veins = []
    for _ in range(17):
        y = random.randint(20, 620)
        d = _meander(-40, y, 1250, y + random.randint(-160, 160), random.randint(40, 110))
        veins.append(vein(d, "#a8742c", random.uniform(1.4, 3.6), random.uniform(0.4, 0.7)))
        veins.append(vein(d, "#ecc069", random.uniform(0.5, 1.1), 0.85))
    for _ in range(10):
        y = random.randint(0, 640)
        d = _meander(-40, y, 1250, y + random.randint(-200, 200), random.randint(60, 140))
        veins.append(vein(d, "#4a2438", random.uniform(2.5, 7), random.uniform(0.35, 0.6)))
    body.extend(veins)

    random.seed(5)
    for _ in range(80):
        x, y = random.randint(0, 1200), random.randint(0, 640)
        body.append(f"<circle cx='{x}' cy='{y}' r='{random.uniform(0.5,1.8):.1f}' "
                    f"fill='#ffffff' opacity='{random.uniform(0.2,0.7):.2f}'/>")

    defs.append("<linearGradient id='mbg' x1='0' y1='0' x2='1' y2='1'>"
                "<stop offset='0' stop-color='#0e7f92'/><stop offset='0.35' stop-color='#18a0ad'/>"
                "<stop offset='0.65' stop-color='#0d8a9c'/><stop offset='1' stop-color='#0a6d84'/></linearGradient>")
    defs.append("<radialGradient id='mg1' cx='0.25' cy='0.3' r='0.7'>"
                "<stop offset='0' stop-color='#7fd8dd' stop-opacity='0.65'/>"
                "<stop offset='1' stop-color='#7fd8dd' stop-opacity='0'/></radialGradient>")
    defs.append("<radialGradient id='mg2' cx='0.8' cy='0.75' r='0.7'>"
                "<stop offset='0' stop-color='#a5e6e9' stop-opacity='0.55'/>"
                "<stop offset='1' stop-color='#a5e6e9' stop-opacity='0'/></radialGradient>")
    defs.append("<linearGradient id='goldstroke' x1='0' y1='0' x2='1' y2='0'>"
                "<stop offset='0' stop-color='#8a5a1e'/><stop offset='0.5' stop-color='#eec25f'/>"
                "<stop offset='1' stop-color='#8a5a1e'/></linearGradient>")

    base = ("<rect width='1200' height='640' fill='url(#mbg)'/>"
            "<rect width='1200' height='640' fill='url(#mg1)'/>"
            "<rect width='1200' height='640' fill='url(#mg2)'/>")
    sheen = ("<ellipse cx='280' cy='120' rx='460' ry='150' fill='url(#mg1)'/>"
             "<ellipse cx='1000' cy='520' rx='420' ry='140' fill='url(#mg2)'/>")
    return "".join(defs), base + "".join(body) + sheen


def bg_saltflats():
    import random
    random.seed(11)
    defs, body = [], []

    cloud_specs = [
        ("d1", "#0a1230", 0.92, [(130, 88, 240, 38), (60, 115, 150, 26)]),
        ("d2", "#0d1738", 0.88, [(400, 60, 270, 32), (540, 82, 170, 24)]),
        ("d3", "#0a1230", 0.92, [(860, 68, 310, 38), (990, 95, 180, 26)]),
        ("d4", "#101c42", 0.88, [(1120, 105, 250, 32)]),
        ("d5", "#16264e", 0.8, [(620, 118, 290, 30)]),
        ("d6", "#22375f", 0.6, [(90, 150, 200, 26)]),
        ("d7", "#22375f", 0.6, [(950, 160, 280, 28)]),
        ("d8", "#8fb7dd", 0.36, [(310, 175, 220, 16)]),
        ("d9", "#9cc3e4", 0.3, [(740, 188, 240, 15)]),
        ("d10", "#cfe2f2", 0.5, [(310, 185, 200, 6)]),
        ("d11", "#cfe2f2", 0.42, [(750, 198, 210, 5)]),
    ]
    for gid, col, op, els in cloud_specs:
        defs.append(_puff(gid, col, op))
        for cx, cy, w, h in els:
            body.append(f"<ellipse cx='{cx}' cy='{cy}' rx='{w}' ry='{h}' fill='url(#{gid})'/>")

    body.append("<path d='M0 330 L55 308 L120 325 L195 298 L270 322 L345 292 L430 320 L510 304 "
                "L600 322 L685 300 L765 320 L845 304 L930 324 L1005 308 L1085 324 L1155 314 "
                "L1200 322 L1200 360 L0 360 Z' fill='#2a2f55'/>")
    body.append("<path d='M0 342 L85 328 L180 340 L285 326 L400 340 L520 330 L660 341 L780 329 "
                "L910 341 L1035 331 L1160 342 L1200 336 L1200 370 L0 370 Z' fill='#1d2340'/>")

    # polygonal salt crust
    rows, y_top = 8, 348
    bounds, y = [y_top], y_top
    for i in range(rows):
        y += 7 + i * i * 2.8
        bounds.append(min(y, 650))
    vp = 600
    for r_i in range(rows):
        y0, y1 = bounds[r_i], bounds[r_i + 1]
        cols = 9 + r_i * 2
        for c_i in range(cols):
            t0, t1 = c_i / cols, (c_i + 1) / cols
            s = 1 + r_i * 0.26
            x0 = vp + (t0 - 0.5) * 1250 * s
            x1 = vp + (t1 - 0.5) * 1250 * s
            j = 6 + r_i * 2.5
            p = [(x0 + random.uniform(-j, j), y0 + random.uniform(-3, 3)),
                 (x1 + random.uniform(-j, j), y0 + random.uniform(-3, 3)),
                 (x1 + random.uniform(-j, j), y1 + random.uniform(-4, 4)),
                 (x0 + random.uniform(-j, j), y1 + random.uniform(-4, 4))]
            base = random.uniform(0.58, 0.88)
            blu = int(185 * base + random.uniform(-10, 15))
            fill = f"rgb({int(blu*0.82)},{int(blu*0.95)},{min(blu+14,255)})"
            d = "M " + " L ".join(f"{px:.0f} {py:.0f}" for px, py in p) + " Z"
            body.append(f"<path d='{d}' fill='{fill}' stroke='#122c4a' "
                        f"stroke-width='{1.1 + r_i * 0.25:.1f}' opacity='0.96'/>")
            if random.random() < 0.5:
                mx = sum(px for px, _ in p) / 4 + random.uniform(-14, 14)
                my = sum(py for _, py in p) / 4 + random.uniform(-8, 8)
                body.append(f"<path d='M {p[0][0]:.0f} {p[0][1]:.0f} Q {mx:.0f} {my:.0f} "
                            f"{p[2][0]:.0f} {p[2][1]:.0f}' fill='none' stroke='#0e2438' "
                            f"stroke-width='{1.4 + r_i * 0.3:.1f}' opacity='0.75'/>")

    defs.append("<linearGradient id='dsky' x1='0' y1='0' x2='0' y2='1'>"
                "<stop offset='0' stop-color='#050b1e'/><stop offset='0.35' stop-color='#0c1d42'/>"
                "<stop offset='0.62' stop-color='#1c3f72'/><stop offset='0.82' stop-color='#3a6ea8'/>"
                "<stop offset='1' stop-color='#6fa3cf'/></linearGradient>")
    defs.append("<radialGradient id='dsun' cx='0.18' cy='0.42' r='0.5'>"
                "<stop offset='0' stop-color='#ffe9c2' stop-opacity='0.9'/>"
                "<stop offset='0.4' stop-color='#ffc98a' stop-opacity='0.4'/>"
                "<stop offset='1' stop-color='#ffc98a' stop-opacity='0'/></radialGradient>")
    defs.append("<linearGradient id='ground' x1='0' y1='0' x2='0' y2='1'>"
                "<stop offset='0' stop-color='#93b2d2'/><stop offset='0.25' stop-color='#789cc4'/>"
                "<stop offset='1' stop-color='#3f6392'/></linearGradient>")
    defs.append("<radialGradient id='gsheen' cx='0.5' cy='0.5' r='0.5'>"
                "<stop offset='0' stop-color='#ffe9c2' stop-opacity='0.35'/>"
                "<stop offset='1' stop-color='#ffe9c2' stop-opacity='0'/></radialGradient>")
    defs.append("<radialGradient id='gsheen2' cx='0.5' cy='0.5' r='0.5'>"
                "<stop offset='0' stop-color='#b9d2ea' stop-opacity='0.3'/>"
                "<stop offset='1' stop-color='#b9d2ea' stop-opacity='0'/></radialGradient>")
    defs.append("<radialGradient id='vig' cx='0.5' cy='0.45' r='0.75'>"
                "<stop offset='0.55' stop-color='#020612' stop-opacity='0'/>"
                "<stop offset='1' stop-color='#020612' stop-opacity='0.5'/></radialGradient>")

    sky = ("<rect width='1200' height='640' fill='url(#dsky)'/>"
           "<rect width='1200' height='640' fill='url(#dsun)'/>")
    ground = "<rect x='0' y='345' width='1200' height='295' fill='url(#ground)'/>"
    end = ("<ellipse cx='220' cy='440' rx='330' ry='80' fill='url(#gsheen)'/>"
           "<ellipse cx='650' cy='500' rx='540' ry='70' fill='url(#gsheen2)'/>"
           "<rect width='1200' height='640' fill='url(#vig)'/>")
    return "".join(defs), sky + "".join(body[:11]) + ground + "".join(body[11:]) + end


BACKGROUNDS = {"temple": bg_temple, "marble": bg_marble, "saltflats": bg_saltflats}


# ----------------------------------------------------------------------------
# Panels: left (profile info) + right (stat cards & language bar chart)
# ----------------------------------------------------------------------------
def bar_chart(languages, s):
    rows = []
    x, y, bar_w = 860, 292, 150
    for i, (lang, pct) in enumerate(languages):
        cy = y + i * 34
        color = LANG_COLORS.get(lang, "#7a6a58")
        w = max(2.0, pct / 100 * bar_w)
        rows.append(
            f"<text x='{x}' y='{cy+4}' font-family='IBM Plex Sans, sans-serif' font-size='12' "
            f"fill='{s['text']}'>{lang}</text>"
            f"<rect x='{x+96}' y='{cy-6}' width='{bar_w}' height='11' rx='5.5' fill='{s['track']}'/>"
            f"<rect x='{x+96}' y='{cy-6}' width='{w:.1f}' height='11' rx='5.5' fill='{color}'/>"
            f"<text x='{x+96+bar_w+10}' y='{cy+4}' font-family='IBM Plex Mono, monospace' "
            f"font-size='11' fill='{s['sub']}'>{pct:.1f}%</text>"
        )
    return "".join(rows)


def stat_card(x, y, value, label, s, small=False):
    fs = 17 if small else 20
    return (
        f"<rect x='{x}' y='{y}' width='118' height='52' rx='10' fill='{s['card']}' "
        f"fill-opacity='{s['card_op']}' stroke='{s['card']}' stroke-opacity='0.6' stroke-width='0.8'/>"
        f"<text x='{x+59}' y='{y+26}' text-anchor='middle' font-family='IBM Plex Mono, monospace' "
        f"font-size='{fs}' font-weight='500' fill='{s['card_text']}' font-variant-numeric='tabular-nums'>{value}</text>"
        f"<text x='{x+59}' y='{y+43}' text-anchor='middle' font-family='IBM Plex Sans, sans-serif' "
        f"font-size='10.5' fill='{s['card_sub']}'>{label}</text>"
    )


def render_panels(stats, s):
    contacts = [
        ("Google Developer", USERNAME),
        ("X (Twitter)", f"@{USERNAME}"),
        ("Email", f"{USERNAME}@yahoo.com"),
        ("Google Play", USERNAME),
    ]
    contact_svg = ""
    for i, (label, value) in enumerate(contacts):
        yy = 200 + i * 28
        contact_svg += (
            f"<text x='75' y='{yy}' font-family='IBM Plex Sans, sans-serif' font-size='11' "
            f"fill='{s['sub']}'><tspan font-weight='600' fill='{s['text']}'>{label}</tspan>"
            f"   {value}</text>"
        )

    loc_small = len(stats["loc_str"]) > 7
    right = (
        stat_card(862, 55, stats["repos"], "repos", s)
        + stat_card(990, 55, stats["stars"], "stars", s)
        + stat_card(862, 117, stats["commits"], "commits", s)
        + stat_card(990, 117, stats["loc_str"], "lines of code", s, small=loc_small)
        + f"<text x='862' y='240' font-family='IBM Plex Sans, sans-serif' font-size='13' "
          f"font-weight='600' fill='{s['head']}'>Code Breakdown</text>"
        + f"<rect x='862' y='250' width='280' height='1.5' fill='{s['line']}' opacity='0.6'/>"
        + bar_chart(stats["languages"], s)
    )

    left = (
        f"<text x='60' y='85' font-family='Space Grotesk, sans-serif' font-size='46' "
        f"font-weight='600' fill='{s['head']}' letter-spacing='0.5'>{stats['name']}</text>"
        f"<text x='60' y='118' font-family='IBM Plex Sans, sans-serif' font-size='14' "
        f"fill='{s['sub']}'>कृत्य । सहिष्णुता । मोक्षः</text>"
        f"<text x='60' y='160' font-family='IBM Plex Sans, sans-serif' font-size='13' "
        f"font-weight='600' fill='{s['head']}'>Connect</text>"
        f"<rect x='60' y='170' width='340' height='1.5' fill='{s['line']}' opacity='0.6'/>"
        + contact_svg
        + f"<text x='60' y='325' font-family='IBM Plex Sans, sans-serif' font-size='13' "
          f"font-weight='600' fill='{s['head']}'>Hobbies &amp; Passions</text>"
        + f"<rect x='60' y='335' width='340' height='1.5' fill='{s['line']}' opacity='0.6'/>"
        + f"<text x='75' y='357' font-family='IBM Plex Sans, sans-serif' font-size='12' "
          f"fill='{s['sub']}'>Reading · Exploring Places · Photography · Developer</text>"
        + f"<text x='60' y='395' font-family='IBM Plex Sans, sans-serif' font-size='13' "
          f"font-weight='600' fill='{s['head']}'>Programming Languages</text>"
        + f"<rect x='60' y='405' width='340' height='1.5' fill='{s['line']}' opacity='0.6'/>"
        + f"<text x='75' y='427' font-family='IBM Plex Sans, sans-serif' font-size='12' "
          f"fill='{s['sub']}'>HTML · CSS · JavaScript · TypeScript · Python · C · C++</text>"
        + f"<text x='60' y='465' font-family='IBM Plex Sans, sans-serif' font-size='13' "
          f"font-weight='600' fill='{s['head']}'>Computer Languages</text>"
        + f"<rect x='60' y='475' width='340' height='1.5' fill='{s['line']}' opacity='0.6'/>"
        + f"<text x='75' y='497' font-family='IBM Plex Sans, sans-serif' font-size='12' "
          f"fill='{s['sub']}'>React · Docker · Express · FastAPI · REST · GitHub · RAG</text>"
        + f"<text x='60' y='615' font-family='IBM Plex Mono, monospace' font-size='9' "
          f"fill='{s['sub']}'>updated {format_ist_now()}</text>"
    )
    scrim = ""
    if s.get("scrim"):
        op = s.get("scrim_op", "0.3")
        scrim = (
            f"<rect x='40' y='40' width='395' height='480' rx='18' fill='{s['scrim']}' fill-opacity='{op}'/>"
            f"<rect x='845' y='45' width='318' height='445' rx='18' fill='{s['scrim']}' fill-opacity='{op}'/>"
        )
    return scrim + left + right


def generate_svg(stats, theme):
    defs, body = BACKGROUNDS[theme]()
    style = THEME_STYLE[theme]
    return (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<svg viewBox='0 0 1200 640' xmlns='http://www.w3.org/2000/svg'>\n"
        f"<defs>{defs}</defs>\n"
        f"{body}\n"
        f"{render_panels(stats, style)}\n"
        "</svg>"
    )


def main():
    print(f"Fetching stats for {USERNAME}...")
    stats = fetch_stats()
    print(json.dumps({k: v for k, v in stats.items() if k != 'languages'}, indent=2))
    print("Languages:", stats["languages"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = OUT_DIR / f"github-banner-{theme}.svg"
        path.write_text(generate_svg(stats, theme), encoding="utf-8")
        print(f"Banner written to {path}")


if __name__ == "__main__":
    main()
