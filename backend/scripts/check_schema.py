"""Quick schema check for the dev database.

Confirms the migration applied: run after `alembic upgrade head`.
"""

import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "data" / "dolfin.db"
con = sqlite3.connect(db)

tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
print(f"database: {db}")
print(f"tables ({len(tables)}): {', '.join(sorted(tables))}")
print()

checks = {
    "portfolio_snapshots table": "portfolio_snapshots" in tables,
}

for table, column in [
    ("intervention_logs", "preview_id"),
    ("intervention_logs", "user_action"),
    ("reflections", "preview_id"),
]:
    if table in tables:
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        checks[f"{table}.{column}"] = column in cols

if "alembic_version" in tables:
    versions = [r[0] for r in con.execute("SELECT version_num FROM alembic_version")]
    checks["alembic stamped"] = bool(versions)
    print(f"alembic version: {versions}")

nulls = 0
if "intervention_logs" in tables:
    nulls = con.execute(
        "SELECT COUNT(*) FROM intervention_logs WHERE user_action IS NULL"
    ).fetchone()[0]
    checks["no NULL user_action"] = nulls == 0

print()
for name, ok in checks.items():
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")

con.close()
print()
print("all good" if all(checks.values()) else "some checks failed")
