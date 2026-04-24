"""
Build a static HTML training dashboard from the database.
Run: python scripts/build_dashboard.py
Output: dashboard/index.html
"""
from __future__ import annotations

import json
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
    failure_technique_usage,
    overview_stats,
    exercise_list,
    exercise_e1rm_trend,
    weekly_muscle_group_volume,
    rpe_distribution,
    fatigue_within_phase,
    deload_effect,
    stimulus_fatigue_by_exercise,
    weekly_tonnage_by_phase,
)

OUTPUT = Path(__file__).parent.parent / "dashboard" / "index.html"

HIGHLIGHT_EXERCISES = {
    "Barbell Bench Press", "Barbell Back Squat", "Barbell Romanian Deadlift",
    "Hack Squat", "Leg Press", "Lean Back Lat Pulldown", "Neutral Grip Lat Pulldown",
    "Wide Grip Lat Pulldown", "Chest Supported Machine Row", "Deficit Pendlay Row",
    "Incline DB Press 45 Degree", "DB Bulgarian Split Squat", "Seated Leg Curl",
    "Leg Extension",
}

# Roman numerals for masthead issue/volume
_ROMAN = [(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),
          (50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")]


def roman(n: int) -> str:
    out = ""
    for v, s in _ROMAN:
        while n >= v:
            out += s
            n -= v
    return out


def serial(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, date):
        return str(obj)
    raise TypeError(f"Not serialisable: {type(obj)}")


def build(conn) -> None:
    overview = overview_stats(conn)
    tonnage = weekly_tonnage_by_phase(conn)

    current_phase = overview.get("current_phase")
    muscle_volume = weekly_muscle_group_volume(conn, phase=current_phase) if current_phase else []
    rpe_dist = rpe_distribution(conn, phase=current_phase) if current_phase else []
    fatigue = fatigue_within_phase(conn, phase=current_phase) if current_phase else []

    deload = deload_effect(conn)
    stimulus = stimulus_fatigue_by_exercise(conn, min_sets=10)

    lifts = exercise_list(conn, min_sets=12)
    e1rm_by_ex: dict[str, list[dict]] = {
        row["exercise"]: exercise_e1rm_trend(conn, row["exercise"]) for row in lifts
    }

    prs_all = personal_records(conn)
    prs = sorted([r for r in prs_all if r["exercise"] in HIGHLIGHT_EXERCISES],
                 key=lambda r: r["exercise"])

    techniques = failure_technique_usage(conn)

    data = {
        "overview":       overview,
        "weekly_tonnage": tonnage,
        "muscle_volume":  muscle_volume,
        "rpe_dist":       rpe_dist,
        "fatigue":        fatigue,
        "deload":         deload,
        "stimulus":       stimulus,
        "exercise_list":  lifts,
        "e1rm_by_ex":     e1rm_by_ex,
        "prs":            prs,
        "techniques":     techniques,
    }

    OUTPUT.write_text(render(data))
    print(f"Dashboard written to {OUTPUT}")


def render(data: dict) -> str:
    j = lambda d: json.dumps(d, default=serial)
    o = data["overview"] or {}
    phase = o.get("current_phase") or 0
    week = o.get("current_week") or 0
    total_sessions = o.get("total_sessions") or 0
    year_roman = roman(date.today().year)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The Training Almanac — A. Sharma</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght,SOFT@0,9..144,300..900,0..100;1,9..144,300..900,0..100&family=Newsreader:ital,opsz,wght@0,6..72,200..800;1,6..72,200..800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --paper:#F1E9D6; --paper-2:#EBE1CB; --ink:#1A1410; --ink-soft:#3E2E1F;
    --muted:#8A7F6E; --rule:#2E231B; --accent:#C83C29; --accent-2:#8E1F12;
    --slate:#2C3E50; --band:rgba(200,60,41,0.08);
    --f-display:"Fraunces","Times New Roman",serif;
    --f-body:"Newsreader",Georgia,serif;
    --f-mono:"JetBrains Mono",ui-monospace,monospace;
    --max-w:1160px; --gutter:clamp(1.25rem,4vw,3rem);
  }}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  html,body{{background:var(--paper);color:var(--ink);}}
  body{{font-family:var(--f-body);font-size:17px;line-height:1.55;
    font-feature-settings:"kern","liga","onum";
    -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
    overflow-x:hidden;}}
  body::before{{content:"";position:fixed;inset:0;pointer-events:none;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.1 0 0 0 0 0.08 0 0 0 0 0.05 0 0 0 0.35 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.55'/></svg>");
    opacity:0.35;mix-blend-mode:multiply;z-index:1;}}
  main{{position:relative;z-index:2;}}
  .phase-rail{{position:fixed;top:50%;
    left:max(1rem,calc(50vw - (var(--max-w) / 2) - 3.5rem));
    transform:translateY(-50%);writing-mode:vertical-rl;
    font-family:var(--f-mono);font-size:0.72rem;letter-spacing:0.38em;
    text-transform:uppercase;color:var(--accent);font-weight:700;z-index:3;
    display:flex;align-items:center;gap:1rem;pointer-events:none;}}
  .phase-rail .rail-dot{{writing-mode:horizontal-tb;display:inline-block;
    width:6px;height:6px;background:var(--accent);border-radius:50%;}}
  @media(max-width:1280px){{.phase-rail{{display:none;}}}}
  .page{{max-width:var(--max-w);margin:0 auto;padding:0 var(--gutter);}}
  .masthead{{padding:4.5rem 0 2.5rem;border-bottom:2px solid var(--rule);position:relative;}}
  .masthead::after{{content:"";display:block;height:1px;background:var(--rule);margin-top:6px;}}
  .masthead-top,.masthead-bottom{{font-family:var(--f-mono);font-size:0.72rem;
    letter-spacing:0.22em;text-transform:uppercase;color:var(--ink-soft);
    display:flex;justify-content:space-between;gap:2rem;}}
  .masthead-top{{padding-bottom:1.25rem;border-bottom:1px solid var(--rule);}}
  .masthead-bottom{{padding-top:1.25rem;text-transform:none;font-size:0.78rem;
    letter-spacing:0.04em;font-style:italic;font-family:var(--f-body);}}
  .masthead-title{{font-family:var(--f-display);font-weight:400;
    font-size:clamp(3.5rem,10vw,7.5rem);line-height:0.95;letter-spacing:-0.03em;
    text-align:center;padding:1.5rem 0 1.25rem;
    font-variation-settings:"opsz" 144,"SOFT" 0;}}
  .masthead-title em{{font-style:italic;color:var(--accent);
    font-variation-settings:"opsz" 144,"SOFT" 100,"wght" 400;}}
  .issue-n{{color:var(--accent);}}
  section{{padding:4rem 0;border-bottom:1px solid var(--rule);position:relative;}}
  section:last-of-type{{border-bottom:none;}}
  .section-head{{display:grid;grid-template-columns:auto 1fr auto;
    align-items:baseline;gap:1.25rem;margin-bottom:2.5rem;}}
  .section-num{{font-family:var(--f-mono);font-weight:700;font-size:0.75rem;
    letter-spacing:0.2em;color:var(--accent);}}
  .section-head h2{{font-family:var(--f-display);font-weight:300;
    font-size:clamp(1.9rem,4vw,2.8rem);line-height:1.05;letter-spacing:-0.01em;
    font-variation-settings:"opsz" 96,"SOFT" 20;}}
  .section-head h2 em{{font-style:italic;font-weight:400;color:var(--accent);}}
  .section-head .dek{{font-family:var(--f-mono);font-size:0.7rem;
    letter-spacing:0.18em;text-transform:uppercase;color:var(--ink-soft);
    justify-self:end;align-self:center;}}
  .editor-note{{font-family:var(--f-body);font-style:italic;font-size:1.05rem;
    color:var(--ink-soft);max-width:60ch;margin:0 0 2rem 0;
    border-left:2px solid var(--accent);padding-left:1rem;}}
  .editor-note::first-letter{{font-family:var(--f-display);font-size:2.5rem;
    line-height:0.8;float:left;margin:0.25rem 0.4rem 0 0;color:var(--accent);
    font-weight:400;}}
  .hero-stats{{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:0;
    border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);}}
  .hero-stat{{padding:2rem 1.5rem;border-right:1px solid var(--rule);position:relative;}}
  .hero-stat:last-child{{border-right:none;}}
  .hero-stat:first-child{{background:linear-gradient(180deg,transparent 0%,rgba(200,60,41,0.04) 100%);}}
  .hero-label{{font-family:var(--f-mono);font-size:0.66rem;letter-spacing:0.22em;
    text-transform:uppercase;color:var(--ink-soft);margin-bottom:0.75rem;}}
  .hero-value{{font-family:var(--f-display);
    font-size:clamp(2.4rem,6vw,4.8rem);font-weight:300;line-height:0.95;
    font-variation-settings:"opsz" 144,"SOFT" 0;letter-spacing:-0.02em;
    font-variant-numeric:tabular-nums lining-nums;}}
  .hero-stat:first-child .hero-value{{color:var(--accent);
    font-variation-settings:"opsz" 144,"SOFT" 0,"wght" 400;}}
  .hero-unit{{font-family:var(--f-body);font-style:italic;font-size:0.92rem;
    color:var(--muted);margin-top:0.25rem;}}
  @media(max-width:820px){{.hero-stats{{grid-template-columns:1fr 1fr;}}
    .hero-stat{{border-bottom:1px solid var(--rule);}}
    .hero-stat:nth-child(2n){{border-right:none;}}
    .hero-stat:nth-last-child(-n+2){{border-bottom:none;}}}}
  .fig{{position:relative;padding:1.5rem;background:var(--paper-2);
    border:1px solid var(--rule);}}
  .fig canvas{{max-height:320px;}}
  .fig-caption{{font-family:var(--f-mono);font-size:0.68rem;letter-spacing:0.12em;
    color:var(--muted);text-transform:uppercase;margin-top:1rem;
    padding-top:0.75rem;border-top:1px dashed var(--rule);
    display:flex;justify-content:space-between;gap:1rem;}}
  .lift-control{{display:flex;align-items:center;gap:1.25rem;flex-wrap:wrap;
    border:1px solid var(--rule);background:var(--paper-2);
    padding:1.25rem 1.5rem;margin-bottom:1.5rem;}}
  .lift-control label{{font-family:var(--f-mono);font-size:0.7rem;
    letter-spacing:0.22em;text-transform:uppercase;color:var(--ink-soft);}}
  .lift-select-wrap{{position:relative;flex:1;min-width:260px;}}
  #exerciseSelect{{appearance:none;-webkit-appearance:none;width:100%;
    font-family:var(--f-display);font-style:italic;font-weight:400;
    font-size:1.6rem;letter-spacing:-0.01em;color:var(--ink);
    background:transparent;border:none;border-bottom:2px solid var(--ink);
    padding:0.25rem 2.25rem 0.5rem 0;cursor:pointer;
    font-variation-settings:"opsz" 72,"SOFT" 60;}}
  #exerciseSelect:focus{{outline:none;border-bottom-color:var(--accent);}}
  .lift-select-wrap::after{{content:"▼";position:absolute;right:0.25rem;
    top:0.6rem;color:var(--accent);font-size:0.75rem;pointer-events:none;}}
  .lift-grid{{display:grid;grid-template-columns:2.2fr 1fr;gap:1.5rem;}}
  @media(max-width:820px){{.lift-grid{{grid-template-columns:1fr;}}}}
  .lift-stats{{display:grid;grid-template-columns:1fr 1fr;gap:0;
    border:1px solid var(--rule);}}
  .mini-stat{{padding:1.25rem 1rem;border-right:1px solid var(--rule);
    border-bottom:1px solid var(--rule);}}
  .mini-stat:nth-child(2n){{border-right:none;}}
  .mini-stat:nth-last-child(-n+2){{border-bottom:none;}}
  .mini-label{{font-family:var(--f-mono);font-size:0.62rem;letter-spacing:0.2em;
    text-transform:uppercase;color:var(--muted);margin-bottom:0.4rem;}}
  .mini-value{{font-family:var(--f-display);font-size:1.8rem;line-height:1;
    font-weight:400;font-variant-numeric:tabular-nums lining-nums;
    font-variation-settings:"opsz" 72,"SOFT" 20;}}
  .mini-value .u{{font-size:0.75rem;font-family:var(--f-body);font-style:italic;
    color:var(--muted);margin-left:0.25rem;}}
  .split-2{{display:grid;grid-template-columns:1fr 1.2fr;gap:1.5rem;}}
  @media(max-width:820px){{.split-2{{grid-template-columns:1fr;}}}}
  table{{width:100%;border-collapse:collapse;font-family:var(--f-mono);font-size:0.88rem;}}
  thead th{{text-align:left;font-weight:700;font-size:0.66rem;letter-spacing:0.16em;
    text-transform:uppercase;color:var(--ink-soft);padding:0.75rem 0.6rem;
    border-bottom:2px solid var(--rule);}}
  tbody td{{padding:0.7rem 0.6rem;border-bottom:1px dotted var(--rule);
    font-variant-numeric:tabular-nums;}}
  tbody tr:last-child td{{border-bottom:none;}}
  .pr-table .ex-name{{font-family:var(--f-display);font-size:1.05rem;font-weight:400;
    font-style:italic;font-variation-settings:"opsz" 48,"SOFT" 40;}}
  .pr-table .wt{{color:var(--accent);font-weight:700;font-size:1rem;}}
  .pr-table .date-cell{{color:var(--muted);}}
  tbody tr.deload-row{{background:rgba(200,60,41,0.05);}}
  tbody tr.deload-row .wk-cell::before{{content:"❦ ";color:var(--accent);}}
  .technique-list{{display:flex;flex-direction:column;gap:1.2rem;}}
  .technique-row{{display:grid;grid-template-columns:160px 1fr auto;gap:1rem;align-items:center;}}
  .tech-name{{font-family:var(--f-display);font-style:italic;font-size:1.25rem;
    font-variation-settings:"opsz" 48,"SOFT" 40;}}
  .tech-bar-wrap{{height:2px;background:var(--rule);position:relative;overflow:visible;}}
  .tech-bar{{height:8px;position:absolute;top:-3px;left:0;background:var(--accent);
    transition:width 1.2s cubic-bezier(.22,.61,.36,1);}}
  .tech-count{{font-family:var(--f-mono);font-weight:700;font-size:1.1rem;
    font-variant-numeric:tabular-nums;color:var(--ink);min-width:40px;text-align:right;}}
  .delta-up{{color:var(--accent);}}
  .delta-down{{color:#2C7A3E;}}
  .delta-flat{{color:var(--muted);}}
  .ornament{{text-align:center;margin:3rem 0;color:var(--accent);font-size:1.1rem;letter-spacing:2em;}}
  .colophon{{padding:3.5rem 0 2.5rem;text-align:center;font-family:var(--f-body);
    font-style:italic;color:var(--muted);font-size:0.88rem;
    border-top:2px solid var(--rule);border-bottom:1px solid var(--rule);margin-top:2rem;}}
  .colophon .rule-dot{{color:var(--accent);margin:0 0.5rem;}}
  @keyframes riseIn{{from{{opacity:0;transform:translateY(12px);}}to{{opacity:1;transform:translateY(0);}}}}
  .rise{{animation:riseIn 0.9s cubic-bezier(.22,.61,.36,1) both;}}
  .rise-1{{animation-delay:0.05s;}}
  .rise-2{{animation-delay:0.20s;}}
</style>
</head>
<body>

<div class="phase-rail">
  <span>Phase {roman(phase)} · Week {roman(week)}</span>
  <span class="rail-dot"></span>
  <span>{year_roman}</span>
</div>

<main class="page">

  <header class="masthead rise rise-1">
    <div class="masthead-top">
      <span>Vol. <span class="issue-n">{roman(phase)}</span> · No. <span class="issue-n">{roman(week)}</span></span>
      <span>Est. MMXXV</span>
      <span>Last: {o.get('last_session_date','—')}</span>
    </div>
    <h1 class="masthead-title">The Training <em>Almanac</em></h1>
    <div class="masthead-bottom">
      <span>Kept by A. Sharma</span>
      <span>An honest record of the weights lifted and the hours spent under them.</span>
      <span>Sessions logged: <strong>{total_sessions}</strong></span>
    </div>
  </header>

  <section class="rise rise-2">
    <div class="section-head">
      <div class="section-num">§ I</div>
      <h2>The Numbers, <em>so far</em></h2>
      <div class="dek">Cumulative</div>
    </div>
    <div class="hero-stats">
      <div class="hero-stat">
        <div class="hero-label">Tonnage lifted</div>
        <div class="hero-value" id="heroTonnage">—</div>
        <div class="hero-unit">kilograms, all told</div>
      </div>
      <div class="hero-stat">
        <div class="hero-label">Weeks trained</div>
        <div class="hero-value" id="heroWeeks">—</div>
        <div class="hero-unit">across phases</div>
      </div>
      <div class="hero-stat">
        <div class="hero-label">Sessions</div>
        <div class="hero-value" id="heroSessions">—</div>
        <div class="hero-unit">logged honestly</div>
      </div>
      <div class="hero-stat">
        <div class="hero-label">Latest lift</div>
        <div class="hero-value" id="heroLast" style="font-size:clamp(1.4rem,3vw,2.2rem);">—</div>
        <div class="hero-unit">most recent session</div>
      </div>
    </div>
  </section>

  <div class="ornament">· · ·</div>

  <section>
    <div class="section-head">
      <div class="section-num">§ II</div>
      <h2>The Shape of <em>the Year</em></h2>
      <div class="dek">Weekly Tonnage</div>
    </div>
    <p class="editor-note">Each bar is a week's total tonnage. The dips are deloads — the program breathing. The ramp before each dip is accumulation. A well-shaped mesocycle looks like ascending stairs with regular landings.</p>
    <div class="fig">
      <canvas id="tonnageChart"></canvas>
      <div class="fig-caption">
        <span>Fig. 1 — Tonnage per week, grouped by phase</span>
        <span>Deload weeks marked in <span style="color:var(--accent);font-weight:700;">red</span></span>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <div class="section-num">§ III</div>
      <h2>One Lift, <em>Over Time</em></h2>
      <div class="dek">Estimated 1-Rep Max</div>
    </div>
    <p class="editor-note">Choose a lift. Watch its estimated one-rep-max walk forward through the phases — a truer gauge of strength than today's weight on the bar. Computed by Epley: <span style="font-family:var(--f-mono);color:var(--accent);font-style:normal;">weight × (1 + reps / 30)</span>.</p>
    <div class="lift-control">
      <label for="exerciseSelect">Select lift</label>
      <div class="lift-select-wrap"><select id="exerciseSelect"></select></div>
    </div>
    <div class="lift-grid">
      <div class="fig">
        <canvas id="e1rmChart"></canvas>
        <div class="fig-caption">
          <span>Fig. 2 — Epley e1RM per working set</span>
          <span id="liftRange">—</span>
        </div>
      </div>
      <div class="lift-stats">
        <div class="mini-stat"><div class="mini-label">Peak e1RM</div><div class="mini-value" id="peakE1rm">— <span class="u">kg</span></div></div>
        <div class="mini-stat"><div class="mini-label">Latest top set</div><div class="mini-value" id="latestTop">—</div></div>
        <div class="mini-stat"><div class="mini-label">Sets logged</div><div class="mini-value" id="setCount">—</div></div>
        <div class="mini-stat"><div class="mini-label">Avg RPE</div><div class="mini-value" id="recentRpe">—</div></div>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <div class="section-num">§ IV</div>
      <h2>Volume, <em>by Muscle</em></h2>
      <div class="dek">Working Sets / Week</div>
    </div>
    <p class="editor-note">Weekly working sets per muscle group, current phase only. The shaded band marks Schoenfeld's 10–20 set zone for hypertrophy. Below is undertraining; far above is diminishing return.</p>
    <div class="fig">
      <canvas id="muscleVolumeChart"></canvas>
      <div class="fig-caption">
        <span>Fig. 3 — Phase {roman(phase)}, by muscle group</span>
        <span>Band: 10–20 sets / wk</span>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <div class="section-num">§ V</div>
      <h2>Intensity, <em>Distilled</em></h2>
      <div class="dek">RPE &amp; Fatigue</div>
    </div>
    <div class="split-2">
      <div class="fig">
        <canvas id="rpeDistChart"></canvas>
        <div class="fig-caption">
          <span>Fig. 4 — Histogram of RPE (whole buckets)</span>
          <span>All sets, phase {roman(phase)}</span>
        </div>
      </div>
      <div class="fig">
        <div style="font-family:var(--f-mono);font-size:0.66rem;letter-spacing:0.22em;text-transform:uppercase;color:var(--ink-soft);margin-bottom:1rem;">Fatigue within <span style="color:var(--accent);">Phase {roman(phase)}</span></div>
        <table class="fatigue-table">
          <thead><tr><th>Wk</th><th>Avg RPE</th><th>Partial %</th><th>Good %</th><th>Sets</th></tr></thead>
          <tbody id="fatigueBody"></tbody>
        </table>
        <div class="fig-caption"><span>Fig. 5 — RPE climbs; deload resets</span></div>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <div class="section-num">§ VI</div>
      <h2>Does the Deload <em>Work?</em></h2>
      <div class="dek">Before · During · After</div>
    </div>
    <p class="editor-note">A good deload should cut RPE markedly and let the tonnage bounce back the following week. If it doesn't — rest longer, or rest more often.</p>
    <div class="fig">
      <table class="deload-table">
        <thead><tr><th>Phase</th><th>Deload Wk</th><th>Pre RPE</th><th>Deload RPE</th><th>Post RPE</th><th>Pre Tonnage</th><th>Post Tonnage</th><th>Δ</th></tr></thead>
        <tbody id="deloadBody"></tbody>
      </table>
    </div>
  </section>

  <section>
    <div class="section-head">
      <div class="section-num">§ VII</div>
      <h2>Stimulus vs <em>Fatigue</em></h2>
      <div class="dek">Cost / Reward</div>
    </div>
    <p class="editor-note">Every lift plotted by cost (average RPE) against reward (tonnage per set). The upper-left quadrant is gold — high stimulus at lower fatigue. The lower-right is a candidate to replace or cut.</p>
    <div class="fig">
      <canvas id="stimulusChart"></canvas>
      <div class="fig-caption">
        <span>Fig. 6 — Exercises with ≥ 10 working sets</span>
        <span>Size = set count</span>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <div class="section-num">§ VIII</div>
      <h2>Personal <em>Bests</em></h2>
      <div class="dek">Heaviest Set on Record</div>
    </div>
    <div class="fig">
      <table class="pr-table">
        <thead><tr><th>Exercise</th><th>Weight</th><th>Reps</th><th>Phase</th><th>Date</th></tr></thead>
        <tbody id="prBody"></tbody>
      </table>
    </div>
  </section>

  <section>
    <div class="section-head">
      <div class="section-num">§ IX</div>
      <h2>Techniques <em>Employed</em></h2>
      <div class="dek">Intensifiers</div>
    </div>
    <p class="editor-note"><em>Myo-reps</em> — short-rest mini-sets that extend a working set past failure. <em>LLP</em> — lengthened partials at end-range. <em>Static holds</em> — isometric finishers.</p>
    <div class="fig">
      <div class="technique-list" id="techniqueList"></div>
      <div class="fig-caption"><span>Fig. 7 — Count of sets containing each technique</span></div>
    </div>
  </section>

  <footer class="colophon">
    Set in Fraunces, Newsreader &amp; JetBrains Mono
    <span class="rule-dot">❦</span>
    Compiled from <span id="footSessions">{total_sessions}</span> sessions
    <span class="rule-dot">❦</span>
    Kept in Postgres, printed in HTML
  </footer>

</main>

<script>
const OVERVIEW        = {j(data['overview'] or {{}})};
const WEEKLY_TONNAGE  = {j(data['weekly_tonnage'])};
const MUSCLE_VOLUME   = {j(data['muscle_volume'])};
const RPE_DIST        = {j(data['rpe_dist'])};
const FATIGUE         = {j(data['fatigue'])};
const DELOAD          = {j(data['deload'])};
const STIMULUS        = {j(data['stimulus'])};
const EXERCISE_LIST   = {j(data['exercise_list'])};
const E1RM_BY_EXERCISE = {j(data['e1rm_by_ex'])};
const PRS             = {j(data['prs'])};
const TECHNIQUES      = {j(data['techniques'])};

const C = {{
  ink:"#1A1410", paper:"#F1E9D6", paper2:"#EBE1CB", muted:"#8A7F6E",
  accent:"#C83C29", accent2:"#8E1F12", slate:"#2C3E50",
  faint:"rgba(46,35,27,0.08)",
}};

Chart.defaults.font.family = "'JetBrains Mono', ui-monospace, monospace";
Chart.defaults.font.size = 10;
Chart.defaults.color = C.muted;
Chart.defaults.borderColor = C.faint;
Chart.defaults.plugins.tooltip.backgroundColor = C.ink;
Chart.defaults.plugins.tooltip.titleFont = {{ family: "'JetBrains Mono'", size: 10 }};
Chart.defaults.plugins.tooltip.bodyFont  = {{ family: "'JetBrains Mono'", size: 11 }};
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.borderColor = C.accent;
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.cornerRadius = 0;

const fmtInt = n => n == null ? "—" : Number(n).toLocaleString();
const fmt1   = n => n == null ? "—" : Number(n).toFixed(1);
const fmt2   = n => n == null ? "—" : Number(n).toFixed(2);

(function fillHero() {{
  document.getElementById("heroTonnage").textContent   = fmtInt(OVERVIEW.total_tonnage_kg);
  document.getElementById("heroWeeks").textContent     = fmtInt(OVERVIEW.weeks_trained);
  document.getElementById("heroSessions").textContent  = fmtInt(OVERVIEW.total_sessions);
  document.getElementById("heroLast").textContent      = OVERVIEW.last_session_date
    ? new Date(OVERVIEW.last_session_date).toLocaleDateString("en-US",{{month:"short",day:"numeric"}})
    : "—";
}})();

(function renderTonnage() {{
  if (!WEEKLY_TONNAGE.length) return;
  const labels = WEEKLY_TONNAGE.map(r => `P${{r.phase}}·W${{r.week}}`);
  const data   = WEEKLY_TONNAGE.map(r => r.tonnage_kg);
  const colors = WEEKLY_TONNAGE.map(r => r.is_deload_week ? C.accent : C.ink);
  new Chart(document.getElementById("tonnageChart"), {{
    type: "bar",
    data: {{ labels, datasets: [{{ data, backgroundColor: colors, borderWidth: 0, borderRadius: 0, barPercentage: 0.7 }}] }},
    options: {{
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{
          label: ctx => `${{fmtInt(ctx.parsed.y)}} kg` + (WEEKLY_TONNAGE[ctx.dataIndex].is_deload_week ? "   ❦ DELOAD" : "")
        }} }}
      }},
      scales: {{
        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 9 }}, maxRotation: 0, autoSkip: false }} }},
        y: {{ beginAtZero: true, grid: {{ color: C.faint, drawBorder: false }},
              ticks: {{ callback: v => (v/1000) + "k", font: {{ size: 9 }} }},
              title: {{ display: true, text: "KG · WEEK", font: {{ size: 9, weight: 700 }}, color: C.muted }} }}
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
    const rows = (E1RM_BY_EXERCISE[exName] || []).map(r => ({{ ...r, e1rm_kg: r.e1rm_kg == null ? null : Number(r.e1rm_kg) }}));
    const byDate = {{}};
    rows.forEach(r => {{
      if (r.e1rm_kg == null) return;
      if (!byDate[r.date] || r.e1rm_kg > byDate[r.date].e1rm_kg) byDate[r.date] = r;
    }});
    const top = Object.values(byDate).sort((a,b) => a.date.localeCompare(b.date));
    const labels = top.map(r => String(r.date).slice(5));
    const values = top.map(r => r.e1rm_kg);
    const pointColors = top.map(r => r.is_deload_week ? C.accent : C.ink);

    const peak = rows.reduce((a,b) => (b.e1rm_kg||0) > (a.e1rm_kg||0) ? b : a, rows[0] || {{e1rm_kg:0}});
    const latest = rows[rows.length - 1] || {{}};
    const avgRpe = rows.length ? rows.reduce((s,r) => s + Number(r.rpe||0), 0) / rows.length : 0;

    document.getElementById("peakE1rm").innerHTML = `${{fmt1(peak.e1rm_kg)}} <span class="u">kg</span>`;
    document.getElementById("latestTop").innerHTML = latest.weight_kg
      ? `${{latest.weight_kg}} <span class="u">×${{latest.reps_full}}</span>` : "—";
    document.getElementById("setCount").textContent = fmtInt(rows.length);
    document.getElementById("recentRpe").textContent = fmt1(avgRpe);
    document.getElementById("liftRange").textContent = labels.length ? `${{top[0].date}} — ${{top[top.length-1].date}}` : "—";

    if (chart) chart.destroy();
    chart = new Chart(document.getElementById("e1rmChart"), {{
      type: "line",
      data: {{ labels, datasets: [{{
        data: values, borderColor: C.ink,
        backgroundColor: "rgba(200,60,41,0.06)",
        borderWidth: 2, pointRadius: 4,
        pointBackgroundColor: pointColors, pointBorderColor: C.paper, pointBorderWidth: 1,
        tension: 0.25, fill: true,
      }}] }},
      options: {{
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ callbacks: {{
            label: ctx => {{
              const r = top[ctx.dataIndex];
              return `${{fmt1(r.e1rm_kg)}} kg e1RM · ${{r.weight_kg}}kg × ${{r.reps_full}}` + (r.is_deload_week ? "   ❦ DELOAD" : "");
            }}
          }} }}
        }},
        scales: {{
          x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 9 }} }} }},
          y: {{ grid: {{ color: C.faint, drawBorder: false }}, ticks: {{ callback: v => v + " kg", font: {{ size: 9 }} }} }}
        }}
      }}
    }});
  }}

  sel.addEventListener("change", e => draw(e.target.value));
  if (EXERCISE_LIST.length) {{ sel.value = EXERCISE_LIST[0].exercise; draw(EXERCISE_LIST[0].exercise); }}
}})();

(function renderMuscle() {{
  if (!MUSCLE_VOLUME.length) return;
  const weeks = [...new Set(MUSCLE_VOLUME.map(r => `P${{r.phase}}·W${{r.week}}`))];
  const muscles = [...new Set(MUSCLE_VOLUME.map(r => r.muscle_group))];
  const palette = [C.ink, C.accent, C.slate, "#5D5847", "#A6654E", "#486D5B", "#8A5A32", "#6B4A2F", "#3F5A3F"];

  const datasets = muscles.map((m, i) => ({{
    label: m,
    data: weeks.map(w => {{
      const [p,wk] = w.replace("P","").split("·W").map(Number);
      const row = MUSCLE_VOLUME.find(r => r.phase === p && r.week === wk && r.muscle_group === m);
      return row ? row.working_sets : 0;
    }}),
    backgroundColor: palette[i % palette.length],
    borderWidth: 0, borderRadius: 0, barPercentage: 0.75,
  }}));

  new Chart(document.getElementById("muscleVolumeChart"), {{
    type: "bar",
    data: {{ labels: weeks, datasets }},
    options: {{
      plugins: {{
        legend: {{ position: "bottom", labels: {{ font: {{ size: 10, family: "'JetBrains Mono'" }}, usePointStyle: true, boxWidth: 8, padding: 14 }} }},
        tooltip: {{ callbacks: {{ label: ctx => `${{ctx.dataset.label}}: ${{ctx.parsed.y}} sets` }} }}
      }},
      scales: {{
        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 9 }} }} }},
        y: {{ beginAtZero: true, grid: {{ color: C.faint, drawBorder: false }}, ticks: {{ font: {{ size: 9 }} }},
              title: {{ display: true, text: "SETS / WEEK", font: {{ size: 9, weight: 700 }}, color: C.muted }} }}
      }}
    }},
    plugins: [{{
      id: "schoenfeldBand",
      beforeDatasetsDraw(chart) {{
        const {{ ctx, chartArea, scales: {{ y }} }} = chart;
        if (!chartArea) return;
        const y10 = y.getPixelForValue(10);
        const y20 = y.getPixelForValue(20);
        ctx.save();
        ctx.fillStyle = "rgba(200,60,41,0.08)";
        ctx.fillRect(chartArea.left, y20, chartArea.right - chartArea.left, y10 - y20);
        ctx.strokeStyle = "rgba(200,60,41,0.45)";
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(chartArea.left, y10); ctx.lineTo(chartArea.right, y10);
        ctx.moveTo(chartArea.left, y20); ctx.lineTo(chartArea.right, y20);
        ctx.stroke();
        ctx.restore();
      }}
    }}]
  }});
}})();

(function renderRpeDist() {{
  if (!RPE_DIST.length) return;
  const labels = RPE_DIST.map(r => `RPE ${{r.rpe_bucket}}`);
  const data = RPE_DIST.map(r => r.sets);
  const colors = RPE_DIST.map(r => r.rpe_bucket >= 9 ? C.accent : r.rpe_bucket >= 7 ? C.ink : C.muted);
  new Chart(document.getElementById("rpeDistChart"), {{
    type: "bar",
    data: {{ labels, datasets: [{{ data, backgroundColor: colors, borderWidth: 0, borderRadius: 0, barPercentage: 0.85 }}] }},
    options: {{
      indexAxis: "y",
      plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: ctx => `${{ctx.parsed.x}} sets` }} }} }},
      scales: {{
        x: {{ grid: {{ color: C.faint, drawBorder: false }}, ticks: {{ font: {{ size: 9 }} }} }},
        y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10, weight: 700 }} }} }}
      }}
    }}
  }});
}})();

(function renderFatigueTable() {{
  const body = document.getElementById("fatigueBody");
  if (!FATIGUE.length) {{ body.innerHTML = `<tr><td colspan="5" style="color:var(--muted);font-style:italic;">No data yet.</td></tr>`; return; }}
  body.innerHTML = FATIGUE.map(r => `
    <tr class="${{r.is_deload_week ? 'deload-row' : ''}}">
      <td class="wk-cell">${{r.week}}</td>
      <td><strong>${{fmt2(r.avg_rpe)}}</strong></td>
      <td>${{r.partial_rep_share_pct != null ? fmt1(r.partial_rep_share_pct) + '%' : '—'}}</td>
      <td>${{r.good_rep_share_pct != null ? fmt1(r.good_rep_share_pct) + '%' : '—'}}</td>
      <td style="color:var(--muted)">${{r.total_sets}}</td>
    </tr>`).join("");
}})();

(function renderDeload() {{
  const body = document.getElementById("deloadBody");
  if (!DELOAD.length) {{ body.innerHTML = `<tr><td colspan="8" style="color:var(--muted);font-style:italic;">No deloads on record yet.</td></tr>`; return; }}
  body.innerHTML = DELOAD.map(r => {{
    const drop = (r.pre_avg_rpe != null && r.deload_avg_rpe != null) ? Number(r.pre_avg_rpe) - Number(r.deload_avg_rpe) : null;
    const dcls = drop == null ? "delta-flat" : drop > 1 ? "delta-down" : drop > 0.3 ? "delta-flat" : "delta-up";
    const dtext = drop == null ? "—" : drop > 0 ? `−${{fmt1(drop)}} RPE` : `+${{fmt1(-drop)}} RPE`;
    return `
      <tr>
        <td>Phase ${{r.phase}}</td>
        <td class="wk-cell"><strong>Wk ${{r.deload_week}}</strong></td>
        <td>${{fmt2(r.pre_avg_rpe)}}</td>
        <td style="color:var(--accent);font-weight:700;">${{fmt2(r.deload_avg_rpe)}}</td>
        <td>${{r.post_avg_rpe != null ? fmt2(r.post_avg_rpe) : "—"}}</td>
        <td>${{fmtInt(r.pre_tonnage_kg)}}</td>
        <td>${{r.post_tonnage_kg != null ? fmtInt(r.post_tonnage_kg) : "—"}}</td>
        <td class="${{dcls}}"><strong>${{dtext}}</strong></td>
      </tr>`;
  }}).join("");
}})();

(function renderStimulus() {{
  if (!STIMULUS.length) return;
  const data = STIMULUS.map(r => ({{
    x: Number(r.avg_rpe),
    y: Number(r.avg_tonnage_per_set),
    r: Math.sqrt(r.set_count) * 1.6,
    label: r.exercise, setCount: r.set_count,
  }}));
  new Chart(document.getElementById("stimulusChart"), {{
    type: "bubble",
    data: {{ datasets: [{{
      data,
      backgroundColor: data.map(d => d.y > 700 && d.x < 8.5 ? "rgba(200,60,41,0.55)" : "rgba(26,20,16,0.45)"),
      borderColor: data.map(d => d.y > 700 && d.x < 8.5 ? C.accent2 : C.ink),
      borderWidth: 1.5,
    }}] }},
    options: {{
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{
          title: items => items[0].raw.label,
          label: item => {{
            const d = item.raw;
            return [`RPE: ${{fmt2(d.x)}}`, `Tonnage/set: ${{fmtInt(d.y)}} kg`, `Sets: ${{d.setCount}}`];
          }}
        }} }}
      }},
      scales: {{
        x: {{ title: {{ display: true, text: "AVG RPE  →  FATIGUE", font: {{ size: 9, weight: 700 }}, color: C.muted }},
              grid: {{ color: C.faint, drawBorder: false }}, ticks: {{ font: {{ size: 9 }} }} }},
        y: {{ title: {{ display: true, text: "TONNAGE / SET  →  STIMULUS", font: {{ size: 9, weight: 700 }}, color: C.muted }},
              grid: {{ color: C.faint, drawBorder: false }}, ticks: {{ callback: v => v + " kg", font: {{ size: 9 }} }} }}
      }}
    }},
    plugins: [{{
      id: "exLabels",
      afterDatasetDraw(chart) {{
        const {{ ctx }} = chart;
        const meta = chart.getDatasetMeta(0);
        ctx.save();
        ctx.fillStyle = C.ink;
        ctx.font = "italic 11px Newsreader, serif";
        meta.data.forEach((pt, i) => {{
          const d = data[i];
          ctx.fillText(d.label, pt.x + pt.options.radius + 4, pt.y + 3);
        }});
        ctx.restore();
      }}
    }}]
  }});
}})();

(function renderPRs() {{
  const body = document.getElementById("prBody");
  if (!PRS.length) {{ body.innerHTML = `<tr><td colspan="5" style="color:var(--muted);font-style:italic;">No PRs yet.</td></tr>`; return; }}
  body.innerHTML = PRS.map(r => `
    <tr>
      <td class="ex-name">${{r.exercise}}</td>
      <td class="wt">${{r.weight_kg > 0 ? r.weight_kg + ' kg' : 'BW'}}</td>
      <td>${{r.reps_full}}</td>
      <td>P${{r.phase}} · W${{r.week}}</td>
      <td class="date-cell">${{r.date}}</td>
    </tr>`).join("");
}})();

(function renderTechniques() {{
  const container = document.getElementById("techniqueList");
  if (!TECHNIQUES.length) {{ container.innerHTML = `<div style="color:var(--muted);font-style:italic;">None recorded yet.</div>`; return; }}
  const max = Math.max(...TECHNIQUES.map(t => t.usage_count));
  container.innerHTML = TECHNIQUES.map(t => `
    <div class="technique-row">
      <div class="tech-name">${{t.technique}}</div>
      <div class="tech-bar-wrap">
        <div class="tech-bar" style="width:0%" data-w="${{(t.usage_count / max * 100).toFixed(1)}}%"></div>
      </div>
      <div class="tech-count">${{t.usage_count}}</div>
    </div>`).join("");
  requestAnimationFrame(() => {{
    container.querySelectorAll(".tech-bar").forEach(b => b.style.width = b.dataset.w);
  }});
}})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    conn = get_connection()
    build(conn)
    conn.close()
