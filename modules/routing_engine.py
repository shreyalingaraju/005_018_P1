"""
Intelligent complaint routing engine (BCS502 - Computer Networks).

The campus routing table maps a location prefix (the LOCATION_CODE of a
validated identifier) to a primary and a backup network administrator,
much like a router maps a destination prefix to a next hop with a fallback.

Algorithm (route_complaint):
    1. Extract the location code from the validated identifier.
    2. Look the code up in the routing table (SQLite).
    3. Unknown zone            -> forward to Central_Admin (queue for CENTRAL if busy).
    4. Primary available       -> assign to primary.
    5. Primary busy/inactive   -> try backup; if available assign to backup.
    6. Both unavailable        -> insert into the priority waiting queue (status stays Pending).

process_waiting_queue drains the queue Critical -> High -> Medium -> Low
(FIFO inside a priority) whenever an administrator becomes available.
"""
from modules import admin_manager, complaint_manager, queue_manager
from modules.database import transaction
from modules.utils import AppError, now_str, write_audit

CENTRAL_ZONE = "CENTRAL"

# Initial configuration used ONLY by the seed script. After initialisation
# the routing_table in SQLite is the source of truth.
DEFAULT_ROUTING_CONFIG = {
    "HOST": {"name": "Hostels", "primary": "Admin_HOST", "backup": "Backup_HOST"},
    "LAB": {"name": "Laboratories", "primary": "Admin_LAB", "backup": "Backup_LAB"},
    "ADM": {"name": "Admin Block", "primary": "Admin_ADM", "backup": "Backup_ADM"},
    "LIB": {"name": "Library", "primary": "Admin_LIB", "backup": "Backup_LIB"},
    "CANT": {"name": "Canteen", "primary": "Admin_CANT", "backup": "Backup_CANT"},
    "SPRT": {"name": "Sports Complex", "primary": "Admin_SPRT", "backup": "Backup_SPRT"},
}

ASSIGNED_PRIMARY = "ASSIGNED_PRIMARY"
ASSIGNED_BACKUP = "ASSIGNED_BACKUP"
FORWARDED_CENTRAL = "FORWARDED_CENTRAL"
QUEUED = "QUEUED"


def extract_location_code(identifier):
    """DEVICE-LOCATION-FLOOR -> LOCATION (the routing prefix)."""
    parts = (identifier or "").split("-")
    if len(parts) != 3 or not parts[1]:
        raise AppError("Malformed identifier: cannot extract the location prefix.", 400)
    return parts[1]


def get_zone_administrators(conn, location_code):
    """Routing-table lookup. Returns None when the prefix has no entry."""
    row = conn.execute(
        "SELECT z.id AS zone_id, z.location_code, z.location_name, "
        "r.primary_admin_id, r.backup_admin_id, r.updated_at "
        "FROM campus_zones z JOIN routing_table r ON r.zone_id = z.id "
        "WHERE z.location_code = ?", (location_code,)
    ).fetchone()
    if row is None:
        return None
    return {
        "zone_id": row["zone_id"],
        "location_code": row["location_code"],
        "location_name": row["location_name"],
        "primary": admin_manager.get_admin(conn, row["primary_admin_id"]) if row["primary_admin_id"] else None,
        "backup": admin_manager.get_admin(conn, row["backup_admin_id"]) if row["backup_admin_id"] else None,
        "updated_at": row["updated_at"],
    }


def check_administrator_availability(conn, admin_id):
    """True only if the administrator exists, is active and is Available."""
    if admin_id is None:
        return False
    row = conn.execute("SELECT availability, is_active FROM administrators WHERE id = ?",
                       (admin_id,)).fetchone()
    return bool(row) and row["is_active"] == 1 and row["availability"] == admin_manager.AVAILABLE


def _admin_brief(admin):
    if not admin:
        return None
    return {"id": admin["id"], "name": admin["name"], "admin_code": admin["admin_code"],
            "availability": admin["availability"], "is_active": admin["is_active"],
            "admin_role": admin["admin_role"]}


def _select_target(conn, location_code):
    """
    Pure decision step (no writes). Returns (decision, steps) where decision is
    {outcome, admin, zone_code, zone_name}.
    """
    steps = [{"stage": "Extract prefix", "detail": f"Location code '{location_code}' extracted from identifier.",
              "result": "ok"}]
    zone = get_zone_administrators(conn, location_code)
    if zone is None:
        steps.append({"stage": "Zone lookup", "result": "warn",
                      "detail": f"No routing-table entry for '{location_code}' -> Unknown zone."})
        central = admin_manager.get_central_admin(conn)
        if central and check_administrator_availability(conn, central["id"]):
            steps.append({"stage": "Central administrator", "result": "ok",
                          "detail": f"{central['name']} ({central['admin_code']}) is Available."})
            return {"outcome": FORWARDED_CENTRAL, "admin": central, "zone_code": CENTRAL_ZONE,
                    "zone_name": "Central Network Operations"}, steps
        steps.append({"stage": "Central administrator", "result": "fail",
                      "detail": "Central administrator is Busy -> queued for central assignment."})
        return {"outcome": QUEUED, "admin": None, "zone_code": CENTRAL_ZONE,
                "zone_name": "Central Network Operations"}, steps

    steps.append({"stage": "Zone lookup", "result": "ok",
                  "detail": f"'{location_code}' -> {zone['location_name']}."})
    primary, backup = zone["primary"], zone["backup"]
    if primary and check_administrator_availability(conn, primary["id"]):
        steps.append({"stage": "Primary administrator", "result": "ok",
                      "detail": f"{primary['name']} ({primary['admin_code']}) is Available."})
        return {"outcome": ASSIGNED_PRIMARY, "admin": primary, "zone_code": location_code,
                "zone_name": zone["location_name"]}, steps
    steps.append({"stage": "Primary administrator", "result": "fail",
                  "detail": (f"{primary['name']} ({primary['admin_code']}) is "
                             f"{primary['availability'] if primary['is_active'] else 'Inactive'}.")
                  if primary else "No primary administrator configured."})
    if backup and check_administrator_availability(conn, backup["id"]):
        steps.append({"stage": "Backup administrator", "result": "ok",
                      "detail": f"{backup['name']} ({backup['admin_code']}) is Available."})
        return {"outcome": ASSIGNED_BACKUP, "admin": backup, "zone_code": location_code,
                "zone_name": zone["location_name"]}, steps
    steps.append({"stage": "Backup administrator", "result": "fail",
                  "detail": (f"{backup['name']} ({backup['admin_code']}) is "
                             f"{backup['availability'] if backup['is_active'] else 'Inactive'}.")
                  if backup else "No backup administrator configured."})
    return {"outcome": QUEUED, "admin": None, "zone_code": location_code,
            "zone_name": zone["location_name"]}, steps


def preview_route(conn, identifier):
    """Dry-run of the routing decision (used by the Technical Overview)."""
    code = extract_location_code(identifier)
    decision, steps = _select_target(conn, code)
    if decision["outcome"] == QUEUED:
        steps.append({"stage": "Waiting queue", "result": "warn",
                      "detail": f"Would join queue '{decision['zone_code']}' "
                                f"({queue_manager.queue_size(conn, decision['zone_code'])} already waiting)."})
    else:
        steps.append({"stage": "Assignment", "result": "ok",
                      "detail": f"Would be assigned to {decision['admin']['name']}."})
    return {"outcome": decision["outcome"], "zone_code": decision["zone_code"],
            "zone_name": decision["zone_name"], "admin": _admin_brief(decision["admin"]),
            "steps": steps}


def route_complaint(conn, complaint_pk, actor=None):
    """Route a Pending complaint. Runs inside a single transaction."""
    with transaction(conn):
        complaint = complaint_manager.get_by_pk(conn, complaint_pk)
        if complaint is None:
            raise AppError("Complaint not found.", 404)
        if complaint["status"] != complaint_manager.PENDING or complaint["assigned_admin_id"]:
            raise AppError("Complaint has already been routed.", 409)
        if conn.execute("SELECT 1 FROM waiting_queue WHERE complaint_id = ?", (complaint_pk,)).fetchone():
            raise AppError("Complaint is already waiting in the queue.", 409)

        code = extract_location_code(complaint["identifier"])
        decision, steps = _select_target(conn, code)
        outcome, admin = decision["outcome"], decision["admin"]

        if outcome == FORWARDED_CENTRAL or (outcome == QUEUED and decision["zone_code"] == CENTRAL_ZONE):
            write_audit(conn, "CENTRAL_FORWARD", "complaint", complaint["complaint_id"],
                        f"Unknown zone '{code}' forwarded to central administrator.", actor)

        if outcome == QUEUED:
            queue_manager.enqueue(conn, complaint_pk, decision["zone_code"], complaint["priority"],
                                  complaint["priority_rank"], complaint["submission_time"])
            conn.execute("UPDATE complaints SET routed_zone = ?, updated_at = ? WHERE id = ?",
                         (decision["zone_code"], now_str(), complaint_pk))
            pos = conn.execute("SELECT queue_position FROM waiting_queue WHERE complaint_id = ?",
                               (complaint_pk,)).fetchone()["queue_position"]
            remark = (f"All administrators for {decision['zone_name']} are busy. Added to the "
                      f"{complaint['priority']}-priority waiting queue at position {pos}.")
            complaint_manager.add_history(conn, complaint_pk, "QUEUED", complaint_manager.PENDING,
                                          complaint_manager.PENDING, remark, None)
            steps.append({"stage": "Waiting queue", "result": "warn", "detail": remark})
            write_audit(conn, "QUEUED", "complaint", complaint["complaint_id"],
                        f"zone={decision['zone_code']}, priority={complaint['priority']}, position={pos}", actor)
            return {"outcome": outcome, "admin": None, "zone_code": decision["zone_code"],
                    "zone_name": decision["zone_name"], "queue_position": pos, "steps": steps}

        label = {ASSIGNED_PRIMARY: "primary administrator", ASSIGNED_BACKUP: "backup administrator",
                 FORWARDED_CENTRAL: "central administrator (unknown zone fallback)"}[outcome]
        remark = f"Routed to {label} {admin['name']} ({admin['admin_code']})."
        action = "FORWARDED_CENTRAL" if outcome == FORWARDED_CENTRAL else "ASSIGNED"
        if not complaint_manager.mark_assigned(conn, complaint, admin, remark, None, action,
                                               decision["zone_code"]):
            raise AppError("Complaint could not be assigned (concurrent update).", 409)
        steps.append({"stage": "Assignment", "result": "ok", "detail": remark})
        return {"outcome": outcome, "admin": _admin_brief(admin), "zone_code": decision["zone_code"],
                "zone_name": decision["zone_name"], "queue_position": None, "steps": steps}


def _available_admin_for_zone(conn, zone_code):
    if zone_code == CENTRAL_ZONE:
        central = admin_manager.get_central_admin(conn)
        return central if central and check_administrator_availability(conn, central["id"]) else None
    zone = get_zone_administrators(conn, zone_code)
    if zone is None:
        central = admin_manager.get_central_admin(conn)
        return central if central and check_administrator_availability(conn, central["id"]) else None
    for candidate in (zone["primary"], zone["backup"]):
        if candidate and check_administrator_availability(conn, candidate["id"]):
            return candidate
    return None


def process_waiting_queue(conn, zone_code=None, actor=None):
    """
    Assign waiting complaints in priority order (Critical -> Low, FIFO within
    a priority). Transaction-safe: each assignment is guarded so a complaint
    is never assigned twice. Returns the list of assignments in the order made.
    """
    assignments = []
    with transaction(conn):
        for zone in queue_manager.zones_with_waiting(conn, zone_code):
            admin = _available_admin_for_zone(conn, zone)
            if admin is None:
                continue
            for item in queue_manager.get_waiting(conn, zone):
                complaint = complaint_manager.get_by_pk(conn, item["complaint_pk"])
                role = {"primary": "primary", "backup": "backup", "central": "central"}[admin["admin_role"]]
                remark = (f"Assigned from the waiting queue ({item['priority']} priority, position "
                          f"{item['queue_position']}) to {role} administrator {admin['name']}.")
                if complaint_manager.mark_assigned(conn, complaint, admin, remark, actor, "ASSIGNED"):
                    assignments.append({"complaint_id": complaint["complaint_id"],
                                        "priority": item["priority"], "zone_code": zone,
                                        "admin": _admin_brief(admin)})
                else:
                    # Stale queue entry (complaint no longer pending) - drop it.
                    queue_manager.remove(conn, item["complaint_pk"])
            queue_manager.recompute_positions(conn, zone)
        if assignments:
            write_audit(conn, "QUEUE_PROCESSED", "waiting_queue", zone_code or "ALL",
                        f"{len(assignments)} complaint(s) assigned: "
                        + ", ".join(a["complaint_id"] for a in assignments), actor)
    return assignments


def zones_for_admin(conn, admin_id):
    admin = admin_manager.get_admin(conn, admin_id)
    if admin and admin["admin_role"] == "central":
        return [CENTRAL_ZONE]
    rows = conn.execute(
        "SELECT z.location_code FROM routing_table r JOIN campus_zones z ON z.id = r.zone_id "
        "WHERE r.primary_admin_id = ? OR r.backup_admin_id = ?", (admin_id, admin_id)).fetchall()
    return [r["location_code"] for r in rows]


def update_administrator_availability(conn, admin_id, status, actor=None):
    """
    Change availability. When an administrator becomes Available the waiting
    queue of every zone they serve is processed automatically.
    """
    with transaction(conn):
        admin = admin_manager.set_availability(conn, admin_id, status, actor)
        processed = []
        if status == admin_manager.AVAILABLE:
            for zone in zones_for_admin(conn, admin_id):
                processed += process_waiting_queue(conn, zone, actor)
        return {"admin": admin_manager.get_admin(conn, admin_id), "processed": processed}


def update_routing_entry(conn, location_code, primary_id, backup_id, actor=None):
    """Change the administrators mapped to a zone (central admin only)."""
    with transaction(conn):
        zone = conn.execute("SELECT id, location_name FROM campus_zones WHERE location_code = ?",
                            (location_code,)).fetchone()
        if zone is None:
            raise AppError("Unknown campus zone.", 404)
        try:
            primary_id, backup_id = int(primary_id), int(backup_id)
        except (TypeError, ValueError):
            raise AppError("Primary and backup administrator IDs are required.", 400)
        if primary_id == backup_id:
            raise AppError("Primary and backup administrators must be different.", 400)
        for aid in (primary_id, backup_id):
            adm = admin_manager.get_admin(conn, aid)
            if adm is None:
                raise AppError(f"Administrator {aid} not found.", 404)
            if adm["admin_role"] == "central":
                raise AppError("The central administrator cannot be mapped to a single zone.", 400)
        ts = now_str()
        conn.execute("UPDATE routing_table SET primary_admin_id = ?, backup_admin_id = ?, updated_at = ? "
                     "WHERE zone_id = ?", (primary_id, backup_id, ts, zone["id"]))
        conn.execute("UPDATE campus_zones SET primary_admin_id = ?, backup_admin_id = ? WHERE id = ?",
                     (primary_id, backup_id, zone["id"]))
        conn.execute("UPDATE administrators SET assigned_zone = ? WHERE id IN (?, ?)",
                     (location_code, primary_id, backup_id))
        write_audit(conn, "ROUTING_UPDATED", "zone", location_code,
                    f"primary={primary_id}, backup={backup_id}", actor)
        processed = process_waiting_queue(conn, location_code, actor)
        return {"zone": get_zone_administrators(conn, location_code), "processed": processed}


def reassign_complaint(conn, complaint_id, new_admin_id, actor, remarks=None):
    """Manual reassignment by the central administrator (recorded in history)."""
    with transaction(conn):
        complaint = complaint_manager.get_complaint(conn, complaint_id)
        if complaint is None:
            raise AppError("Complaint not found.", 404)
        if complaint["status"] == complaint_manager.RESOLVED:
            raise AppError("Resolved complaints cannot be reassigned.", 409)
        new_admin = admin_manager.get_admin(conn, new_admin_id)
        if new_admin is None or not new_admin["is_active"]:
            raise AppError("Target administrator not found or inactive.", 404)
        if complaint["assigned_admin_id"] == new_admin["id"]:
            raise AppError("Complaint is already assigned to this administrator.", 409)

        previous_admin = complaint.get("admin_name") or "waiting queue"
        ts = now_str()
        note = f"Reassigned from {previous_admin} to {new_admin['name']} ({new_admin['admin_code']})."
        if remarks:
            note += f" Reason: {remarks.strip()[:300]}"
        conn.execute(
            "UPDATE complaints SET assigned_admin_id = ?, status = 'Assigned', "
            "assigned_time = ?, in_progress_time = NULL, updated_at = ? WHERE id = ?",
            (new_admin["id"], ts, ts, complaint["id"]))
        queue_manager.remove(conn, complaint["id"])
        complaint_manager.add_history(conn, complaint["id"], "REASSIGNED", complaint["status"],
                                      complaint_manager.ASSIGNED, note, actor, ts)
        write_audit(conn, "REASSIGNED", "complaint", complaint["complaint_id"], note, actor)
        return complaint_manager.get_complaint(conn, complaint["complaint_id"])


def get_routing_table(conn):
    rows = conn.execute(
        "SELECT z.location_code, z.location_name, r.updated_at, "
        "p.id AS primary_id, p.name AS primary_name, p.admin_code AS primary_code, "
        "p.availability AS primary_availability, p.is_active AS primary_active, "
        "b.id AS backup_id, b.name AS backup_name, b.admin_code AS backup_code, "
        "b.availability AS backup_availability, b.is_active AS backup_active "
        "FROM routing_table r JOIN campus_zones z ON z.id = r.zone_id "
        "LEFT JOIN administrators p ON p.id = r.primary_admin_id "
        "LEFT JOIN administrators b ON b.id = r.backup_admin_id ORDER BY z.id").fetchall()
    return [dict(r) for r in rows]


def get_zone_overview(conn):
    """Routing table + per-zone complaint statistics (for zone cards)."""
    table = get_routing_table(conn)
    stats = {r["location_code"]: dict(r) for r in conn.execute(
        "SELECT location_code, COUNT(*) AS total, "
        "SUM(status IN ('Assigned','In Progress')) AS assigned, "
        "SUM(status = 'Resolved') AS resolved, SUM(status = 'Pending') AS pending "
        "FROM complaints GROUP BY location_code").fetchall()}
    waiting = {r["zone_code"]: r["n"] for r in conn.execute(
        "SELECT zone_code, COUNT(*) AS n FROM waiting_queue GROUP BY zone_code").fetchall()}
    for z in table:
        s = stats.get(z["location_code"], {})
        z["total"] = s.get("total") or 0
        z["assigned"] = s.get("assigned") or 0
        z["resolved"] = s.get("resolved") or 0
        z["waiting"] = waiting.get(z["location_code"], 0)
    return {"zones": table, "central_waiting": waiting.get(CENTRAL_ZONE, 0)}
