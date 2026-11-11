#!/usr/bin/env python3
"""Renders the animated SVG cards used by the profile README. Stdlib only.

  python scripts/render.py            scrape live contributions, then render
  python scripts/render.py --offline  re-render from data/contributions.json
  python scripts/render.py --test     run the self-check

Everything personal lives in the CONFIG block below. Edit it, run the script,
commit. The GitHub Action in .github/workflows/profile.yml does this daily.
"""
import base64
import datetime as dt
import html
import json
import math
import os
import random
import re
import sys
import urllib.request

# ----------------------------------------------------------------- CONFIG ---
USER = "karthikreddyyalala"
NAME_ROWS = ["KARTHIK REDDY", "YALALA"]          # big tiles, one row each
# small tiles, 33 characters max: (what it says, what it flips to)
ROLE_ROWS = [("LLMOPS AND AI INFRA ENGINEER", "OPEN TO FULL TIME ROLES MAY 2027"),
             ("ASU COMPUTER SCIENCE 4.0 GPA 2027", "AWS CERTIFIED CLOUD PRACTITIONER")]
ABOUT = ["I build the part of GenAI that has to survive production:",
         "eval gates, guardrails, RAG pipelines and the AWS underneath."]
ACTION = "Open my portfolio"
# when (6), where (17), what (20), what it flips to (20), boarding now?
BOARD = [
    ("SUM 26", "AVIS BUDGET GROUP", "4 GENAI APPS SHIPPED", "170 HOURS SAVED", False),
    ("AUG 26", "PROFESSORDM", "LEADS ARCHITECTURE", "7 PERSON AI MVP TEAM", True),
    ("NOW", "CRUCIBLE", "6 AGENT INTERVIEWER", "LANGGRAPH ON BEDROCK", False),
    ("NOW", "FINRAG", "SEC FILINGS OVER MCP", "CITED ANSWERS", False),
    ("MAY 27", "FULL TIME ROLE", "OPEN TO OFFERS", "AI AND SOFTWARE", False),
]
STACK = [
    ("Interface", "React, TypeScript, Node.js"),
    ("Orchestration", "LangGraph, LangChain, CrewAI, MCP, FastAPI"),
    ("Models", "Amazon Bedrock, Bedrock AgentCore, Claude, OpenAI, Hugging Face"),
    ("Infrastructure", "AWS Lambda, API Gateway, DynamoDB, CloudFront, Docker, Pinecone"),
    ("Evals and guardrails", "RAG evaluation, adversarial and regression tests, structured outputs"),
    ("Languages", "Python, TypeScript, JavaScript, Java, C++, SQL"),
]
# (repo name, description, language)
REPOS = [
    ("Crucible", "AI mock interviewer that tracks your weak spots across "
     "sessions. A 6-agent LangGraph pipeline on Claude and Bedrock.",
     "TypeScript"),
    ("FinRAG", "Cited financial intelligence over SEC filings, exposed as "
     "MCP tools.", "Python"),
]
# ------------------------------------------------------------- END CONFIG ---

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "contributions.json")
CARDS = os.path.join(ROOT, "cards")


# ------------------------------------------------------------------- data ---
def parse(page):
    """GitHub's public contributions fragment -> sorted [(date, count)]."""
    tips = dict(re.findall(
        r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>(.*?)</tool-tip>', page, re.S))
    days = {}
    for tag in re.findall(r'<td[^>]*data-date="[^"]*"[^>]*>', page):
        date = re.search(r'data-date="([\d-]+)"', tag)[1]
        cell = re.search(r'\bid="([^"]+)"', tag)
        m = re.match(r"\s*(\d[\d,]*) contribution", tips.get(cell[1], "") if cell else "")
        count = int(m[1].replace(",", "")) if m else 0
        level = re.search(r'data-level="(\d)"', tag)
        if count == 0 and level and level[1] != "0":
            raise ValueError(f"{date} is shaded but has no count: markup changed")
        days[date] = count
    if len(days) < 300:
        raise ValueError(f"only {len(days)} calendar cells found: markup changed")
    return sorted(days.items())


def fetch():
    req = urllib.request.Request(
        f"https://github.com/users/{USER}/contributions",
        headers={"User-Agent": "profile-readme-bot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return parse(r.read().decode("utf-8", "replace"))


def stats(days):
    counts = [c for _, c in days]
    runs, start = [], None  # (length, start index, end index)
    for i, c in enumerate(counts + [0]):
        if c and start is None:
            start = i
        elif not c and start is not None:
            runs.append((i - start, start, i - 1))
            start = None
    # today isn't over yet, so an empty today doesn't break the streak
    last = len(counts) - 1 if counts[-1] else len(counts) - 2
    current = next((r for r in runs if r[2] == last), (0, None, None))
    longest = max(runs, default=(0, None, None))
    best = max(range(len(counts)), key=counts.__getitem__)
    monthly = {}
    for d, c in days:
        monthly[d[:7]] = monthly.get(d[:7], 0) + c
    active = sum(1 for c in counts if c)
    return dict(total=sum(counts), active=active,
                avg=sum(counts) / active if active else 0,
                current=current, longest=longest,
                best=(days[best][0], counts[best]),
                monthly=sorted(monthly.items()))


def levels(days):
    nz = sorted(c for _, c in days if c)
    cuts = [nz[len(nz) * q // 4] for q in (1, 2, 3)] if nz else []
    return [0 if not c else 1 + sum(c > q for q in cuts) for _, c in days]


def nice(date):
    d = dt.date.fromisoformat(date)
    return f"{d:%b} {d.day}"


# ---------------------------------------------------------------- drawing ---
MAROON, HOUSING, BLANK = "#7d1a37", "#5e1228", "#6c1c33"   # wall, board housing, empty tile
BONE, SHADE, UNDER, INK = "#f3ead8", "#cfc1a4", "#e2d6bd", "#2b1116"  # tile, falling flap, rising flap, letters
GOLD, SOFT = "#ffc627", "#f0d3cf"           # status only; reading text on maroon
HEAT = [HOUSING, "#9c3a52", "#c3604f", "#dd8a4b", "#eeb06a"]   # the best day alone is GOLD
LETTERS, DIGITS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0123456789"
WIDE, NARROW = 900, 450   # narrow cards are served to phones through <picture> in the README

esc = html.escape


def font_face(family, file, weight):
    path = os.path.join(ROOT, "fonts", file)
    if not os.path.exists(path):
        return ""   # falls back to the system faces named in CSS below
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return (f"@font-face{{font-family:{family};font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")


FACES = {"c": font_face("BC", "barlow-condensed-600.woff2", 600),
         "t": font_face("BT", "barlow-500.woff2", 500)}
CSS = (
    ".h,.g{font-family:BC,'Arial Narrow',Arial,sans-serif;font-weight:600}"
    ".t{font-family:BT,'Helvetica Neue',Arial,sans-serif;font-weight:500}"
    f".g{{fill:{INK};text-anchor:middle}}"
    # a tile frame: shown only for its own slice of time
    ".f{opacity:0;animation:show var(--s) step-end var(--d,0s)}@keyframes show{from,to{opacity:1}}"
    # a flip in two phases: the top half falls to the hinge, then the bottom half swings down
    ".k,.u{opacity:0;transform-box:fill-box}.k{transform-origin:50% 100%}.u{transform-origin:50% 0}"
    ".k1{animation:fall var(--s) linear var(--d)}.u1{animation:rise var(--s) linear var(--d)}"
    "@keyframes fall{0%{opacity:.92;transform:scaleY(1)}50%{opacity:.92;transform:scaleY(0)}50.1%,to{opacity:0}}"
    "@keyframes rise{0%,49.9%{opacity:0;transform:scaleY(0)}50%{opacity:.92;transform:scaleY(0)}"
    "to{opacity:.92;transform:scaleY(1)}}"
    # tiles that alternate between two messages forever
    ".b{opacity:0;animation:alt 14s step-end var(--d) infinite}@keyframes alt{0%{opacity:0}50%,to{opacity:1}}"
    ".k2{animation:fall2 14s linear var(--d) infinite}.u2{animation:rise2 14s linear var(--d) infinite}"
    "@keyframes fall2{0%,50%{opacity:.92;transform:scaleY(1)}.7%,50.7%{opacity:.92;transform:scaleY(0)}"
    ".71%,49.99%,50.71%,to{opacity:0}}"
    "@keyframes rise2{0%,.69%,50%,50.69%{opacity:0;transform:scaleY(0)}.7%,50.7%{opacity:.92;transform:scaleY(0)}"
    "1.4%,51.4%{opacity:.92;transform:scaleY(1)}1.41%,49.99%,51.41%,to{opacity:0}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
)


def svg(w, h, body, aria, css="", defs=""):
    faces = FACES["c"] + (FACES["t"] if 'class="t"' in body else "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(aria)}"><title>{esc(aria)}</title>'
            f"<style>{faces}{CSS}{css}</style><defs>{defs}</defs>{body}</svg>")


def wall(w, h, body, aria, css="", defs=""):
    """A card on the terminal wall. 4px outer margin so neighbours get a gap."""
    return svg(w, h, f'<rect x="4" y="4" width="{w-8}" height="{h-8}" rx="10" fill="{MAROON}"/>{body}',
               aria, css, defs)


def flaps(x, y, text, cw, ch, gap, size, t0, stagger=0.04, n=5, step=0.085, alt=None, alt_at=6.0):
    """A row of split-flap tiles. Each tile shuffles n glyphs, then lands on its
    letter. `alt` is a second message the row flips to at `alt_at` seconds (under
    7) and back every 7 seconds after, forever."""
    rng = random.Random(text)   # seeded, so re-rendering never changes the file
    tid = f"t{int(x)}_{int(y)}"
    tile, blank = f'<use href="#{tid}"/>', f'<use href="#{tid}b"/>'
    top = f'width="{cw}" height="{ch/2}" rx="2.5" fill="{SHADE}"'
    bottom = f'y="{ch/2}" width="{cw}" height="{ch/2}" rx="2.5" fill="{UNDER}"'
    face = lambda g: blank if g == " " else (
        f'{tile}<text class="g" x="{cw/2:.1f}" y="{ch/2+size*.35:.1f}">{esc(g)}</text>')
    out = (f'<defs><rect id="{tid}" width="{cw}" height="{ch}" rx="2.5" fill="{BONE}"/>'
           f'<rect id="{tid}b" width="{cw}" height="{ch}" rx="2.5" fill="{BLANK}" stroke="{BLANK}"/></defs>'
           f'<g font-size="{size}" style="--s:{step}s">')
    for i, c in enumerate(text):
        start = t0 + i * stagger
        out += f'<g transform="translate({x+i*(cw+gap):.1f} {y})">{face(c)}'
        if c != " ":
            pool = DIGITS if c.isdigit() else LETTERS
            out += f'<use class="f" href="#{tid}b" style="animation-duration:{start:.2f}s"/>'   # empty until its turn
            for j in range(n):
                out += f'<g class="f" style="--d:{start+j*step:.3f}s">{face(rng.choice(pool))}</g>'
            count = f"--d:{start:.2f}s;animation-iteration-count:{n+1}"
            out += f'<rect class="k k1" {top} style="{count}"/><rect class="u u1" {bottom} style="{count}"/>'
        other = alt[i] if alt and i < len(alt) else c
        if alt and other != c:
            d = f"--d:{alt_at + i * 0.03 - 7:.2f}s"   # negative: joins the 14s loop mid-cycle
            out += (f'<g class="b" style="{d}">{face(other)}</g>'
                    f'<rect class="k k2" {top} style="{d}"/><rect class="u u2" {bottom} style="{d}"/>')
        if c != " " or (alt and other != c):
            out += f'<path d="M0 {ch/2}h{cw}" stroke="{INK}" stroke-opacity="{.3 if ch > 40 else .16}"/>'
        out += "</g>"
    return out + "</g>"


def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur]


# ------------------------------------------------------------------ cards ---
# Every card takes w: WIDE for desktop, NARROW for phones.
def hero(w):
    narrow = w == NARROW
    m = 28 if narrow else 48
    rows = " ".join(NAME_ROWS).split() if narrow else NAME_ROWS
    cols = max(len(r) for r in rows)
    cw = round((w - 2 * m + 4) / cols - 4, 2)
    ch, size = (68, 62) if narrow else (76, 70)
    y = 40
    body = ""
    for r, row in enumerate(rows):
        body += flaps(m, y, row.ljust(cols), cw, ch, 4, size, 0.3 + r * 0.45, 0.05, 7)
        y += ch + 6
    y += 10
    small_cols = 17 if narrow else 33
    sw = round((w - 2 * m + 2) / small_cols - 2, 2)
    r = 0
    for role, also in ROLE_ROWS:
        a, b = wrap(role, small_cols), wrap(also, small_cols)
        for i in range(max(len(a), len(b))):
            body += flaps(m, y, (a[i] if i < len(a) else "").ljust(small_cols), sw, 30, 2, 26,
                          1.5 + r * 0.4, 0.025, 4,
                          alt=(b[i] if i < len(b) else "").ljust(small_cols), alt_at=6.6 + r * 0.08)
            y += 34
            r += 1
    housing = f'<rect x="{m-20}" y="20" width="{w-2*m+40}" height="{y-4}" rx="8" fill="{HOUSING}"/>'
    y += 34
    lines = wrap(" ".join(ABOUT), 46) if narrow else ABOUT
    for i, line in enumerate(lines):
        body += f'<text class="t" x="{m}" y="{y+18+i*27}" font-size="19" fill="{BONE}">{esc(line)}</text>'
    if narrow:
        y += len(lines) * 27 + 18
        px, pw = m, w - 2 * m
    else:
        px, pw = w - m - 250, 250
    body += (f'<rect x="{px}" y="{y}" width="{pw}" height="60" rx="8" fill="{GOLD}"/>'
             f'<text class="h" x="{px+pw/2}" y="{y+39}" font-size="27" fill="{INK}" text-anchor="middle">{esc(ACTION)}</text>')
    aria = (f"{' '.join(NAME_ROWS).title()}. " + " ".join(f"{a.capitalize()}. {b.capitalize()}." for a, b in ROLE_ROWS)
            + f" {' '.join(ABOUT)} {ACTION}.")
    return wall(w, y + 60 + 26, housing + body, aria)


def board(w):
    narrow = w == NARROW
    widths = (6, 17, 20)
    if narrow:
        pitch, cw, ch, size, m = 16.4, 14.8, 26, 18, 28
        xs = [m, m + (widths[0] + .7) * pitch, m]
        entry = 70
    else:
        pitch, cw, ch, size, m = 17.8, 16, 28, 20, 60
        xs = [m, m + (widths[0] + .7) * pitch, m + (widths[0] + widths[1] + 1.4) * pitch]
        entry = 34
    gap = pitch - cw
    top = 56
    body = (f'<text class="h" x="{48 if not narrow else m}" y="42" font-size="26" fill="{BONE}">On the board</text>'
            f'<rect x="{m-(32 if not narrow else 20)}" y="{top}" width="{w-2*m+(64 if not narrow else 40)}" '
            f'height="{(56 if not narrow else 30)+len(BOARD)*entry}" rx="8" fill="{HOUSING}"/>')
    y0 = top + 18
    if not narrow:
        for x, label in zip(xs, ("When", "Where", "What")):
            body += f'<text class="t" x="{x:.1f}" y="{top+26}" font-size="14" fill="{SOFT}">{label}</text>'
        y0 = top + 38
    for r, (when, where, what, also, live) in enumerate(BOARD):
        y, t = y0 + r * entry, 0.4 + r * 0.4
        y2 = y + ch + 4 if narrow else y
        body += flaps(xs[0], y, when.ljust(widths[0]), cw, ch, gap, size, t, 0.02, 3)
        body += flaps(xs[1], y, where.ljust(widths[1]), cw, ch, gap, size, t + .12, 0.02, 3)
        body += flaps(xs[2], y2, what.ljust(widths[2]), cw, ch, gap, size, t + .45, 0.02, 3,
                      alt=also.ljust(widths[2]), alt_at=3.4 + r * 0.5)
        if live:    # the job that is boarding now gets the blinking lamps
            lx = m - 16 if not narrow else m - 10
            body += (f'<circle class="lamp" cx="{lx}" cy="{y+8}" r="4" fill="{GOLD}"/>'
                     f'<circle class="lamp l2" cx="{lx}" cy="{y+20}" r="4" fill="{GOLD}"/>')
    css = ("@keyframes lamp{50%{opacity:.15}}.lamp{animation:lamp 1.4s step-end infinite}"
           ".l2{animation-delay:.7s}")
    aria = "On the board. " + " ".join(
        f"{when}: {where}, {what.lower()}, {also.lower()}." for when, where, what, also, _ in BOARD)
    return wall(w, (124 if not narrow else 100) + len(BOARD) * entry, body, aria, css)


def throughput(w, days, st):
    narrow = w == NARROW
    m = 28 if narrow else 48
    body, x = "", m
    for k, group in enumerate(f"{st['total']:,}".split(",")):   # odometer
        if k:
            body += f'<text class="h" x="{x-1}" y="96" font-size="50" fill="{BONE}">,</text>'
            x += 14
        body += flaps(x, 40, group, 40, 58, 4, 52, 0.3 + k * 0.2, 0.09, 8, 0.07)
        x += len(group) * 44
    body += (f'<text class="t" x="{x+12}" y="66" font-size="20" fill="{BONE}">contributions</text>'
             f'<text class="t" x="{x+12}" y="90" font-size="20" fill="{BONE}">in the last year</text>')
    cur, lon, best = st["current"], st["longest"], st["best"]
    facts = [f"Best day: {best[1]}, on {nice(best[0])}",
             f"Longest streak: {lon[0]} days",
             f"Current streak: {cur[0]} day{'s' * (cur[0] != 1)}"]
    y0 = 128
    for i, fact in enumerate(facts):
        if narrow:
            body += f'<text class="t" x="{m}" y="{138+i*25}" font-size="17" fill="{SOFT}">{esc(fact)}</text>'
            y0 = 214
        else:
            body += (f'<text class="t" x="{w-m}" y="{54+i*24}" font-size="16" fill="{SOFT}" '
                     f'text-anchor="end">{esc(fact)}</text>')
    shown = days[-(26 * 7 + dt.date.fromisoformat(days[-1][0]).isoweekday() % 7 + 1):] if narrow else days
    lv = dict(zip((d for d, _ in days), levels(days)))
    pad = (dt.date.fromisoformat(shown[0][0]).weekday() + 1) % 7   # columns start on Sunday
    cols = math.ceil((pad + len(shown)) / 7)
    pitch = (w - 2 * m + 3) / cols
    cell = pitch - 3
    prev, last_x = None, -99
    for i, (date, count) in enumerate(shown, pad):
        col, row = divmod(i, 7)
        cx, cy = m + col * pitch, y0 + row * pitch
        d = dt.date.fromisoformat(date)
        if row == 0 and d.month != prev and cx - last_x > 34:
            body += (f'<text class="t" x="{cx:.1f}" y="{y0+7*pitch+15:.0f}" font-size="13" '
                     f'fill="{SOFT}">{d:%b}</text>')
            last_x = cx
        if row == 0:
            prev = d.month
        peak = date == best[0]
        body += (f'<rect class="c" x="{cx:.1f}" y="{cy:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2" '
                 f'fill="{GOLD if peak else HEAT[lv[date]]}" style="animation-delay:{0.5+col*0.025:.2f}s">'
                 f"<title>{count} on {date}</title></rect>")
        if peak:
            body += (f'<rect class="c peak" x="{cx-3:.1f}" y="{cy-3:.1f}" width="{cell+6:.1f}" '
                     f'height="{cell+6:.1f}" rx="4" fill="none" stroke="{GOLD}" stroke-width="1.5"/>')
    css = (".c{transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.16,1,.3,1) both}"
           "@keyframes pop{from{opacity:0;transform:scale(.3)}}"
           ".peak{animation:pop .45s 2.2s both,ring 2.4s 2.8s ease-in-out infinite}@keyframes ring{50%{opacity:.2}}")
    foot = 36
    if narrow:
        body += (f'<text class="t" x="{m}" y="{y0+7*pitch+42:.0f}" font-size="14" fill="{SOFT}">'
                 f"The grid shows the last six months.</text>")
        foot = 62
    aria = (f"{st['total']:,} contributions in the last year. " + ". ".join(facts) + ".")
    return wall(w, round(y0 + 7 * pitch + foot), body, aria, css)


def stack(w):
    narrow = w == NARROW
    m = 28 if narrow else 48
    body, y = f'<text class="h" x="{m}" y="48" font-size="26" fill="{BONE}">Stack</text>', 70
    for label, items in STACK:
        body += (f'<path d="M{m} {y}H{w-m}" stroke="{BONE}" stroke-opacity=".28"/>'
                 f'<text class="h" x="{m}" y="{y+24}" font-size="19" fill="{BONE}">{esc(label)}</text>')
        if narrow:
            lines = wrap(items, 50)
            for i, line in enumerate(lines):
                body += f'<text class="t" x="{m}" y="{y+48+i*22}" font-size="16.5" fill="{SOFT}">{esc(line)}</text>'
            y += 40 + len(lines) * 22
        else:
            body += f'<text class="t" x="236" y="{y+24}" font-size="16.5" fill="{SOFT}">{esc(items)}</text>'
            y += 36
    aria = "Stack. " + " ".join(f"{label}: {items}." for label, items in STACK)
    return wall(w, y + 18, body, aria)


def ticket(w, name, desc, lang):
    """A repo as a paper ticket: punched notches and a tear line before the stub."""
    narrow = w == NARROW
    h, tear = (190, w - 124) if narrow else (132, w - 190)
    mid = (tear + w - 4) / 2
    body = (f'<rect x="4" y="4" width="{w-8}" height="{h-8}" rx="10" fill="{BONE}" mask="url(#punch)"/>'
            f'<path d="M{tear} 20V{h-20}" stroke="{INK}" stroke-opacity=".35" stroke-dasharray="2 6" stroke-linecap="round"/>'
            f'<text class="h" x="28" y="{60 if narrow else 78}" font-size="{36 if narrow else 40}" fill="{INK}">{esc(name)}</text>')
    width = 38 if narrow else 62
    lines = wrap(desc, width)
    while len(lines) > 1 and " " not in lines[-1] and width > 30:   # no one-word last line
        width -= 2
        lines = wrap(desc, width)
    lines = lines[:4]
    tx, ty = (28, 90) if narrow else (250, 74 - (len(lines) - 1) * 11)
    for i, line in enumerate(lines):
        body += (f'<text class="t" x="{tx}" y="{ty+i*22}" font-size="16" fill="{INK}" '
                 f'fill-opacity=".85">{esc(line)}</text>')
    body += (f'<text class="t" x="{mid:.0f}" y="{h/2-8:.0f}" font-size="13" fill="{INK}" fill-opacity=".7" text-anchor="middle">Written in</text>'
             f'<text class="h" x="{mid:.0f}" y="{h/2+18:.0f}" font-size="23" fill="{INK}" text-anchor="middle">{esc(lang)}</text>')
    defs = (f'<mask id="punch"><rect width="{w}" height="{h}" fill="#fff"/>'
            f'<circle cx="{tear}" cy="4" r="9"/><circle cx="{tear}" cy="{h-4}" r="9"/></mask>')
    return svg(w, h, body, f"{name}: {desc} Written in {lang}.", defs=defs)


def plate(w, label, primary):
    """A link plate. The portfolio plate spans the row; the others take half each."""
    narrow = w == NARROW
    pw, h, size = (w if primary else w // 2), (100 if narrow else 84), (30 if primary or narrow else 26)
    fill, ink = (GOLD, INK) if primary else (MAROON, BONE)
    return svg(pw, h, f'<rect x="4" y="4" width="{pw-8}" height="{h-8}" rx="8" fill="{fill}"/>'
               f'<text class="h" x="{pw/2}" y="{h/2+size*.35:.0f}" font-size="{size}" '
               f'fill="{ink}" text-anchor="middle">{esc(label)}</text>', label)


# -------------------------------------------------------------------- run ---
def render(days):
    st = stats(days)
    out = {}
    for w, suffix in ((WIDE, ""), (NARROW, "-narrow")):
        out.update({"hero" + suffix: hero(w), "board" + suffix: board(w),
                    "throughput" + suffix: throughput(w, days, st), "stack" + suffix: stack(w)})
        out.update({f"repo-{r[0].lower()}{suffix}": ticket(w, *r) for r in REPOS})
        out.update({"link-portfolio" + suffix: plate(w, ACTION, True),
                    "link-linkedin" + suffix: plate(w, "LinkedIn", False),
                    "link-email" + suffix: plate(w, "Email", False)})
    os.makedirs(CARDS, exist_ok=True)
    for name, card in out.items():
        with open(os.path.join(CARDS, name + ".svg"), "w", encoding="utf-8") as f:
            f.write(card)
    return st


def test():
    cell = ('<td data-date="{d}" id="c{i}" data-level="{l}" class="ContributionCalendar-day"></td>'
            '<tool-tip for="c{i}">{t}</tool-tip>')
    start = dt.date(2026, 1, 1)
    plan = {0: 2, 1: 3, 2: 1, 10: 5, 364: 1}   # day offset -> count
    page = "".join(cell.format(
        d=start + dt.timedelta(i), i=i, l=1 if i in plan else 0,
        t=f"{plan[i]} contributions on a day." if i in plan else "No contributions on a day.")
        for i in range(365))
    days = parse(page)
    st = stats(days)
    assert len(days) == 365 and st["total"] == 12 and st["active"] == 5
    assert st["longest"][0] == 3 and st["current"][0] == 1
    assert st["best"] == ("2026-01-11", 5)
    assert stats(days[:-1])["current"][0] == 0          # gap before today
    assert stats(days[:3] + [("x", 0)])["current"][0] == 3  # empty today keeps the streak
    assert levels([("a", 0), ("b", 1), ("c", 9)])[0] == 0
    try:
        parse(page.replace("5 contributions", "oops"))
        raise AssertionError("shaded cell without a count should fail")
    except ValueError:
        pass
    assert wrap("aa bb cc", 5) == ["aa bb", "cc"]
    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        test()
        sys.exit()
    if "--offline" in sys.argv:
        with open(DATA, encoding="utf-8") as f:
            days = [tuple(d) for d in json.load(f)["days"]]
    else:
        days = fetch()   # raises before anything is written if GitHub's markup changed
        os.makedirs(os.path.dirname(DATA), exist_ok=True)
        with open(DATA, "w", encoding="utf-8") as f:
            json.dump({"user": USER, "days": days}, f, separators=(",", ":"))
    st = render(days)
    print(f"{st['total']:,} contributions, current streak {st['current'][0]}, "
          f"longest {st['longest'][0]}, best day {st['best'][1]} on {st['best'][0]}")
