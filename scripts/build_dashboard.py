"""
Build a static HTML training dashboard from the database.
Run: python scripts/build_dashboard.py
Output: docs/index.html
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traininglogs.db.db import get_connection
from traininglogs.analytics.queries import (
    personal_records,
    overview_stats,
    exercise_list,
    exercise_sets_trend,
    goal_vs_actual,
    weekly_tonnage_by_phase,
    session_list,
)

OUTPUT = Path(__file__).parent.parent / "docs" / "index.html"
PROGRAMS_DIR = Path(__file__).parent.parent / "inputs" / "programs"

GITHUB_REPO = "apoorvasharma007/traininglogs"
GITHUB_BRANCH = "main"

HIGHLIGHT_EXERCISES = {
    "Barbell Bench Press", "Barbell Back Squat", "Barbell Romanian Deadlift",
    "Hack Squat", "Leg Press", "Lean Back Lat Pulldown", "Neutral Grip Lat Pulldown",
    "Wide Grip Lat Pulldown", "Chest Supported Machine Row", "Deficit Pendlay Row",
    "Incline DB Press 45 Degree", "DB Bulgarian Split Squat", "Seated Leg Curl",
    "Leg Extension",
}

FOCUS_SHORT = {
    "Legs Hypertrophy": "Legs",
    "Push Hypertrophy": "Push",
    "Pull Hypertrophy": "Pull",
    "Upper Strength": "Upper",
    "Lower Strength": "Lower",
}

FOCUS_COLOR = {
    "Legs Hypertrophy": "#dc2626",
    "Push Hypertrophy": "#2563eb",
    "Pull Hypertrophy": "#16a34a",
    "Upper Strength": "#9333ea",
    "Lower Strength": "#d97706",
}


import re as _re


def parse_programs() -> list[dict]:
    """Scan inputs/programs/*/program.md, extract alias from YAML frontmatter."""
    programs = []
    for prog_md in sorted(PROGRAMS_DIR.glob("*/program.md")):
        slug = prog_md.parent.name
        text = prog_md.read_text()
        alias = None
        if text.startswith("---"):
            m = _re.search(r"^alias:\s*(.+)$", text, _re.MULTILINE)
            if m:
                alias = m.group(1).strip()
        if not alias:
            alias = slug.replace("_", " ").title()
        programs.append({
            "alias": alias,
            "slug": slug,
            "github_url": f"https://github.com/{GITHUB_REPO}/blob/{GITHUB_BRANCH}/inputs/programs/{slug}/program.md",
        })
    return programs


def serial(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, date):
        return str(obj)
    raise TypeError(f"Not serialisable: {type(obj)}")


def github_url(source_file: str) -> str:
    return f"https://github.com/{GITHUB_REPO}/blob/{GITHUB_BRANCH}/{source_file}"


def build_timeline(sessions: list[dict]) -> dict:
    """Group sessions by year → ISO week for the timeline."""
    by_year: dict[int, dict[int, list[dict]]] = {}
    for s in sessions:
        d = s["date"] if isinstance(s["date"], date) else date.fromisoformat(str(s["date"]))
        iso = d.isocalendar()
        year = d.year
        week_num = iso[1]
        month_name = d.strftime("%b")
        by_year.setdefault(year, {})
        by_year[year].setdefault(week_num, {
            "week_num": week_num,
            "month": month_name,
            "sessions": [],
        })
        by_year[year][week_num]["sessions"].append({
            "date": str(d),
            "date_display": d.strftime("%-d %b"),
            "focus": s.get("focus") or "—",
            "focus_short": FOCUS_SHORT.get(s.get("focus") or "", s.get("focus") or "—"),
            "focus_color": FOCUS_COLOR.get(s.get("focus") or "", "#6b7280"),
            "phase": s.get("phase"),
            "week": s.get("week"),
            "is_deload": bool(s.get("is_deload_week")),
            "github_url": github_url(s["source_file"]) if s.get("source_file") else None,
        })

    result = {}
    for year in sorted(by_year.keys(), reverse=True):
        weeks = sorted(by_year[year].values(), key=lambda w: w["week_num"], reverse=True)
        result[year] = weeks
    return result


def build(conn) -> None:
    overview = overview_stats(conn)
    load_data = weekly_tonnage_by_phase(conn)

    lifts = exercise_list(conn, min_sets=12)
    sets_by_ex: dict[str, list[dict]] = {
        row["exercise"]: exercise_sets_trend(conn, row["exercise"]) for row in lifts
    }
    goal_by_ex: dict[str, list[dict]] = {
        row["exercise"]: goal_vs_actual(conn, row["exercise"]) for row in lifts
    }

    prs_all = personal_records(conn)
    prs = sorted([r for r in prs_all if r["exercise"] in HIGHLIGHT_EXERCISES],
                 key=lambda r: r["exercise"])

    sessions = session_list(conn)
    timeline = build_timeline(sessions)

    last = sessions[0] if sessions else None
    last_session = None
    if last:
        d = last["date"] if isinstance(last["date"], date) else date.fromisoformat(str(last["date"]))
        last_session = {
            "date_display": d.strftime("%-d %b %Y"),
            "focus": last.get("focus") or "—",
            "phase": last.get("phase"),
            "week": last.get("week"),
            "github_url": github_url(last["source_file"]) if last.get("source_file") else None,
        }

    programs_list = parse_programs()
    current_plan_alias = "—"
    if last and last.get("source_file"):
        parts = Path(last["source_file"]).parts
        if len(parts) >= 3 and parts[0] == "inputs" and parts[1] == "programs":
            slug = parts[2]
            for p in programs_list:
                if p["slug"] == slug:
                    current_plan_alias = p["alias"]
                    break

    data = {
        "overview":           overview,
        "weekly_load":        load_data,
        "exercise_list":      lifts,
        "sets_by_ex":         sets_by_ex,
        "goal_by_ex":         goal_by_ex,
        "prs":                prs,
        "pr_count":           len(prs),
        "timeline":           timeline,
        "last_session":       last_session,
        "programs":           programs_list,
        "current_plan_alias": current_plan_alias,
    }

    OUTPUT.write_text(render(data))
    print(f"Dashboard written to {OUTPUT}")


def render(data: dict) -> str:
    j = lambda d: json.dumps(d, default=serial)
    o = data["overview"] or {}
    total_sessions = o.get("total_sessions") or 0
    current_phase = o.get("current_phase")
    ls = data["last_session"] or {}
    programs = data["programs"]
    current_plan_alias = data.get("current_plan_alias", "—")
    programs_html = "".join(
        f'<a href="{p["github_url"]}" target="_blank" rel="noopener" class="program-link-wrap">'
        f'{p["alias"]} <span class="arrow">↗</span></a>'
        for p in programs
    )

    # Last session banner
    if ls:
        phase_week = f"Phase {ls['phase']} · Week {ls['week']}" if ls.get("phase") else ""
        parts = [ls["focus"]]
        if phase_week:
            parts.append(phase_week)
        parts.append(ls["date_display"])
        banner_text = " · ".join(parts)
        if ls.get("github_url"):
            banner_inner = f'<a href="{ls["github_url"]}" target="_blank" rel="noopener" class="last-session-link">{banner_text} <span class="arrow">↗</span></a>'
        else:
            banner_inner = banner_text
    else:
        banner_inner = "No sessions logged yet."

    # Timeline HTML
    timeline = data["timeline"]
    years = sorted(timeline.keys(), reverse=True)
    timeline_html = ""
    if years:
        year_tabs = "".join(
            f'<button class="year-tab{" active" if i == 0 else ""}" data-year="{y}">{y}</button>'
            for i, y in enumerate(years)
        )
        timeline_html = f'<div class="year-tabs">{year_tabs}</div>\n'
        for i, year in enumerate(years):
            hidden = "" if i == 0 else ' hidden'
            timeline_html += f'<div class="year-panel" data-year="{year}"{hidden}>\n'
            timeline_html += '  <div class="timeline-rows">\n'
            for week in timeline[year]:
                wn = week["week_num"]
                mo = week["month"]
                chips = ""
                for s in sorted(week["sessions"], key=lambda x: x["date"]):
                    color = s["focus_color"]
                    label = s["focus_short"]
                    date_str = s["date_display"]
                    deload_cls = " deload" if s["is_deload"] else ""
                    if s.get("github_url"):
                        chips += (
                            f'<a href="{s["github_url"]}" target="_blank" rel="noopener" '
                            f'class="session-chip{deload_cls}" style="--chip-color:{color};" '
                            f'title="{s["focus"]} · {date_str}">'
                            f'<span class="chip-label">{label}</span>'
                            f'<span class="chip-date">{date_str}</span>'
                            f'</a>'
                        )
                    else:
                        chips += (
                            f'<span class="session-chip{deload_cls}" style="--chip-color:{color};">'
                            f'<span class="chip-label">{label}</span>'
                            f'<span class="chip-date">{date_str}</span>'
                            f'</span>'
                        )
                timeline_html += (
                    f'    <div class="timeline-row">'
                    f'<span class="week-label">W{wn} <span class="week-month">{mo}</span></span>'
                    f'<span class="week-chips">{chips}</span>'
                    f'</div>\n'
                )
            timeline_html += '  </div>\n</div>\n'

    phase_display = f"Phase {current_phase}" if current_phase else "—"
    last_date_display = ls.get("date_display", "—") if ls else "—"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Training Log — Apoorva Sharma</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {{
  --bg: #ffffff;
  --bg-2: #f9fafb;
  --bg-3: #f3f4f6;
  --ink: #111827;
  --ink-2: #374151;
  --muted: #6b7280;
  --border: #e5e7eb;
  --border-strong: #d1d5db;
  --red: #dc2626;
  --red-light: #fef2f2;
  --red-mid: #fee2e2;
  --f-sans: "Inter", system-ui, sans-serif;
  --f-mono: "JetBrains Mono", ui-monospace, monospace;
  --max-w: 1100px;
  --gap: clamp(1rem, 3vw, 2rem);
  --radius: 6px;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: var(--bg); color: var(--ink); }}
body {{
  font-family: var(--f-sans);
  font-size: 15px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: inherit; text-decoration: none; }}
.page {{ max-width: var(--max-w); margin: 0 auto; padding: 0 var(--gap); }}

/* Header */
.site-header {{
  padding: 2.5rem 0 1.75rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 1rem;
}}
.site-title {{
  font-size: clamp(1.5rem, 4vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--ink);
}}
.site-title span {{ color: var(--red); }}
.site-name {{
  font-family: var(--f-mono);
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--muted);
}}

/* Last session banner */
.last-session-banner {{
  padding: 1.25rem 1.5rem;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin: 2.5rem 0;
  font-size: 0.92rem;
  font-family: var(--f-mono);
  color: var(--ink-2);
  letter-spacing: 0.02em;
  display: flex;
  align-items: center;
  gap: 1.25rem;
}}
.last-session-banner .label {{
  text-transform: uppercase;
  font-size: 0.6rem;
  letter-spacing: 0.14em;
  color: var(--muted);
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
}}
.last-session-link {{
  color: var(--ink);
  font-weight: 500;
  transition: color 0.15s;
}}
.last-session-link:hover {{ color: var(--red); }}
.last-session-link .arrow {{ color: var(--red); margin-left: 0.2em; }}

/* Sections */
section {{
  padding: 3rem 0;
  border-bottom: 1px solid var(--border);
}}
section:last-of-type {{ border-bottom: none; }}
.section-head {{
  display: flex;
  align-items: baseline;
  gap: 1rem;
  margin-bottom: 1.75rem;
  flex-wrap: wrap;
}}
.section-head h2 {{
  font-size: clamp(1.15rem, 2.5vw, 1.5rem);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--ink);
}}
.section-dek {{
  font-family: var(--f-mono);
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-left: auto;
}}
.section-note {{
  font-size: 0.85rem;
  color: var(--muted);
  max-width: 72ch;
  margin-bottom: 1.5rem;
  line-height: 1.7;
}}

/* Hero stats */
.hero-stats {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}}
.hero-stat {{
  background: var(--bg);
  padding: 1.5rem 1.25rem;
}}
.hero-stat:first-child {{ background: var(--red-light); }}
.hero-label {{
  font-family: var(--f-mono);
  font-size: 0.62rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.6rem;
}}
.hero-value {{
  font-size: clamp(1.1rem, 2.2vw, 1.5rem);
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}}
.hero-stat:first-child .hero-value {{ color: var(--red); }}
.hero-unit {{
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 0.3rem;
}}
@media(max-width:700px) {{
  .hero-stats {{ grid-template-columns: 1fr 1fr; }}
}}

/* Timeline */
.year-tabs {{
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}}
.year-tab {{
  font-family: var(--f-mono);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  padding: 0.35rem 0.9rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s;
}}
.year-tab.active, .year-tab:hover {{
  background: var(--red);
  color: #fff;
  border-color: var(--red);
}}
.timeline-rows {{
  display: flex;
  flex-direction: column;
  gap: 2px;
}}
.timeline-row {{
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius);
  background: var(--bg);
  transition: background 0.1s;
}}
.timeline-row:hover {{ background: var(--bg-2); }}
.week-label {{
  font-family: var(--f-mono);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--ink-2);
  min-width: 5rem;
  white-space: nowrap;
  letter-spacing: 0.02em;
}}
.week-month {{
  color: var(--muted);
  font-weight: 400;
}}
.week-chips {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}}
.session-chip {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.6rem;
  border-radius: 4px;
  background: color-mix(in srgb, var(--chip-color) 10%, white);
  border: 1px solid color-mix(in srgb, var(--chip-color) 25%, white);
  font-size: 0.72rem;
  font-family: var(--f-mono);
  font-weight: 500;
  color: var(--chip-color);
  transition: all 0.15s;
  white-space: nowrap;
}}
a.session-chip:hover {{
  background: color-mix(in srgb, var(--chip-color) 18%, white);
  border-color: var(--chip-color);
}}
.session-chip.deload {{
  opacity: 0.65;
}}
.chip-label {{ font-weight: 600; }}
.chip-date {{
  font-size: 0.65rem;
  font-weight: 400;
  opacity: 0.8;
}}

/* Charts */
.fig {{
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
}}
.fig canvas {{ max-height: 300px; }}
.fig-caption {{
  font-family: var(--f-mono);
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  color: var(--muted);
  text-transform: uppercase;
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}}

/* Lift selector */
.lift-control {{
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}}
.lift-control label {{
  font-family: var(--f-mono);
  font-size: 0.65rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  white-space: nowrap;
}}
#exerciseSelect {{
  font-family: var(--f-sans);
  font-size: 0.9rem;
  font-weight: 500;
  background: var(--bg);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  color: var(--ink);
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  flex: 1;
  min-width: 220px;
}}
#exerciseSelect:focus {{ outline: 2px solid var(--red); outline-offset: 1px; }}

/* Lift grid */
.lift-grid {{ display: grid; grid-template-columns: 2.2fr 1fr; gap: 1.25rem; }}
@media(max-width:700px) {{ .lift-grid {{ grid-template-columns: 1fr; }} }}
.lift-stats {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}}
.mini-stat {{ background: var(--bg); padding: 1rem 0.9rem; }}
.mini-label {{
  font-family: var(--f-mono);
  font-size: 0.6rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.4rem;
}}
.mini-value {{
  font-size: 1.4rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}}
.mini-value .u {{ font-size: 0.7rem; font-weight: 400; color: var(--muted); margin-left: 0.15rem; }}

/* Tables */
table {{ width: 100%; border-collapse: collapse; font-family: var(--f-mono); font-size: 0.82rem; }}
thead th {{
  text-align: left;
  font-size: 0.6rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
  padding: 0.6rem 0.65rem;
  border-bottom: 2px solid var(--border-strong);
  white-space: nowrap;
}}
tbody td {{
  padding: 0.6rem 0.65rem;
  border-bottom: 1px solid var(--border);
  font-variant-numeric: tabular-nums;
}}
tbody tr:last-child td {{ border-bottom: none; }}
tbody tr:hover td {{ background: var(--bg-2); }}
.pr-table .ex-name {{ font-family: var(--f-sans); font-weight: 600; font-size: 0.88rem; }}
.pr-table .wt {{ color: var(--red); font-weight: 700; }}
.pr-table .date-cell {{ color: var(--muted); }}

/* Program link */
.program-link-wrap {{
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  font-family: var(--f-mono);
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--ink-2);
  background: var(--bg-2);
  transition: all 0.15s;
  margin-top: 0.5rem;
}}
.program-link-wrap:hover {{
  border-color: var(--red);
  color: var(--red);
  background: var(--red-light);
}}
.program-link-wrap .arrow {{ color: var(--red); }}

/* Footer */
.site-footer {{
  padding: 2rem 0;
  border-top: 1px solid var(--border);
  margin-top: 2rem;
  font-family: var(--f-mono);
  font-size: 0.65rem;
  letter-spacing: 0.06em;
  color: var(--muted);
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}}
</style>
</head>
<body>
<main class="page">

  <header class="site-header">
    <div class="site-title">Training <span>Log</span></div>
    <div class="site-name">Apoorva Sharma</div>
  </header>

  <div class="last-session-banner">
    <span class="label">Last session</span>
    {banner_inner}
  </div>

  <section>
    <div class="section-head">
      <h2>Overview</h2>
      <div class="section-dek">Cumulative</div>
    </div>
    <div class="hero-stats">
      <div class="hero-stat">
        <div class="hero-label">Total sessions</div>
        <div class="hero-value">{total_sessions}</div>
        <div class="hero-unit">logged</div>
      </div>
      <div class="hero-stat">
        <div class="hero-label">Current plan</div>
        <div class="hero-value">{current_plan_alias}</div>
        <div class="hero-unit">&nbsp;</div>
      </div>
      <div class="hero-stat">
        <div class="hero-label">Current phase</div>
        <div class="hero-value">{phase_display}</div>
        <div class="hero-unit">&nbsp;</div>
      </div>
      <div class="hero-stat">
        <div class="hero-label">Last session</div>
        <div class="hero-value">{last_date_display}</div>
        <div class="hero-unit">&nbsp;</div>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Session Timeline</h2>
      <div class="section-dek">By calendar week</div>
    </div>
    {timeline_html if timeline_html else '<p class="section-note">No sessions logged yet.</p>'}
  </section>

  <section>
    <div class="section-head">
      <h2>Weekly Load</h2>
      <div class="section-dek">Volume</div>
    </div>
    <p class="section-note">Total weight moved per week. Deload weeks shown in red. A well-shaped mesocycle accumulates then drops — the dip is intentional.</p>
    <div class="fig">
      <canvas id="loadChart"></canvas>
      <div class="fig-caption">
        <span>Load per week by phase</span>
        <span>Deload weeks in red</span>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Strength Progression</h2>
      <div class="section-dek">Top weight per day</div>
    </div>
    <p class="section-note">Top working weight per day. Red line shows the goal weight logged for that session.</p>
    <div class="lift-control">
      <label for="exerciseSelect">Exercise</label>
      <select id="exerciseSelect"></select>
    </div>
    <div class="lift-grid">
      <div class="fig">
        <canvas id="e1rmChart"></canvas>
        <div class="fig-caption">
          <span>Actual weight (black) · Goal weight (red)</span>
          <span id="liftRange">—</span>
        </div>
      </div>
      <div class="lift-stats">
        <div class="mini-stat"><div class="mini-label">Latest top set</div><div class="mini-value" id="latestTop">—</div></div>
        <div class="mini-stat"><div class="mini-label">Sets logged</div><div class="mini-value" id="setCount">—</div></div>
        <div class="mini-stat"><div class="mini-label">Avg RPE</div><div class="mini-value" id="recentRpe">—</div></div>
        <div class="mini-stat"><div class="mini-label">Note</div><div class="mini-value" id="topNote" style="font-size:1rem;font-family:var(--f-sans);font-weight:400;color:var(--ink-2);">—</div></div>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Personal Bests</h2>
      <div class="section-dek">Heaviest set on record</div>
    </div>
    <div class="fig">
      <table class="pr-table">
        <thead><tr><th>Exercise</th><th>Weight</th><th>Reps</th><th>Date</th></tr></thead>
        <tbody id="prBody"></tbody>
      </table>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Program</h2>
      <div class="section-dek">Training plans</div>
    </div>
    {programs_html if programs_html else '<p class="section-note">No programs found.</p>'}
  </section>

  <footer class="site-footer">
    <span>Training Log — Apoorva Sharma</span>
    <span>Built from {total_sessions} sessions · Supabase + static HTML</span>
  </footer>

</main>

<script>
const WEEKLY_LOAD      = {j(data['weekly_load'])};
const EXERCISE_LIST    = {j(data['exercise_list'])};
const SETS_BY_EXERCISE = {j(data['sets_by_ex'])};
const GOAL_BY_EXERCISE = {j(data['goal_by_ex'])};
const PRS              = {j(data['prs'])};

const C = {{
  ink: "#111827",
  muted: "#6b7280",
  border: "#e5e7eb",
  bg2: "#f9fafb",
  red: "#dc2626",
  redFaint: "rgba(220,38,38,0.08)",
}};

Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.color = C.muted;
Chart.defaults.borderColor = C.border;
Chart.defaults.plugins.tooltip.backgroundColor = C.ink;
Chart.defaults.plugins.tooltip.titleFont = {{ family: "'JetBrains Mono'", size: 10 }};
Chart.defaults.plugins.tooltip.bodyFont  = {{ family: "'JetBrains Mono'", size: 11 }};
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 4;

const fmtInt = n => n == null ? "—" : Number(n).toLocaleString();
const fmt1   = n => n == null ? "—" : Number(n).toFixed(1);

// Year toggle
document.querySelectorAll(".year-tab").forEach(btn => {{
  btn.addEventListener("click", () => {{
    const year = btn.dataset.year;
    document.querySelectorAll(".year-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".year-panel").forEach(p => {{
      p.hidden = p.dataset.year !== year;
    }});
  }});
}});

(function renderLoad() {{
  if (!WEEKLY_LOAD.length) return;
  const labels = WEEKLY_LOAD.map(r => `P${{r.phase}}·W${{r.week}}`);
  const data   = WEEKLY_LOAD.map(r => r.tonnage_kg);
  const colors = WEEKLY_LOAD.map(r => r.is_deload_week ? C.red : C.ink);
  new Chart(document.getElementById("loadChart"), {{
    type: "bar",
    data: {{ labels, datasets: [{{ data, backgroundColor: colors, borderWidth: 0, borderRadius: 2, barPercentage: 0.75 }}] }},
    options: {{
      plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{
        label: ctx => `${{fmtInt(ctx.parsed.y)}} kg${{WEEKLY_LOAD[ctx.dataIndex].is_deload_week ? " · DELOAD" : ""}}`
      }} }} }},
      scales: {{
        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 9 }}, maxRotation: 0, autoSkip: false }} }},
        y: {{ beginAtZero: true, grid: {{ color: C.border }},
              ticks: {{ callback: v => (v/1000).toFixed(0) + "k", font: {{ size: 9 }} }} }}
      }}
    }}
  }});
}})();

(function renderLift() {{
  const sel = document.getElementById("exerciseSelect");
  EXERCISE_LIST.forEach(ex => {{
    const opt = document.createElement("option");
    opt.value = ex.exercise; opt.textContent = ex.exercise;
    sel.appendChild(opt);
  }});
  let chart;
  function draw(exName) {{
    const rows = (SETS_BY_EXERCISE[exName] || []).map(r => ({{ ...r, weight_kg: r.weight_kg == null ? null : Number(r.weight_kg) }}));

    // Detect bodyweight exercise (all sets have null weight_kg)
    const isBW = rows.every(r => r.weight_kg == null);

    // Top set per day: highest weight_kg (or reps_full for bodyweight)
    const byDate = {{}};
    rows.forEach(r => {{
      const val = isBW ? r.reps_full : r.weight_kg;
      if (val == null) return;
      const prev = byDate[r.date];
      if (!prev || val > (isBW ? prev.reps_full : prev.weight_kg)) byDate[r.date] = r;
    }});
    const top = Object.values(byDate).sort((a,b) => a.date.localeCompare(b.date));
    const labels = top.map(r => String(r.date).slice(5));
    const values = top.map(r => isBW ? r.reps_full : r.weight_kg);
    const pointColors = top.map(r => r.is_deload_week ? C.red : C.ink);

    // Goal weight: one per session date, null where not set
    const goalRows = (GOAL_BY_EXERCISE[exName] || []);
    const goalByDate = {{}};
    goalRows.forEach(r => {{ if (r.goal_weight_kg != null) goalByDate[r.date] = Number(r.goal_weight_kg); }});
    const goalData = top.map(r => goalByDate[r.date] ?? null);
    const hasGoal = goalData.some(v => v != null);

    // Side stats
    const latest = top[top.length - 1] || {{}};
    const rpeRows = rows.filter(r => r.rpe);
    const avgRpe = rpeRows.length ? rpeRows.reduce((s,r) => s + Number(r.rpe), 0) / rpeRows.length : null;
    const topNote = latest.notes || "";

    document.getElementById("latestTop").innerHTML = isBW
      ? (latest.reps_full ? `BW <span class="u">×${{latest.reps_full}}</span>` : "—")
      : (latest.weight_kg ? `${{latest.weight_kg}} <span class="u">×${{latest.reps_full}}</span>` : "—");
    document.getElementById("setCount").textContent  = fmtInt(rows.length);
    document.getElementById("recentRpe").textContent = rows.filter(r=>r.rpe).length ? fmt1(avgRpe) : "—";
    document.getElementById("topNote").textContent   = topNote || "💪";
    document.getElementById("liftRange").textContent = labels.length ? `${{top[0].date}} — ${{top[top.length-1].date}}` : "—";

    if (chart) chart.destroy();
    const datasets = [
      {{
        label: "Weight",
        data: values, borderColor: C.ink,
        backgroundColor: C.redFaint,
        borderWidth: 2, pointRadius: 4,
        pointBackgroundColor: pointColors, pointBorderColor: "#fff", pointBorderWidth: 1.5,
        tension: 0.25, fill: true,
      }},
    ];
    if (hasGoal) datasets.push({{
      label: "Goal",
      data: goalData, borderColor: "rgba(220,38,38,0.45)",
      borderWidth: 1.5, borderDash: [6, 4],
      pointRadius: goalData.map(v => v != null ? 3 : 0),
      pointBackgroundColor: "rgba(220,38,38,0.45)", pointBorderColor: "#fff", pointBorderWidth: 1,
      tension: 0.25, fill: false, spanGaps: false,
    }});
    const unit = isBW ? "reps" : "kg";
    chart = new Chart(document.getElementById("e1rmChart"), {{
      type: "line",
      data: {{ labels, datasets }},
      options: {{
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ callbacks: {{
            label: ctx => {{
              if (ctx.datasetIndex === 1) return `Goal: ${{ctx.parsed.y}} ${{unit}}`;
              const r = top[ctx.dataIndex];
              return isBW
                ? `BW × ${{r.reps_full}}${{r.is_deload_week ? " · DELOAD" : ""}}`
                : `${{r.weight_kg}} kg × ${{r.reps_full}}${{r.is_deload_week ? " · DELOAD" : ""}}`;
            }}
          }} }}
        }},
        scales: {{
          x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 9 }} }} }},
          y: {{ beginAtZero: false, grid: {{ color: C.border }}, ticks: {{ callback: v => v + " " + unit, font: {{ size: 9 }} }} }}
        }}
      }}
    }});
  }}
  sel.addEventListener("change", e => draw(e.target.value));
  if (EXERCISE_LIST.length) {{ sel.value = EXERCISE_LIST[0].exercise; draw(EXERCISE_LIST[0].exercise); }}
}})();

(function renderPRs() {{
  const body = document.getElementById("prBody");
  if (!PRS.length) {{ body.innerHTML = `<tr><td colspan="4" style="color:var(--muted)">No PRs yet.</td></tr>`; return; }}
  body.innerHTML = PRS.map(r => `
    <tr>
      <td class="ex-name">${{r.exercise}}</td>
      <td class="wt">${{r.weight_kg > 0 ? r.weight_kg + " kg" : "BW"}}</td>
      <td>${{r.reps_full}}</td>
      <td class="date-cell">${{r.date}}</td>
    </tr>`).join("");
}})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    conn = get_connection()
    build(conn)
    conn.close()
