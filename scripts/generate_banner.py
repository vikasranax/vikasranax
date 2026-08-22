#!/usr/bin/env python3
"""
Generates a custom ink-wash landscape GitHub profile banner.
Layout: Left = contacts/personal, Right = donut chart + stats.
Updates every 6 hours via GitHub Actions.
Fonts: Space Grotesk (headlines), IBM Plex Sans (body), IBM Plex Mono (data).

Data sources:
- Repos / stars / languages / commit counts: GitHub GraphQL API (one query,
  commit counts come straight from `history.totalCount` -- no pagination
  guesswork).
- Lines of code: real count via a shallow `git clone --depth 1` of each repo
  (not a bytes/25 estimate), skipping lockfiles, binaries, and vendor dirs.
"""
import os
import sys
import json
import shutil
import tempfile
import subprocess
import urllib.request
import datetime
import math

def ordinal_suffix(day):
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

def format_ist_now():
    """Return current time in IST with ordinal date format."""
    utc = datetime.datetime.now(datetime.timezone.utc)
    ist = utc + datetime.timedelta(hours=5, minutes=30)
    suffix = ordinal_suffix(ist.day)
    return ist.strftime(f"%d{suffix} %B %Y \u00b7 %I:%M %p IST")

USERNAME = os.environ.get("GITHUB_USERNAME", "vikasranax")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

GRAPHQL_URL = "https://api.github.com/graphql"
REPOS_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    name
    bio
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false, orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        stargazerCount
        defaultBranchRef {
          name
          target {
            ... on Commit { history { totalCount } }
          }
        }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

def graphql_call(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "vikasranax-banner-generator")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"GraphQL error: {e}", file=sys.stderr)
        return {}

def fetch_repo_data():
    """Fetch user info + per-repo stars/commits/languages via GraphQL."""
    repos = []
    name, bio = USERNAME, ""
    cursor = None
    while True:
        result = graphql_call(REPOS_QUERY, {"login": USERNAME, "cursor": cursor})
        data = (result or {}).get("data", {}).get("user")
        if not data:
            print(f"GraphQL response missing user data: {result}", file=sys.stderr)
            break
        name = data.get("name") or USERNAME
        bio = data.get("bio") or ""
        repo_block = data["repositories"]
        repos.extend(repo_block["nodes"])
        if repo_block["pageInfo"]["hasNextPage"]:
            cursor = repo_block["pageInfo"]["endCursor"]
        else:
            break
    return name, bio, repos

# --- Real line-of-code counting via shallow clone -------------------------

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "vendor", ".next", "target",
    "__pycache__", "venv", ".venv", "coverage", "out", ".idea", ".vscode",
    "bin", "obj", ".gradle",
}
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "composer.lock",
    "Cargo.lock", "poetry.lock", "Gemfile.lock",
}
SKIP_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp", ".svg",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar",
    ".mp4", ".mp3", ".mov", ".avi", ".wav",
    ".map", ".lock", ".min.js", ".min.css",
    ".jar", ".class", ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".db", ".sqlite", ".sqlite3",
}
MAX_FILE_BYTES = 2_000_000  # skip anything bigger than 2MB (likely data/binary)
CLONE_TIMEOUT = 90

def count_lines_in_repo(repo_name, default_branch):
    if not default_branch:
        return 0
    tmp = tempfile.mkdtemp(prefix="loc_")
    total = 0
    try:
        clone_url = f"https://github.com/{USERNAME}/{repo_name}.git"
        subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch",
             "--branch", default_branch, "--quiet", clone_url, tmp],
            check=True, timeout=CLONE_TIMEOUT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for root, dirs, files in os.walk(tmp):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for fname in files:
                if fname in SKIP_FILES:
                    continue
                lower = fname.lower()
                if lower.endswith(".min.js") or lower.endswith(".min.css"):
                    continue
                ext = os.path.splitext(lower)[1]
                if ext in SKIP_EXTS:
                    continue
                fpath = os.path.join(root, fname)
                try:
                    if os.path.getsize(fpath) > MAX_FILE_BYTES:
                        continue
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        total += sum(1 for _ in f)
                except (OSError, IsADirectoryError):
                    continue
    except Exception as e:
        print(f"clone/count failed for {repo_name}: {e}", file=sys.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return total

def fetch_stats():
    name, bio, repos = fetch_repo_data()

    lang_stats = {}
    total_bytes = 0
    stars = 0
    total_commits = 0
    total_loc = 0

    for r in repos:
        stars += r.get("stargazerCount", 0) or 0

        branch_ref = r.get("defaultBranchRef")
        default_branch = branch_ref["name"] if branch_ref else None
        if branch_ref and branch_ref.get("target"):
            total_commits += branch_ref["target"].get("history", {}).get("totalCount", 0)

        for edge in r.get("languages", {}).get("edges", []):
            lang = edge["node"]["name"]
            size = edge["size"]
            lang_stats[lang] = lang_stats.get(lang, 0) + size
            total_bytes += size

        total_loc += count_lines_in_repo(r["name"], default_branch)

    sorted_langs = sorted(lang_stats.items(), key=lambda x: x[1], reverse=True)[:6]
    lang_percentages = []
    for lang, bytes_count in sorted_langs:
        pct = round((bytes_count / total_bytes) * 100, 1) if total_bytes else 0
        lang_percentages.append((lang, pct))

    if total_loc >= 1000:
        loc_str = f"{total_loc/1000:.1f}k"
    else:
        loc_str = str(total_loc)

    return {
        "repos": len(repos),
        "stars": stars,
        "commits": total_commits,
        "loc": total_loc,
        "loc_str": loc_str,
        "languages": lang_percentages,
        "name": name,
        "bio": bio,
    }

LANG_COLORS = {
    "TypeScript": "#3a6a8a", "JavaScript": "#a0903a", "HTML": "#7a5040",
    "CSS": "#5a7a5a", "Python": "#6a5a7a", "C++": "#7a6a4a",
    "Java": "#8a5a4a", "Dockerfile": "#4a6a8a", "Shell": "#5a5a5a",
    "Go": "#4a7a8a", "Rust": "#8a4a4a", "Ruby": "#8a4a5a",
    "PHP": "#6a5a8a", "Swift": "#8a6a3a", "Kotlin": "#6a4a8a",
    "C": "#4a5a7a", "C#": "#5a4a7a",
}

def get_lang_color(lang):
    return LANG_COLORS.get(lang, "#7a6a58")

def donut_chart(cx, cy, r, languages, stroke_width=16):
    if not languages:
        return ""
    circumference = 2 * math.pi * r
    segments = []
    offset = 0
    for lang, pct in languages:
        color = get_lang_color(lang)
        seg_len = (pct / 100) * circumference
        gap = circumference - seg_len
        dasharray = f"{seg_len:.2f} {gap:.2f}"
        rotate = -90 + (offset / circumference) * 360
        segments.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_width}" stroke-dasharray="{dasharray}" '
            f'stroke-linecap="butt" transform="rotate({rotate:.2f} {cx} {cy})" opacity="0.9"/>'
        )
        offset += seg_len
    return "\n    ".join(segments)

def ashoka_chakra(cx, cy, r, stroke_color="#1a1a6a", stroke_width=1.6, opacity=0.65):
    lines = []
    for i in range(24):
        angle = i * 15
        rad = math.pi * angle / 180
        x1 = cx + (r * 0.15) * math.cos(rad)
        y1 = cy + (r * 0.15) * math.sin(rad)
        x2 = cx + r * math.cos(rad)
        y2 = cy + r * math.sin(rad)
        lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke_color}" stroke-width="{stroke_width}" opacity="{opacity}"/>'
        )
    outer = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{stroke_color}" stroke-width="{stroke_width}" opacity="{opacity}"/>'
    inner = f'<circle cx="{cx}" cy="{cy}" r="{r*0.15}" fill="none" stroke="{stroke_color}" stroke-width="{stroke_width}" opacity="{opacity}"/>'
    return "\n    ".join([outer, inner] + lines)

# Donut geometry lives in ONE place now, shared by the background track ring,
# the colored arcs, and the "Top / Languages" label -- this is what was
# causing the double-donut / misaligned-ring bug (the old code hardcoded two
# different centers in two different places).
DONUT_CX = 1020
DONUT_CY = 205
DONUT_R = 42
DONUT_STROKE = 14

def generate_svg(stats):
    langs = stats["languages"]
    now = format_ist_now()
    name_text = stats.get("name", USERNAME) or USERNAME
    bio_text = stats.get("bio", "") or "TypeScript | JavaScript | Python | React | Docker"

    donut = donut_chart(DONUT_CX, DONUT_CY, DONUT_R, langs, stroke_width=DONUT_STROKE)

    legend_items = []
    for i, (lang, pct) in enumerate(langs[:5]):
        y = 278 + i * 19
        color = get_lang_color(lang)
        legend_items.append(
            f'<circle cx="970" cy="{y}" r="5" fill="{color}" opacity="0.9"/>'
            f'<text x="982" y="{y+4}" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="#4a4038">{lang} {pct:.1f}%</text>'
        )
    legend_svg = "\n    ".join(legend_items)

    contacts = [
        ("Google Developer", "vikasranax"),
        ("X (Twitter)", "@vikasranax"),
        ("LinkedIn", "linkedin.com/in/vikasranax"),
        ("Google Play", "vikasranax"),
    ]
    contact_svg = ""
    for i, (label, value) in enumerate(contacts):
        y = 200 + i * 28
        contact_svg += (
            f'<text x="75" y="{y}" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="#5a5048">'
            f'<tspan font-weight="500" fill="#3a3530">{label}</tspan>  {value}</text>'
        )

    svg_template = """<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1200 520" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#f3efe8"/>
      <stop offset="30%" stop-color="#e6ded2"/>
      <stop offset="65%" stop-color="#d2c8ba"/>
      <stop offset="100%" stop-color="#bdb2a2"/>
    </linearGradient>
    <radialGradient id="sunGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#f6d9a8" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#f6d9a8" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="mist1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#b8b0a4" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#b8b0a4" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="mist2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#a0988c" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#a0988c" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="mist3" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#8a8278" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="#8a8278" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="waterGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#b8c4c8" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#93a6ac" stop-opacity="0.78"/>
    </linearGradient>
    <linearGradient id="indiaGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#ff9933" stop-opacity="0.13"/>
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0.06"/>
      <stop offset="100%" stop-color="#138808" stop-opacity="0.13"/>
    </linearGradient>
    <filter id="blur1"><feGaussianBlur stdDeviation="2"/></filter>
    <filter id="blur2"><feGaussianBlur stdDeviation="4"/></filter>
    <filter id="blur3"><feGaussianBlur stdDeviation="9"/></filter>
  </defs>

  <rect width="1200" height="520" fill="url(#skyGrad)"/>
  <rect width="1200" height="520" fill="url(#indiaGrad)"/>

  <!-- Sun disc + Ashoka Chakra, top center -->
  <circle cx="600" cy="78" r="70" fill="url(#sunGlow)"/>
  <g opacity="0.85">
    {chakra}
  </g>

  <!-- Birds, high sky -->
  <g fill="none" stroke="#4a4038" stroke-width="1.5" opacity="0.5">
    <path d="M180,120 Q184,116 188,120 Q192,116 196,120"/>
    <path d="M230,100 Q234,96 238,100 Q242,96 246,100"/>
    <path d="M980,110 Q984,106 988,110 Q992,106 996,110"/>
    <path d="M1030,130 Q1034,126 1038,130 Q1042,126 1046,130"/>
  </g>

  <!-- Far mountains, full width -->
  <path d="M0,340 Q150,250 320,285 T650,255 T950,275 T1200,235 V520 H0Z" fill="#c8c0b4" opacity="0.5" filter="url(#blur3)"/>
  <path d="M0,320 Q220,215 440,260 T820,220 T1200,250 V520 H0Z" fill="#b8b0a2" opacity="0.4" filter="url(#blur3)"/>
  <rect x="0" y="200" width="1200" height="150" fill="url(#mist1)" filter="url(#blur2)"/>

  <!-- Mid karst mountains -->
  <path d="M-50,520 Q120,355 300,400 T620,345 T940,375 T1250,320 V520 H-50Z" fill="#a09888" opacity="0.6" filter="url(#blur2)"/>
  <path d="M-50,520 Q220,375 460,415 T820,360 T1150,395 T1250,355 V520 H-50Z" fill="#908878" opacity="0.5" filter="url(#blur2)"/>
  <rect x="0" y="260" width="1200" height="130" fill="url(#mist2)" filter="url(#blur2)"/>

  <!-- Great Wall, far right, following the ridge line -->
  <g transform="translate(0,-6)">
    <path d="M840,352 L852,344 L864,349 L876,341 L888,346 L900,338 L912,343 L924,335 L936,340 L948,332 L960,337 L972,329 L984,334 L996,326 L1008,331 L1020,323 L1032,328 L1044,320 L1056,325 L1068,317 L1080,322 L1092,314 L1104,319 L1116,311 L1128,316 L1140,308 L1152,313 L1164,305 L1176,310 L1188,302 L1200,307 V520 H840Z" fill="#6a6258" opacity="0.4" filter="url(#blur1)"/>
    <g opacity="0.5">
      <rect x="852" y="343" width="4" height="6" fill="#5a5048"/>
      <rect x="876" y="340" width="4" height="6" fill="#5a5048"/>
      <rect x="900" y="337" width="4" height="6" fill="#5a5048"/>
      <rect x="924" y="334" width="4" height="6" fill="#5a5048"/>
      <rect x="948" y="331" width="4" height="6" fill="#5a5048"/>
      <rect x="972" y="328" width="4" height="6" fill="#5a5048"/>
      <rect x="996" y="325" width="4" height="6" fill="#5a5048"/>
      <rect x="1020" y="322" width="4" height="6" fill="#5a5048"/>
      <rect x="1044" y="319" width="4" height="6" fill="#5a5048"/>
      <rect x="1068" y="316" width="4" height="6" fill="#5a5048"/>
      <rect x="1092" y="313" width="4" height="6" fill="#5a5048"/>
      <rect x="1116" y="310" width="4" height="6" fill="#5a5048"/>
      <rect x="1140" y="307" width="4" height="6" fill="#5a5048"/>
      <rect x="1164" y="304" width="4" height="6" fill="#5a5048"/>
      <rect x="1188" y="301" width="4" height="6" fill="#5a5048"/>
    </g>
  </g>

  <!-- Near mountains -->
  <path d="M-50,520 Q150,430 360,465 T720,420 T1080,450 T1250,405 V520 H-50Z" fill="#7a7266" opacity="0.7" filter="url(#blur1)"/>
  <path d="M-50,520 Q260,450 520,485 T920,440 T1250,470 V520 H-50Z" fill="#6a6258" opacity="0.8"/>

  <!-- Water -->
  <rect x="0" y="462" width="1200" height="58" fill="url(#waterGrad)"/>
  <path d="M0,462 Q300,467 600,462 T1200,467 V520 H0Z" fill="#a8b8bc" opacity="0.4"/>

  <!-- Bamboo grove, far left -->
  <g opacity="0.42" transform="translate(30,0)">
    <line x1="0" y1="322" x2="0" y2="175" stroke="#4a6a3a" stroke-width="3" stroke-linecap="round"/>
    <line x1="14" y1="312" x2="14" y2="152" stroke="#4a6a3a" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="-14" y1="316" x2="-14" y2="200" stroke="#4a6a3a" stroke-width="2" stroke-linecap="round"/>
    <line x1="-6" y1="282" x2="4" y2="272" stroke="#5a7a4a" stroke-width="1.5" fill="none"/>
    <line x1="8" y1="252" x2="18" y2="242" stroke="#5a7a4a" stroke-width="1.5" fill="none"/>
    <line x1="-10" y1="222" x2="0" y2="212" stroke="#5a7a4a" stroke-width="1.5" fill="none"/>
    <line x1="10" y1="192" x2="20" y2="182" stroke="#5a7a4a" stroke-width="1.5" fill="none"/>
  </g>

  <!-- Red maple, left edge -->
  <g opacity="0.75" transform="translate(20,0)">
    <path d="M35,520 Q42,475 48,455 Q50,445 46,440 Q48,434 50,428" stroke="#7a4030" stroke-width="3" fill="none"/>
    <path d="M50,428 Q36,418 30,424 Q34,412 42,406 Q48,401 54,412 Q60,406 66,418 Q72,424 60,430 Q66,436 58,442 Q50,436 50,428Z" fill="#c86050"/>
    <path d="M46,444 Q32,434 26,442 Q28,428 36,422 Q42,417 48,428 Q54,422 58,434 Q62,440 50,446Z" fill="#b05040"/>
    <path d="M50,466 Q34,456 28,464 Q30,450 38,444 Q44,439 50,450 Q56,444 60,456 Q64,462 52,468Z" fill="#a04030"/>
  </g>

  <!-- Lotus flowers -->
  <g opacity="0.85" transform="translate(120,0)">
    <ellipse cx="0" cy="490" rx="14" ry="8" fill="#d06060" transform="rotate(-20 0 490)"/>
    <ellipse cx="0" cy="490" rx="14" ry="8" fill="#c85050" transform="rotate(20 0 490)"/>
    <ellipse cx="0" cy="490" rx="14" ry="8" fill="#d06060" transform="rotate(50 0 490)"/>
    <ellipse cx="0" cy="490" rx="14" ry="8" fill="#c85050" transform="rotate(-50 0 490)"/>
    <ellipse cx="0" cy="490" rx="14" ry="8" fill="#d06060" transform="rotate(80 0 490)"/>
    <ellipse cx="0" cy="490" rx="14" ry="8" fill="#c85050" transform="rotate(-80 0 490)"/>
    <circle cx="0" cy="490" r="5" fill="#f0c8a0"/>
    <ellipse cx="46" cy="502" rx="10" ry="6" fill="#b85050" transform="rotate(-20 46 502)"/>
    <ellipse cx="46" cy="502" rx="10" ry="6" fill="#a84040" transform="rotate(20 46 502)"/>
    <ellipse cx="46" cy="502" rx="10" ry="6" fill="#b85050" transform="rotate(50 46 502)"/>
    <ellipse cx="46" cy="502" rx="10" ry="6" fill="#a84040" transform="rotate(-50 46 502)"/>
    <circle cx="46" cy="502" r="4" fill="#f0c8a0"/>
    <path d="M0,498 Q-2,510 -5,520" stroke="#4a6a4a" stroke-width="2" fill="none" opacity="0.6"/>
    <path d="M46,508 Q43,515 39,520" stroke="#4a6a4a" stroke-width="1.5" fill="none" opacity="0.6"/>
  </g>

  <!-- Peacock -->
  <g opacity="0.75" transform="translate(230, 415) scale(1.05)">
    <ellipse cx="0" cy="22" rx="10" ry="16" fill="#1a5a7a"/>
    <path d="M-4,10 Q-8,-8 0,-20 Q8,-8 4,10Z" fill="#1a5a7a"/>
    <circle cx="0" cy="-24" r="6" fill="#1a5a7a"/>
    <path d="M4,-24 L10,-22 L4,-20Z" fill="#c8a030"/>
    <path d="M-2,-30 L-6,-42 M0,-30 L0,-44 M2,-30 L6,-42" stroke="#1a5a7a" stroke-width="2" fill="none"/>
    <circle cx="-6" cy="-42" r="2" fill="#1a5a7a"/>
    <circle cx="0" cy="-44" r="2" fill="#1a5a7a"/>
    <circle cx="6" cy="-42" r="2" fill="#1a5a7a"/>
    <path d="M-6,35 Q-50,15 -60,-25 Q-35,-15 -6,30Z" fill="#2a7a9a" opacity="0.7"/>
    <path d="M6,35 Q50,15 60,-25 Q35,-15 6,30Z" fill="#2a7a9a" opacity="0.7"/>
    <path d="M-4,38 Q-30,55 -45,25 Q-25,42 -4,35Z" fill="#3a8aaa" opacity="0.6"/>
    <path d="M4,38 Q30,55 45,25 Q25,42 4,35Z" fill="#3a8aaa" opacity="0.6"/>
    <circle cx="-30" cy="5" r="4" fill="#f0c040" opacity="0.85"/>
    <circle cx="-30" cy="5" r="2" fill="#1a5a7a" opacity="0.9"/>
    <circle cx="30" cy="5" r="4" fill="#f0c040" opacity="0.85"/>
    <circle cx="30" cy="5" r="2" fill="#1a5a7a" opacity="0.9"/>
    <circle cx="-18" cy="28" r="3.5" fill="#f0c040" opacity="0.75"/>
    <circle cx="-18" cy="28" r="1.8" fill="#1a5a7a" opacity="0.85"/>
    <circle cx="18" cy="28" r="3.5" fill="#f0c040" opacity="0.75"/>
    <circle cx="18" cy="28" r="1.8" fill="#1a5a7a" opacity="0.85"/>
    <circle cx="-42" cy="-8" r="3" fill="#f0c040" opacity="0.7"/>
    <circle cx="-42" cy="-8" r="1.5" fill="#1a5a7a" opacity="0.8"/>
    <circle cx="42" cy="-8" r="3" fill="#f0c040" opacity="0.7"/>
    <circle cx="42" cy="-8" r="1.5" fill="#1a5a7a" opacity="0.8"/>
    <line x1="-4" y1="38" x2="-6" y2="48" stroke="#1a5a7a" stroke-width="2"/>
    <line x1="4" y1="38" x2="6" y2="48" stroke="#1a5a7a" stroke-width="2"/>
  </g>

  <!-- Pandas -->
  <g opacity="0.75" transform="translate(340,0)">
    <ellipse cx="0" cy="472" rx="16" ry="12" fill="#2a2420"/>
    <circle cx="-8" cy="465" r="8" fill="#2a2420"/>
    <ellipse cx="-13" cy="460" rx="4" ry="3" fill="#2a2420"/>
    <ellipse cx="-3" cy="460" rx="4" ry="3" fill="#2a2420"/>
    <circle cx="-10" cy="465" r="2" fill="#f3efe8"/>
    <circle cx="-6" cy="465" r="2" fill="#f3efe8"/>
    <ellipse cx="-8" cy="469" rx="2.2" ry="1.4" fill="#f3efe8"/>
    <ellipse cx="50" cy="482" rx="11" ry="8" fill="#3a3428"/>
    <circle cx="44" cy="476" r="5.5" fill="#3a3428"/>
    <ellipse cx="40" cy="472" rx="2.8" ry="2" fill="#3a3428"/>
    <ellipse cx="48" cy="472" rx="2.8" ry="2" fill="#3a3428"/>
  </g>

  <!-- Vietnamese farmer, rice hat -->
  <g opacity="0.7" transform="translate(450, 458)">
    <ellipse cx="0" cy="-8" rx="28" ry="8" fill="#4a4038" opacity="0.9"/>
    <ellipse cx="0" cy="-8" rx="22" ry="5" fill="#5a5048" opacity="0.8"/>
    <path d="M-10,0 L-7,22 L7,22 L10,0Z" fill="#5a5048" opacity="0.8"/>
    <circle cx="0" cy="-14" r="5" fill="#6a6058" opacity="0.8"/>
    <line x1="12" y1="5" x2="22" y2="-5" stroke="#5a5048" stroke-width="2" opacity="0.7"/>
  </g>

  <!-- Korean hanok roof -->
  <g opacity="0.7" transform="translate(30,0)">
    <path d="M500,308 Q520,293 540,303 Q560,293 580,303 Q600,293 620,308" stroke="#5a5048" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M505,311 Q525,298 545,306 Q565,298 585,306 Q605,298 615,311" stroke="#6a6058" stroke-width="2" fill="none" stroke-linecap="round"/>
    <rect x="530" y="311" width="24" height="18" rx="2" fill="#7a7068" opacity="0.6"/>
    <rect x="566" y="311" width="24" height="18" rx="2" fill="#7a7068" opacity="0.6"/>
    <rect x="528" y="311" width="3" height="18" fill="#5a5048" opacity="0.7"/>
    <rect x="551" y="311" width="3" height="18" fill="#5a5048" opacity="0.7"/>
    <rect x="566" y="311" width="3" height="18" fill="#5a5048" opacity="0.7"/>
    <rect x="589" y="311" width="3" height="18" fill="#5a5048" opacity="0.7"/>
  </g>

  <!-- Cherry blossom petals, scattered -->
  <g opacity="0.35">
    <ellipse cx="680" cy="205" rx="4" ry="2" fill="#e08090" transform="rotate(20 680 205)"/>
    <ellipse cx="710" cy="225" rx="3" ry="1.5" fill="#d07080" transform="rotate(-15 710 225)"/>
    <ellipse cx="650" cy="245" rx="3.5" ry="1.8" fill="#e08090" transform="rotate(45 650 245)"/>
    <ellipse cx="730" cy="185" rx="2.5" ry="1.2" fill="#d07080" transform="rotate(30 730 185)"/>
    <ellipse cx="770" cy="215" rx="3" ry="1.5" fill="#e08090" transform="rotate(-25 770 215)"/>
  </g>

  <!-- Japanese torii gate -->
  <g opacity="0.5" transform="translate(700, 290) scale(0.72)">
    <rect x="-35" y="0" width="4" height="50" fill="#8a3020" opacity="0.7"/>
    <rect x="35" y="0" width="4" height="50" fill="#8a3020" opacity="0.7"/>
    <rect x="-45" y="5" width="90" height="5" rx="2" fill="#a03020" opacity="0.8"/>
    <rect x="-40" y="35" width="80" height="4" rx="2" fill="#a03020" opacity="0.8"/>
    <path d="M-50,5 Q0,-5 50,5" stroke="#a03020" stroke-width="3" fill="none" opacity="0.8"/>
  </g>

  <!-- Cherry blossom branch, right side -->
  <g opacity="0.8" transform="translate(-30,0)">
    <path d="M1080,440 Q1090,420 1100,405 Q1108,412 1118,402" stroke="#5a4038" stroke-width="2.5" fill="none" opacity="0.7"/>
    <path d="M1100,405 Q1110,395 1125,390" stroke="#5a4038" stroke-width="2" fill="none" opacity="0.6"/>
    <circle cx="1100" cy="405" r="6" fill="#e08090"/>
    <circle cx="1106" cy="410" r="5.5" fill="#d07080"/>
    <circle cx="1094" cy="410" r="5" fill="#e08090"/>
    <circle cx="1100" cy="415" r="5.5" fill="#d07080"/>
    <circle cx="1100" cy="408" r="2.5" fill="#f8d0d8"/>
    <circle cx="1106" cy="412" r="2" fill="#f8d0d8"/>
    <circle cx="1094" cy="412" r="2" fill="#f8d0d8"/>
    <circle cx="1125" cy="390" r="5" fill="#e08090"/>
    <circle cx="1130" cy="394" r="4.5" fill="#d07080"/>
    <circle cx="1120" cy="394" r="4" fill="#e08090"/>
    <circle cx="1125" cy="398" r="4.5" fill="#d07080"/>
    <circle cx="1125" cy="393" r="2" fill="#f8d0d8"/>
  </g>

  <!-- Chinese pavilion -->
  <g opacity="0.45" transform="translate(800, 300) scale(0.62)">
    <path d="M-25,0 Q0,-12 25,0" stroke="#5a4038" stroke-width="3" fill="none"/>
    <path d="M-20,0 L-20,25 L20,25 L20,0" fill="#6a5040" opacity="0.6"/>
    <rect x="-3" y="8" width="6" height="10" rx="1" fill="#5a4038" opacity="0.7"/>
    <line x1="0" y1="0" x2="0" y2="-15" stroke="#5a4038" stroke-width="2"/>
    <circle cx="0" cy="-15" r="3" fill="#c8a030" opacity="0.6"/>
  </g>

  <!-- Indian flag tricolor, footer -->
  <rect x="0" y="512" width="1200" height="3" fill="#ff9933" opacity="0.45"/>
  <rect x="0" y="515" width="1200" height="3" fill="#ffffff" opacity="0.4"/>
  <rect x="0" y="518" width="1200" height="2" fill="#138808" opacity="0.45"/>

  <!-- Foreground mist -->
  <rect x="0" y="420" width="1200" height="100" fill="url(#mist3)" filter="url(#blur2)"/>

  <!-- LEFT: Personal + Contacts -->
  <text x="60" y="85" font-family="Space Grotesk, sans-serif" font-size="48" font-weight="500" fill="#2a2520" letter-spacing="1">{name}</text>
  <text x="60" y="118" font-family="IBM Plex Sans, sans-serif" font-size="14" fill="#5a5048">{bio}</text>

  <text x="60" y="155" font-family="IBM Plex Sans, sans-serif" font-size="13" font-weight="500" fill="#4a4038">Connect</text>
  <rect x="60" y="165" width="320" height="2" rx="1" fill="#b8b0a4" opacity="0.4"/>
  {contacts}

  <text x="60" y="330" font-family="IBM Plex Sans, sans-serif" font-size="13" font-weight="500" fill="#4a4038">Human Languages</text>
  <rect x="60" y="340" width="320" height="2" rx="1" fill="#b8b0a4" opacity="0.4"/>
  <text x="75" y="362" font-family="IBM Plex Sans, sans-serif" font-size="12" fill="#5a5048">\u0939\u093f\u0928\u094d\u0926\u0940 \u00b7 English \u00b7 \u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u00b7 \u4e2d\u56fd\u4eba 路 Bahasa Indonesia</text>

  <!-- RIGHT: Stats + Donut -->
  <g>
    <rect x="860" y="55" width="110" height="50" rx="10" fill="rgba(255,255,255,0.4)" stroke="rgba(255,255,255,0.55)" stroke-width="0.8"/>
    <text x="915" y="78" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="22" font-weight="500" fill="#2a2520" font-variant-numeric="tabular-nums">{repos}</text>
    <text x="915" y="95" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="#4a4038">repos</text>
  </g>
  <g>
    <rect x="985" y="55" width="110" height="50" rx="10" fill="rgba(255,255,255,0.4)" stroke="rgba(255,255,255,0.55)" stroke-width="0.8"/>
    <text x="1040" y="78" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="22" font-weight="500" fill="#2a2520" font-variant-numeric="tabular-nums">{stars}</text>
    <text x="1040" y="95" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="#4a4038">stars</text>
  </g>
  <g>
    <rect x="860" y="115" width="110" height="50" rx="10" fill="rgba(255,255,255,0.4)" stroke="rgba(255,255,255,0.55)" stroke-width="0.8"/>
    <text x="915" y="138" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="22" font-weight="500" fill="#2a2520" font-variant-numeric="tabular-nums">{commits}</text>
    <text x="915" y="155" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="#4a4038">commits</text>
  </g>
  <g>
    <rect x="985" y="115" width="110" height="50" rx="10" fill="rgba(255,255,255,0.4)" stroke="rgba(255,255,255,0.55)" stroke-width="0.8"/>
    <text x="1040" y="138" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="20" font-weight="500" fill="#2a2520" font-variant-numeric="tabular-nums">{loc}</text>
    <text x="1040" y="155" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="#4a4038">lines of code</text>
  </g>

  <text x="920" y="195" font-family="IBM Plex Sans, sans-serif" font-size="13" font-weight="500" fill="#4a4038">Code Breakdown</text>
  <rect x="920" y="205" width="200" height="2" rx="1" fill="#b8b0a4" opacity="0.4"/>

  <circle cx="{dcx}" cy="{dcy}" r="{dr}" fill="none" stroke="#d4cec5" stroke-width="{dsw}" opacity="0.5"/>
  {donut}

  <text x="{dcx}" y="{dcy_top_label}" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="13" font-weight="500" fill="#4a4038">Top</text>
  <text x="{dcx}" y="{dcy_bottom_label}" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="10" fill="#6a6258">Languages</text>

  {legend}

  <text x="60" y="505" font-family="IBM Plex Mono, monospace" font-size="9" fill="#a09888">updated {updated}</text>
</svg>"""

    chakra = ashoka_chakra(600, 78, 26)

    svg = svg_template.format(
        chakra=chakra,
        contacts=contact_svg,
        name=name_text,
        bio=bio_text,
        repos=stats["repos"],
        stars=stats["stars"],
        commits=stats["commits"],
        loc=stats["loc_str"],
        donut=donut,
        dcx=DONUT_CX, dcy=DONUT_CY, dr=DONUT_R, dsw=DONUT_STROKE,
        dcy_top_label=DONUT_CY - 4, dcy_bottom_label=DONUT_CY + 10,
        legend=legend_svg,
        updated=now,
    )
    return svg

def main():
    print("Fetching GitHub stats (GraphQL commits + real cloned LOC count)...")
    stats = fetch_stats()
    print(f"Stats: {json.dumps({k: v for k, v in stats.items() if k != 'languages'}, indent=2)}")
    svg = generate_svg(stats)
    out_path = "assets/github-banner.svg"
    os.makedirs("assets", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Banner written to {out_path}")

if __name__ == "__main__":
    main()
