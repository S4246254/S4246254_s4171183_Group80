"""
app.py — Main Flask application for Sub-Task A: Road Incidents Explorer
Covers Level 1 (Landing), Level 2 (Conditions Summary), Level 3 (Deep Dive)
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from database.setup_db import get_db, setup, DB_PATH

app = Flask(__name__)

# Create DB if it doesn't exist yet
if not os.path.exists(DB_PATH):
    setup()


# ------------------------------------------------------------------ #
# Helper
# ------------------------------------------------------------------ #
def query_db(sql, args=()):
    """Execute a SELECT query and return list of dicts."""
    conn = get_db()
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ #
# Page routes
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    """Level 1 — Landing page. Facts retrieved from DB."""
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


# ------------------------------------------------------------------ #
# API routes (called by JS fetch)
# ------------------------------------------------------------------ #

VALID_COLS = {
    "road":  "ROAD_SURFACE",
    "atmos": "ATMOSPHERIC",
    "light": "LIGHT_COND",
}


@app.route("/api/level2")
def api_level2():
    """
    Level 2: Aggregate accident counts by a chosen condition column.
    Joins, aggregates, filters and sorts — satisfies spec requirements.
    Query params:
        dim      = road | atmos | light
        min_count = integer (minimum accidents to include)
    """
    dim = request.args.get("dim", "road")
    min_count = int(request.args.get("min_count", 0))

    col = VALID_COLS.get(dim, "ROAD_SURFACE")

    sql = f"""
        SELECT
            {col}                          AS condition,
            COUNT(*)                       AS total_accidents,
            SUM(FATALITY)                  AS fatal_count,
            ROUND(AVG(SEVERITY), 2)        AS avg_severity,
            ROUND(
                100.0 * SUM(FATALITY) / COUNT(*), 2
            )                              AS fatal_pct
        FROM ACCIDENT
        WHERE {col} IS NOT NULL
          AND {col} != ''
        GROUP BY {col}
        HAVING COUNT(*) >= ?
        ORDER BY total_accidents DESC
    """
    rows = query_db(sql, (min_count,))
    return jsonify(rows)


@app.route("/api/level3")
def api_level3():
    """
    Level 3: Identify conditions whose accident count is ABOVE the
    statewide per-condition average — using a nested (subquery) approach.

    Outer query filters on the result of the inner average calculation,
    then ranks by severity index descending.

    Query params:
        dim       = road | atmos | light
        high_only = true  (optional — only show high-severity results)
    """
    dim = request.args.get("dim", "road")
    high_only = request.args.get("high_only", "false").lower() == "true"

    col = VALID_COLS.get(dim, "ROAD_SURFACE")

    sev_filter = "AND avg_severity < 2.5" if high_only else ""

    sql = f"""
        SELECT
            condition,
            total_accidents,
            fatal_count,
            fatal_pct,
            avg_severity,
            RANK() OVER (ORDER BY avg_severity ASC) AS severity_rank
        FROM (
            -- Inner query: summarise per condition
            SELECT
                {col}                             AS condition,
                COUNT(*)                          AS total_accidents,
                SUM(FATALITY)                     AS fatal_count,
                ROUND(100.0 * SUM(FATALITY) / COUNT(*), 2) AS fatal_pct,
                ROUND(AVG(SEVERITY), 2)           AS avg_severity
            FROM ACCIDENT
            WHERE {col} IS NOT NULL AND {col} != ''
            GROUP BY {col}
        ) inner_summary
        WHERE total_accidents > (
            -- Nested subquery: statewide average count per condition
            SELECT AVG(cond_count)
            FROM (
                SELECT COUNT(*) AS cond_count
                FROM ACCIDENT
                WHERE {col} IS NOT NULL AND {col} != ''
                GROUP BY {col}
            )
        )
        {sev_filter}
        ORDER BY avg_severity ASC
    """
    rows = query_db(sql)

    # Also return the statewide average for reference line in chart
    avg_sql = f"""
        SELECT AVG(cond_count) AS statewide_avg
        FROM (
            SELECT COUNT(*) AS cond_count
            FROM ACCIDENT
            WHERE {col} IS NOT NULL AND {col} != ''
            GROUP BY {col}
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
