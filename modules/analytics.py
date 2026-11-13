"""Database-driven analytics. Every number is computed from SQLite."""
from modules.complaint_classifier import CATEGORIES
from modules.priority_manager import PRIORITIES
from modules.complaint_manager import STATUSES


def _date_filter(date_from=None, date_to=None, alias="c"):
    clauses, params = [], []
    if date_from:
        clauses.append(f"date({alias}.submission_time) >= date(?)")
        params.append(date_from)
    if date_to:
        clauses.append(f"date({alias}.submission_time) <= date(?)")
        params.append(date_to)
    return clauses, params


def _where(clauses):
    return (" WHERE " + " AND ".join(clauses)) if clauses else ""


def overview(conn, date_from=None, date_to=None):
    clauses, params = _date_filter(date_from, date_to)
    row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(c.status = 'Resolved'), 0) AS resolved, "
        "COALESCE(SUM(c.status != 'Resolved'), 0) AS unresolved, "
        "COALESCE(SUM(c.status = 'Pending'), 0) AS pending, "
        "COALESCE(SUM(c.priority = 'Critical'), 0) AS critical, "
        "COALESCE(SUM(c.priority = 'Critical' AND c.status != 'Resolved'), 0) AS critical_open, "
        "AVG(CASE WHEN c.status = 'Resolved' AND c.resolved_time IS NOT NULL "
        "    THEN (julianday(c.resolved_time) - julianday(c.submission_time)) * 24.0 END) AS avg_hours "
        "FROM complaints c" + _where(clauses), params).fetchone()
    waiting = conn.execute("SELECT COUNT(*) AS n FROM waiting_queue").fetchone()["n"]
    total = row["total"] or 0
    return {
        "total": total,
        "resolved": row["resolved"],
        "unresolved": row["unresolved"],
        "pending": row["pending"],
        "critical": row["critical"],
        "critical_open": row["critical_open"],
        "waiting_queue": waiting,
        "avg_resolution_hours": round(row["avg_hours"], 2) if row["avg_hours"] is not None else None,
        "resolution_rate": round(100.0 * row["resolved"] / total, 1) if total else 0.0,
    }


def by_zone(conn, date_from=None, date_to=None):
    clauses, params = _date_filter(date_from, date_to)
    join_cond = "c.location_code = z.location_code" + "".join(" AND " + c for c in clauses)
    rows = conn.execute(
        "SELECT z.location_code, z.location_name, COUNT(c.id) AS total, "
        "COALESCE(SUM(c.status = 'Resolved'), 0) AS resolved, "
        "COALESCE(SUM(c.status != 'Resolved'), 0) AS unresolved, "
        "COALESCE(SUM(c.priority = 'Critical'), 0) AS critical "
        f"FROM campus_zones z LEFT JOIN complaints c ON {join_cond} "
        "GROUP BY z.id ORDER BY z.id", params).fetchall()
    return [dict(r) for r in rows]


def _grouped(conn, column, keys, date_from, date_to):
    clauses, params = _date_filter(date_from, date_to)
    rows = conn.execute(f"SELECT c.{column} AS k, COUNT(*) AS n FROM complaints c"
                        + _where(clauses) + f" GROUP BY c.{column}", params).fetchall()
    found = {r["k"]: r["n"] for r in rows}
    return [{"label": k, "count": found.get(k, 0)} for k in keys]


def by_category(conn, date_from=None, date_to=None):
    return _grouped(conn, "category", CATEGORIES, date_from, date_to)


def by_priority(conn, date_from=None, date_to=None):
    return _grouped(conn, "priority", PRIORITIES, date_from, date_to)


def by_status(conn, date_from=None, date_to=None):
    return _grouped(conn, "status", STATUSES, date_from, date_to)


def timeline(conn, date_from=None, date_to=None, days=30):
    clauses, params = _date_filter(date_from, date_to)
    if not clauses:
        clauses.append("date(c.submission_time) >= date('now', 'localtime', ?)")
        params.append(f"-{int(days)} days")
    rows = conn.execute(
        "SELECT date(c.submission_time) AS day, COUNT(*) AS submitted, "
        "COALESCE(SUM(c.status = 'Resolved'), 0) AS resolved FROM complaints c"
        + _where(clauses) + " GROUP BY day ORDER BY day", params).fetchall()
    return [dict(r) for r in rows]


def full_report(conn, date_from=None, date_to=None):
    return {
        "overview": overview(conn, date_from, date_to),
        "zones": by_zone(conn, date_from, date_to),
        "categories": by_category(conn, date_from, date_to),
        "priorities": by_priority(conn, date_from, date_to),
        "statuses": by_status(conn, date_from, date_to),
        "timeline": timeline(conn, date_from, date_to),
    }
