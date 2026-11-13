"""Network administrator records (database is the source of truth)."""
from modules.utils import AppError, now_str, write_audit
from modules import user_manager

AVAILABLE = "Available"
BUSY = "Busy"
AVAILABILITY_VALUES = (AVAILABLE, BUSY)

_ADMIN_SELECT = """
SELECT a.id, a.user_id, a.admin_code, a.name, a.email, a.assigned_zone, a.admin_role,
       a.availability, a.is_active, a.created_at,
       (SELECT COUNT(*) FROM complaints c WHERE c.assigned_admin_id = a.id
            AND c.status IN ('Assigned','In Progress')) AS open_complaints,
       (SELECT COUNT(*) FROM complaints c WHERE c.assigned_admin_id = a.id
            AND c.status = 'Resolved') AS resolved_complaints
FROM administrators a
"""


def _as_dict(row):
    if row is None:
        return None
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    d["is_available"] = d["availability"] == AVAILABLE and d["is_active"]
    return d


def get_admin(conn, admin_id):
    return _as_dict(conn.execute(_ADMIN_SELECT + " WHERE a.id = ?", (admin_id,)).fetchone())


def get_admin_by_user(conn, user_id):
    return _as_dict(conn.execute(_ADMIN_SELECT + " WHERE a.user_id = ?", (user_id,)).fetchone())


def get_central_admin(conn):
    return _as_dict(conn.execute(
        _ADMIN_SELECT + " WHERE a.admin_role = 'central' AND a.is_active = 1 ORDER BY a.id LIMIT 1"
    ).fetchone())


def list_admins(conn):
    rows = conn.execute(_ADMIN_SELECT + " ORDER BY CASE a.admin_role WHEN 'central' THEN 0 "
                        "WHEN 'primary' THEN 1 ELSE 2 END, a.assigned_zone, a.id").fetchall()
    return [_as_dict(r) for r in rows]


def set_availability(conn, admin_id, availability, actor=None):
    if availability not in AVAILABILITY_VALUES:
        raise AppError("Availability must be 'Available' or 'Busy'.", 400)
    admin = get_admin(conn, admin_id)
    if admin is None:
        raise AppError("Administrator not found.", 404)
    if admin["availability"] != availability:
        conn.execute("UPDATE administrators SET availability = ? WHERE id = ?", (availability, admin_id))
        write_audit(conn, "AVAILABILITY_CHANGE", "administrator", admin["admin_code"],
                    f"{admin['availability']} -> {availability}", actor)
    return get_admin(conn, admin_id)


def update_admin(conn, admin_id, data, actor=None):
    admin = get_admin(conn, admin_id)
    if admin is None:
        raise AppError("Administrator not found.", 404)
    name = (data.get("name") if "name" in data else admin["name"]) or ""
    name = name.strip()
    if not 2 <= len(name) <= 80:
        raise AppError("Name must be between 2 and 80 characters.", 400)
    is_active = admin["is_active"]
    if "is_active" in data:
        is_active = bool(data["is_active"])
        if not is_active and admin["admin_role"] == "central":
            raise AppError("The central administrator cannot be deactivated.", 400)
    conn.execute("UPDATE administrators SET name = ?, is_active = ? WHERE id = ?",
                 (name, int(is_active), admin_id))
    conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, admin["user_id"]))
    write_audit(conn, "ADMIN_UPDATED", "administrator", admin["admin_code"],
                f"name={name}, active={is_active}", actor)
    return get_admin(conn, admin_id)


def create_admin(conn, data, actor=None, hash_method=None):
    """Create a new network administrator account (central admin only)."""
    clean, errors = user_manager.validate_registration(data)
    zone = (data.get("assigned_zone") or "").strip().upper()
    role = (data.get("admin_role") or "backup").strip().lower()
    code = (data.get("admin_code") or "").strip()
    if role not in ("primary", "backup"):
        errors["admin_role"] = "Role must be primary or backup."
    if not conn.execute("SELECT 1 FROM campus_zones WHERE location_code = ?", (zone,)).fetchone():
        errors["assigned_zone"] = "Select a valid campus zone."
    if not code:
        prefix = "Admin" if role == "primary" else "Backup"
        n = conn.execute("SELECT COUNT(*) AS n FROM administrators WHERE assigned_zone = ?",
                         (zone,)).fetchone()["n"]
        code = f"{prefix}_{zone}_{n + 1}"
    if conn.execute("SELECT 1 FROM administrators WHERE admin_code = ?", (code,)).fetchone():
        errors["admin_code"] = "Administrator code already exists."
    if errors:
        raise AppError("Please correct the highlighted fields.", 400, details=errors)
    user_id = user_manager.create_user(conn, clean["name"], clean["institutional_id"], clean["email"],
                                       clean["password"], "administrator", hash_method)
    cur = conn.execute(
        "INSERT INTO administrators (user_id, admin_code, name, email, assigned_zone, admin_role, "
        "availability, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, 'Available', 1, ?)",
        (user_id, code, clean["name"], clean["email"], zone, role, now_str()),
    )
    write_audit(conn, "ADMIN_CREATED", "administrator", code, f"zone={zone}, role={role}", actor)
    return get_admin(conn, cur.lastrowid)
