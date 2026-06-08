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

@app.route("/focused-view")
def focused_view():
    submitted   = "condition" in request.args
    condition   = request.args.get("condition", "injury")
    year_min    = int(request.args.get("year_min", 2013))
    year_max    = int(request.args.get("year_max", 2024))
    road_types  = request.args.getlist("road_type")
    speed_zones = request.args.getlist("speed_zone")
    deg_urbans  = request.args.getlist("deg_urban")
    lights      = request.args.getlist("light")
    polices     = request.args.getlist("police")
    surfaces    = request.args.getlist("surface")
    atmos_conds = request.args.getlist("atmos")

    CONDITION_CONFIG = {
        "injury": {
            "label":  "Injury Level",
            "select": "i.INJ_LEVEL_DESC",
            "join":   "JOIN Injury i ON p.INJ_LEVEL = i.INJ_LEVEL",
            "group":  "i.INJ_LEVEL",
            "filter": "",
        },
        "road_user": {
            "label":  "Road User Type",
            "select": "ru.ROAD_USER_TYPE_DESC",
            "join":   "JOIN Road_User ru ON p.ROAD_USER_TYPE = ru.ROAD_USER_TYPE",
            "group":  "ru.ROAD_USER_TYPE",
            "filter": "ru.ROAD_USER_TYPE_DESC != 'Not Known'",
        },
        "ejection": {
            "label":  "Ejection Outcome",
            "select": "e.EJECTED_DESC",
            "join":   "JOIN Ejection e ON p.EJECTED_CODE = e.EJECTED_CODE",
            "group":  "e.EJECTED_CODE",
            "filter": "e.EJECTED_CODE != 9",
        },
        "hospital": {
            "label":  "Taken to Hospital",
            "select": "CASE p.TAKEN_HOSPITAL WHEN 'Y' THEN 'Yes' WHEN 'N' THEN 'No' END",
            "join":   "",
            "group":  "p.TAKEN_HOSPITAL",
            "filter": "p.TAKEN_HOSPITAL IN ('Y', 'N')",
        },
        "helmet_belt": {
            "label":  "Helmet / Belt Worn",
            "select": "hb.HELMET_BELT_DESC",
            "join":   "JOIN Helmet_Belt hb ON p.HELMET_BELT_WORN = hb.HELMET_BELT_WORN",
            "group":  "hb.HELMET_BELT_WORN",
            "filter": "hb.HELMET_BELT_WORN != 9",
        },
        "age_group": {
            "label":  "Age Group",
            "select": "CASE p.AGE_GROUP WHEN '5-Dec' THEN '5-12' ELSE p.AGE_GROUP END",
            "join":   "",
            "group":  "p.AGE_GROUP",
            "filter": "p.AGE_GROUP IS NOT NULL AND p.AGE_GROUP != '' AND p.AGE_GROUP != 'Unknown'",
        },
        "sex": {
            "label":  "Sex",
            "select": "CASE p.SEX WHEN 'M' THEN 'Male' WHEN 'F' THEN 'Female' WHEN 'U' THEN 'Unknown' END",
            "join":   "",
            "group":  "p.SEX",
            "filter": "p.SEX IN ('M', 'F', 'U')",
        },
    }

    rows    = []
    summary = ""

    if submitted and condition in CONDITION_CONFIG:
        cfg = CONDITION_CONFIG[condition]

        where_clauses = [
            "CAST(SUBSTR(a.ACCIDENT_DATE, -4) AS INTEGER) BETWEEN ? AND ?"
        ]
        params = [year_min, year_max]

        if cfg["filter"]:
            where_clauses.append(cfg["filter"])

        if road_types:
            where_clauses.append(f"a.ROAD_TYPE IN ({','.join(['?'] * len(road_types))})")
            params.extend(road_types)

        if speed_zones:
            where_clauses.append(f"a.SPEED_ZONE IN ({','.join(['?'] * len(speed_zones))})")
            params.extend([int(s) for s in speed_zones])

        if deg_urbans:
            where_clauses.append(f"n.DEG_URBAN_NAME IN ({','.join(['?'] * len(deg_urbans))})")
            params.extend(deg_urbans)

        if lights:
            where_clauses.append(f"a.LIGHT_CONDITION IN ({','.join(['?'] * len(lights))})")
            params.extend([int(l) for l in lights])

        if polices:
            where_clauses.append(f"a.POLICE_ATTEND IN ({','.join(['?'] * len(polices))})")
            params.extend([int(pl) for pl in polices])

        if surfaces:
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM Surface_Cond_Seq scs "
                f"WHERE scs.ACCIDENT_NO = a.ACCIDENT_NO "
                f"AND scs.SURFACE_COND IN ({','.join(['?'] * len(surfaces))}))"
            )
            params.extend([int(s) for s in surfaces])

        if atmos_conds:
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM Atmospheric_Cond_Seq acs "
                f"WHERE acs.ACCIDENT_NO = a.ACCIDENT_NO "
                f"AND acs.ATMOSPH_COND IN ({','.join(['?'] * len(atmos_conds))}))"
            )
            params.extend([int(ac) for ac in atmos_conds])

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT
                {cfg["select"]}                                              AS condition_value,
                COUNT(*)                                                     AS total_people,
                COUNT(DISTINCT p.ACCIDENT_NO)                                AS total_accidents,
                SUM(CASE WHEN p.INJ_LEVEL = 1 THEN 1 ELSE 0 END)            AS fatalities,
                SUM(CASE WHEN p.TAKEN_HOSPITAL = 'Y' THEN 1 ELSE 0 END)     AS hospitalised
            FROM Person p
            JOIN Accident a   ON p.ACCIDENT_NO = a.ACCIDENT_NO
            LEFT JOIN Node n  ON a.NODE_ID     = n.NODE_ID
            {cfg["join"]}
            WHERE {where_sql}
            GROUP BY {cfg["group"]}
            ORDER BY total_people DESC
        """

        rows = query_db(sql, params)

        if rows:
            total_people = sum(r["total_people"] for r in rows)
            for r in rows:
                r["pct"] = round(100.0 * r["total_people"] / total_people, 1) if total_people else 0

            top = rows[0]

            active_filters = []
            if road_types:  active_filters.append(f"road types ({', '.join(t.title() for t in road_types)})")
            if speed_zones: active_filters.append(f"speed zones ({', '.join(speed_zones)} km/h)")
            if deg_urbans:  active_filters.append("urban classification")
            if lights:      active_filters.append("light conditions")
            if polices:     active_filters.append("police attendance")
            if surfaces:    active_filters.append("road surface")
            if atmos_conds: active_filters.append("atmospheric conditions")

            filter_text = f", filtered by {' and '.join(active_filters)}," if active_filters else ""

            summary = (
                f"Between {year_min} and {year_max}{filter_text} "
                f"{total_people:,} people were recorded across all matched crashes. "
                f"The most represented {cfg['label'].lower()} was "
                f"<strong>{top['condition_value']}</strong>, "
                f"accounting for {top['pct']}% of all involved people "
                f"({top['total_people']:,} individuals across {top['total_accidents']:,} accidents). "
                f"Within this group, {top['fatalities']:,} fatalities and "
                f"{top['hospitalised']:,} hospitalisations were recorded."
            )

    return render_template(
        "focused_view_people.html",
        submitted    = submitted,
        rows         = rows,
        summary      = summary,
        condition    = condition,
        year_min     = year_min,
        year_max     = year_max,
        road_types   = road_types,
        speed_zones  = speed_zones,
        deg_urbans   = deg_urbans,
        lights       = lights,
        polices      = polices,
        surfaces     = surfaces,
        atmos_conds  = atmos_conds,
    )

@app.route("/mission-statement")
def mission_statement():
    mission   = query_db("SELECT CONTENT FROM MISSION_CONTENT WHERE SECTION = 'mission'")
    personas  = query_db("SELECT * FROM PERSONAS ORDER BY PERSONA_KEY ASC")
    team      = query_db("SELECT FULL_NAME, STUDENT_ID FROM TEAM_MEMBERS ORDER BY ID ASC")
    how_conditions = query_db("SELECT CONTENT FROM MISSION_CONTENT WHERE SECTION = 'how_conditions'")
    how_deepdive   = query_db("SELECT CONTENT FROM MISSION_CONTENT WHERE SECTION = 'how_deepdive'")
    how_people     = query_db("SELECT CONTENT FROM MISSION_CONTENT WHERE SECTION = 'how_people'")
    how_hotspot    = query_db("SELECT CONTENT FROM MISSION_CONTENT WHERE SECTION = 'how_hotspot'")

    persona_map = {p["PERSONA_KEY"]: p for p in personas}

    return render_template(
        "mission_statement.html",
        mission_content = mission[0]["CONTENT"]  if mission  else "",
        persona_a       = persona_map.get("a"),
        persona_b       = persona_map.get("b"),
        team            = team,
        how_conditions  = how_conditions[0]["CONTENT"] if how_conditions else "",
        how_deepdive    = how_deepdive[0]["CONTENT"] if how_deepdive else "",
        how_people      = how_people[0]["CONTENT"] if how_people else "",
        how_hotspot     = how_hotspot[0]["CONTENT"] if how_hotspot else "",
    )

@app.route("/people-hotspot")
def people_hotspot():

    injury_opts      = query_db("SELECT INJ_LEVEL AS val, INJ_LEVEL_DESC AS label FROM Injury ORDER BY INJ_LEVEL")
    road_user_opts   = query_db("SELECT ROAD_USER_TYPE AS val, ROAD_USER_TYPE_DESC AS label FROM Road_User WHERE ROAD_USER_TYPE_DESC != 'Not Known' ORDER BY ROAD_USER_TYPE")
    ejection_opts    = query_db("SELECT EJECTED_CODE AS val, EJECTED_DESC AS label FROM Ejection WHERE EJECTED_CODE != 9 ORDER BY EJECTED_CODE")
    helmet_belt_opts = query_db("SELECT HELMET_BELT_WORN AS val, HELMET_BELT_DESC AS label FROM Helmet_Belt WHERE HELMET_BELT_WORN != 9 ORDER BY HELMET_BELT_WORN")
    age_group_opts   = query_db("""
        SELECT DISTINCT AGE_GROUP AS val,
               CASE AGE_GROUP WHEN '5-Dec' THEN '5-12' ELSE AGE_GROUP END AS label
        FROM Person
        WHERE AGE_GROUP IS NOT NULL AND AGE_GROUP != '' AND AGE_GROUP != 'Unknown'
        ORDER BY AGE_GROUP
    """)
    hospital_opts = [{"val": "Y", "label": "Yes"}, {"val": "N", "label": "No"}]
    sex_opts      = [{"val": "M", "label": "Male"}, {"val": "F", "label": "Female"}, {"val": "U", "label": "Unknown"}]

    ALL_OPTS = {
        "injury":      injury_opts,
        "road_user":   road_user_opts,
        "ejection":    ejection_opts,
        "hospital":    hospital_opts,
        "helmet_belt": helmet_belt_opts,
        "age_group":   age_group_opts,
        "sex":         sex_opts,
    }

    CONDITION_LABELS = {
        "injury":      "Injury Level",
        "road_user":   "Road User Type",
        "ejection":    "Ejection Outcome",
        "hospital":    "Taken to Hospital",
        "helmet_belt": "Helmet / Belt Worn",
        "age_group":   "Age Group",
        "sex":         "Sex",
    }

    CONDITION_WHERE = {
        "injury":      ("p.INJ_LEVEL = ?",        int),
        "road_user":   ("p.ROAD_USER_TYPE = ?",   int),
        "ejection":    ("p.EJECTED_CODE = ?",     int),
        "hospital":    ("p.TAKEN_HOSPITAL = ?",   str),
        "helmet_belt": ("p.HELMET_BELT_WORN = ?", int),
        "age_group":   ("p.AGE_GROUP = ?",        str),
        "sex":         ("p.SEX = ?",              str),
    }

    condition       = request.args.get("condition", "injury")
    condition_value = request.args.get("condition_value", "")
    year_min        = int(request.args.get("year_min", 2013))
    year_max        = int(request.args.get("year_max", 2024))
    show_second = "select_condition" in request.args
    submitted   = bool(request.args.get("condition_value", "")) and "select_condition" not in request.args and "condition" in request.args
    condition_chosen = "condition" in request.args

    if condition not in ALL_OPTS:
        condition = "injury"

    current_options = ALL_OPTS[condition]
    lga_rows        = []
    summary         = ""

    if submitted and condition in CONDITION_WHERE:
        where_clause, cast_fn = CONDITION_WHERE[condition]
        inner_where           = where_clause.replace("p.", "p2.")

        try:
            cv = cast_fn(condition_value)
        except (ValueError, TypeError):
            cv = condition_value

        if condition == "age_group" and condition_value == "5-12":
            cv = "5-Dec"

        sql = f"""
            SELECT
                lga_name,
                people_count,
                ROUND(
                    CAST(people_count AS FLOAT) / (
                        SELECT AVG(inner_cnt)
                        FROM (
                            SELECT COUNT(*) AS inner_cnt
                            FROM Person p2
                            JOIN Accident a2 ON p2.ACCIDENT_NO = a2.ACCIDENT_NO
                            LEFT JOIN Node n2  ON a2.NODE_ID   = n2.NODE_ID
                            WHERE {inner_where}
                            AND CAST(SUBSTR(a2.ACCIDENT_DATE, -4) AS INTEGER) BETWEEN ? AND ?
                            AND n2.LGA_NAME IS NOT NULL AND n2.LGA_NAME != ''
                            GROUP BY n2.LGA_NAME
                        )
                    ), 2
                ) AS density_index
            FROM (
                SELECT n.LGA_NAME AS lga_name, COUNT(*) AS people_count
                FROM Person p
                JOIN Accident a ON p.ACCIDENT_NO = a.ACCIDENT_NO
                LEFT JOIN Node n ON a.NODE_ID    = n.NODE_ID
                WHERE {where_clause}
                AND CAST(SUBSTR(a.ACCIDENT_DATE, -4) AS INTEGER) BETWEEN ? AND ?
                AND n.LGA_NAME IS NOT NULL AND n.LGA_NAME != ''
                GROUP BY n.LGA_NAME
            )
            ORDER BY density_index DESC
        """

        params   = [cv, year_min, year_max, cv, year_min, year_max]
        lga_rows = query_db(sql, params)

        def density_class(idx):
            if idx is None: return "hs-d1"
            if idx >= 2.0:  return "hs-d5"
            if idx >= 1.5:  return "hs-d4"
            if idx >= 1.0:  return "hs-d3"
            if idx >= 0.5:  return "hs-d2"
            return "hs-d1"

        for r in lga_rows:
            r["density_class"] = density_class(r["density_index"])
            r["lga_display"]   = r["lga_name"].title()
            r["density_str"]   = f"{r['density_index']:.2f}" if r["density_index"] else "N/A"

        if lga_rows:
            above_avg      = [r for r in lga_rows if r["density_index"] and r["density_index"] >= 1.0]
            top3           = lga_rows[:3]
            selected_label = condition_value

            for opt in current_options:
                if str(opt["val"]) == str(condition_value):
                    selected_label = opt["label"]
                    break

            summary = (
                f"Showing LGA density for <strong>{CONDITION_LABELS[condition]}: "
                f"{selected_label}</strong> between {year_min} and {year_max}. "
                f"Of {len(lga_rows)} LGAs with recorded incidents, "
                f"<strong>{len(above_avg)}</strong> exceed the statewide average "
                f"(density index ≥ 1.0). "
                f"Highest density LGAs: "
                f"<strong>{', '.join(r['lga_display'] for r in top3)}</strong> "
                f"with indices of "
                f"{', '.join(r['density_str'] for r in top3)} respectively."
            )

    return render_template(
        "people_hotspot.html",
        submitted        = submitted,
        show_second      = show_second,
        condition_chosen = condition_chosen,
        condition        = condition,
        condition_value  = str(condition_value),
        year_min         = year_min,
        year_max         = year_max,
        current_options  = current_options,
        lga_rows         = lga_rows,
        summary          = summary,
        condition_label  = CONDITION_LABELS.get(condition, "Condition"),
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
