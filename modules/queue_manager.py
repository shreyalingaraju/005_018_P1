"""
Priority-based waiting queue (persisted in SQLite).

Ordering: priority_rank ASC (Critical first), then created_at ASC (FIFO),
then id ASC as a deterministic tie-breaker for identical timestamps.
"""
from modules.utils import now_str

QUEUE_ORDER = "q.priority_rank ASC, q.created_at ASC, q.id ASC"


def enqueue(conn, complaint_pk, zone_code, priority, priority_rank, created_at=None):
    conn.execute(
        "INSERT OR IGNORE INTO waiting_queue (complaint_id, zone_code, priority, priority_rank, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (complaint_pk, zone_code, priority, priority_rank, created_at or now_str()),
    )
    recompute_positions(conn, zone_code)


def remove(conn, complaint_pk):
    row = conn.execute("SELECT zone_code FROM waiting_queue WHERE complaint_id = ?",
                       (complaint_pk,)).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM waiting_queue WHERE complaint_id = ?", (complaint_pk,))
    recompute_positions(conn, row["zone_code"])
    return True


def recompute_positions(conn, zone_code):
    rows = conn.execute(
        f"SELECT q.id FROM waiting_queue q WHERE q.zone_code = ? ORDER BY {QUEUE_ORDER}",
        (zone_code,),
    ).fetchall()
    for position, row in enumerate(rows, start=1):
        conn.execute("UPDATE waiting_queue SET queue_position = ? WHERE id = ?", (position, row["id"]))


def zones_with_waiting(conn, zone_code=None):
    if zone_code:
        rows = conn.execute("SELECT DISTINCT zone_code FROM waiting_queue WHERE zone_code = ?",
                            (zone_code,)).fetchall()
    else:
        rows = conn.execute("SELECT DISTINCT zone_code FROM waiting_queue").fetchall()
    return [r["zone_code"] for r in rows]


def get_waiting(conn, zone_code=None):
    """Waiting complaints in processing order (optionally for one zone)."""
    sql = (
        "SELECT q.id AS queue_id, q.zone_code, q.priority, q.priority_rank, q.queue_position, "
        "q.created_at AS queued_at, c.id AS complaint_pk, c.complaint_id, c.identifier, "
        "c.category, c.description, c.user_name, c.submission_time, c.status "
        "FROM waiting_queue q JOIN complaints c ON c.id = q.complaint_id"
    )
    params = ()
    if zone_code:
        sql += " WHERE q.zone_code = ?"
        params = (zone_code,)
    sql += f" ORDER BY {QUEUE_ORDER}"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def queue_size(conn, zone_code=None):
    if zone_code:
        return conn.execute("SELECT COUNT(*) AS n FROM waiting_queue WHERE zone_code = ?",
                            (zone_code,)).fetchone()["n"]
    return conn.execute("SELECT COUNT(*) AS n FROM waiting_queue").fetchone()["n"]
