#!/usr/bin/env python3
"""
Generates a custom ink-wash landscape GitHub profile banner
with live stats and cultural elements from India, China, Japan, Korea, Vietnam.
"""
import os
import sys
import json
import urllib.request
import datetime
import math

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
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"API error for {url}: {e}", file=sys.stderr)
        return {}

def fetch_stats():
    user = api_call(f"https://api.github.com/users/{USERNAME}")
    repos = api_call(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated")
    lang_stats = {}
    total_bytes = 0
    stars = 0
    for r in repos:
        stars += r.get("stargazers_count", 0)
        lang_url = r.get("languages_url")
        if lang_url:
            langs = api_call(lang_url)
            for lang, bytes_count in langs.items():
                lang_stats[lang] = lang_stats.get(lang, 0) + bytes_count
                total_bytes += bytes_count

    sorted_langs = sorted(lang_stats.items(), key=lambda x: x[1], reverse=True)[:6]
    lang_percentages = []
    for lang, bytes_count in sorted_langs:
        pct = round((bytes_count / total_bytes) * 100, 1) if total_bytes else 0
        lang_percentages.append((lang, pct))

    forks = sum(r.get("forks_count", 0) for r in repos)

    return {
        "repos": len(repos),
        "stars": stars,
        "forks": forks,
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
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

def ashoka_chakra(cx, cy, r, stroke_color="#000080", stroke_width=1.5, opacity=0.7):
    """Generate SVG for Ashoka Chakra with 24 spokes."""
    lines = []
    for i in range(24):
        angle = i * 15
        rad = 3.14159 * angle / 180
        x1 = cx + (r * 0.15) * math.cos(rad)
        y1 = cy + (r * 0.15) * math.sin(rad)
        x2 = cx + r * math.cos(rad)
        y2 = cy + r * math.sin(rad)
        lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke_color}" stroke-width="{stroke_width}" opacity="{opacity}"/>')
    # Outer and inner circles
    outer = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{stroke_color}" stroke-width="{stroke_width}" opacity="{opacity}"/>'
    inner = f'<circle cx="{cx}" cy="{cy}" r="{r*0.15}" fill="none" stroke="{stroke_color}" stroke-width="{stroke_width}" opacity="{opacity}"/>'
    return "\n    ".join([outer, inner] + lines)

def generate_svg(stats):
    langs = stats["languages"]
    bar_width = 340
    bar_x = 60
    bar_y = 155
    bar_h = 6
    segments = []
    cx = bar_x
    for lang, pct in langs:
        w = (pct / 100) * bar_width
        color = get_lang_color(lang)
        segments.append(f'<rect x="{cx:.1f}" y="{bar_y}" width="{w:.1f}" height="{bar_h}" rx="3" fill="{color}" opacity="0.9"/>')
        cx += w

    lang_labels = "  ".join([f'<tspan fill="{get_lang_color(l)}">● {l} {p:.1f}%</tspan>' for l, p in langs[:4]])

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    name_text = stats.get("name", USERNAME) or USERNAME
    bio_text = stats.get("bio", "") or "TypeScript · JavaScript · Python · React · Docker"

    # Ashoka Chakra in center-top area
    chakra_svg = ashoka_chakra(600, 80, 28, stroke_color="#1a1a6a", stroke_width=1.8, opacity=0.55)

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1200 420" xmlns="http://www.w3.org/2000/svg">
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
      <stop offset="0%" stop-color="#ff9933" stop-opacity="0.18"/>
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0.1"/>
      <stop offset="100%" stop-color="#138808" stop-opacity="0.18"/>
    </linearGradient>
    <filter id="blur1"><feGaussianBlur stdDeviation="2"/></filter>
    <filter id="blur2"><feGaussianBlur stdDeviation="4"/></filter>
    <filter id="blur3"><feGaussianBlur stdDeviation="8"/></filter>
  </defs>

  <rect width="1200" height="420" fill="url(#skyGrad)"/>
  <rect width="1200" height="420" fill="url(#indiaGrad)"/>

  <!-- ===== ASHOKA CHAKRA (center) ===== -->
  <g opacity="0.9">
    {chakra_svg}
  </g>

  <!-- Far mountains -->
  <path d="M0,290 Q150,190 300,230 T600,190 T900,220 T1200,170 V420 H0Z" fill="#c8c0b4" opacity="0.5" filter="url(#blur3)"/>
  <path d="M0,270 Q200,150 400,200 T800,160 T1200,190 V420 H0Z" fill="#b8b0a2" opacity="0.4" filter="url(#blur3)"/>

  <!-- Korean hanok roof -->
  <g opacity="0.75">
    <path d="M430,240 Q450,225 470,235 Q490,225 510,235 Q530,225 550,240" stroke="#5a5048" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M435,243 Q455,230 475,238 Q495,230 515,238 Q535,230 545,243" stroke="#6a6058" stroke-width="2" fill="none" stroke-linecap="round"/>
    <rect x="460" y="243" width="24" height="18" rx="2" fill="#7a7068" opacity="0.6"/>
    <rect x="496" y="243" width="24" height="18" rx="2" fill="#7a7068" opacity="0.6"/>
    <rect x="458" y="243" width="3" height="18" fill="#5a5048" opacity="0.7"/>
    <rect x="481" y="243" width="3" height="18" fill="#5a5048" opacity="0.7"/>
    <rect x="496" y="243" width="3" height="18" fill="#5a5048" opacity="0.7"/>
    <rect x="519" y="243" width="3" height="18" fill="#5a5048" opacity="0.7"/>
  </g>

  <!-- Mist -->
  <rect x="0" y="130" width="1200" height="180" fill="url(#mist1)" filter="url(#blur2)"/>
  <rect x="0" y="170" width="1200" height="160" fill="url(#mist2)" filter="url(#blur2)"/>

  <!-- Mid mountains (Vietnam karst) -->
  <path d="M-50,420 Q100,260 250,300 T550,250 T850,280 T1250,230 V420 H-50Z" fill="#a09888" opacity="0.6" filter="url(#blur2)"/>
  <path d="M-50,420 Q200,280 400,320 T750,270 T1100,300 T1250,260 V420 H-50Z" fill="#908878" opacity="0.5" filter="url(#blur2)"/>

  <!-- Great Wall (China) -->
  <path d="M750,275 L760,268 L770,272 L780,265 L790,270 L800,262 L810,267 L820,260 L830,265 L840,258 L850,263 L860,256 L870,261 L880,254 L890,259 L900,252 L910,257 L920,250 L930,255 L940,248 L950,253 L960,246 L970,251 L980,244 L990,249 L1000,242 L1010,247 L1020,240 L1030,245 L1040,238 L1050,243 L1060,236 L1070,241 L1080,234 L1090,239 L1100,232 L1110,237 L1120,230 L1130,235 L1140,228 L1150,233 L1160,226 L1170,231 L1180,224 L1190,229 L1200,222 V420 H750Z" fill="#6a6258" opacity="0.5" filter="url(#blur1)"/>
  <g opacity="0.6">
    <rect x="760" y="265" width="4" height="6" fill="#5a5048"/>
    <rect x="780" y="260" width="4" height="6" fill="#5a5048"/>
    <rect x="800" y="257" width="4" height="6" fill="#5a5048"/>
    <rect x="820" y="255" width="4" height="6" fill="#5a5048"/>
    <rect x="840" y="252" width="4" height="6" fill="#5a5048"/>
    <rect x="860" y="250" width="4" height="6" fill="#5a5048"/>
    <rect x="880" y="248" width="4" height="6" fill="#5a5048"/>
    <rect x="900" y="246" width="4" height="6" fill="#5a5048"/>
    <rect x="920" y="244" width="4" height="6" fill="#5a5048"/>
    <rect x="940" y="242" width="4" height="6" fill="#5a5048"/>
    <rect x="960" y="240" width="4" height="6" fill="#5a5048"/>
    <rect x="980" y="238" width="4" height="6" fill="#5a5048"/>
    <rect x="1000" y="236" width="4" height="6" fill="#5a5048"/>
    <rect x="1020" y="234" width="4" height="6" fill="#5a5048"/>
    <rect x="1040" y="232" width="4" height="6" fill="#5a5048"/>
    <rect x="1060" y="230" width="4" height="6" fill="#5a5048"/>
    <rect x="1080" y="228" width="4" height="6" fill="#5a5048"/>
    <rect x="1100" y="226" width="4" height="6" fill="#5a5048"/>
    <rect x="1120" y="224" width="4" height="6" fill="#5a5048"/>
    <rect x="1140" y="222" width="4" height="6" fill="#5a5048"/>
    <rect x="1160" y="220" width="4" height="6" fill="#5a5048"/>
    <rect x="1180" y="218" width="4" height="6" fill="#5a5048"/>
  </g>

  <!-- Near mountains -->
  <path d="M-50,420 Q150,320 350,360 T700,310 T1050,340 T1250,290 V420 H-50Z" fill="#7a7266" opacity="0.7" filter="url(#blur1)"/>
  <path d="M-50,420 Q250,340 500,380 T900,330 T1250,360 V420 H-50Z" fill="#6a6258" opacity="0.8"/>

  <!-- Water -->
  <rect x="0" y="360" width="1200" height="60" fill="url(#waterGrad)"/>
  <path d="M0,360 Q300,365 600,360 T1200,365 V420 H0Z" fill="#a8b8bc" opacity="0.4"/>

  <!-- Vietnamese conical hat farmer -->
  <g opacity="0.7" transform="translate(400, 355)">
    <ellipse cx="0" cy="-8" rx="28" ry="8" fill="#4a4038" opacity="0.9"/>
    <ellipse cx="0" cy="-8" rx="22" ry="5" fill="#5a5048" opacity="0.8"/>
    <path d="M-10,0 L-7,22 L7,22 L10,0Z" fill="#5a5048" opacity="0.8"/>
    <circle cx="0" cy="-14" r="5" fill="#6a6058" opacity="0.8"/>
    <line x1="12" y1="5" x2="22" y2="-5" stroke="#5a5048" stroke-width="2" opacity="0.7"/>
  </g>

  <!-- Lotus (India + Vietnam) -->
  <g opacity="0.85">
    <ellipse cx="90" cy="390" rx="14" ry="8" fill="#d06060" transform="rotate(-20 90 390)"/>
    <ellipse cx="90" cy="390" rx="14" ry="8" fill="#c85050" transform="rotate(20 90 390)"/>
    <ellipse cx="90" cy="390" rx="14" ry="8" fill="#d06060" transform="rotate(50 90 390)"/>
    <ellipse cx="90" cy="390" rx="14" ry="8" fill="#c85050" transform="rotate(-50 90 390)"/>
    <ellipse cx="90" cy="390" rx="14" ry="8" fill="#d06060" transform="rotate(80 90 390)"/>
    <ellipse cx="90" cy="390" rx="14" ry="8" fill="#c85050" transform="rotate(-80 90 390)"/>
    <circle cx="90" cy="390" r="5" fill="#f0c8a0"/>
    <ellipse cx="135" cy="402" rx="10" ry="6" fill="#b85050" transform="rotate(-20 135 402)"/>
    <ellipse cx="135" cy="402" rx="10" ry="6" fill="#a84040" transform="rotate(20 135 402)"/>
    <ellipse cx="135" cy="402" rx="10" ry="6" fill="#b85050" transform="rotate(50 135 402)"/>
    <ellipse cx="135" cy="402" rx="10" ry="6" fill="#a84040" transform="rotate(-50 135 402)"/>
    <circle cx="135" cy="402" r="4" fill="#f0c8a0"/>
    <path d="M90,398 Q88,410 85,420" stroke="#4a6a4a" stroke-width="2" fill="none" opacity="0.6"/>
    <path d="M135,408 Q132,415 128,420" stroke="#4a6a4a" stroke-width="1.5" fill="none" opacity="0.6"/>
  </g>

  <!-- Peacock (India) -->
  <g opacity="0.75" transform="translate(190, 305) scale(1.1)">
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

  <!-- Pandas (China) -->
  <g opacity="0.75">
    <ellipse cx="290" cy="372" rx="16" ry="12" fill="#2a2420"/>
    <circle cx="282" cy="365" r="8" fill="#2a2420"/>
    <ellipse cx="277" cy="360" rx="4" ry="3" fill="#2a2420"/>
    <ellipse cx="287" cy="360" rx="4" ry="3" fill="#2a2420"/>
    <circle cx="280" cy="365" r="2" fill="#f0ece6"/>
    <circle cx="284" cy="365" r="2" fill="#f0ece6"/>
    <ellipse cx="282" cy="369" rx="2.2" ry="1.4" fill="#f0ece6"/>
    <ellipse cx="340" cy="382" rx="11" ry="8" fill="#3a3428"/>
    <circle cx="334" cy="376" r="5.5" fill="#3a3428"/>
    <ellipse cx="330" cy="372" rx="2.8" ry="2" fill="#3a3428"/>
    <ellipse cx="338" cy="372" rx="2.8" ry="2" fill="#3a3428"/>
  </g>

  <!-- Cherry blossoms (Japan) -->
  <g opacity="0.8">
    <path d="M1080,340 Q1090,320 1100,305 Q1108,312 1118,302" stroke="#5a4038" stroke-width="2.5" fill="none" opacity="0.7"/>
    <path d="M1100,305 Q1110,295 1125,290" stroke="#5a4038" stroke-width="2" fill="none" opacity="0.6"/>
    <circle cx="1100" cy="305" r="6" fill="#e08090"/>
    <circle cx="1106" cy="310" r="5.5" fill="#d07080"/>
    <circle cx="1094" cy="310" r="5" fill="#e08090"/>
    <circle cx="1100" cy="315" r="5.5" fill="#d07080"/>
    <circle cx="1100" cy="308" r="2.5" fill="#f8d0d8"/>
    <circle cx="1106" cy="312" r="2" fill="#f8d0d8"/>
    <circle cx="1094" cy="312" r="2" fill="#f8d0d8"/>
    <circle cx="1125" cy="290" r="5" fill="#e08090"/>
    <circle cx="1130" cy="294" r="4.5" fill="#d07080"/>
    <circle cx="1120" cy="294" r="4" fill="#e08090"/>
    <circle cx="1125" cy="298" r="4.5" fill="#d07080"/>
    <circle cx="1125" cy="293" r="2" fill="#f8d0d8"/>
    <ellipse cx="1090" cy="330" rx="3" ry="1.5" fill="#e08090" opacity="0.5" transform="rotate(30 1090 330)"/>
    <ellipse cx="1115" cy="345" rx="2.5" ry="1.2" fill="#d07080" opacity="0.4" transform="rotate(-20 1115 345)"/>
    <ellipse cx="1135" cy="320" rx="2" ry="1" fill="#e08090" opacity="0.4" transform="rotate(45 1135 320)"/>
  </g>

  <!-- Birds -->
  <g fill="none" stroke="#4a4038" stroke-width="1.5" opacity="0.55">
    <path d="M520,125 Q525,120 530,125 Q535,120 540,125"/>
    <path d="M560,105 Q564,101 568,105 Q572,101 576,105"/>
    <path d="M545,140 Q549,136 553,140 Q557,136 561,140"/>
  </g>

  <!-- Red maple tree -->
  <g opacity="0.75">
    <path d="M35,420 Q42,375 48,355 Q50,345 46,340 Q48,334 50,328" stroke="#7a4030" stroke-width="3" fill="none"/>
    <path d="M50,328 Q36,318 30,324 Q34,312 42,306 Q48,301 54,312 Q60,306 66,318 Q72,324 60,330 Q66,336 58,342 Q50,336 50,328Z" fill="#c86050"/>
    <path d="M46,344 Q32,334 26,342 Q28,328 36,322 Q42,317 48,328 Q54,322 58,334 Q62,340 50,346Z" fill="#b05040"/>
    <path d="M48,366 Q34,356 28,364 Q30,350 38,344 Q44,339 50,350 Q56,344 60,356 Q64,362 52,368Z" fill="#a04030"/>
  </g>

  <!-- Indian flag tricolor strips at bottom -->
  <rect x="0" y="412" width="1200" height="3" fill="#ff9933" opacity="0.45"/>
  <rect x="0" y="415" width="1200" height="3" fill="#ffffff" opacity="0.4"/>
  <rect x="0" y="418" width="1200" height="2" fill="#138808" opacity="0.45"/>

  <!-- Foreground mist -->
  <rect x="0" y="320" width="1200" height="100" fill="url(#mist3)" filter="url(#blur2)"/>

  <!-- ===== CONTENT OVERLAY ===== -->
  <text x="60" y="90" font-family="var(--kimi-font-sans)" font-size="44" font-weight="500" fill="#2a2520" letter-spacing="1">{name_text}</text>
  <text x="60" y="122" font-family="var(--kimi-font-sans)" font-size="14" fill="#5a5048">{bio_text}</text>

  <!-- Stats cards -->
  <g>
    <rect x="860" y="60" width="110" height="56" rx="10" fill="rgba(255,255,255,0.4)" stroke="rgba(255,255,255,0.55)" stroke-width="0.8"/>
    <text x="915" y="86" text-anchor="middle" font-family="var(--kimi-font-sans)" font-size="22" font-weight="500" fill="#2a2520" font-variant-numeric="tabular-nums">{stats["repos"]}</text>
    <text x="915" y="105" text-anchor="middle" font-family="var(--kimi-font-sans)" font-size="11" fill="#4a4038">repos</text>
  </g>
  <g>
    <rect x="985" y="60" width="110" height="56" rx="10" fill="rgba(255,255,255,0.4)" stroke="rgba(255,255,255,0.55)" stroke-width="0.8"/>
    <text x="1040" y="86" text-anchor="middle" font-family="var(--kimi-font-sans)" font-size="22" font-weight="500" fill="#2a2520" font-variant-numeric="tabular-nums">{stats["stars"]}</text>
    <text x="1040" y="105" text-anchor="middle" font-family="var(--kimi-font-sans)" font-size="11" fill="#4a4038">stars</text>
  </g>
  <g>
    <rect x="860" y="128" width="110" height="56" rx="10" fill="rgba(255,255,255,0.4)" stroke="rgba(255,255,255,0.55)" stroke-width="0.8"/>
    <text x="915" y="154" text-anchor="middle" font-family="var(--kimi-font-sans)" font-size="22" font-weight="500" fill="#2a2520" font-variant-numeric="tabular-nums">{stats["followers"]}</text>
    <text x="915" y="173" text-anchor="middle" font-family="var(--kimi-font-sans)" font-size="11" fill="#4a4038">followers</text>
  </g>
  <g>
    <rect x="985" y="128" width="110" height="56" rx="10" fill="rgba(255,255,255,0.4)" stroke="rgba(255,255,255,0.55)" stroke-width="0.8"/>
    <text x="1040" y="154" text-anchor="middle" font-family="var(--kimi-font-sans)" font-size="20" font-weight="500" fill="#2a2520" font-variant-numeric="tabular-nums">{stats["following"]}</text>
    <text x="1040" y="173" text-anchor="middle" font-family="var(--kimi-font-sans)" font-size="11" fill="#4a4038">following</text>
  </g>

  <!-- Language bar -->
  <rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_h}" rx="3" fill="rgba(255,255,255,0.45)"/>
  {chr(10).join(segments)}

  <text x="60" y="177" font-family="var(--kimi-font-sans)" font-size="10" fill="#5a5048">
    {lang_labels}
  </text>

  <!-- ===== CONTACT / INFO STRIP (replaces pinned repos) ===== -->
  <text x="60" y="205" font-family="var(--kimi-font-sans)" font-size="12" font-weight="500" fill="#4a4038">Connect</text>

  <!-- Card 1: Google Developer + Human Languages -->
  <g>
    <rect x="60" y="215" width="540" height="50" rx="10" fill="rgba(255,255,255,0.35)" stroke="rgba(255,255,255,0.5)" stroke-width="0.8"/>
    <text x="75" y="235" font-family="var(--kimi-font-sans)" font-size="12" font-weight="500" fill="#2a2520">Google Developer</text>
    <text x="75" y="250" font-family="var(--kimi-font-sans)" font-size="10" fill="#5a5048">vikasranax</text>
    <text x="280" y="235" font-family="var(--kimi-font-sans)" font-size="12" font-weight="500" fill="#2a2520">Languages</text>
    <text x="280" y="250" font-family="var(--kimi-font-sans)" font-size="10" fill="#5a5048">हिन्दी · English · Русский · 中國人 · Bahasa Indonesia</text>
  </g>

  <!-- Card 2: X + LinkedIn -->
  <g>
    <rect x="615" y="215" width="540" height="50" rx="10" fill="rgba(255,255,255,0.35)" stroke="rgba(255,255,255,0.5)" stroke-width="0.8"/>
    <text x="630" y="235" font-family="var(--kimi-font-sans)" font-size="12" font-weight="500" fill="#2a2520">X (Twitter)</text>
    <text x="630" y="250" font-family="var(--kimi-font-sans)" font-size="10" fill="#5a5048">@vikasranax</text>
    <text x="780" y="235" font-family="var(--kimi-font-sans)" font-size="12" font-weight="500" fill="#2a2520">LinkedIn</text>
    <text x="780" y="250" font-family="var(--kimi-font-sans)" font-size="10" fill="#5a5048">linkedin.com/in/vikasranax</text>
  </g>

  <text x="60" y="405" font-family="var(--kimi-font-sans)" font-size="10" fill="#8a8278">
    discord: vikasranax  ·  google play: vikasranax  ·  google maps: VRX
  </text>

  <text x="1140" y="405" text-anchor="end" font-family="var(--kimi-font-sans)" font-size="9" fill="#a09888">updated {now}</text>
</svg>'''
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
