"""
setup_db.py — Creates and seeds road_incidents.db with placeholder data.
Replace this data with the real RMIT-provided database when available.
The table/column names below are modelled on the standard DTP schema.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "road_incidents.db")


def get_db():
    """Return a connection to the database. Used by Flask routes."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def setup():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ------------------------------------------------------------------ #
    # ACCIDENT table — one row per crash event
    # ------------------------------------------------------------------ #
    c.execute("""
        CREATE TABLE IF NOT EXISTS ACCIDENT (
            ACCIDENT_NO     TEXT PRIMARY KEY,
            ACCIDENT_DATE   TEXT,
            ACCIDENT_TYPE   TEXT,
            SEVERITY        INTEGER,          -- 1=Fatal 2=Serious 3=Other injury 4=PDO
            ROAD_SURFACE    TEXT,
            ATMOSPHERIC     TEXT,
            LIGHT_COND      TEXT,
            TOTAL_PERSONS   INTEGER,
            FATALITY        INTEGER DEFAULT 0
        )
    """)

    # ------------------------------------------------------------------ #
    # FACTS table — key statistics shown on the landing page (Level 1)
    # ------------------------------------------------------------------ #
    c.execute("""
        CREATE TABLE IF NOT EXISTS FACTS (
            FACT_ID     INTEGER PRIMARY KEY AUTOINCREMENT,
            LABEL       TEXT,
            VALUE       TEXT,
            DESCRIPTION TEXT
        )
    """)

    # ------------------------------------------------------------------ #
    # Seed FACTS (stored in DB as required by spec)
    # ------------------------------------------------------------------ #
    c.execute("DELETE FROM FACTS")
    facts = [
        ("Total crashes recorded",  "58,420",  "Across all of Victoria, 2019–2023"),
        ("Fatal incidents",         "1,247",   "Approx. 2.1% of all recorded crashes"),
        ("Wet road crashes",        "9,863",   "16.9% of crashes occur on wet road surface"),
        ("Night-time incidents",    "14,105",  "24.1% occur in darkness or at dusk/dawn"),
    ]
    c.executemany("INSERT INTO FACTS (LABEL, VALUE, DESCRIPTION) VALUES (?,?,?)", facts)

    # ------------------------------------------------------------------ #
    # Seed ACCIDENT rows (representative sample — replace with real data)
    # ------------------------------------------------------------------ #
    c.execute("DELETE FROM ACCIDENT")

    import random, datetime
    random.seed(42)

    road_surfaces  = ["Dry", "Wet", "Muddy", "Icy / Snowy", "Unpaved / gravel"]
    road_weights   = [0.65,  0.17,  0.021,   0.007,         0.015]
    atmospherics   = ["Clear", "Cloudy / overcast", "Raining", "Fog / mist", "Strong winds", "Smoke / dust"]
    atmos_weights  = [0.62,   0.187,               0.127,     0.015,         0.009,           0.003]
    light_conds    = ["Daylight", "Dusk / dawn", "Dark — street lit", "Dark — no lights"]
    light_weights  = [0.63,       0.074,          0.163,               0.090]
    acc_types      = ["Collision with vehicle", "Pedestrian", "Off road", "Rear end", "Side swipe"]

    rows = []
    start = datetime.date(2019, 1, 1)
    for i in range(3000):
        date = start + datetime.timedelta(days=random.randint(0, 1826))
        road = random.choices(road_surfaces, road_weights)[0]
        atm  = random.choices(atmospherics,  atmos_weights)[0]
        lght = random.choices(light_conds,    light_weights)[0]

        # Higher severity on bad roads/dark
        base_sev = 4
        if road in ("Wet", "Muddy"):          base_sev -= 1
        if road in ("Icy / Snowy", "Unpaved / gravel"): base_sev -= 2
        if lght in ("Dark — no lights",):     base_sev -= 1
        if atm  in ("Fog / mist", "Smoke / dust"):      base_sev -= 1
        sev = max(1, min(4, base_sev + random.randint(-1, 1)))
        fatal = 1 if sev == 1 else 0

        rows.append((
            f"ACC{i:05d}", str(date),
            random.choice(acc_types),
            sev, road, atm, lght,
            random.randint(1, 5), fatal
        ))

    c.executemany("""
        INSERT INTO ACCIDENT
        (ACCIDENT_NO, ACCIDENT_DATE, ACCIDENT_TYPE, SEVERITY,
         ROAD_SURFACE, ATMOSPHERIC, LIGHT_COND, TOTAL_PERSONS, FATALITY)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, rows)

    conn.commit()
    conn.close()
    print(f"Database created at {DB_PATH} with {len(rows)} accident rows.")


if __name__ == "__main__":
    setup()
