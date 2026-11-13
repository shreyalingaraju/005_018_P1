"""
Complaint persistence, status lifecycle and history.

Lifecycle:  Pending -> Assigned -> In Progress -> Resolved
  * Pending -> Assigned       : only via the routing engine / reassignment
  * Assigned -> In Progress   : administrator action
  * In Progress -> Resolved   : administrator action
"""
import secrets
import string
from datetime import datetime

from modules.utils import AppError, from_json, now_str, to_json, write_audit

PENDING = "Pending"
ASSIGNED = "Assigned"
IN_PROGRESS = "In Progress"
RESOLVED = "Resolved"
STATUSES = (PENDING, ASSIGNED, IN_PROGRESS, RESOLVED)

# Every legal transition of the lifecycle state machine.
ALLOWED_TRANSITIONS = {
    PENDING: {ASSIGNED},
    ASSIGNED: {IN_PROGRESS},
    IN_PROGRESS: {RESOLVED},
    RESOLVED: set(),
}
# Transitions an administrator may perform manually.
MANUAL_TRANSITIONS = {(ASSIGNED, IN_PROGRESS), (IN_PROGRESS, RESOLVED)}

_ID_ALPHABET = string.ascii_uppercase + string.digits

_COMPLAINT_SELECT = """
SELECT c.*, a.name AS admin_name, a.admin_code AS admin_code, a.availability AS admin_availability,
       a.admin_role AS admin_role, z.location_name AS location_name
FROM complaints c
LEFT JOIN administrators a ON a.id = c.assigned_admin_id
LEFT JOIN campus_zones z ON z.location_code = c.location_code
"""


def generate_complaint_id(conn, when=None):
    date_part = (when or datetime.now()).strftime("%Y%m%d")
    while True:
        suffix = "".join(secrets.choice(_ID_ALPHABET) for _ in range(6))
        cid = f"CNFR-{date_part}-{suffix}"
        if not conn.execute("SELECT 1 FROM complaints WHERE complaint_id = ?", (cid,)).fetchone():
            return cid


def serialize(row):
    if row is None:
        return None
    d = dict(row)
    d["matched_keywords"] = from_json(d.get("matched_keywords"), {})
    d["detected_categories"] = from_json(d.get("detected_categories"), [])
    if not d.get("location_name"):
        d["location_name"] = "Unregistered zone"
    return d


def add_history(conn, complaint_pk, action, previous_status, new_status, remarks=None, actor=None,
                changed_at=None):
    conn.execute(
        "INSERT INTO complaint_history (complaint_id, action, previous_status, new_status, changed_by, "
        "changed_by_name, remarks, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (complaint_pk, action, previous_status, new_status,
         actor["id"] if actor else None, actor["name"] if actor else "Routing Engine",
         remarks, changed_at or now_str()),
    )


def find_open_duplicate(conn, user_id, identifier, description):
    """An unresolved complaint by the same user, same location and same text."""
    norm = " ".join((description or "").lower().split())
    rows = conn.execute(
        "SELECT complaint_id, description FROM complaints WHERE user_id = ? AND identifier = ? "
        "AND status != 'Resolved'", (user_id, identifier)).fetchall()
    for r in rows:
        if " ".join(r["description"].lower().split()) == norm:
            return r["complaint_id"]
    return None


def insert_complaint(conn, data, actor=None, submitted_at=None):
    """Insert a new complaint in Pending state. Returns the integer primary key."""
    ts = submitted_at or now_str()
    complaint_id = data.get("complaint_id") or generate_complaint_id(conn)
    cur = conn.execute(
        "INSERT INTO complaints (complaint_id, user_id, user_name, institutional_id, device_type, "
        "location_code, floor_number, identifier, description, category, matched_keywords, "
        "detected_categories, priority, priority_rank, status, submission_time, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)",
        (complaint_id, data["user_id"], data["user_name"], data["institutional_id"],
         data["device_type"], data["location_code"], data["floor_number"], data["identifier"],
         data["description"], data["category"], to_json(data.get("matched_keywords", {})),
         to_json(data.get("detected_categories", [])), data["priority"], data["priority_rank"],
         ts, ts),
    )
    add_history(conn, cur.lastrowid, "CREATED", None, PENDING,
                "Complaint registered and validated (DFA + regex).", actor, ts)
    return cur.lastrowid


def get_by_pk(conn, pk):
    return serialize(conn.execute(_COMPLAINT_SELECT + " WHERE c.id = ?", (pk,)).fetchone())


def get_complaint(conn, complaint_id):
    return serialize(conn.execute(_COMPLAINT_SELECT + " WHERE c.complaint_id = ?",
                                  ((complaint_id or "").strip().upper(),)).fetchone())


def list_complaints(conn, user_id=None, admin_id=None, status=None, category=None, priority=None,
                    zone=None, search=None, limit=500):
    where, params = [], []
    if user_id is not None:
        where.append("c.user_id = ?"); params.append(user_id)
    if admin_id is not None:
        where.append("c.assigned_admin_id = ?"); params.append(admin_id)
    if status:
        where.append("c.status = ?"); params.append(status)
    if category:
        where.append("c.category = ?"); params.append(category)
    if priority:
        where.append("c.priority = ?"); params.append(priority)
    if zone:
        where.append("c.location_code = ?"); params.append(zone)
    if search:
        where.append("(c.complaint_id LIKE ? OR c.identifier LIKE ? OR c.description LIKE ?)")
        like = f"%{search.strip()}%"
        params += [like, like, like]
    sql = _COMPLAINT_SELECT + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY c.submission_time DESC, c.id DESC LIMIT ?"
    params.append(int(limit))
    return [serialize(r) for r in conn.execute(sql, params).fetchall()]


def status_counts(conn, user_id=None, admin_id=None):
    where, params = "", ()
    if user_id is not None:
        where, params = "WHERE user_id = ?", (user_id,)
    elif admin_id is not None:
        where, params = "WHERE assigned_admin_id = ?", (admin_id,)
    rows = conn.execute(f"SELECT status, COUNT(*) AS n FROM complaints {where} GROUP BY status",
                        params).fetchall()
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    counts["Total"] = sum(counts[s] for s in STATUSES)
    return counts


def get_history(conn, complaint_pk):
    rows = conn.execute("SELECT * FROM complaint_history WHERE complaint_id = ? ORDER BY changed_at, id",
                        (complaint_pk,)).fetchall()
    return [dict(r) for r in rows]


def mark_assigned(conn, complaint, admin, remarks, actor=None, action="ASSIGNED", routed_zone=None):
    """
    Atomically move a Pending complaint to Assigned.

    The UPDATE is guarded by `status='Pending' AND assigned_admin_id IS NULL`
    so the same complaint can never be assigned twice, even under concurrency.
    """
    ts = now_str()
    cur = conn.execute(
        "UPDATE complaints SET status = 'Assigned', assigned_admin_id = ?, assigned_time = ?, "
        "routed_zone = COALESCE(?, routed_zone), updated_at = ? "
        "WHERE id = ? AND status = 'Pending' AND assigned_admin_id IS NULL",
        (admin["id"], ts, routed_zone, ts, complaint["id"]),
    )
    if cur.rowcount != 1:
        return False
    conn.execute("DELETE FROM waiting_queue WHERE complaint_id = ?", (complaint["id"],))
    add_history(conn, complaint["id"], action, PENDING, ASSIGNED, remarks, actor, ts)
    return True


def can_manage(complaint, user, admin):
    """Central admins manage everything; administrators only their own complaints."""
    if user is None:
        return False
    if user["role"] == "central_admin":
        return True
    return (user["role"] == "administrator" and admin is not None
            and complaint["assigned_admin_id"] == admin["id"])


def can_view(complaint, user, admin):
    if user is None:
        return False
    if user["role"] == "central_admin":
        return True
    if user["role"] == "user":
        return complaint["user_id"] == user["id"]
    return admin is not None and complaint["assigned_admin_id"] == admin["id"]


def update_status(conn, complaint_id, new_status, user, admin, remarks=None):
    complaint = get_complaint(conn, complaint_id)
    if complaint is None:
        raise AppError("Complaint not found.", 404)
    if not can_manage(complaint, user, admin):
        raise AppError("You are not authorised to update this complaint.", 403)
    if new_status not in STATUSES:
        raise AppError(f"Unknown status '{new_status}'.", 400)
    current = complaint["status"]
    if (current, new_status) not in MANUAL_TRANSITIONS:
        allowed = ", ".join(sorted(ALLOWED_TRANSITIONS[current])) or "none (final state)"
        raise AppError(f"Invalid status transition {current} -> {new_status}. "
                       f"Allowed next status: {allowed}.", 409)
    ts = now_str()
    extra = ", in_progress_time = ?" if new_status == IN_PROGRESS else ", resolved_time = ?"
    cur = conn.execute(
        f"UPDATE complaints SET status = ?, updated_at = ?{extra} WHERE id = ? AND status = ?",
        (new_status, ts, ts, complaint["id"], current),
    )
    if cur.rowcount != 1:
        raise AppError("Complaint was modified concurrently; please refresh.", 409)
    add_history(conn, complaint["id"], "STATUS_CHANGE", current, new_status,
                (remarks or "").strip()[:500] or None, user, ts)
    write_audit(conn, "STATUS_CHANGE", "complaint", complaint["complaint_id"],
                f"{current} -> {new_status}", user)
    return get_complaint(conn, complaint["complaint_id"])
