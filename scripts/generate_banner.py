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
import re

def ordinal_suffix(day):
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

def format_ist_now():
    """Return current time in IST with ordinal date format."""
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
        return {}, ""

def get_total_commits(repo_name, default_branch):
    url = f"https://api.github.com/repos/{USERNAME}/{repo_name}/commits?sha={default_branch}&per_page=1"
    data, link = api_call(url)
    if link:
        match = re.search(r'page=(\d+)[^>]*>;\s*rel="last"', link)
        if match:
            return int(match.group(1))
    # Fallback: if API returned actual commits, count them
    if isinstance(data, list) and data:
        return len(data)
    return 0

def fetch_stats():
    user, _ = api_call(f"https://api.github.com/users/{USERNAME}")
    repos, _ = api_call(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated")

    lang_stats = {}
    total_bytes = 0
    stars = 0
    total_commits = 0

    for r in repos:
        stars += r.get("stargazers_count", 0)
        default = r.get("default_branch", "main")
        total_commits += get_total_commits(r["name"], default)

        lang_url = r.get("languages_url")
        if lang_url:
            langs, _ = api_call(lang_url)
            for lang, bytes_count in langs.items():
                lang_stats[lang] = lang_stats.get(lang, 0) + bytes_count
                total_bytes += bytes_count

    sorted_langs = sorted(lang_stats.items(), key=lambda x: x[1], reverse=True)[:6]
    lang_percentages = []
    for lang, bytes_count in sorted_langs:
        pct = round((bytes_count / total_bytes) * 100, 1) if total_bytes else 0
        lang_percentages.append((lang, pct))

    estimated_loc = int(total_bytes / 25) if total_bytes else 0
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

def generate_svg(stats):
    langs = stats["languages"]
    now = format_ist_now()
    name_text = stats.get("name", USERNAME) or USERNAME
    bio_text = stats.get("bio", "") or "TypeScript | JavaScript | Python | React | Docker"

    donut = donut_chart(1020, 245, 38, langs, stroke_width=14)

    legend_items = []
    for i, (lang, pct) in enumerate(langs[:5]):
        y = 275 + i * 20
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
      <stop offset="0%" stop-color="#f0ece6"/>
      <stop offset="35%" stop-color="#ddd7ce"/>
      <stop offset="100%" stop-color="#c8c0b4"/>
    </linearGradient>
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
      <stop offset="100%" stop-color="#9aacb2" stop-opacity="0.75"/>
    </linearGradient>
    <linearGradient id="indiaGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#ff9933" stop-opacity="0.15"/>
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#138808" stop-opacity="0.15"/>
    </linearGradient>
    <filter id="blur1"><feGaussianBlur stdDeviation="2"/></filter>
    <filter id="blur2"><feGaussianBlur stdDeviation="4"/></filter>
    <filter id="blur3"><feGaussianBlur stdDeviation="8"/></filter>
  </defs>

  <rect width="1200" height="520" fill="url(#skyGrad)"/>
  <rect width="1200" height="520" fill="url(#indiaGrad)"/>

  <!-- Ashoka Chakra center-top -->
  <g opacity="0.85">
    {chakra}
  </g>

  <!-- Far mountains -->
  <path d="M0,360 Q150,260 300,300 T600,260 T900,290 T1200,240 V520 H0Z" fill="#c8c0b4" opacity="0.5" filter="url(#blur3)"/>
  <path d="M0,340 Q200,220 400,270 T800,230 T1200,260 V520 H0Z" fill="#b8b0a2" opacity="0.4" filter="url(#blur3)"/>

  <!-- Bamboo (shared Asian) -->
  <g opacity="0.4">
    <line x1="30" y1="320" x2="30" y2="180" stroke="#4a6a3a" stroke-width="3" stroke-linecap="round"/>
    <line x1="42" y1="310" x2="42" y2="160" stroke="#4a6a3a" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="25" y1="280" x2="35" y2="270" stroke="#5a7a4a" stroke-width="1.5" fill="none"/>
    <line x1="38" y1="250" x2="48" y2="240" stroke="#5a7a4a" stroke-width="1.5" fill="none"/>
    <line x1="22" y1="220" x2="32" y2="210" stroke="#5a7a4a" stroke-width="1.5" fill="none"/>
    <line x1="40" y1="200" x2="50" y2="190" stroke="#5a7a4a" stroke-width="1.5" fill="none"/>
  </g>

  <!-- Korean hanok roof -->
  <g opacity="0.7">
    <path d="M430,310 Q450,295 470,305 Q490,295 510,305 Q530,295 550,310" stroke="#5a5048" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M435,313 Q455,300 475,308 Q495,300 515,308 Q535,300 545,313" stroke="#6a6058" stroke-width="2" fill="none" stroke-linecap="round"/>
    <rect x="460" y="313" width="24" height="18" rx="2" fill="#7a7068" opacity="0.6"/>
    <rect x="496" y="313" width="24" height="18" rx="2" fill="#7a7068" opacity="0.6"/>
    <rect x="458" y="313" width="3" height="18" fill="#5a5048" opacity="0.7"/>
    <rect x="481" y="313" width="3" height="18" fill="#5a5048" opacity="0.7"/>
    <rect x="496" y="313" width="3" height="18" fill="#5a5048" opacity="0.7"/>
    <rect x="519" y="313" width="3" height="18" fill="#5a5048" opacity="0.7"/>
  </g>

  <!-- Japanese torii gate -->
  <g opacity="0.5" transform="translate(620, 285) scale(0.7)">
    <rect x="-35" y="0" width="4" height="50" fill="#8a3020" opacity="0.7"/>
    <rect x="35" y="0" width="4" height="50" fill="#8a3020" opacity="0.7"/>
    <rect x="-45" y="5" width="90" height="5" rx="2" fill="#a03020" opacity="0.8"/>
    <rect x="-40" y="35" width="80" height="4" rx="2" fill="#a03020" opacity="0.8"/>
    <path d="M-50,5 Q0,-5 50,5" stroke="#a03020" stroke-width="3" fill="none" opacity="0.8"/>
  </g>

  <!-- Chinese pavilion -->
  <g opacity="0.45" transform="translate(680, 300) scale(0.6)">
    <path d="M-25,0 Q0,-12 25,0" stroke="#5a4038" stroke-width="3" fill="none"/>
    <path d="M-20,0 L-20,25 L20,25 L20,0" fill="#6a5040" opacity="0.6"/>
    <rect x="-3" y="8" width="6" height="10" rx="1" fill="#5a4038" opacity="0.7"/>
    <line x1="0" y1="0" x2="0" y2="-15" stroke="#5a4038" stroke-width="2"/>
    <circle cx="0" cy="-15" r="3" fill="#c8a030" opacity="0.6"/>
  </g>

  <!-- Scattered cherry blossom petals -->
  <g opacity="0.35">
    <ellipse cx="550" cy="200" rx="4" ry="2" fill="#e08090" transform="rotate(20 550 200)"/>
    <ellipse cx="580" cy="220" rx="3" ry="1.5" fill="#d07080" transform="rotate(-15 580 220)"/>
    <ellipse cx="520" cy="240" rx="3.5" ry="1.8" fill="#e08090" transform="rotate(45 520 240)"/>
    <ellipse cx="600" cy="180" rx="2.5" ry="1.2" fill="#d07080" transform="rotate(30 600 180)"/>
    <ellipse cx="650" cy="210" rx="3" ry="1.5" fill="#e08090" transform="rotate(-25 650 210)"/>
    <ellipse cx="480" cy="190" rx="2" ry="1" fill="#d07080" transform="rotate(60 480 190)"/>
  </g>

  <!-- Mist -->
  <rect x="0" y="200" width="1200" height="180" fill="url(#mist1)" filter="url(#blur2)"/>
  <rect x="0" y="240" width="1200" height="160" fill="url(#mist2)" filter="url(#blur2)"/>

  <!-- Mid mountains Vietnam karst -->
  <path d="M-50,520 Q100,360 250,400 T550,350 T850,380 T1250,330 V520 H-50Z" fill="#a09888" opacity="0.6" filter="url(#blur2)"/>
  <path d="M-50,520 Q200,380 400,420 T750,370 T1100,400 T1250,360 V520 H-50Z" fill="#908878" opacity="0.5" filter="url(#blur2)"/>

  <!-- Great Wall China -->
  <path d="M750,345 L760,338 L770,342 L780,335 L790,340 L800,332 L810,337 L820,330 L830,335 L840,328 L850,333 L860,326 L870,331 L880,324 L890,329 L900,322 L910,327 L920,320 L930,325 L940,318 L950,323 L960,316 L970,321 L980,314 L990,319 L1000,312 L1010,317 L1020,310 L1030,315 L1040,308 L1050,313 L1060,306 L1070,311 L1080,304 L1090,309 L1100,302 L1110,307 L1120,300 L1130,305 L1140,298 L1150,303 L1160,296 L1170,301 L1180,294 L1190,299 L1200,292 V520 H750Z" fill="#6a6258" opacity="0.45" filter="url(#blur1)"/>
  <g opacity="0.55">
    <rect x="760" y="335" width="4" height="6" fill="#5a5048"/>
    <rect x="780" y="330" width="4" height="6" fill="#5a5048"/>
    <rect x="800" y="327" width="4" height="6" fill="#5a5048"/>
    <rect x="820" y="325" width="4" height="6" fill="#5a5048"/>
    <rect x="840" y="322" width="4" height="6" fill="#5a5048"/>
    <rect x="860" y="320" width="4" height="6" fill="#5a5048"/>
    <rect x="880" y="318" width="4" height="6" fill="#5a5048"/>
    <rect x="900" y="316" width="4" height="6" fill="#5a5048"/>
    <rect x="920" y="314" width="4" height="6" fill="#5a5048"/>
    <rect x="940" y="312" width="4" height="6" fill="#5a5048"/>
    <rect x="960" y="310" width="4" height="6" fill="#5a5048"/>
    <rect x="980" y="308" width="4" height="6" fill="#5a5048"/>
    <rect x="1000" y="306" width="4" height="6" fill="#5a5048"/>
    <rect x="1020" y="304" width="4" height="6" fill="#5a5048"/>
    <rect x="1040" y="302" width="4" height="6" fill="#5a5048"/>
    <rect x="1060" y="300" width="4" height="6" fill="#5a5048"/>
    <rect x="1080" y="298" width="4" height="6" fill="#5a5048"/>
    <rect x="1100" y="296" width="4" height="6" fill="#5a5048"/>
    <rect x="1120" y="294" width="4" height="6" fill="#5a5048"/>
    <rect x="1140" y="292" width="4" height="6" fill="#5a5048"/>
    <rect x="1160" y="290" width="4" height="6" fill="#5a5048"/>
    <rect x="1180" y="288" width="4" height="6" fill="#5a5048"/>
  </g>

  <!-- Near mountains -->
  <path d="M-50,520 Q150,420 350,460 T700,410 T1050,440 T1250,390 V520 H-50Z" fill="#7a7266" opacity="0.7" filter="url(#blur1)"/>
  <path d="M-50,520 Q250,440 500,480 T900,430 T1250,460 V520 H-50Z" fill="#6a6258" opacity="0.8"/>

  <!-- Water -->
  <rect x="0" y="460" width="1200" height="60" fill="url(#waterGrad)"/>
  <path d="M0,460 Q300,465 600,460 T1200,465 V520 H0Z" fill="#a8b8bc" opacity="0.4"/>

  <!-- Vietnamese farmer -->
  <g opacity="0.7" transform="translate(400, 455)">
    <ellipse cx="0" cy="-8" rx="28" ry="8" fill="#4a4038" opacity="0.9"/>
    <ellipse cx="0" cy="-8" rx="22" ry="5" fill="#5a5048" opacity="0.8"/>
    <path d="M-10,0 L-7,22 L7,22 L10,0Z" fill="#5a5048" opacity="0.8"/>
    <circle cx="0" cy="-14" r="5" fill="#6a6058" opacity="0.8"/>
    <line x1="12" y1="5" x2="22" y2="-5" stroke="#5a5048" stroke-width="2" opacity="0.7"/>
  </g>

  <!-- Lotus -->
  <g opacity="0.85">
    <ellipse cx="90" cy="490" rx="14" ry="8" fill="#d06060" transform="rotate(-20 90 490)"/>
    <ellipse cx="90" cy="490" rx="14" ry="8" fill="#c85050" transform="rotate(20 90 490)"/>
    <ellipse cx="90" cy="490" rx="14" ry="8" fill="#d06060" transform="rotate(50 90 490)"/>
    <ellipse cx="90" cy="490" rx="14" ry="8" fill="#c85050" transform="rotate(-50 90 490)"/>
    <ellipse cx="90" cy="490" rx="14" ry="8" fill="#d06060" transform="rotate(80 90 490)"/>
    <ellipse cx="90" cy="490" rx="14" ry="8" fill="#c85050" transform="rotate(-80 90 490)"/>
    <circle cx="90" cy="490" r="5" fill="#f0c8a0"/>
    <ellipse cx="135" cy="502" rx="10" ry="6" fill="#b85050" transform="rotate(-20 135 502)"/>
    <ellipse cx="135" cy="502" rx="10" ry="6" fill="#a84040" transform="rotate(20 135 502)"/>
    <ellipse cx="135" cy="502" rx="10" ry="6" fill="#b85050" transform="rotate(50 135 502)"/>
    <ellipse cx="135" cy="502" rx="10" ry="6" fill="#a84040" transform="rotate(-50 135 502)"/>
    <circle cx="135" cy="502" r="4" fill="#f0c8a0"/>
    <path d="M90,498 Q88,510 85,520" stroke="#4a6a4a" stroke-width="2" fill="none" opacity="0.6"/>
    <path d="M135,508 Q132,515 128,520" stroke="#4a6a4a" stroke-width="1.5" fill="none" opacity="0.6"/>
  </g>

  <!-- Peacock -->
  <g opacity="0.75" transform="translate(190, 405) scale(1.1)">
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
  <g opacity="0.75">
    <ellipse cx="290" cy="472" rx="16" ry="12" fill="#2a2420"/>
    <circle cx="282" cy="465" r="8" fill="#2a2420"/>
    <ellipse cx="277" cy="460" rx="4" ry="3" fill="#2a2420"/>
    <ellipse cx="287" cy="460" rx="4" ry="3" fill="#2a2420"/>
    <circle cx="280" cy="465" r="2" fill="#f0ece6"/>
    <circle cx="284" cy="465" r="2" fill="#f0ece6"/>
    <ellipse cx="282" cy="469" rx="2.2" ry="1.4" fill="#f0ece6"/>
    <ellipse cx="340" cy="482" rx="11" ry="8" fill="#3a3428"/>
    <circle cx="334" cy="476" r="5.5" fill="#3a3428"/>
    <ellipse cx="330" cy="472" rx="2.8" ry="2" fill="#3a3428"/>
    <ellipse cx="338" cy="472" rx="2.8" ry="2" fill="#3a3428"/>
  </g>

  <!-- Cherry blossoms Japan -->
  <g opacity="0.8">
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
    <ellipse cx="1090" cy="430" rx="3" ry="1.5" fill="#e08090" opacity="0.5" transform="rotate(30 1090 430)"/>
    <ellipse cx="1115" cy="445" rx="2.5" ry="1.2" fill="#d07080" opacity="0.4" transform="rotate(-20 1115 445)"/>
    <ellipse cx="1135" cy="420" rx="2" ry="1" fill="#e08090" opacity="0.4" transform="rotate(45 1135 420)"/>
  </g>

  <!-- Birds -->
  <g fill="none" stroke="#4a4038" stroke-width="1.5" opacity="0.55">
    <path d="M520,155 Q525,150 530,155 Q535,150 540,155"/>
    <path d="M560,135 Q564,131 568,135 Q572,131 576,135"/>
    <path d="M545,170 Q549,166 553,170 Q557,166 561,170"/>
  </g>

  <!-- Red maple -->
  <g opacity="0.75">
    <path d="M35,520 Q42,475 48,455 Q50,445 46,440 Q48,434 50,428" stroke="#7a4030" stroke-width="3" fill="none"/>
    <path d="M50,428 Q36,418 30,424 Q34,412 42,406 Q48,401 54,412 Q60,406 66,418 Q72,424 60,430 Q66,436 58,442 Q50,436 50,428Z" fill="#c86050"/>
    <path d="M46,444 Q32,434 26,442 Q28,428 36,422 Q42,417 48,428 Q54,422 58,434 Q62,440 50,446Z" fill="#b05040"/>
    <path d="M50,466 Q34,456 28,464 Q30,450 38,444 Q44,439 50,450 Q56,444 60,456 Q64,462 52,468Z" fill="#a04030"/>
  </g>

  <!-- Indian flag tricolor -->
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
  <text x="75" y="362" font-family="IBM Plex Sans, sans-serif" font-size="12" fill="#5a5048">हिन्दी · English · Русский · 中國人 · Bahasa Indonesia</text>

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

  <circle cx="1020" cy="210" r="42" fill="none" stroke="#d4cec5" stroke-width="14" opacity="0.5"/>
  {donut}

  <text x="1020" y="206" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="13" font-weight="500" fill="#4a4038">Top</text>
  <text x="1020" y="220" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="10" fill="#6a6258">Languages</text>

  {legend}

  <text x="60" y="505" font-family="IBM Plex Mono, monospace" font-size="9" fill="#a09888">updated {updated}</text>
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
