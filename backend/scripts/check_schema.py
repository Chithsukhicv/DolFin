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

# The AI reasoning layer's tables. A missing one of these only surfaces as a
# runtime error the first time someone uses the feature, which is a bad place to
# find out a migration was skipped.
for table in [
    "knowledge_chunks",
    "ai_findings",
    "pattern_analyses",
    "chat_sessions",
    "chat_messages",
    "generated_questions",
]:
    checks[f"{table} table"] = table in tables

for table, column in [
    ("intervention_logs", "preview_id"),
    ("intervention_logs", "user_action"),
    ("reflections", "preview_id"),
    # Reflection analysis: the AI's read on what the learner wrote.
    ("reflections", "reasoning_class"),
    ("reflections", "ai_response"),
    ("reflections", "ai_citations"),
    ("reflections", "ai_mode"),
    # Corpus B isolation depends on this column existing and being populated.
    ("knowledge_chunks", "owner_user_id"),
    ("knowledge_chunks", "embedding"),
    ("ai_findings", "source"),
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

# Every Corpus B chunk must have an owner. A null here is the exact shape of the
# bug that would let one learner's trade history reach another learner's prompt,
# because the retriever's owner filter would not match it to anyone.
if "knowledge_chunks" in tables:
    orphans = con.execute(
        "SELECT COUNT(*) FROM knowledge_chunks "
        "WHERE corpus = 'B' AND owner_user_id IS NULL"
    ).fetchone()[0]
    checks["no unowned Corpus B chunks"] = orphans == 0

    counts = dict(
        con.execute("SELECT corpus, COUNT(*) FROM knowledge_chunks GROUP BY corpus")
    )
    print(f"corpus sizes: {counts or 'not indexed yet'}")
    checks["Corpus A indexed"] = counts.get("A", 0) >= 80

print()
for name, ok in checks.items():
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")

con.close()
print()
print("all good" if all(checks.values()) else "some checks failed")
