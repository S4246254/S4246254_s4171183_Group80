"""
app.py — Main Flask application for Sub-Task A: Road Incidents Explorer

Covers Level 1 (Landing), Level 2 (Conditions Summary), Level 3 (Deep Dive)

Updated to work with the real Victorian road-accidents database schema:
  - Road surface is stored in Surface_Cond_Seq + Road_Surface_Cond (M:M)
  - Atmospheric condition is in Atmospheric_Cond_Seq + Amospheric_Cond (M:M)
  - Light condition is a FK on Accident.LIGHT_CONDITION -> Light_Condition
  - Severity is derived from Person.INJ_LEVEL (1=Fatality … 4=Not injured)
  - Fatalities are counted as Person rows with INJ_LEVEL = 1
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from database.setup_db import get_db, setup, DB_PATH, DDL_MISSION_CONTENT, DDL_PERSONAS, DDL_TEAM_MEMBERS, seed_mission

app = Flask(__name__)

# Initialise DB and all required tables on startup
if not os.path.exists(DB_PATH):
    setup()
else:
    _conn = get_db()
    _conn.execute(DDL_MISSION_CONTENT)
    _conn.execute(DDL_PERSONAS)
    _conn.execute(DDL_TEAM_MEMBERS)
    seed_mission(_conn)
    _conn.commit()
    _conn.close()


# ------------------------------------------------------------------ #
# Helper
# ------------------------------------------------------------------ #

def query_db(sql, args=()):
    """Execute a SELECT query and return a list of dicts."""
    conn = get_db()
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ #
# Page routes
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    """Level 1 — Landing page. Facts retrieved from FACTS table in DB."""
    facts = query_db("SELECT LABEL, VALUE, DESCRIPTION FROM FACTS")
    return render_template("landing.html", facts=facts)


@app.route("/conditions")
def conditions():
    """Level 2 — Conditions summary page."""
    return render_template("conditions.html")


@app.route("/deepdive")
def deepdive():
    """Level 3 — Deep dive page."""
    return render_template("deepdive.html")

@app.route("/mission-statement")
def mission_statement():
    mission   = query_db("SELECT CONTENT FROM MISSION_CONTENT WHERE SECTION = 'mission'")
    how_to    = query_db("SELECT CONTENT FROM MISSION_CONTENT WHERE SECTION = 'how_to_use'")
    personas  = query_db("SELECT * FROM PERSONAS ORDER BY PERSONA_KEY ASC")
    team      = query_db("SELECT FULL_NAME, STUDENT_ID FROM TEAM_MEMBERS ORDER BY ID ASC")

    persona_map = {p["PERSONA_KEY"]: p for p in personas}

    return render_template(
        "mission_statement.html",
        mission_content = mission[0]["CONTENT"]  if mission  else "",
        how_to_use      = how_to[0]["CONTENT"]   if how_to   else "",
        persona_a       = persona_map.get("a"),
        persona_b       = persona_map.get("b"),
        team            = team,
    )
# ------------------------------------------------------------------ #
# Dimension config
#
# Each dimension maps to a SQL fragment that produces two columns:
#   condition  — the human-readable label
#   accident_no — the accident identifier (for joining / grouping)
#
# Road surface and atmospheric condition use junction tables (M:M).
# Light condition is a direct FK on the Accident table.
# ------------------------------------------------------------------ #

# Validated dimension keys — never accept raw user input in SQL
VALID_DIMS = {"road", "atmos", "light"}

DIM_JOIN = {
    # dim_key: (join_sql, group_column_expr, human_label_expr)
    "road": (
        """
        JOIN Surface_Cond_Seq scs ON a.ACCIDENT_NO = scs.ACCIDENT_NO
        JOIN Road_Surface_Cond rsc ON scs.SURFACE_COND = rsc.SURFACE_COND
        """,
        "rsc.SURFACE_COND_DESC",
        "rsc.SURFACE_COND_DESC",
        "rsc.SURFACE_COND_DESC NOT IN ('Unk.')",          # exclude unknowns
    ),
    "atmos": (
        """
        JOIN Atmospheric_Cond_Seq acs ON a.ACCIDENT_NO = acs.ACCIDENT_NO
        JOIN Amospheric_Cond ac ON acs.ATMOSPH_COND = ac.ATMOSPH_COND
        """,
        "ac.ATMOSPH_COND_DESC",
        "ac.ATMOSPH_COND_DESC",
        "ac.ATMOSPH_COND_DESC != 'Not known'",
    ),
    "light": (
        """
        JOIN Light_Condition lc ON a.LIGHT_CONDITION = lc.COND_ID
        """,
        "lc.COND_NAME",
        "lc.COND_NAME",
        "lc.COND_NAME != 'Unknown'",
    ),
}


# ------------------------------------------------------------------ #
# API — Level 2
# ------------------------------------------------------------------ #

@app.route("/api/level2")
def api_level2():
    """
    Level 2: Aggregate accident counts by a chosen condition column.

    For each condition value, returns:
      - total_accidents  (COUNT of distinct accidents)
      - fatal_count      (accidents with at least one fatality)
      - avg_persons      (average number of persons involved)
      - fatal_pct        (percentage of accidents with a fatality)

    Uses JOIN, GROUP BY, HAVING, ORDER BY, COUNT, AVG, SUM.

    Query params:
      dim       = road | atmos | light
      min_count = integer — minimum accidents to include (default 0)
    """
    dim = request.args.get("dim", "road")
    if dim not in VALID_DIMS:
        return jsonify({"error": "Invalid dimension"}), 400

    min_count = max(0, int(request.args.get("min_count", 0)))

    join_sql, group_col, label_col, exclude_filter = DIM_JOIN[dim]

    sql = f"""
        SELECT
            {label_col}                                           AS condition,
            COUNT(DISTINCT a.ACCIDENT_NO)                         AS total_accidents,
            SUM(CASE WHEN a.NO_PERSONS_KILLED > 0 THEN 1 ELSE 0 END)
                                                                  AS fatal_count,
            ROUND(AVG(a.NO_PERSONS), 2)                           AS avg_persons,
            ROUND(
                100.0 * SUM(CASE WHEN a.NO_PERSONS_KILLED > 0 THEN 1 ELSE 0 END)
                      / COUNT(DISTINCT a.ACCIDENT_NO),
                2
            )                                                     AS fatal_pct
        FROM Accident a
        {join_sql}
        WHERE {exclude_filter}
        GROUP BY {group_col}
        HAVING COUNT(DISTINCT a.ACCIDENT_NO) >= ?
        ORDER BY total_accidents DESC
    """
    rows = query_db(sql, (min_count,))
    return jsonify(rows)


# ------------------------------------------------------------------ #
# API — Level 3
# ------------------------------------------------------------------ #

@app.route("/api/level3")
def api_level3():
    """
    Level 3: Identify conditions whose accident count is ABOVE the
    statewide per-condition average — nested subquery approach.

    The outer query filters on the result of the inner average
    calculation, then ranks by fatality percentage descending.

    Also returns the statewide average for the chart reference line.

    Query params:
      dim       = road | atmos | light
      high_only = true — only show conditions with fatal_pct > 0
    """
    dim = request.args.get("dim", "road")
    if dim not in VALID_DIMS:
        return jsonify({"error": "Invalid dimension"}), 400

    high_only = request.args.get("high_only", "false").lower() == "true"

    join_sql, group_col, label_col, exclude_filter = DIM_JOIN[dim]

    high_only_filter = "AND fatal_pct > 0" if high_only else ""

    sql = f"""
        SELECT
            condition,
            total_accidents,
            fatal_count,
            fatal_pct,
            avg_persons,
            RANK() OVER (ORDER BY fatal_pct DESC) AS severity_rank
        FROM (
            -- Inner summary: one row per condition
            SELECT
                {label_col}                                           AS condition,
                COUNT(DISTINCT a.ACCIDENT_NO)                         AS total_accidents,
                SUM(CASE WHEN a.NO_PERSONS_KILLED > 0 THEN 1 ELSE 0 END)
                                                                      AS fatal_count,
                ROUND(
                    100.0 * SUM(CASE WHEN a.NO_PERSONS_KILLED > 0 THEN 1 ELSE 0 END)
                          / COUNT(DISTINCT a.ACCIDENT_NO),
                    2
                )                                                     AS fatal_pct,
                ROUND(AVG(a.NO_PERSONS), 2)                           AS avg_persons
            FROM Accident a
            {join_sql}
            WHERE {exclude_filter}
            GROUP BY {group_col}
        ) inner_summary
        WHERE total_accidents > (
            -- Nested subquery: statewide average accident count per condition
            SELECT AVG(cond_count)
            FROM (
                SELECT COUNT(DISTINCT a.ACCIDENT_NO) AS cond_count
                FROM Accident a
                {join_sql}
                WHERE {exclude_filter}
                GROUP BY {group_col}
            )
        )
        {high_only_filter}
        ORDER BY fatal_pct DESC
    """

    rows = query_db(sql)

    # Statewide average for the chart reference line
    avg_sql = f"""
        SELECT AVG(cond_count) AS statewide_avg
        FROM (
            SELECT COUNT(DISTINCT a.ACCIDENT_NO) AS cond_count
            FROM Accident a
            {join_sql}
            WHERE {exclude_filter}
            GROUP BY {group_col}
        )
    """
    avg_row = query_db(avg_sql)
    avg_val = round(avg_row[0]["statewide_avg"], 1) if avg_row else 0

    return jsonify({"rows": rows, "statewide_avg": avg_val})


# ------------------------------------------------------------------ #
# Run
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    app.run(debug=True)
