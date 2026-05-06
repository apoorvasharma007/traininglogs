"""Build a static HTML training dashboard from the database."""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from traininglogs.db.db import get_connection
from traininglogs.analytics.queries import (
    overview_stats,
    session_list,
    key_lift_prs,
)

REPO_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT = REPO_ROOT / "docs" / "index.html"
KEY_LIFTS_CONFIG = REPO_ROOT / "config" / "key_lifts.yaml"
GITHUB_BASE = "https://github.com/apoorvasharma007/traininglogs/blob/main"


def serial(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, date):
        return str(obj)
    raise TypeError(f"Not serialisable: {type(obj)}")


def load_key_lifts() -> list[str]:
    return yaml.safe_load(KEY_LIFTS_CONFIG.read_text())["key_lifts"]


def brief_to_html(md: str) -> str:
    md = md.strip()
    md = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", md)
    md = re.sub(r"\*(.+?)\*", r"<em>\1</em>", md)
    paragraphs = [p.strip() for p in md.split("\n\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paragraphs)


def date_to_ms(d) -> int:
    s = str(d)
    return int(datetime.strptime(s, "%Y-%m-%d").timestamp() * 1000)


def get_exercises_with_sessions(conn, min_sessions: int = 3) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.name
            FROM exercises e
            JOIN sessions s  ON s.session_id = e.session_id
            JOIN working_sets ws ON ws.exercise_id = e.id
            WHERE ws.weight_kg IS NOT NULL
            GROUP BY e.name
            HAVING COUNT(DISTINCT s.session_id) >= %s
            ORDER BY e.name ASC
            """,
            (min_sessions,),
        )
        return [row[0] for row in cur.fetchall()]


def get_all_goal_vs_actual(conn, exercise_names: list[str]) -> dict:
    if not exercise_names:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                e.name,
                s.date,
                s.phase,
                s.week,
                ws.number        AS set_number,
                ws.weight_kg     AS actual_kg,
                e.goal_weight_kg,
                e.goal_rep_min,
                e.goal_rep_max,
                ws.reps_full,
                ws.rpe
            FROM working_sets ws
            JOIN exercises e ON e.id = ws.exercise_id
            JOIN sessions  s ON s.session_id = e.session_id
            WHERE ws.weight_kg IS NOT NULL
              AND e.name = ANY(%s)
            ORDER BY e.name ASC, s.date ASC, ws.number ASC
            """,
            (exercise_names,),
        )
        cols = [d[0] for d in cur.description]
        raw: dict = {}
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            name = d.pop("name")
            raw.setdefault(name, []).append(d)

    result: dict = {}
    for name, rows in raw.items():
        sets = [
            {
                "x": date_to_ms(r["date"]),
                "y": float(r["actual_kg"]),
                "reps": r["reps_full"],
                "rpe": float(r["rpe"]) if r["rpe"] is not None else None,
                "set_n": r["set_number"],
                "date": str(r["date"]),
            }
            for r in rows
        ]
        seen_dates: set = set()
        goals = []
        for r in rows:
            if r["goal_weight_kg"] is not None and str(r["date"]) not in seen_dates:
                seen_dates.add(str(r["date"]))
                rep_min = r["goal_rep_min"]
                rep_max = r["goal_rep_max"]
                goal_reps = (rep_min + rep_max) / 2 if rep_min and rep_max else None
                goals.append({
                    "x": date_to_ms(r["date"]),
                    "goal_kg": float(r["goal_weight_kg"]),
                    "goal_reps": goal_reps,
                    "date": str(r["date"]),
                })
        result[name] = {"sets": sets, "goals": goals}

    return result


def build(conn) -> None:
    overview = overview_stats(conn)
    sessions = session_list(conn)
    key_lifts = load_key_lifts()
    prs = key_lift_prs(conn, key_lifts)
    brief_html = "<p>—</p>"

    prog_exercises = get_exercises_with_sessions(conn, min_sessions=3)
    prog_data = get_all_goal_vs_actual(conn, prog_exercises)

    data = {
        "overview": overview,
        "sessions": sessions,
        "brief_html": brief_html,
        "key_lifts": key_lifts,
        "prs": prs,
        "prog_exercises": prog_exercises,
        "prog_data": prog_data,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(data))
    print(f"Dashboard written to {OUTPUT}")


def render(data: dict) -> str:
    j = lambda d: json.dumps(d, default=serial)
    o = data["overview"] or {}
    phase = o.get("current_phase") or 0
    week = o.get("current_week") or 0
    last_date = o.get("last_session_date") or "—"
    total_sessions = o.get("total_sessions") or 0

    brief_html = data["brief_html"]

    session_opts = ""
    for s in data["sessions"]:
        src = s.get("source_file") or ""
        href = f"{GITHUB_BASE}/{src}" if src else "#"
        focus = s.get("focus") or ""
        deload = " [deload]" if s.get("is_deload_week") else ""
        label = f"{s['date']} — {focus} (P{s['phase']}·W{s['week']}){deload}"
        session_opts += f'<option value="{href}">{label}</option>\n'

    rep_brackets = [1, 3, 5, 8, 10]

    def pr_cell(rep_prs: dict, reps: int) -> str:
        p = rep_prs.get(reps)
        if not p:
            return "<td>—</td>"
        return f'<td><span class="pr-w">{p["weight_kg"]} kg</span><br><span class="pr-d">{p["date"]}</span></td>'

    pr_rows = ""
    for lift in data["key_lifts"]:
        pr = data["prs"].get(lift, {})
        rep_prs = pr.get("rep_prs", {})
        e1rm = pr.get("e1rm_kg")
        e1rm_date = pr.get("e1rm_date", "")
        e1rm_cell = (
            f'<td><span class="pr-w">{e1rm:.1f} kg</span><br><span class="pr-d">{e1rm_date}</span></td>'
            if e1rm else "<td>—</td>"
        )
        cells = "".join(pr_cell(rep_prs, r) for r in rep_brackets)
        pr_rows += f'<tr><td class="lift-name">{lift}</td>{e1rm_cell}{cells}</tr>\n'

    prog_opts = "".join(
        f'<option value="{ex}">{ex}</option>\n'
        for ex in data["prog_exercises"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Training Log — A. Sharma</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght,SOFT@0,9..144,300..900,0..100;1,9..144,300..900,0..100&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {{
  --paper: #F1E9D6;
  --paper-2: #EBE1CB;
  --ink: #1A1410;
  --muted: #8A7F6E;
  --rule: rgba(26,20,16,0.18);
  --accent: #C83C29;
  --faint: rgba(26,20,16,0.06);
  --f-display: "Fraunces", "Times New Roman", serif;
  --f-body: Georgia, "Times New Roman", serif;
  --f-mono: "JetBrains Mono", ui-monospace, monospace;
  --max-w: 1080px;
  --gap: clamp(1rem, 3vw, 2.5rem);
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: var(--paper); color: var(--ink); }}
body {{
  font-family: var(--f-body);
  font-size: 16px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}
.page {{ max-width: var(--max-w); margin: 0 auto; padding: 0 var(--gap); }}

/* Header */
.site-header {{
  padding: 2.5rem 0 2rem;
  border-bottom: 2px solid var(--ink);
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 1rem;
}}
.site-title {{
  font-family: var(--f-display);
  font-size: clamp(2rem, 6vw, 3.5rem);
  font-weight: 300;
  letter-spacing: -0.02em;
  line-height: 1;
  font-variation-settings: "opsz" 144, "SOFT" 0;
}}
.site-meta {{
  font-family: var(--f-mono);
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  text-align: right;
  line-height: 1.8;
}}
.site-meta .accent {{ color: var(--accent); }}

/* Sections */
section {{
  padding: 3rem 0;
  border-bottom: 1px solid var(--rule);
}}
section:last-of-type {{ border-bottom: none; }}
.section-title {{
  font-family: var(--f-display);
  font-size: clamp(1.4rem, 3vw, 2rem);
  font-weight: 300;
  letter-spacing: -0.01em;
  margin-bottom: 1.5rem;
  font-variation-settings: "opsz" 72, "SOFT" 20;
}}

/* Brief */
.brief {{
  font-size: 1rem;
  color: var(--ink);
  max-width: 68ch;
  margin-bottom: 2rem;
}}
.brief p + p {{ margin-top: 0.75rem; }}

/* Session picker */
.session-picker {{
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}}
.session-picker label {{
  font-family: var(--f-mono);
  font-size: 0.68rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted);
  white-space: nowrap;
}}
.session-picker select {{
  font-family: var(--f-mono);
  font-size: 0.82rem;
  background: var(--paper-2);
  border: 1px solid var(--rule);
  color: var(--ink);
  padding: 0.45rem 0.75rem;
  cursor: pointer;
  min-width: 360px;
  max-width: 100%;
}}
.session-picker select:focus {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.session-link-btn {{
  font-family: var(--f-mono);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--paper);
  background: var(--ink);
  border: none;
  padding: 0.45rem 1rem;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
  white-space: nowrap;
}}
.session-link-btn:hover {{ background: var(--accent); }}

/* PR table */
.pr-table-wrap {{ overflow-x: auto; }}
table {{
  width: 100%;
  border-collapse: collapse;
  font-family: var(--f-mono);
  font-size: 0.8rem;
}}
thead th {{
  text-align: left;
  font-size: 0.62rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
  padding: 0.6rem 0.75rem;
  border-bottom: 2px solid var(--ink);
  white-space: nowrap;
}}
tbody td {{
  padding: 0.65rem 0.75rem;
  border-bottom: 1px solid var(--rule);
  vertical-align: top;
}}
tbody tr:last-child td {{ border-bottom: none; }}
tbody tr:hover td {{ background: var(--faint); }}
.lift-name {{
  font-family: var(--f-display);
  font-style: italic;
  font-size: 0.95rem;
  font-weight: 400;
  font-variation-settings: "opsz" 48, "SOFT" 40;
  white-space: nowrap;
  min-width: 200px;
}}
.pr-w {{
  font-weight: 700;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}}
.pr-d {{
  font-size: 0.65rem;
  color: var(--muted);
}}

/* Progression chart */
.chart-controls {{
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}}
.chart-controls label {{
  font-family: var(--f-mono);
  font-size: 0.68rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted);
}}
.chart-controls select {{
  font-family: var(--f-mono);
  font-size: 0.82rem;
  background: var(--paper-2);
  border: 1px solid var(--rule);
  color: var(--ink);
  padding: 0.45rem 0.75rem;
  cursor: pointer;
  min-width: 300px;
}}
.chart-controls select:focus {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.chart-wrap {{
  background: var(--paper-2);
  border: 1px solid var(--rule);
  padding: 1.25rem;
}}
.chart-wrap canvas {{ max-height: 360px; }}
.chart-legend {{
  display: flex;
  gap: 1.5rem;
  margin-top: 1rem;
  font-family: var(--f-mono);
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}}
.legend-dot {{
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.4rem;
  vertical-align: middle;
}}
.legend-line {{
  display: inline-block;
  width: 16px;
  height: 2px;
  margin-right: 0.4rem;
  vertical-align: middle;
  position: relative;
  top: -1px;
}}
.no-goal-note {{
  font-family: var(--f-mono);
  font-size: 0.68rem;
  color: var(--muted);
  margin-top: 0.75rem;
}}

/* Footer */
footer {{
  padding: 2rem 0;
  font-family: var(--f-mono);
  font-size: 0.65rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  border-top: 2px solid var(--ink);
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}}
</style>
</head>
<body>
<div class="page">

  <header class="site-header">
    <h1 class="site-title">Training Log</h1>
    <div class="site-meta">
      <div>Phase <span class="accent">{phase}</span> · Week <span class="accent">{week}</span></div>
      <div>Last session: <span class="accent">{last_date}</span></div>
      <div>{total_sessions} sessions logged</div>
    </div>
  </header>

  <!-- § 1 — Focus -->
  <section>
    <h2 class="section-title">Current Program</h2>
    <div class="brief">{brief_html}</div>
    <div class="session-picker">
      <label for="sessionSelect">Session archive</label>
      <select id="sessionSelect">
        {session_opts}
      </select>
      <a id="sessionLink" class="session-link-btn" href="#" target="_blank" rel="noopener">Open ↗</a>
    </div>
  </section>

  <!-- § 2 — Key-lift PRs -->
  <section>
    <h2 class="section-title">Key Lift PRs</h2>
    <div class="pr-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Lift</th>
            <th>e1RM (Epley)</th>
            <th>1 rep</th>
            <th>3 reps</th>
            <th>5 reps</th>
            <th>8 reps</th>
            <th>10 reps</th>
          </tr>
        </thead>
        <tbody>
          {pr_rows}
        </tbody>
      </table>
    </div>
  </section>

  <!-- § 3 — Progression -->
  <section>
    <h2 class="section-title">Strength Progression</h2>
    <div class="chart-controls">
      <label for="progSelect">Exercise</label>
      <select id="progSelect">
        {prog_opts}
      </select>
    </div>
    <div class="chart-wrap">
      <canvas id="progChart"></canvas>
    </div>
    <div class="chart-legend">
      <span><span class="legend-dot" style="background:var(--ink);opacity:0.45;"></span>All sets (e1RM)</span>
      <span><span class="legend-line" style="background:var(--ink);"></span>Best e1RM / session</span>
      <span><span class="legend-line" style="background:var(--accent);border-top:2px dashed var(--accent);background:transparent;"></span>Goal weight (reference)</span>
    </div>
    <p style="font-family:var(--f-mono);font-size:0.65rem;color:var(--muted);margin-top:0.5rem;">
      Y-axis: estimated 1-rep max via Epley formula (weight &times; (1 + reps/30)).
      Goal line uses the programmed rep target (midpoint of goal rep range) to convert goal weight to e1RM.
    </p>
    <div class="no-goal-note" id="noGoalNote" style="display:none;">
      No goal weights recorded for this exercise.
    </div>
  </section>

  <footer>
    <span>A. Sharma</span>
    <span>Built from Postgres · {total_sessions} sessions</span>
    <span>{last_date}</span>
  </footer>

</div>

<script>
const PROG_DATA = {j(data['prog_data'])};

const C = {{
  ink: "#1A1410",
  accent: "#C83C29",
  muted: "#8A7F6E",
  paper: "#F1E9D6",
  paper2: "#EBE1CB",
  faint: "rgba(26,20,16,0.07)",
}};

Chart.defaults.font.family = "'JetBrains Mono', ui-monospace, monospace";
Chart.defaults.font.size = 10;
Chart.defaults.color = C.muted;
Chart.defaults.plugins.tooltip.backgroundColor = C.ink;
Chart.defaults.plugins.tooltip.titleFont = {{ family: "'JetBrains Mono'", size: 10 }};
Chart.defaults.plugins.tooltip.bodyFont  = {{ family: "'JetBrains Mono'", size: 10 }};
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 0;
Chart.defaults.plugins.tooltip.borderColor = C.accent;
Chart.defaults.plugins.tooltip.borderWidth = 1;

// Session picker
(function() {{
  const sel = document.getElementById("sessionSelect");
  const btn = document.getElementById("sessionLink");
  function update() {{
    const href = sel.value;
    btn.href = href && href !== "#" ? href : "#";
    btn.style.opacity = href && href !== "#" ? "1" : "0.4";
  }}
  sel.addEventListener("change", update);
  update();
}})();

// Progression chart
(function() {{
  const sel = document.getElementById("progSelect");
  let chart = null;

  function fmtDate(ms) {{
    return new Date(ms).toLocaleDateString("en-US", {{ month: "short", day: "numeric", year: "2-digit" }});
  }}

  function epley(weight, reps) {{
    if (!reps || reps < 1) return weight;
    return weight * (1 + reps / 30);
  }}

  function draw(exName) {{
    const ex = PROG_DATA[exName];
    if (!ex) return;

    const hasGoals = ex.goals && ex.goals.length > 0;
    document.getElementById("noGoalNote").style.display = hasGoals ? "none" : "block";

    const e1rmSets = ex.sets.map(s => ({{
      x: s.x,
      y: Math.round(epley(s.y, s.reps) * 10) / 10,
      actual_kg: s.y,
      reps: s.reps,
      rpe: s.rpe,
      set_n: s.set_n,
      date: s.date,
    }}));

    const topByDate = {{}};
    e1rmSets.forEach(s => {{
      if (topByDate[s.x] == null || s.y > topByDate[s.x]) topByDate[s.x] = s.y;
    }});
    const topLine = Object.entries(topByDate)
      .sort((a, b) => Number(a[0]) - Number(b[0]))
      .map(([x, y]) => ({{ x: Number(x), y }}));

    const e1rmGoals = ex.goals.map(g => {{
      const reps = g.goal_reps || 5;
      return {{
        x: g.x,
        y: Math.round(epley(g.goal_kg, reps) * 10) / 10,
        raw_goal: g.goal_kg,
        goal_reps: g.goal_reps,
      }};
    }});

    const datasets = [
      {{
        label: "All sets",
        type: "scatter",
        data: e1rmSets,
        backgroundColor: "rgba(26,20,16,0.35)",
        pointRadius: 4,
        pointHoverRadius: 6,
        order: 3,
      }},
      {{
        label: "Best e1RM",
        type: "line",
        data: topLine,
        borderColor: C.ink,
        backgroundColor: "transparent",
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 0,
        tension: 0,
        order: 2,
      }},
      {{
        label: "Goal",
        type: "line",
        data: e1rmGoals,
        borderColor: C.accent,
        borderDash: [6, 4],
        backgroundColor: "transparent",
        borderWidth: 2,
        pointRadius: 4,
        pointBackgroundColor: C.accent,
        pointBorderColor: C.paper,
        pointBorderWidth: 1.5,
        tension: 0,
        order: 1,
      }},
    ];

    if (chart) chart.destroy();
    chart = new Chart(document.getElementById("progChart"), {{
      type: "scatter",
      data: {{ datasets }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            callbacks: {{
              title: items => fmtDate(items[0].parsed.x),
              label: item => {{
                const d = item.raw;
                if (item.dataset.label === "Goal") return `Goal e1RM: ${{d.y}} kg  (${{d.raw_goal}} kg × ${{d.goal_reps}} reps programmed)`;
                if (item.dataset.label === "Best e1RM") return `Best e1RM: ${{d.y}} kg`;
                const parts = [`e1RM: ${{d.y}} kg  (${{d.actual_kg}} kg × ${{d.reps || "?"}} reps)`];
                if (d.rpe != null) parts.push(`RPE ${{d.rpe}}`);
                return parts;
              }},
            }},
          }},
        }},
        scales: {{
          x: {{
            type: "linear",
            grid: {{ color: C.faint }},
            ticks: {{
              callback: v => fmtDate(v),
              maxRotation: 35,
              autoSkip: true,
              maxTicksLimit: 12,
            }},
          }},
          y: {{
            title: {{
              display: true,
              text: "Estimated 1RM (kg)",
              color: C.muted,
              font: {{ family: "'JetBrains Mono'", size: 9 }},
              padding: {{ bottom: 6 }},
            }},
            grid: {{ color: C.faint }},
            ticks: {{ callback: v => v + " kg" }},
          }},
        }},
      }},
    }});
  }}

  sel.addEventListener("change", e => draw(e.target.value));
  if (sel.options.length) draw(sel.value);
}})();
</script>
</body>
</html>"""


def main() -> None:
    conn = get_connection()
    build(conn)
    conn.close()


if __name__ == "__main__":
    main()
