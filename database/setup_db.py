"""
database/setup_db.py
====================
Sets up the SQLite database for the Road Incidents Explorer.

The real Victorian road-accidents DB is already structured with proper
relational tables. This script:

  1. Copies the provided .db file to road_incidents.db (if needed).
  2. Creates the FACTS table (required by the spec to store landing-page
     stats in the DB).
  3. Derives and seeds four FACTS rows from the real accident data.

Usage
-----
    python database/setup_db.py          # set up FACTS table
    python database/setup_db.py --reset  # drop and re-seed FACTS

Real DB table overview
-----------------------
  Accident            — 177,867 incidents (primary table)
  Surface_Cond_Seq    — M:M link to Road_Surface_Cond
  Road_Surface_Cond   — lookup: Dry, Wet, Muddy, Snowy, Icy, Unk.
  Atmospheric_Cond_Seq— M:M link to Amospheric_Cond
  Amospheric_Cond     — lookup: Clear, Raining, Fog, etc.
  Light_Condition     — lookup: Day, Dusk/dawn, Dark …
  Person              — 413,966 person records with INJ_LEVEL
  Injury              — lookup: 1=Fatality, 2=Serious, 3=Other, 4=Not injured
  Vehicle             — 324,548 vehicle records
  Node                — geographic info (lat/lon, LGA, postcode)
"""

import sqlite3
import os
import sys
import shutil

# ------------------------------------------------------------------ #
# Path configuration
# ------------------------------------------------------------------ #

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

DB_PATH = os.path.join(_ROOT, "database/Road_Accidents.db")  # Working DB file used by app.py

# Path to the provided source DB — update if yours has a different name
_SOURCE_DB = os.path.join(_ROOT, "database/Road_Accidents.db")


# ------------------------------------------------------------------ #
# Connection helper (imported by app.py)
# ------------------------------------------------------------------ #

def get_db() -> sqlite3.Connection:
    """Return an open SQLite connection with row_factory set to Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ------------------------------------------------------------------ #
# Ensure the working DB file exists
# ------------------------------------------------------------------ #

def _ensure_db_file() -> None:
    """
    Copy the source DB to road_incidents.db if it doesn't already exist.
    If neither file exists, raise a helpful error.
    """
    if os.path.exists(DB_PATH):
        return

    if os.path.exists(_SOURCE_DB):
        print(f"Copying {os.path.basename(_SOURCE_DB)} → road_incidents.db …")
        shutil.copy2(_SOURCE_DB, DB_PATH)
        print("  Done.")
        return

    raise FileNotFoundError(
        f"No database file found.\n"
        f"Expected one of:\n"
        f"  {DB_PATH}\n"
        f"  {_SOURCE_DB}\n"
        f"Place the provided .db file in the project root and rename it\n"
        f"'road_incidents.db', or update _SOURCE_DB in setup_db.py."
    )


# ------------------------------------------------------------------ #
# FACTS table
# ------------------------------------------------------------------ #

DDL_FACTS = """
CREATE TABLE IF NOT EXISTS FACTS (
    ID          INTEGER PRIMARY KEY AUTOINCREMENT,
    LABEL       TEXT    NOT NULL,
    VALUE       TEXT    NOT NULL,
    DESCRIPTION TEXT
);
"""


def seed_facts(conn: sqlite3.Connection) -> None:
    """
    Derive four landing-page facts from the real accident data and
    insert them into the FACTS table.

    Facts chosen:
      1. Total incidents recorded
      2. Total fatalities (persons with INJ_LEVEL = 1)
      3. Most common road surface condition
      4. Proportion of incidents that occurred in daylight
    """
    conn.execute("DELETE FROM FACTS")

    facts_to_insert = []

    # 1. Total incidents
    total = conn.execute("SELECT COUNT(*) FROM Accident").fetchone()[0]
    facts_to_insert.append((
        "Total Incidents",
        f"{total:,}",
        "Total road incidents recorded in the Victorian dataset",
    ))

    # 2. Total fatalities (person-level)
    fatalities = conn.execute(
        "SELECT COUNT(*) FROM Person WHERE INJ_LEVEL = 1"
    ).fetchone()[0]
    facts_to_insert.append((
        "Lives Lost",
        f"{fatalities:,}",
        "People killed across all recorded incidents",
    ))

    # 3. Most common road surface
    surface_row = conn.execute("""
        SELECT rsc.SURFACE_COND_DESC, COUNT(*) AS cnt
        FROM Surface_Cond_Seq s
        JOIN Road_Surface_Cond rsc ON s.SURFACE_COND = rsc.SURFACE_COND
        WHERE rsc.SURFACE_COND_DESC != 'Unk.'
        GROUP BY rsc.SURFACE_COND_DESC
        ORDER BY cnt DESC
        LIMIT 1
    """).fetchone()
    surface_label = surface_row[0] if surface_row else "Unknown"
    facts_to_insert.append((
        "Most Common Surface",
        surface_label,
        "Road surface condition present in the most incidents",
    ))

    # 4. Daytime incidents percentage
    day_count = conn.execute("""
        SELECT COUNT(*) FROM Accident
        WHERE LIGHT_CONDITION = 1
    """).fetchone()[0]
    day_pct = round(100.0 * day_count / total, 1) if total else 0
    facts_to_insert.append((
        "Daytime Incidents",
        f"{day_pct}%",
        "Proportion of incidents that occurred during daylight hours",
    ))

    conn.executemany(
        "INSERT INTO FACTS (LABEL, VALUE, DESCRIPTION) VALUES (?, ?, ?)",
        facts_to_insert,
    )
    print(f"  Seeded {len(facts_to_insert)} facts into FACTS table.")
    for label, value, _ in facts_to_insert:
        print(f"    {label}: {value}")


# ------------------------------------------------------------------ #
# Public entry point
# ------------------------------------------------------------------ #

def setup(reset: bool = False) -> None:
    """Ensure DB exists, create FACTS table, seed it."""
    _ensure_db_file()

    conn = get_db()
    try:
        if reset:
            print("Dropping FACTS table …")
            conn.execute("DROP TABLE IF EXISTS FACTS")

        print("Creating FACTS table …")
        conn.execute(DDL_FACTS)
        conn.commit()

        print("Seeding FACTS …")
        seed_facts(conn)
        conn.commit()

        print(f"\nDone. Database ready at: {DB_PATH}")
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# CLI
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    if reset_flag:
        confirm = input("Drop and re-seed the FACTS table? [y/N] ")
        if confirm.strip().lower() != "y":
            print("Aborted.")
            sys.exit(0)
    setup(reset=reset_flag)
