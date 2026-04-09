#!/usr/bin/env python3
"""
Generate pages/intelligence.html from an Anthropic Claude briefing on nature-based finance.
Requires: pip install anthropic
Environment: ANTHROPIC_API_KEY
"""

from __future__ import annotations

import html
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-5"
MAX_TOKENS = 2000

# Exact briefing prompt (date substituted); JSON instructions sent as a separate user block below.
BRIEFING_PROMPT = """You are a nature-based finance analyst.
Generate a structured intelligence
briefing on the current state of
nature-based finance. Include:

1. MARKET PULSE: 3-4 key developments
in nature-based finance in the past
30 days — carbon markets, biodiversity
credits, green bonds, ecosystem services

2. CAPITAL FLOWS: Where institutional
capital is moving in nature-based
solutions — notable funds, deals,
or commitments

3. SIGNAL vs NOISE: One thing that is
being overhyped and one genuine
emerging opportunity in this space

4. SDG GAP ANALYSIS: Which SDGs related
to nature are most underfunded right
now and why

5. SUSHANT'S TAKE: A brief analytical
perspective (2-3 sentences) on what
this means for impact investors and
fund managers

Format each section with a clear title
and 2-4 sentences of analysis. Be
specific, data-informed, and direct.
Write for sophisticated investors and
fund managers, not for a general
audience. Today's date is {date}."""

JSON_INSTRUCTION = """Now respond with ONLY valid JSON (no markdown fences, no prose outside JSON) using this exact structure:
{"sections":[
  {"title":"MARKET PULSE","body":"plain text, 2-4 sentences"},
  {"title":"CAPITAL FLOWS","body":"plain text, 2-4 sentences"},
  {"title":"SIGNAL vs NOISE","body":"plain text, 2-4 sentences"},
  {"title":"SDG GAP ANALYSIS","body":"plain text, 2-4 sentences"},
  {"title":"SUSHANT'S TAKE","body":"plain text, 2-4 sentences"}
]}
Each body must be plain text only (no HTML tags). Escape double quotes inside strings properly."""

NAV_AND_OPEN = """  <!-- ── HEADER ── -->
  <header class="site-header">
    <nav class="site-nav" aria-label="Primary">
      <a href="../index.html" class="nav-logo" aria-label="Sushant Shrestha — home">
        <span class="nav-logo-name">Sushant Shrestha</span>
        <span class="nav-logo-tag">VENTURE CAPITAL · SYSTEMS ANALYST · AUTHOR</span>
      </a>
      <button class="nav-toggle" aria-expanded="false" aria-label="Open menu" aria-controls="nav-links">
        <span></span><span></span><span></span>
      </button>
      <ul class="nav-links" id="nav-links">
        <li><a href="about.html">About</a></li>
        <li><a href="ventures.html">Ventures</a></li>
        <li><a href="services.html">Services</a></li>
        <li><a href="teaching.html">Perspectives</a></li>
        <li><a href="writing.html">Writing</a></li>
        <li><a href="testimonials.html">Testimonials</a></li>
        <li><a href="connect.html">Connect</a></li>
      </ul>
    </nav>
  </header>
"""

FOOTER_AND_SCRIPT = """  <!-- ── FOOTER ── -->
  <footer class="site-footer">
    <div class="footer-inner">
      <span>© 2026 Sushant Shrestha</span>
      <span>Pacific Northwest · Bay Area</span>
    </div>
  </footer>

  <script src="../assets/js/main.js"></script>
"""


def extract_json_obj(text: str) -> dict | None:
    """Find JSON object in response (handles optional markdown fence)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    last_open = text.rfind("{")
    if last_open == -1:
        return None
    depth = 0
    for i in range(last_open, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[last_open : i + 1])
                except json.JSONDecodeError:
                    break
    return None


def sections_fallback(text: str) -> list[dict[str, str]]:
    return [
        {
            "title": "INTELLIGENCE BRIEFING",
            "body": text.strip()[:8000],
        }
    ]


def body_to_paragraphs(body: str) -> str:
    body = body.strip()
    if not body:
        return '<p style="margin:0;">&nbsp;</p>'
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paras:
        paras = [body]
    lines: list[str] = []
    for i, p in enumerate(paras):
        margin_bottom = "0" if i == len(paras) - 1 else "12px"
        lines.append(
            f'<p style="margin:0 0 {margin_bottom};">{html.escape(p)}</p>'
        )
    return "\n".join(lines)


def build_html(sections: list[dict[str, str]], updated_iso: str) -> str:
    cards: list[str] = []
    for sec in sections:
        title = html.escape(str(sec.get("title", "SECTION")).strip())
        body_html = body_to_paragraphs(str(sec.get("body", "")))
        cards.append(
            f"""      <div style="background:#f5f5f7;border-radius:12px;padding:24px;margin-bottom:16px;">
        <h2 style="font-family:'Inter',sans-serif;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:#1d1d1f;margin:0 0 12px;">{title}</h2>
        <div style="font-family:'Inter',sans-serif;font-size:15px;font-weight:400;line-height:1.8;color:#1d1d1f;">
          {body_html}
        </div>
      </div>"""
        )

    cards_block = "\n".join(cards)
    try:
        dt = datetime.fromisoformat(updated_iso.replace("Z", "+00:00"))
        display_ts = dt.strftime("%B %d, %Y at %H:%M UTC")
    except ValueError:
        display_ts = updated_iso

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Intelligence — AI-synthesized briefing on nature-based finance, capital flows, and SDG investment gaps.">
  <title>Intelligence | Sushant Shrestha</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../assets/css/main.css">
</head>
<body>

{NAV_AND_OPEN}
  <main>

    <!-- ── PAGE HEADER ── -->
    <section class="page-hero">
      <div class="page-hero-inner">
        <p class="kicker">NATURE-BASED FINANCE</p>
        <h1 class="page-hero-name">Intelligence</h1>
        <p class="page-intro">AI-synthesized briefing on nature-based finance, capital flows, and SDG investment gaps. Updated periodically.</p>
      </div>
    </section>

    <div class="section">
{cards_block}
      <p style="font-family:'Inter',sans-serif;font-size:12px;color:#aeaeb2;margin:24px 0 0;">Last updated: {html.escape(display_ts)}</p>
    </div>

  </main>

{FOOTER_AND_SCRIPT}</body>
</html>
"""


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set.")

    today = date.today().isoformat()
    user_block_1 = BRIEFING_PROMPT.format(date=today)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_block_1},
                    {"type": "text", "text": JSON_INSTRUCTION},
                ],
            }
        ],
    )

    parts: list[str] = []
    for block in message.content:
        if block.type == "text":
            parts.append(block.text)
    raw = "\n".join(parts)

    parsed = extract_json_obj(raw)
    if parsed and isinstance(parsed.get("sections"), list):
        sections = []
        for item in parsed["sections"]:
            if isinstance(item, dict) and "title" in item and "body" in item:
                sections.append({"title": item["title"], "body": item["body"]})
        if len(sections) != 5:
            sections = sections_fallback(raw)
    else:
        sections = sections_fallback(raw)

    updated_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    html_out = build_html(sections, updated_iso)

    root = Path(__file__).resolve().parent
    out_path = root / "pages" / "intelligence.html"
    out_path.write_text(html_out, encoding="utf-8")
    print("Intelligence page updated successfully")


if __name__ == "__main__":
    main()
