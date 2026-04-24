"""
Reusable training analytics queries.
All functions take a psycopg2 connection and return plain dicts/lists.
Add new queries here as useful patterns emerge.
"""

from psycopg2.extensions import connection as Connection


def exercise_progression(conn: Connection, exercise_name: str) -> list[dict]:
    """Weight and reps over time for a given exercise. One row per working set."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.date,
                s.phase,
                s.week,
                ws.number       AS set_number,
                ws.weight_kg,
                ws.reps_full,
                ws.reps_partial,
                ws.rpe,
                ws.rep_quality
            FROM working_sets ws
            JOIN exercises e ON e.id = ws.exercise_id
            JOIN sessions s ON s.session_id = e.session_id
            WHERE LOWER(e.name) = LOWER(%s)
            ORDER BY s.date ASC, ws.number ASC
            """,
            (exercise_name,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def personal_records(conn: Connection) -> list[dict]:
    """Heaviest weight lifted per exercise (across all working sets)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH ranked AS (
                SELECT
                    e.name          AS exercise,
                    ws.weight_kg,
                    ws.reps_full,
                    s.date,
                    s.phase,
                    s.week,
                    ROW_NUMBER() OVER (
                        PARTITION BY e.name ORDER BY ws.weight_kg DESC
                    ) AS rn
                FROM working_sets ws
                JOIN exercises e ON e.id = ws.exercise_id
                JOIN sessions s ON s.session_id = e.session_id
                WHERE ws.weight_kg IS NOT NULL
            )
            SELECT exercise, weight_kg, reps_full, date, phase, week
            FROM ranked
            WHERE rn = 1
            ORDER BY exercise ASC
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def volume_by_session(conn: Connection, phase: int | None = None) -> list[dict]:
    """Total working sets per session, optionally filtered by phase."""
    params = []
    where = ""
    if phase is not None:
        where = "WHERE s.phase = %s"
        params.append(phase)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                s.session_id,
                s.date,
                s.phase,
                s.week,
                s.focus,
                COUNT(ws.id) AS total_working_sets
            FROM sessions s
            JOIN exercises e ON e.session_id = s.session_id
            JOIN working_sets ws ON ws.exercise_id = e.id
            {where}
            GROUP BY s.session_id, s.date, s.phase, s.week, s.focus
            ORDER BY s.date ASC
            """,
            params,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def rpe_trend(conn: Connection, phase: int | None = None) -> list[dict]:
    """Average RPE per session over time. Shows if you're working harder."""
    params: list = [phase] if phase is not None else []
    phase_filter = "AND s.phase = %s" if phase is not None else ""

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                s.date,
                s.phase,
                s.week,
                s.focus,
                ROUND(AVG(ws.rpe)::numeric, 2) AS avg_rpe,
                COUNT(ws.id) AS sets_recorded
            FROM sessions s
            JOIN exercises e ON e.session_id = s.session_id
            JOIN working_sets ws ON ws.exercise_id = e.id
            WHERE ws.rpe IS NOT NULL
            {phase_filter}
            GROUP BY s.date, s.phase, s.week, s.focus
            ORDER BY s.date ASC
            """,
            params,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def top_rpe_sets(conn: Connection, n: int = 10) -> list[dict]:
    """The N hardest sets you've ever done (RPE 10, sorted by weight)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.date,
                s.phase,
                s.week,
                e.name          AS exercise,
                ws.weight_kg,
                ws.reps_full,
                ws.reps_partial,
                ws.rpe,
                ws.rep_quality,
                ws.failure_technique
            FROM working_sets ws
            JOIN exercises e ON e.id = ws.exercise_id
            JOIN sessions s ON s.session_id = e.session_id
            WHERE ws.rpe = 10
            ORDER BY ws.weight_kg DESC NULLS LAST
            LIMIT %s
            """,
            (n,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def sessions_per_week(conn: Connection) -> list[dict]:
    """Number of sessions logged per phase/week. Shows training consistency."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                phase,
                week,
                COUNT(*) AS session_count,
                MIN(date) AS week_start,
                MAX(date) AS week_end
            FROM sessions
            GROUP BY phase, week
            ORDER BY phase ASC, week ASC
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def failure_technique_usage(conn: Connection) -> list[dict]:
    """How often each failure technique (MyoReps, LLP, etc.) has been used."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                failure_technique->>'technique_type' AS technique,
                COUNT(*) AS usage_count
            FROM working_sets
            WHERE failure_technique IS NOT NULL
            GROUP BY technique
            ORDER BY usage_count DESC
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def custom_query(conn: Connection, sql: str, params: list | None = None) -> list[dict]:
    """
    Run an arbitrary read-only SQL query against the DB.
    Use for ad-hoc exploration. Promote useful queries to named functions above.
    """
    with conn.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def overview_stats(conn: Connection) -> dict:
    """Hero-strip numbers: total tonnage lifted, weeks trained, current phase/week, last session."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(ws.weight_kg * ws.reps_full), 0)::bigint AS total_tonnage_kg,
                COUNT(DISTINCT (s.phase, s.week))                      AS weeks_trained,
                (SELECT phase FROM sessions ORDER BY date DESC LIMIT 1) AS current_phase,
                (SELECT week  FROM sessions ORDER BY date DESC LIMIT 1) AS current_week,
                (SELECT date  FROM sessions ORDER BY date DESC LIMIT 1) AS last_session_date,
                COUNT(DISTINCT s.session_id)                           AS total_sessions
            FROM sessions s
            LEFT JOIN exercises e ON e.session_id = s.session_id
            LEFT JOIN working_sets ws ON ws.exercise_id = e.id
            """
        )
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else {}


def exercise_e1rm_trend(conn: Connection, exercise_name: str) -> list[dict]:
    """
    Epley 1-rep-max estimate per working set over time: weight * (1 + reps/30).
    Lets you see true strength progression independent of rep-scheme changes.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.date,
                s.phase,
                s.week,
                s.is_deload_week,
                ws.number        AS set_number,
                ws.weight_kg,
                ws.reps_full,
                ws.reps_partial,
                ws.rpe,
                ws.rep_quality,
                CASE
                    WHEN ws.weight_kg IS NULL OR ws.reps_full IS NULL OR ws.reps_full = 0
                        THEN NULL
                    ELSE ROUND((ws.weight_kg * (1 + ws.reps_full::numeric / 30))::numeric, 2)
                END AS e1rm_kg
            FROM working_sets ws
            JOIN exercises e ON e.id = ws.exercise_id
            JOIN sessions s  ON s.session_id = e.session_id
            WHERE LOWER(e.name) = LOWER(%s)
            ORDER BY s.date ASC, ws.number ASC
            """,
            (exercise_name,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def exercise_list(conn: Connection, min_sets: int = 10) -> list[dict]:
    """
    Distinct exercises with at least `min_sets` working sets. Used to populate the
    progression dropdown so we only show exercises with enough data to be meaningful.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.name AS exercise,
                   COUNT(ws.id) AS set_count,
                   MIN(s.date) AS first_date,
                   MAX(s.date) AS last_date
            FROM exercises e
            JOIN working_sets ws ON ws.exercise_id = e.id
            JOIN sessions s      ON s.session_id   = e.session_id
            GROUP BY e.name
            HAVING COUNT(ws.id) >= %s
            ORDER BY COUNT(ws.id) DESC
            """,
            (min_sets,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def weekly_muscle_group_volume(conn: Connection, phase: int | None = None) -> list[dict]:
    """
    Weekly working sets per muscle group. Compared against the 10-20 sets/week
    hypertrophy band (Schoenfeld) to spot under/over-training.
    Explodes target_muscle_groups[] so each set counts once per group it trains.
    """
    params: list = []
    phase_filter = ""
    if phase is not None:
        phase_filter = "WHERE s.phase = %s"
        params.append(phase)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                s.phase,
                s.week,
                mg AS muscle_group,
                COUNT(ws.id) AS working_sets
            FROM sessions s
            JOIN exercises e    ON e.session_id   = s.session_id
            JOIN working_sets ws ON ws.exercise_id = e.id
            CROSS JOIN LATERAL UNNEST(COALESCE(e.target_muscle_groups, ARRAY[]::TEXT[])) AS mg
            {phase_filter}
            GROUP BY s.phase, s.week, mg
            ORDER BY s.phase ASC, s.week ASC, mg ASC
            """,
            params,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def rpe_distribution(conn: Connection, phase: int | None = None) -> list[dict]:
    """
    Histogram of RPE bucketed to whole numbers (6-10). Shows intensity profile:
    a healthy hypertrophy block tends to live at RPE 7-9, strength peaks push higher.
    """
    params: list = []
    phase_filter = ""
    if phase is not None:
        phase_filter = "AND s.phase = %s"
        params.append(phase)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                FLOOR(ws.rpe)::int AS rpe_bucket,
                COUNT(*)           AS sets
            FROM working_sets ws
            JOIN exercises e    ON e.id = ws.exercise_id
            JOIN sessions  s    ON s.session_id = e.session_id
            WHERE ws.rpe IS NOT NULL
            {phase_filter}
            GROUP BY rpe_bucket
            ORDER BY rpe_bucket ASC
            """,
            params,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fatigue_within_phase(conn: Connection, phase: int) -> list[dict]:
    """
    Per-week fatigue markers within a phase. A well-programmed mesocycle should
    show RPE and partial-rep share *rising* through accumulation, then dropping on deload.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.week,
                s.is_deload_week,
                ROUND(AVG(ws.rpe)::numeric, 2)                                  AS avg_rpe,
                ROUND(
                    (SUM(COALESCE(ws.reps_partial, 0))::numeric /
                     NULLIF(SUM(COALESCE(ws.reps_full, 0) + COALESCE(ws.reps_partial, 0)), 0)
                    ) * 100, 2
                )                                                               AS partial_rep_share_pct,
                ROUND(
                    (SUM(CASE WHEN ws.rep_quality IN ('good','perfect') THEN 1 ELSE 0 END)::numeric /
                     NULLIF(COUNT(ws.rep_quality), 0)
                    ) * 100, 2
                )                                                               AS good_rep_share_pct,
                COUNT(ws.id)                                                    AS total_sets
            FROM sessions s
            JOIN exercises e    ON e.session_id = s.session_id
            JOIN working_sets ws ON ws.exercise_id = e.id
            WHERE s.phase = %s
            GROUP BY s.week, s.is_deload_week
            ORDER BY s.week ASC
            """,
            (phase,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def deload_effect(conn: Connection) -> list[dict]:
    """
    Paired comparison around each deload week: avg RPE and tonnage the week before,
    during, and after the deload. Answers 'do my deloads actually reset fatigue?'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH weekly AS (
                SELECT
                    s.phase,
                    s.week,
                    BOOL_OR(s.is_deload_week)                                 AS is_deload,
                    AVG(ws.rpe)                                                AS avg_rpe,
                    SUM(ws.weight_kg * ws.reps_full)                           AS tonnage_kg
                FROM sessions s
                JOIN exercises e    ON e.session_id = s.session_id
                JOIN working_sets ws ON ws.exercise_id = e.id
                GROUP BY s.phase, s.week
            ),
            deloads AS (
                SELECT phase, week FROM weekly WHERE is_deload
            )
            SELECT
                d.phase,
                d.week                                                         AS deload_week,
                ROUND(pre.avg_rpe::numeric,  2)                                AS pre_avg_rpe,
                ROUND(cur.avg_rpe::numeric,  2)                                AS deload_avg_rpe,
                ROUND(post.avg_rpe::numeric, 2)                                AS post_avg_rpe,
                pre.tonnage_kg::bigint                                         AS pre_tonnage_kg,
                cur.tonnage_kg::bigint                                         AS deload_tonnage_kg,
                post.tonnage_kg::bigint                                        AS post_tonnage_kg
            FROM deloads d
            LEFT JOIN weekly pre  ON pre.phase  = d.phase AND pre.week  = d.week - 1
            LEFT JOIN weekly cur  ON cur.phase  = d.phase AND cur.week  = d.week
            LEFT JOIN weekly post ON post.phase = d.phase AND post.week = d.week + 1
            ORDER BY d.phase ASC, d.week ASC
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def stimulus_fatigue_by_exercise(conn: Connection, min_sets: int = 10) -> list[dict]:
    """
    Per-exercise stimulus-to-fatigue proxy: avg tonnage per set (stimulus) vs avg RPE
    (fatigue). Outliers at high RPE / low tonnage are candidates to drop or replace.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                e.name                                                       AS exercise,
                COUNT(ws.id)                                                  AS set_count,
                ROUND(AVG(ws.weight_kg * ws.reps_full)::numeric, 1)           AS avg_tonnage_per_set,
                ROUND(AVG(ws.rpe)::numeric, 2)                                AS avg_rpe,
                ROUND(AVG(ws.weight_kg)::numeric, 1)                          AS avg_weight_kg,
                ROUND(AVG(ws.reps_full)::numeric, 1)                          AS avg_reps
            FROM exercises e
            JOIN working_sets ws ON ws.exercise_id = e.id
            WHERE ws.rpe IS NOT NULL
              AND ws.weight_kg IS NOT NULL
              AND ws.reps_full IS NOT NULL
            GROUP BY e.name
            HAVING COUNT(ws.id) >= %s
            ORDER BY AVG(ws.weight_kg * ws.reps_full) DESC
            """,
            (min_sets,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def weekly_tonnage_by_phase(conn: Connection) -> list[dict]:
    """
    Total tonnage (kg) per phase/week. Visualising this shows the mesocycle shape:
    accumulation ramp followed by a deload dip.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.phase,
                s.week,
                BOOL_OR(s.is_deload_week)                                     AS is_deload_week,
                COALESCE(SUM(ws.weight_kg * ws.reps_full), 0)::bigint         AS tonnage_kg,
                COUNT(ws.id)                                                  AS working_sets,
                ROUND(AVG(ws.rpe)::numeric, 2)                                AS avg_rpe
            FROM sessions s
            JOIN exercises e     ON e.session_id = s.session_id
            JOIN working_sets ws ON ws.exercise_id = e.id
            GROUP BY s.phase, s.week
            ORDER BY s.phase ASC, s.week ASC
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
