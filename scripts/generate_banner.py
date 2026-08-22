#!/usr/bin/env python3
"""
Generates a custom ink-wash landscape GitHub profile banner.
Layout: Left = contacts/personal, Right = donut chart + stats.
Updates every 6 hours via GitHub Actions.
Fonts: Space Grotesk (headlines), IBM Plex Sans (body), IBM Plex Mono (data).
"""
import os
import sys
import json
import urllib.request
import datetime
import math
import re


def ordinal_suffix(day):
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_ist_now():
    utc = datetime.datetime.now(datetime.timezone.utc)
    ist = utc + datetime.timedelta(hours=5, minutes=30)
    suffix = ordinal_suffix(ist.day)
    return ist.strftime(f"%d{suffix} %B %Y · %I:%M %p IST")


USERNAME = os.environ.get("GITHUB_USERNAME", "vikasranax")
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def api_call(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "vikasranax-banner-generator")
    if TOKEN:
        req.add_header("Authorization", f"token {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            link = resp.headers.get("Link", "")
            return data, link
    except Exception as e:
        print(f"API error for {url}: {e}", file=sys.stderr)
        return [], ""


def get_total_commits(repo_name, default_branch):
    """
    Use per_page=1 and read the Link header's last-page number.
    With per_page=1, the last-page number equals the total commit count.
    """
    url = (
        f"https://api.github.com/repos/{USERNAME}/{repo_name}/commits"
        f"?sha={default_branch}&per_page=1"
    )
    data, link = api_call(url)
    if link:
        matches = re.findall(r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"', link)
        if matches:
            return int(matches[-1])
    if isinstance(data, list):
        return len(data)
    return 0


def fetch_all_repos():
    """Paginate through every public repo (not just first 100)."""
    all_repos = []
    page = 1
    while page <= 10:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&sort=updated"
        )
        repos, _ = api_call(url)
        if not isinstance(repos, list) or not repos:
            break
        all_repos.extend(repos)
        if len(repos) < 100:
            break
        page += 1
    return all_repos


def fetch_stats():
    user, _ = api_call(f"https://api.github.com/users/{USERNAME}")
    repos = fetch_all_repos()

    lang_stats = {}
    total_bytes = 0
    stars = 0
    total_commits = 0

    SKIP_LANGS = {
        "HTML", "CSS", "Dockerfile", "Shell", "Makefile",
        "Markdown", "JSON", "YAML", "TOML", "TeX", "BitBake",
        "Batchfile", "PowerShell", "Jupyter Notebook",
    }

    for r in repos:
        stars += r.get("stargazers_count", 0)
        default = r.get("default_branch") or "main"
        try:
            total_commits += get_total_commits(r["name"], default)
        except Exception as e:
            print(f"commits fetch failed for {r.get('name')}: {e}", file=sys.stderr)

        lang_url = r.get("languages_url")
        if lang_url:
            langs, _ = api_call(lang_url)
            if isinstance(langs, dict):
                for lang, bytes_count in langs.items():
                    if lang in SKIP_LANGS:
                        continue
                    lang_stats[lang] = lang_stats.get(lang, 0) + bytes_count
                    total_bytes += bytes_count

    sorted_langs = sorted(lang_stats.items(), key=lambda x: x[1], reverse=True)[:6]
    total_for_pct = sum(v for _, v in sorted_langs) or 1
    lang_percentages = []
    for lang, bytes_count in sorted_langs:
        pct = round((bytes_count / total_for_pct) * 100, 1)
        lang_percentages.append((lang, pct))

    # LOC: per-language weighted estimate (bytes / avg line length)
    LANG_DIVISOR = {
        "TypeScript": 22, "JavaScript": 22, "Python": 24,
        "Java": 22, "C++": 20, "C": 20, "C#": 22, "Go": 22,
        "Rust": 22, "Ruby": 24, "PHP": 22, "Swift": 22,
        "Kotlin": 22, "Dockerfile": 28, "Shell": 26,
    }
    estimated_loc = 0
    for lang, b in lang_stats.items():
        estimated_loc += b // LANG_DIVISOR.get(lang, 22)

    if estimated_loc >= 1000:
        loc_str = f"{estimated_loc/1000:.1f}k"
    else:
        loc_str = str(estimated_loc)

    return {
        "repos": len(repos),
        "stars": stars,
        "commits": total_commits,
        "loc": estimated_loc,
        "loc_str": loc_str,
        "languages": lang_percentages,
        "name": user.get("name", USERNAME),
        "bio": user.get("bio", ""),
    }


LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "HTML": "#e34c26",
    "CSS": "#563d7c", "Python": "#3776ab", "C++": "#f34b7d",
    "Java": "#b07219", "Dockerfile": "#384d54", "Shell": "#89e051",
    "Go": "#00add8", "Rust": "#dea584", "Ruby": "#cc342d",
    "PHP": "#4f5d95", "Swift": "#ffac45", "Kotlin": "#a97bff",
    "C": "#555555", "C#": "#178600",
}


def get_lang_color(lang):
    return LANG_COLORS.get(lang, "#7a6a58")


def donut_chart(cx, cy, r, languages, stroke_width=14):
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
            f'stroke-linecap="butt" transform="rotate({rotate:.2f} {cx} {cy})" opacity="0.95"/>'
        )
        offset += seg_len
    return "\n    ".join(segments)


def ashoka_chakra(cx, cy, r, stroke_color="#1a3a6a", stroke_width=1.4, opacity=0.55):
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
    outer = (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="{stroke_color}" stroke-width="{stroke_width}" opacity="{opacity}"/>'
    )
    inner = (
        f'<circle cx="{cx}" cy="{cy}" r="{r*0.15}" fill="none" '
        f'stroke="{stroke_color}" stroke-width="{stroke_width}" opacity="{opacity}"/>'
    )
    return "\n    ".join([outer, inner] + lines)


def generate_svg(stats):
    langs = stats["languages"]
    now = format_ist_now()
    name_text = stats.get("name", USERNAME) or USERNAME
    bio_text = stats.get("bio", "") or "TypeScript | JavaScript | Python | React | Docker"

    # === Donut chart aligned with its background track ===
    donut_cx, donut_cy, donut_r = 970, 285, 44
    donut = donut_chart(donut_cx, donut_cy, donut_r, langs, stroke_width=14)

    # === Legend on the right side of donut, vertically centered ===
    legend_items = []
    legend_x = 1030
    legend_text_x = legend_x + 14
    for i, (lang, pct) in enumerate(langs[:5]):
        y = donut_cy - 44 + i * 22
        color = get_lang_color(lang)
        legend_items.append(
            f'<circle cx="{legend_x}" cy="{y}" r="5" fill="{color}" opacity="0.95"/>'
            f'<text x="{legend_text_x}" y="{y+4}" font-family="IBM Plex Sans, sans-serif" '
            f'font-size="11" fill="#3a3530">{lang} {pct:.1f}%</text>'
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
            f'<tspan font-weight="600" fill="#2a2520">{label}</tspan>   {value}</text>'
        )

    svg_template = """<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1200 520" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fbf6ec"/>
      <stop offset="40%" stop-color="#f1ead9"/>
      <stop offset="75%" stop-color="#dccfb6"/>
      <stop offset="100%" stop-color="#b8a988"/>
    </linearGradient>
    <linearGradient id="sunGlow" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffd9a0" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="#ffb070" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="mist1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fff8e8" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="#fff8e8" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="mist2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e8dec8" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#e8dec8" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="waterGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#a8b8bc" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#7a9098" stop-opacity="0.85"/>
    </linearGradient>
    <linearGradient id="indiaGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#ff9933" stop-opacity="0.10"/>
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0.04"/>
      <stop offset="100%" stop-color="#138808" stop-opacity="0.10"/>
    </linearGradient>
    <radialGradient id="vignette" cx="0.5" cy="0.45" r="0.75">
      <stop offset="60%" stop-color="#000000" stop-opacity="0"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0.18"/>
    </radialGradient>
    <filter id="blur1"><feGaussianBlur stdDeviation="2"/></filter>
    <filter id="blur2"><feGaussianBlur stdDeviation="5"/></filter>
    <filter id="blur3"><feGaussianBlur stdDeviation="10"/></filter>
  </defs>

  <!-- ===== Sky & atmosphere ===== -->
  <rect width="1200" height="520" fill="url(#skyGrad)"/>
  <rect width="1200" height="520" fill="url(#indiaGrad)"/>

  <!-- Soft sun glow -->
  <circle cx="980" cy="120" r="180" fill="url(#sunGlow)"/>
  <circle cx="980" cy="120" r="34" fill="#f9d29c" opacity="0.45" filter="url(#blur2)"/>

  <!-- Ashoka Chakra (subtle, top-center) -->
  <g opacity="0.6">
    {chakra}
  </g>

  <!-- ===== Far mountains (misty) ===== -->
  <path d="M0,355 Q160,260 320,300 T640,265 T960,295 T1200,250 V520 H0Z"
        fill="#b8b0a4" opacity="0.45" filter="url(#blur3)"/>
  <path d="M0,335 Q220,225 440,275 T860,235 T1200,265 V520 H0Z"
        fill="#a8a094" opacity="0.4" filter="url(#blur3)"/>

  <!-- ===== Bamboo (left, subtle) ===== -->
  <g opacity="0.35">
    <line x1="32" y1="330" x2="32" y2="160" stroke="#4a6a3a" stroke-width="3" stroke-linecap="round"/>
    <line x1="46" y1="320" x2="46" y2="140" stroke="#4a6a3a" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="24" y1="280" x2="36" y2="268" stroke="#5a7a4a" stroke-width="1.5"/>
    <line x1="40" y1="248" x2="52" y2="236" stroke="#5a7a4a" stroke-width="1.5"/>
    <line x1="20" y1="220" x2="32" y2="208" stroke="#5a7a4a" stroke-width="1.5"/>
    <line x1="44" y1="190" x2="56" y2="178" stroke="#5a7a4a" stroke-width="1.5"/>
    <ellipse cx="36" cy="158" rx="6" ry="2" fill="#6a8a4a" transform="rotate(30 36 158)"/>
    <ellipse cx="46" cy="138" rx="5" ry="2" fill="#6a8a4a" transform="rotate(-20 46 138)"/>
  </g>

  <!-- ===== Mid mountains (Vietnam karst silhouettes) ===== -->
  <path d="M-50,520 Q120,360 280,400 T560,355 T860,385 T1250,335 V520 H-50Z"
        fill="#9a9080" opacity="0.55" filter="url(#blur2)"/>
  <path d="M-50,520 Q220,390 420,430 T780,380 T1100,410 T1250,365 V520 H-50Z"
        fill="#82786a" opacity="0.55" filter="url(#blur2)"/>

  <!-- ===== Mist layers ===== -->
  <rect x="0" y="220" width="1200" height="180" fill="url(#mist1)" filter="url(#blur2)"/>
  <rect x="0" y="260" width="1200" height="160" fill="url(#mist2)" filter="url(#blur2)"/>

  <!-- ===== Pavilion (small, refined) ===== -->
  <g opacity="0.7" transform="translate(640, 305)">
    <path d="M-30,0 Q0,-14 30,0" stroke="#5a4038" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M-26,5 Q0,-9 26,5" stroke="#6a5040" stroke-width="2" fill="none" stroke-linecap="round"/>
    <rect x="-22" y="3" width="44" height="22" rx="2" fill="#6a5040" opacity="0.55"/>
    <rect x="-14" y="9" width="6" height="16" rx="1" fill="#3a2820" opacity="0.7"/>
    <rect x="8" y="9" width="6" height="16" rx="1" fill="#3a2820" opacity="0.7"/>
    <line x1="0" y1="-14" x2="0" y2="-22" stroke="#5a4038" stroke-width="2"/>
    <circle cx="0" cy="-22" r="3" fill="#c8a030" opacity="0.7"/>
  </g>

  <!-- ===== Torii gate (subtle) ===== -->
  <g opacity="0.45" transform="translate(540, 320) scale(0.65)">
    <rect x="-32" y="0" width="4" height="48" fill="#8a3020" opacity="0.7"/>
    <rect x="28" y="0" width="4" height="48" fill="#8a3020" opacity="0.7"/>
    <rect x="-40" y="4" width="80" height="5" rx="2" fill="#a03020" opacity="0.8"/>
    <rect x="-36" y="32" width="72" height="4" rx="2" fill="#a03020" opacity="0.8"/>
    <path d="M-44,4 Q0,-4 44,4" stroke="#a03020" stroke-width="3" fill="none" opacity="0.8"/>
  </g>

  <!-- ===== Cherry blossom branch ===== -->
  <g opacity="0.85">
    <path d="M1140,440 Q1120,420 1095,405 Q1080,398 1065,395" stroke="#5a4038" stroke-width="2.5" fill="none"/>
    <path d="M1095,405 Q1085,395 1075,388" stroke="#5a4038" stroke-width="1.8" fill="none"/>
    <circle cx="1095" cy="405" r="6" fill="#e8a0b0"/>
    <circle cx="1102" cy="410" r="5.5" fill="#d890a0"/>
    <circle cx="1088" cy="410" r="5" fill="#e8a0b0"/>
    <circle cx="1095" cy="415" r="5.5" fill="#d890a0"/>
    <circle cx="1095" cy="408" r="2.5" fill="#f8d0d8"/>
    <circle cx="1075" cy="388" r="5" fill="#e8a0b0"/>
    <circle cx="1080" cy="392" r="4.5" fill="#d890a0"/>
    <circle cx="1070" cy="392" r="4" fill="#e8a0b0"/>
    <circle cx="1075" cy="396" r="4.5" fill="#d890a0"/>
    <circle cx="1075" cy="390" r="2" fill="#f8d0d8"/>
    <ellipse cx="1120" cy="430" rx="3" ry="1.5" fill="#e8a0b0" opacity="0.55" transform="rotate(30 1120 430)"/>
    <ellipse cx="1105" cy="445" rx="2.5" ry="1.2" fill="#d890a0" opacity="0.45" transform="rotate(-20 1105 445)"/>
  </g>

  <!-- ===== Great Wall (subtle, distant) ===== -->
  <path d="M780,345 L790,338 L800,342 L810,335 L820,340 L830,332 L840,337 L850,330 L860,335 L870,328 L880,333 L890,326 L900,331 L910,324 L920,329 L930,322 L940,327 L950,320 L960,325 L970,318 V520 H780Z"
        fill="#6a6258" opacity="0.35" filter="url(#blur1)"/>

  <!-- ===== Near mountains ===== -->
  <path d="M-50,520 Q160,425 360,465 T720,415 T1080,445 T1250,395 V520 H-50Z"
        fill="#7a7266" opacity="0.65" filter="url(#blur1)"/>
  <path d="M-50,520 Q260,445 510,485 T920,435 T1250,465 V520 H-50Z"
        fill="#5e564a" opacity="0.8"/>

  <!-- ===== Water reflection ===== -->
  <rect x="0" y="465" width="1200" height="55" fill="url(#waterGrad)"/>
  <path d="M0,465 Q300,470 600,465 T1200,470 V520 H0Z" fill="#a0b0b4" opacity="0.4"/>
  <line x1="0" y1="478" x2="1200" y2="478" stroke="#c8d8dc" stroke-width="0.6" opacity="0.4"/>
  <line x1="0" y1="488" x2="1200" y2="488" stroke="#c8d8dc" stroke-width="0.5" opacity="0.3"/>

  <!-- ===== Lotus (India element) ===== -->
  <g opacity="0.85">
    <ellipse cx="100" cy="490" rx="13" ry="7" fill="#d06060" transform="rotate(-20 100 490)"/>
    <ellipse cx="100" cy="490" rx="13" ry="7" fill="#c85050" transform="rotate(20 100 490)"/>
    <ellipse cx="100" cy="490" rx="13" ry="7" fill="#d06060" transform="rotate(50 100 490)"/>
    <ellipse cx="100" cy="490" rx="13" ry="7" fill="#c85050" transform="rotate(-50 100 490)"/>
    <ellipse cx="100" cy="490" rx="13" ry="7" fill="#d06060" transform="rotate(80 100 490)"/>
    <ellipse cx="100" cy="490" rx="13" ry="7" fill="#c85050" transform="rotate(-80 100 490)"/>
    <circle cx="100" cy="490" r="4.5" fill="#f0c8a0"/>
    <path d="M100,498 Q98,510 95,520" stroke="#4a6a4a" stroke-width="2" fill="none" opacity="0.6"/>
  </g>

  <!-- ===== Peacock (subtle, right side) ===== -->
  <g opacity="0.7" transform="translate(440, 425) scale(0.9)">
    <ellipse cx="0" cy="22" rx="9" ry="14" fill="#1a5a7a"/>
    <path d="M-3,8 Q-7,-8 0,-18 Q7,-8 3,8Z" fill="#1a5a7a"/>
    <circle cx="0" cy="-22" r="5" fill="#1a5a7a"/>
    <path d="M3,-22 L9,-20 L3,-18Z" fill="#c8a030"/>
    <path d="M-5,35 Q-42,15 -52,-20 Q-30,-12 -5,30Z" fill="#2a7a9a" opacity="0.6"/>
    <path d="M5,35 Q42,15 52,-20 Q30,-12 5,30Z" fill="#2a7a9a" opacity="0.6"/>
    <circle cx="-26" cy="3" r="3.5" fill="#f0c040" opacity="0.85"/>
    <circle cx="-26" cy="3" r="1.6" fill="#1a5a7a"/>
    <circle cx="26" cy="3" r="3.5" fill="#f0c040" opacity="0.85"/>
    <circle cx="26" cy="3" r="1.6" fill="#1a5a7a"/>
    <circle cx="-15" cy="22" r="3" fill="#f0c040" opacity="0.75"/>
    <circle cx="15" cy="22" r="3" fill="#f0c040" opacity="0.75"/>
    <line x1="-3" y1="36" x2="-5" y2="46" stroke="#1a5a7a" stroke-width="2"/>
    <line x1="3" y1="36" x2="5" y2="46" stroke="#1a5a7a" stroke-width="2"/>
  </g>

  <!-- ===== Birds ===== -->
  <g fill="none" stroke="#3a3530" stroke-width="1.4" opacity="0.55">
    <path d="M620,140 Q625,135 630,140 Q635,135 640,140"/>
    <path d="M660,120 Q664,116 668,120 Q672,116 676,120"/>
    <path d="M645,158 Q649,154 653,158 Q657,154 661,158"/>
  </g>

  <!-- ===== Indian tricolor stripe ===== -->
  <rect x="0" y="513" width="1200" height="2.5" fill="#ff9933" opacity="0.45"/>
  <rect x="0" y="515.5" width="1200" height="2.5" fill="#ffffff" opacity="0.4"/>
  <rect x="0" y="518" width="1200" height="2" fill="#138808" opacity="0.45"/>

  <!-- ===== Foreground mist ===== -->
  <rect x="0" y="425" width="1200" height="95" fill="url(#mist2)" filter="url(#blur2)"/>

  <!-- ===== Vignette ===== -->
  <rect width="1200" height="520" fill="url(#vignette)"/>

  <!-- ================= LEFT PANEL ================= -->
  <text x="60" y="85" font-family="Space Grotesk, sans-serif" font-size="46" font-weight="600"
        fill="#1f1a14" letter-spacing="0.5">{name}</text>
  <text x="60" y="115" font-family="IBM Plex Sans, sans-serif" font-size="13.5" fill="#4a4038">{bio}</text>

  <text x="60" y="155" font-family="IBM Plex Sans, sans-serif" font-size="13" font-weight="600" fill="#2a2520">Connect</text>
  <rect x="60" y="165" width="340" height="1.5" rx="0.75" fill="#9a9080" opacity="0.5"/>
  {contacts}

  <text x="60" y="335" font-family="IBM Plex Sans, sans-serif" font-size="13" font-weight="600" fill="#2a2520">Human Languages</text>
  <rect x="60" y="345" width="340" height="1.5" rx="0.75" fill="#9a9080" opacity="0.5"/>
  <text x="75" y="367" font-family="IBM Plex Sans, sans-serif" font-size="12" fill="#4a4038">हिन्दी · English · Русский · 中國人 · Bahasa Indonesia</text>

  <!-- ================= RIGHT PANEL: stats ================= -->
  <g>
    <rect x="860" y="55" width="115" height="52" rx="10" fill="#ffffff" fill-opacity="0.42"
          stroke="#ffffff" stroke-opacity="0.55" stroke-width="0.8"/>
    <text x="917.5" y="80" text-anchor="middle" font-family="IBM Plex Mono, monospace"
          font-size="22" font-weight="500" fill="#1f1a14" font-variant-numeric="tabular-nums">{repos}</text>
    <text x="917.5" y="97" text-anchor="middle" font-family="IBM Plex Sans, sans-serif"
          font-size="11" fill="#4a4038">repos</text>
  </g>
  <g>
    <rect x="985" y="55" width="115" height="52" rx="10" fill="#ffffff" fill-opacity="0.42"
          stroke="#ffffff" stroke-opacity="0.55" stroke-width="0.8"/>
    <text x="1042.5" y="80" text-anchor="middle" font-family="IBM Plex Mono, monospace"
          font-size="22" font-weight="500" fill="#1f1a14" font-variant-numeric="tabular-nums">{stars}</text>
    <text x="1042.5" y="97" text-anchor="middle" font-family="IBM Plex Sans, sans-serif"
          font-size="11" fill="#4a4038">stars</text>
  </g>
  <g>
    <rect x="860" y="115" width="115" height="52" rx="10" fill="#ffffff" fill-opacity="0.42"
          stroke="#ffffff" stroke-opacity="0.55" stroke-width="0.8"/>
    <text x="917.5" y="140" text-anchor="middle" font-family="IBM Plex Mono, monospace"
          font-size="22" font-weight="500" fill="#1f1a14" font-variant-numeric="tabular-nums">{commits}</text>
    <text x="917.5" y="157" text-anchor="middle" font-family="IBM Plex Sans, sans-serif"
          font-size="11" fill="#4a4038">commits</text>
  </g>
  <g>
    <rect x="985" y="115" width="115" height="52" rx="10" fill="#ffffff" fill-opacity="0.42"
          stroke="#ffffff" stroke-opacity="0.55" stroke-width="0.8"/>
    <text x="1042.5" y="140" text-anchor="middle" font-family="IBM Plex Mono, monospace"
          font-size="20" font-weight="500" fill="#1f1a14" font-variant-numeric="tabular-nums">{loc}</text>
    <text x="1042.5" y="157" text-anchor="middle" font-family="IBM Plex Sans, sans-serif"
          font-size="11" fill="#4a4038">lines of code</text>
  </g>

  <!-- ================= Code Breakdown ================= -->
  <text x="860" y="200" font-family="IBM Plex Sans, sans-serif" font-size="13" font-weight="600" fill="#2a2520">Code Breakdown</text>
  <rect x="860" y="210" width="280" height="1.5" rx="0.75" fill="#9a9080" opacity="0.5"/>

  <!-- Donut background track (SAME center as donut) -->
  <circle cx="{dcx}" cy="{dcy}" r="{dr}" fill="none" stroke="#e0d8c8" stroke-width="14" opacity="0.55"/>
  {donut}

  <!-- Center label inside donut -->
  <text x="{dcx}" y="{dcy}-3" text-anchor="middle" font-family="IBM Plex Sans, sans-serif"
        font-size="12" font-weight="600" fill="#3a3530">Code</text>
  <text x="{dcx}" y="{dcy}+10" text-anchor="middle" font-family="IBM Plex Sans, sans-serif"
        font-size="9.5" fill="#6a6258">mix</text>

  {legend}

  <!-- ================= Footer timestamp ================= -->
  <text x="60" y="505" font-family="IBM Plex Mono, monospace" font-size="9" fill="#7a7064">updated {updated}</text>
</svg>"""

    chakra = ashoka_chakra(600, 70, 26)

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
        dcx=donut_cx,
        dcy=donut_cy,
        dr=donut_r,
        legend=legend_svg,
        updated=now,
    )
    return svg


def main():
    print("Fetching GitHub stats...")
    stats = fetch_stats()
    print(f"Stats: {json.dumps(stats, indent=2)}")
    svg = generate_svg(stats)
    out_path = "assets/github-banner.svg"
    os.makedirs("assets", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Banner written to {out_path}")


if __name__ == "__main__":
    main()
