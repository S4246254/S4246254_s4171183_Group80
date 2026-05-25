# Victorian Road Incidents Explorer — Sub-Task A

Programming Studio S1 2026 | RMIT University

## Project structure

```
road_incidents/
├── app.py                  # Flask app — all routes
├── requirements.txt
├── database/
│   └── setup_db.py         # DB creation, seeding, get_db() helper
├── templates/
│   ├── base.html           # Shared layout, nav, header, footer
│   ├── landing.html        # Level 1 — Landing page (4 facts from DB)
│   ├── conditions.html     # Level 2 — Conditions summary (aggregate SQL)
│   └── deepdive.html       # Level 3 — Deep dive (nested SQL)
└── static/
    ├── css/style.css
    └── js/
        ├── main.js         # Shared utilities
        ├── conditions.js   # Level 2 JS + Chart.js
        └── deepdive.js     # Level 3 JS + Chart.js
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up and seed the database (placeholder data)
python database/setup_db.py

# 3. Run the app
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## Swapping in the real RMIT database

1. Place the provided `.db` file in the project root and rename it to `road_incidents.db`
   (or update `DB_PATH` in `database/setup_db.py` to match your filename).

2. Check the real column names in your DB:
   ```python
   import sqlite3
   conn = sqlite3.connect("road_incidents.db")
   print(conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
   # Then for each table:
   print(conn.execute("PRAGMA table_info(ACCIDENT)").fetchall())
   ```

3. Update `VALID_COLS` in `app.py` and the SQL in `api_level2` / `api_level3`
   to match the real column names.

4. Update or remove `setup_db.py` seed data — the FACTS table still needs to be
   populated as the spec requires facts to be stored in and retrieved from the DB.

## Pages

| URL           | Level | Description                                      |
|---------------|-------|--------------------------------------------------|
| `/`           | 1     | Landing page — 4 key facts from DB              |
| `/conditions` | 2     | Filter by road/atmospheric/light, aggregated SQL |
| `/deepdive`   | 3     | Nested query — above-average risk conditions     |

## SQL approach

**Level 2** uses: `JOIN`, `GROUP BY`, `HAVING`, `ORDER BY`, `COUNT`, `AVG`, `SUM`

**Level 3** uses: nested subquery in `WHERE` clause — the outer query filters on the
result of an inner `AVG(COUNT(...))` subquery, satisfying the "use results of one
query as input to another" requirement.
