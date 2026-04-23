"""
Build a static HTML training dashboard from the database.
Run: python scripts/build_dashboard.py
Output: dashboard/index.html
"""
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traininglogs.db.db import get_connection
from traininglogs.analytics.queries import (
    personal_records,
    volume_by_session,
    rpe_trend,
    failure_technique_usage,
    sessions_per_week,
    custom_query,
)

OUTPUT = Path(__file__).parent.parent / "dashboard" / "index.html"

HIGHLIGHT_EXERCISES = {
    "Barbell Bench Press",
    "Barbell Back Squat",
    "Barbell Romanian Deadlift",
    "Hack Squat",
    "Leg Press",
    "Lean Back Lat Pulldown",
    "Neutral Grip Lat Pulldown",
    "Wide Grip Lat Pulldown",
    "Chest Supported Machine Row",
    "Deficit Pendlay Row",
    "Incline DB Press 45 Degree",
    "DB Bulgarian Split Squat",
    "Seated Leg Curl",
    "Leg Extension",
}


def serial(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, date):
        return str(obj)
    raise TypeError(f"Not serialisable: {type(obj)}")


def build(conn):
    prs_all = personal_records(conn)
    prs = [r for r in prs_all if r["exercise"] in HIGHLIGHT_EXERCISES]
    prs.sort(key=lambda r: r["exercise"])

    volume = volume_by_session(conn)
    rpe = rpe_trend(conn)
    techniques = failure_technique_usage(conn)
    consistency = sessions_per_week(conn)

    overview = custom_query(conn, """
        SELECT
            (SELECT COUNT(*) FROM sessions) AS total_sessions,
            (SELECT COUNT(*) FROM working_sets) AS total_sets,
            (SELECT MAX(phase) FROM sessions) AS current_phase,
            (SELECT week FROM sessions ORDER BY date DESC LIMIT 1) AS current_week,
            (SELECT date FROM sessions ORDER BY date DESC LIMIT 1) AS last_session
    """)[0]

    data = {
        "overview": overview,
        "prs": prs,
        "volume": volume,
        "rpe": rpe,
        "techniques": techniques,
        "consistency": consistency,
    }

    html = render(data)
    OUTPUT.write_text(html)
    print(f"Dashboard written to {OUTPUT}")


def render(data: dict) -> str:
    j = lambda d: json.dumps(d, default=serial)
    o = data["overview"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Training Dashboard — Apoorva Sharma</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f0f0f;
    --surface: #1a1a1a;
    --border: #2a2a2a;
    --accent: #e8ff00;
    --text: #f0f0f0;
    --muted: #888;
    --red: #ff4444;
    --green: #44ff88;
    --blue: #44aaff;
    --orange: #ff8844;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; padding: 2rem; }}
  h1 {{ font-size: 1.4rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); margin-bottom: 0.25rem; }}
  .subtitle {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 2.5rem; }}
  .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
  .grid-3 {{ display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; }}
  .stat-label {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 0.4rem; }}
  .stat-value {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
  .stat-sub {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.25rem; }}
  .section-title {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 1rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; color: var(--muted); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--border); }}
  td {{ padding: 0.5rem 0.5rem; border-bottom: 1px solid var(--border); }}
  tr:last-child td {{ border-bottom: none; }}
  .pr-weight {{ font-weight: 700; color: var(--accent); }}
  .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; }}
  .badge-phase {{ background: #1e2a10; color: var(--accent); }}
  canvas {{ max-height: 240px; }}
  .technique-row {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }}
  .technique-bar-wrap {{ flex: 1; background: var(--border); border-radius: 4px; height: 8px; overflow: hidden; }}
  .technique-bar {{ height: 100%; border-radius: 4px; }}
  .technique-label {{ font-size: 0.78rem; width: 80px; }}
  .technique-count {{ font-size: 0.78rem; color: var(--muted); width: 36px; text-align: right; }}
  @media (max-width: 900px) {{
    .grid-4, .grid-2, .grid-3 {{ grid-template-columns: 1fr 1fr; }}
  }}
  @media (max-width: 600px) {{
    .grid-4, .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
    body {{ padding: 1rem; }}
  }}
</style>
</head>
<body>

<h1>Training Dashboard</h1>
<p class="subtitle">Apoorva Sharma &nbsp;·&nbsp; Bodybuilding Transformation System &nbsp;·&nbsp; Last updated: {o['last_session']}</p>

<!-- Overview stats -->
<div class="grid-4">
  <div class="card">
    <div class="stat-label">Total Sessions</div>
    <div class="stat-value">{o['total_sessions']}</div>
  </div>
  <div class="card">
    <div class="stat-label">Total Working Sets</div>
    <div class="stat-value">{o['total_sets']}</div>
  </div>
  <div class="card">
    <div class="stat-label">Current Phase</div>
    <div class="stat-value">{o['current_phase']}</div>
  </div>
  <div class="card">
    <div class="stat-label">Current Week</div>
    <div class="stat-value">{o['current_week']}</div>
  </div>
</div>

<!-- Volume + RPE charts -->
<div class="grid-2">
  <div class="card">
    <div class="section-title">Volume — Working Sets per Session</div>
    <canvas id="volumeChart"></canvas>
  </div>
  <div class="card">
    <div class="section-title">Average RPE per Session</div>
    <canvas id="rpeChart"></canvas>
  </div>
</div>

<!-- PRs + Techniques + Consistency -->
<div class="grid-3">
  <div class="card">
    <div class="section-title">Personal Records — Key Lifts</div>
    <table>
      <thead><tr><th>Exercise</th><th>Weight</th><th>Reps</th><th>Date</th></tr></thead>
      <tbody id="prTable"></tbody>
    </table>
  </div>

  <div class="card">
    <div class="section-title">Failure Technique Usage</div>
    <div id="techniqueList"></div>
  </div>

  <div class="card">
    <div class="section-title">Sessions per Week</div>
    <canvas id="consistencyChart"></canvas>
  </div>
</div>

<script>
const VOLUME = {j(data['volume'])};
const RPE    = {j(data['rpe'])};
const PRS    = {j(data['prs'])};
const TECH   = {j(data['techniques'])};
const CONS   = {j(data['consistency'])};

const ACCENT = '#e8ff00';
const MUTED  = '#444';
const chartDefaults = {{
  color: '#888',
  borderColor: '#2a2a2a',
}};
Chart.defaults.color = '#888';
Chart.defaults.borderColor = '#2a2a2a';

// Volume chart
new Chart(document.getElementById('volumeChart'), {{
  type: 'bar',
  data: {{
    labels: VOLUME.map(r => r.date),
    datasets: [{{
      data: VOLUME.map(r => r.total_working_sets),
      backgroundColor: VOLUME.map(r => r.phase === 3 ? '#e8ff0044' : '#44aaff22'),
      borderColor: VOLUME.map(r => r.phase === 3 ? ACCENT : '#44aaff'),
      borderWidth: 1,
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ display: false }},
      y: {{ grid: {{ color: '#1e1e1e' }}, ticks: {{ stepSize: 5 }} }}
    }}
  }}
}});

// RPE chart
new Chart(document.getElementById('rpeChart'), {{
  type: 'line',
  data: {{
    labels: RPE.map(r => r.date),
    datasets: [{{
      data: RPE.map(r => parseFloat(r.avg_rpe)),
      borderColor: '#ff8844',
      backgroundColor: '#ff884411',
      borderWidth: 2,
      pointRadius: 2,
      tension: 0.3,
      fill: true,
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ display: false }},
      y: {{ min: 7, max: 10.5, grid: {{ color: '#1e1e1e' }} }}
    }}
  }}
}});

// PR table
const tbody = document.getElementById('prTable');
PRS.forEach(r => {{
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${{r.exercise}}</td>
    <td class="pr-weight">${{r.weight_kg > 0 ? r.weight_kg + ' kg' : 'BW'}}</td>
    <td>${{r.reps_full}}</td>
    <td style="color:var(--muted)">${{r.date}}</td>`;
  tbody.appendChild(tr);
}});

// Technique bars
const techColors = {{ MyoReps: '#e8ff00', LLP: '#44aaff', StaticHold: '#ff8844' }};
const maxUsage = Math.max(...TECH.map(t => t.usage_count));
const techDiv = document.getElementById('techniqueList');
TECH.forEach(t => {{
  const pct = (t.usage_count / maxUsage * 100).toFixed(1);
  techDiv.innerHTML += `
    <div class="technique-row">
      <div class="technique-label">${{t.technique}}</div>
      <div class="technique-bar-wrap">
        <div class="technique-bar" style="width:${{pct}}%;background:${{techColors[t.technique] || '#888'}}"></div>
      </div>
      <div class="technique-count">${{t.usage_count}}</div>
    </div>`;
}});

// Consistency chart
new Chart(document.getElementById('consistencyChart'), {{
  type: 'bar',
  data: {{
    labels: CONS.map(r => `P${{r.phase}}W${{r.week}}`),
    datasets: [{{
      data: CONS.map(r => r.session_count),
      backgroundColor: CONS.map(r => r.session_count >= 5 ? '#44ff8833' : '#ff444433'),
      borderColor: CONS.map(r => r.session_count >= 5 ? '#44ff88' : '#ff4444'),
      borderWidth: 1,
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ maxRotation: 90, font: {{ size: 9 }} }} }},
      y: {{ min: 0, max: 6, ticks: {{ stepSize: 1 }}, grid: {{ color: '#1e1e1e' }} }}
    }}
  }}
}});
</script>
</body>
</html>"""


if __name__ == "__main__":
    conn = get_connection()
    build(conn)
    conn.close()
