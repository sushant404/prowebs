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
        <li><a href="intelligence.html">Intelligence</a></li>
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


def pick_section(sections: list[dict[str, str]], title: str) -> str:
    for sec in sections:
        if str(sec.get("title", "")).strip().lower() == title.strip().lower():
            return str(sec.get("body", "")).strip()
    return ""


def split_signal_noise(body: str) -> tuple[str, str]:
    """
    Split SIGNAL vs NOISE into (overhyped, opportunity).
    Prefer paragraph split; fallback to a first-sentence split.
    """
    body = body.strip()
    if not body:
        return "", ""

    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if len(paras) >= 2:
        return paras[0], "\n\n".join(paras[1:]).strip()

    parts = re.split(r"(?<=[.!?])\s+", body, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return body, ""


def build_html(sections: list[dict[str, str]], updated_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(updated_iso.replace("Z", "+00:00"))
        display_ts = dt.strftime("%B %d, %Y at %H:%M UTC")
    except ValueError:
        display_ts = updated_iso

    market_pulse = pick_section(sections, "MARKET PULSE")
    capital_flows = pick_section(sections, "CAPITAL FLOWS")
    signal_noise = pick_section(sections, "SIGNAL vs NOISE")
    sdg_gap = pick_section(sections, "SDG GAP ANALYSIS")
    sushant_take = pick_section(sections, "SUSHANT'S TAKE")

    overhyped, opportunity = split_signal_noise(signal_noise)

    def card_full(title: str, body: str, border_left: str, pill_bg: str, pill_text: str) -> str:
        return f"""      <div style="background:#f5f5f7;border-radius:16px;padding:32px;border-left:4px solid {border_left};margin-bottom:16px;position:relative;">
        <span style="position:absolute;top:24px;right:24px;background:{pill_bg};color:#ffffff;font-family:'Inter',sans-serif;font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;padding:4px 10px;border-radius:980px;">{html.escape(pill_text)}</span>
        <h2 style="font-family:'Inter',sans-serif;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:#1d1d1f;margin:0 0 12px;">{html.escape(title)}</h2>
        <div style="font-family:'Inter',sans-serif;font-size:15px;font-weight:400;line-height:1.8;color:#1d1d1f;">{body_to_paragraphs(body)}</div>
      </div>"""

    def card_half(title: str, body: str, border_left: str, pill_bg: str, pill_text: str) -> str:
        return f"""          <div style="background:#f5f5f7;border-radius:16px;padding:32px;border-left:4px solid {border_left};position:relative;">
            <span style="position:absolute;top:24px;right:24px;background:{pill_bg};color:#ffffff;font-family:'Inter',sans-serif;font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;padding:4px 10px;border-radius:980px;">{html.escape(pill_text)}</span>
            <h2 style="font-family:'Inter',sans-serif;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:#1d1d1f;margin:0 0 12px;">{html.escape(title)}</h2>
            <div style="font-family:'Inter',sans-serif;font-size:15px;font-weight:400;line-height:1.8;color:#1d1d1f;">{body_to_paragraphs(body)}</div>
          </div>"""

    metric_1_num, metric_1_label = "$2.1B", "Voluntary carbon Q1 2026"
    metric_2_num, metric_2_label = "3.2x", "Brazil Forest Bond oversubscribed"
    metric_3_num, metric_3_label = "$1.8B", "Mirova Natural Capital Fund III"

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

    <!-- ── HERO ── -->
    <section style="background:#1d1d1f;padding:48px 0;color:#ffffff;">
      <div style="max-width:980px;margin:0 auto;padding:0 24px;display:grid;grid-template-columns:1.4fr 1fr;gap:24px;align-items:start;">
        <div>
          <div style="font-family:'Inter',sans-serif;font-size:11px;font-weight:500;letter-spacing:0.12em;text-transform:uppercase;color:#6e6e73;line-height:1;">NATURE-BASED FINANCE · INTELLIGENCE</div>
          <h1 style="font-family:'Inter',sans-serif;font-size:40px;font-weight:600;color:#ffffff;letter-spacing:-0.02em;margin:12px 0 10px;line-height:1.1;">Intelligence Briefing</h1>
          <p style="font-family:'Inter',sans-serif;font-size:16px;font-weight:400;color:#6e6e73;line-height:1.7;max-width:480px;margin:0;">AI-synthesized analysis of capital flows, market signals, and investment gaps in nature-based finance.</p>
          <p style="font-family:'Inter',sans-serif;font-size:12px;color:#444;margin-top:16px;margin-bottom:0;">Last updated: {html.escape(display_ts)}</p>
        </div>

        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;align-content:start;">
          <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:16px 20px;">
            <div style="font-family:'Inter',sans-serif;font-size:24px;font-weight:600;color:#ffffff;line-height:1.1;margin:0 0 6px;">{html.escape(metric_1_num)}</div>
            <div style="font-family:'Inter',sans-serif;font-size:11px;color:#6e6e73;line-height:1.3;">{html.escape(metric_1_label)}</div>
          </div>
          <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:16px 20px;">
            <div style="font-family:'Inter',sans-serif;font-size:24px;font-weight:600;color:#ffffff;line-height:1.1;margin:0 0 6px;">{html.escape(metric_2_num)}</div>
            <div style="font-family:'Inter',sans-serif;font-size:11px;color:#6e6e73;line-height:1.3;">{html.escape(metric_2_label)}</div>
          </div>
          <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:16px 20px;">
            <div style="font-family:'Inter',sans-serif;font-size:24px;font-weight:600;color:#ffffff;line-height:1.1;margin:0 0 6px;">{html.escape(metric_3_num)}</div>
            <div style="font-family:'Inter',sans-serif;font-size:11px;color:#6e6e73;line-height:1.3;">{html.escape(metric_3_label)}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ── CONTENT ── -->
    <section style="background:#ffffff;">
      <div style="max-width:980px;margin:0 auto;padding:40px 24px;">

{card_full("Market Pulse", market_pulse, "#1d1d1f", "#1d1d1f", "MARKET PULSE")}

{card_full("Capital Flows", capital_flows, "#0071e3", "#0071e3", "CAPITAL FLOWS")}

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
{card_half("Overhyped", overhyped, "#E24B4A", "#E24B4A", "OVERHYPED")}
{card_half("Opportunity", opportunity, "#34c759", "#34c759", "OPPORTUNITY")}
        </div>

        <div style="background:#f5f5f7;border-radius:16px;padding:32px;border-left:4px solid #EF9F27;margin-bottom:16px;position:relative;">
          <span style="position:absolute;top:24px;right:24px;background:#EF9F27;color:#1d1d1f;font-family:'Inter',sans-serif;font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;padding:4px 10px;border-radius:980px;">SDG GAP ANALYSIS</span>
          <h2 style="font-family:'Inter',sans-serif;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:#1d1d1f;margin:0 0 12px;">SDG Gap Analysis</h2>
          <div style="font-family:'Inter',sans-serif;font-size:15px;font-weight:400;line-height:1.8;color:#1d1d1f;margin:0 0 16px;">{body_to_paragraphs(sdg_gap)}</div>

          <div style="margin-top:8px;">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:8px;">
              <div style="font-family:'Inter',sans-serif;font-size:12px;color:#6e6e73;">SDG 14 — Life Below Water</div>
              <div style="font-family:'Inter',sans-serif;font-size:12px;color:#6e6e73;">8% funded</div>
            </div>
            <div style="background:#e8e8e8;height:6px;border-radius:3px;overflow:hidden;margin-bottom:14px;">
              <div style="width:8%;background:#EF9F27;height:6px;border-radius:3px;"></div>
            </div>

            <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:8px;">
              <div style="font-family:'Inter',sans-serif;font-size:12px;color:#6e6e73;">SDG 15 — Life on Land</div>
              <div style="font-family:'Inter',sans-serif;font-size:12px;color:#6e6e73;">12% funded</div>
            </div>
            <div style="background:#e8e8e8;height:6px;border-radius:3px;overflow:hidden;">
              <div style="width:12%;background:#EF9F27;height:6px;border-radius:3px;"></div>
            </div>
          </div>
        </div>

        <div style="background:#1d1d1f;color:#ffffff;border-radius:16px;padding:32px;margin-bottom:16px;position:relative;">
          <span style="position:absolute;top:24px;right:24px;background:rgba(255,255,255,0.1);color:#ffffff;font-family:'Inter',sans-serif;font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;padding:4px 10px;border-radius:980px;">SUSHANT'S TAKE</span>
          <div style="font-family:'Inter',sans-serif;font-size:60px;font-weight:300;color:rgba(255,255,255,0.1);line-height:0.9;margin-bottom:8px;user-select:none;">"</div>
          <div style="font-family:'Inter',sans-serif;font-size:16px;font-weight:400;font-style:italic;line-height:1.8;color:#ffffff;">{body_to_paragraphs(sushant_take)}</div>
        </div>

        <p style="text-align:center;font-family:'Inter',sans-serif;font-size:13px;color:#aeaeb2;line-height:1.7;margin:24px auto 0;max-width:720px;">This briefing is AI-synthesized using Claude by Anthropic and updated periodically. It reflects publicly available information and represents analytical perspective, not investment advice.</p>

      </div>
    </section>

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
