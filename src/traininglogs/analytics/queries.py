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
