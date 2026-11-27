"""Read a compact personal notification center from committed portfolio decisions."""

from .store import timestamp


def recent(db, category):
    groups = {"warnings": ("incomplete", "unavailable"), "trades": ("entry", "exit")}
    if category not in groups:
        raise ValueError("Select observation warnings or simulated fills.")
    # One notice per portfolio and event type. Older outages remain in history
    # after a recovery. The run detail and overview show current state.
    records = db.execute("""WITH latest AS (
        SELECT run_id, kind, count(*) AS occurrences, max(revision) AS revision
        FROM public_decisions WHERE kind IN (?,?) GROUP BY run_id,kind
    ) SELECT r.id, r.wallet, r.name, r.status, d.kind, d.recorded, d.reason, d.revision,
             l.occurrences FROM latest l JOIN public_runs r ON r.id=l.run_id
             JOIN public_decisions d ON d.run_id=l.run_id AND d.revision=l.revision
             ORDER BY d.rowid DESC LIMIT 21""", groups[category]).fetchall()
    return {"checkedAt": timestamp(), "category": category, "more": len(records) > 20,
            "items": [dict(row) for row in records[:20]]}
