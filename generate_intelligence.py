#!/usr/bin/env python3
"""
Generate intelligence dashboard pages using an LLM API briefing on nature-based finance.
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

import time

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

VC_TRENDS_PROMPT = """You are a venture capital analyst.
Generate a structured intelligence
briefing on current venture capital
trends. Include:

1. MARKET PULSE: 3-4 key developments
in global venture capital in the past
30 days — deal volumes, sector shifts,
notable raises

2. CAPITAL FLOWS: Where institutional
and LP capital is moving — which
sectors are attracting investment and
which are being avoided

3. SIGNAL vs NOISE: One trend being
overhyped and one genuine emerging
opportunity in venture

4. SECTOR HEAT MAP: Rate these sectors
as Hot, Warm, or Cooling right now:
AI Infrastructure, Climate Tech,
Biotech, Fintech, Defense Tech,
Consumer. One sentence explanation
for each.

5. FUND MANAGER TAKE: A brief
analytical perspective on what this
means for emerging and impact fund
managers specifically

Write for sophisticated fund managers
and institutional allocators.
Today's date is {date}."""

SDG_GAP_PROMPT = """You are an impact finance analyst
specializing in SDG-aligned capital.
Generate a structured intelligence
briefing on SDG investment gaps.
Include:

1. MARKET PULSE: Current state of
SDG-aligned finance globally —
key developments in the past 30 days

2. CAPITAL FLOWS: Which SDGs are
attracting capital and which are
critically underfunded — be specific
with percentages or dollar figures
where possible

3. SIGNAL vs NOISE: One SDG narrative
being overhyped and one genuine
funding opportunity being missed

4. GAP ANALYSIS: The three most
underfunded SDGs right now with a
one-sentence explanation of why
capital is not flowing there

5. ALLOCATOR TAKE: What this means
for impact-first fund managers and
institutional allocators seeking
SDG alignment

Write for sophisticated impact
investors and fund managers.
Today's date is {date}."""

AI_CAPITAL_PROMPT = """You are a technology venture analyst.
Generate a structured intelligence
briefing on AI and emerging tech
capital flows. Include:

1. MARKET PULSE: 3-4 key developments
in AI and emerging tech funding in
the past 30 days

2. CAPITAL FLOWS: Where institutional
capital is concentrating in AI —
infrastructure, applications, safety,
or adjacent technologies

3. SIGNAL vs NOISE: One AI investment
theme being overhyped and one genuine
emerging opportunity

4. REGULATORY SIGNALS: Key regulatory
developments affecting AI investment
thesis and fund strategy globally

5. FUND MANAGER TAKE: What this means
for venture and impact fund managers
incorporating AI into their thesis

Write for sophisticated fund managers
and technology investors.
Today's date is {date}."""

IMPACT_FUNDS_PROMPT = """You are an impact investing analyst.
Generate a structured intelligence
briefing on the global impact fund
landscape. Include:

1. MARKET PULSE: Key developments in
impact fund raising, closing, and
deploying in the past 30 days

2. CAPITAL FLOWS: LP appetite for
impact funds — which strategies are
attracting capital and which are
facing headwinds

3. SIGNAL vs NOISE: One impact fund
trend being overhyped and one genuine
structural shift in how impact capital
is being deployed

4. MANAGER LANDSCAPE: Notable emerging
managers, first-time funds, or
established managers making notable
moves in the impact space

5. ALLOCATOR TAKE: What this means
for LPs evaluating impact fund
managers and for GPs raising
impact-focused vehicles

Write for sophisticated LPs,
fund-of-funds managers, and emerging
impact GPs.
Today's date is {date}."""

JSON_INSTRUCTION = """Now respond with ONLY valid JSON (no markdown fences, no prose outside JSON) using this exact structure:
{
  "metrics": [
    {"number": "string", "label": "string"},
    {"number": "string", "label": "string"},
    {"number": "string", "label": "string"}
  ],
  "sections": [
    {"title": "MARKET PULSE", "body": "plain text, 2-4 sentences"},
    {"title": "CAPITAL FLOWS", "body": "plain text, 2-4 sentences"},
    {"title": "SIGNAL vs NOISE", "body": "plain text, 2-4 sentences"},
    {"title": "SECTION 4", "body": "plain text, 2-4 sentences"},
    {"title": "SECTION 5", "body": "plain text, 2-4 sentences"}
  ]
}

Rules:
- Output JSON only.
- Each body must be plain text only (no HTML tags).
- metrics must contain exactly 3 items, data-informed and specific to this briefing.
- Use the exact titles requested in the prompt for sections 4 and 5 (e.g. SECTOR HEAT MAP / FUND MANAGER TAKE).
- Escape double quotes inside strings properly."""

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
        <li><a href="intelligence.html">Intel</a></li>
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


def metrics_fallback() -> list[dict[str, str]]:
    return [
        {"number": "—", "label": "Metric"},
        {"number": "—", "label": "Metric"},
        {"number": "—", "label": "Metric"},
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


def build_html(
    *,
    hero_kicker: str,
    hero_title: str,
    hero_subtitle: str,
    accent: str,
    metrics: list[dict[str, str]],
    sections: list[dict[str, str]],
    updated_iso: str,
) -> str:
    try:
        dt = datetime.fromisoformat(updated_iso.replace("Z", "+00:00"))
        display_ts = dt.strftime("%B %d, %Y at %H:%M UTC")
    except ValueError:
        display_ts = updated_iso

    market_pulse = pick_section(sections, "MARKET PULSE")
    capital_flows = pick_section(sections, "CAPITAL FLOWS")
    signal_noise = pick_section(sections, "SIGNAL vs NOISE")

    # Section 4 and 5 vary by dashboard; we render by position if needed.
    section4 = sections[3]["body"].strip() if len(sections) >= 4 and isinstance(sections[3], dict) else ""
    section4_title = sections[3]["title"].strip() if len(sections) >= 4 and isinstance(sections[3], dict) else "SECTION 4"

    section5 = sections[4]["body"].strip() if len(sections) >= 5 and isinstance(sections[4], dict) else ""
    section5_title = sections[4]["title"].strip() if len(sections) >= 5 and isinstance(sections[4], dict) else "SECTION 5"

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

    m = metrics if isinstance(metrics, list) and len(metrics) == 3 else metrics_fallback()
    metric_1_num, metric_1_label = str(m[0].get("number", "—")), str(m[0].get("label", "Metric"))
    metric_2_num, metric_2_label = str(m[1].get("number", "—")), str(m[1].get("label", "Metric"))
    metric_3_num, metric_3_label = str(m[2].get("number", "—")), str(m[2].get("label", "Metric"))

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

    <div style="max-width:980px;margin:0 auto;padding:12px 24px 0;">
      <a href="intelligence.html" style="font-family:'Inter',sans-serif;font-size:13px;color:#6e6e73;text-decoration:none;">← Back to Intelligence</a>
    </div>

    <!-- ── HERO ── -->
    <section style="background:#1d1d1f;padding:48px 0;color:#ffffff;">
      <div style="max-width:980px;margin:0 auto;padding:0 24px;display:grid;grid-template-columns:1.4fr 1fr;gap:24px;align-items:start;">
        <div>
          <div style="font-family:'Inter',sans-serif;font-size:11px;font-weight:500;letter-spacing:0.12em;text-transform:uppercase;color:#6e6e73;line-height:1;">{html.escape(hero_kicker)}</div>
          <h1 style="font-family:'Inter',sans-serif;font-size:40px;font-weight:600;color:#ffffff;letter-spacing:-0.02em;margin:12px 0 10px;line-height:1.1;">{html.escape(hero_title)}</h1>
          <p style="font-family:'Inter',sans-serif;font-size:16px;font-weight:400;color:#6e6e73;line-height:1.7;max-width:480px;margin:0;">{html.escape(hero_subtitle)}</p>
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

{card_full("Capital Flows", capital_flows, accent, accent, "CAPITAL FLOWS")}

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
{card_half("Overhyped", overhyped, "#E24B4A", "#E24B4A", "OVERHYPED")}
{card_half("Opportunity", opportunity, "#34c759", "#34c759", "OPPORTUNITY")}
        </div>

{card_full(section4_title, section4, "#EF9F27", "#EF9F27", section4_title)}

        <div style="background:#1d1d1f;color:#ffffff;border-radius:16px;padding:32px;margin-bottom:16px;position:relative;">
          <span style="position:absolute;top:24px;right:24px;background:rgba(255,255,255,0.1);color:#ffffff;font-family:'Inter',sans-serif;font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;padding:4px 10px;border-radius:980px;">{html.escape(section5_title)}</span>
          <div style="font-family:'Inter',sans-serif;font-size:60px;font-weight:300;color:rgba(255,255,255,0.1);line-height:0.9;margin-bottom:8px;user-select:none;">"</div>
          <div style="font-family:'Inter',sans-serif;font-size:16px;font-weight:400;font-style:italic;line-height:1.8;color:#ffffff;">{body_to_paragraphs(section5)}</div>
        </div>

        <p style="text-align:center;font-family:'Inter',sans-serif;font-size:13px;color:#aeaeb2;line-height:1.7;margin:24px auto 0;max-width:720px;">This briefing is AI-synthesized using a large language model API and updated periodically. It reflects publicly available information and represents analytical perspective, not investment advice.</p>

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

    dashboards = [
        {
            "name": "Nature-Based Finance",
            "outfile": "nature-finance.html",
            "prompt": BRIEFING_PROMPT,
            "hero_kicker": "NATURE-BASED FINANCE · INTELLIGENCE",
            "hero_title": "Nature-Based Finance Pulse",
            "hero_subtitle": "AI-synthesized analysis of capital flows, market signals, and investment gaps in nature-based finance.",
            "accent": "#0071e3",
        },
        {
            "name": "Venture Capital Trends",
            "outfile": "venture-trends.html",
            "prompt": VC_TRENDS_PROMPT,
            "hero_kicker": "VENTURE CAPITAL · INTELLIGENCE",
            "hero_title": "Venture Capital Trends",
            "hero_subtitle": "AI-synthesized analysis of capital flows, market signals, and sector heat for venture capital.",
            "accent": "#0071e3",
        },
        {
            "name": "SDG Investment Gap",
            "outfile": "sdg-gap.html",
            "prompt": SDG_GAP_PROMPT,
            "hero_kicker": "IMPACT FINANCE · INTELLIGENCE",
            "hero_title": "SDG Investment Gap",
            "hero_subtitle": "AI-synthesized analysis of SDG-aligned capital flows and the most underfunded themes for impact allocators.",
            "accent": "#EF9F27",
        },
        {
            "name": "AI & Emerging Tech Capital",
            "outfile": "ai-capital.html",
            "prompt": AI_CAPITAL_PROMPT,
            "hero_kicker": "AI & TECHNOLOGY · INTELLIGENCE",
            "hero_title": "AI & Emerging Tech Capital",
            "hero_subtitle": "AI-synthesized analysis of funding flows, regulatory signals, and investable opportunities in AI and emerging tech.",
            "accent": "#6b21a8",
        },
        {
            "name": "Impact Fund Landscape",
            "outfile": "impact-funds.html",
            "prompt": IMPACT_FUNDS_PROMPT,
            "hero_kicker": "IMPACT FUNDS · INTELLIGENCE",
            "hero_title": "Impact Fund Landscape",
            "hero_subtitle": "AI-synthesized analysis of fundraising signals, LP appetite, and manager moves across the impact fund market.",
            "accent": "#E24B4A",
        },
    ]

    client = anthropic.Anthropic(api_key=api_key)
    root = Path(__file__).resolve().parent
    pages_dir = root / "pages"

    today = date.today().isoformat()
    for i, dash in enumerate(dashboards, start=1):
        print(f"Generating dashboard {i}/5: {dash['name']}")
        user_block_1 = str(dash["prompt"]).format(date=today)

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

        parsed = extract_json_obj(raw) or {}

        sec_list = parsed.get("sections")
        if isinstance(sec_list, list):
            sections: list[dict[str, str]] = []
            for item in sec_list:
                if isinstance(item, dict) and "title" in item and "body" in item:
                    sections.append({"title": str(item["title"]), "body": str(item["body"])})
            if len(sections) != 5:
                sections = sections_fallback(raw)
        else:
            sections = sections_fallback(raw)

        metrics = parsed.get("metrics")
        if not (isinstance(metrics, list) and len(metrics) == 3):
            metrics = metrics_fallback()

        updated_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        html_out = build_html(
            hero_kicker=str(dash["hero_kicker"]),
            hero_title=str(dash["hero_title"]),
            hero_subtitle=str(dash["hero_subtitle"]),
            accent=str(dash["accent"]),
            metrics=metrics,
            sections=sections,
            updated_iso=updated_iso,
        )

        out_path = pages_dir / str(dash["outfile"])
        out_path.write_text(html_out, encoding="utf-8")

        if i < len(dashboards):
            time.sleep(2)

    print("All dashboards updated successfully")


if __name__ == "__main__":
    main()
