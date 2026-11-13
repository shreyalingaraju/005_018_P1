"""Part B - routing table, administrator allocation and the priority waiting queue."""
from modules import complaint_manager, queue_manager, routing_engine
from modules.database import transaction
from tests.conftest import admin_id, set_availability


def _make(conn, identifier="WIFI-HOST-2", category="Connectivity", priority="Medium", rank=3, ts=None):
    dev, loc, floor = identifier.split("-")
    with transaction(conn):
        return complaint_manager.insert_complaint(conn, {
            "user_id": 1, "user_name": "Aarav Sharma", "institutional_id": "1RV22CS001",
            "device_type": dev, "location_code": loc, "floor_number": int(floor), "identifier": identifier,
            "description": "test complaint", "category": category, "matched_keywords": {},
            "detected_categories": [category], "priority": priority, "priority_rank": rank}, submitted_at=ts)


def test_routing_table_has_six_zones(conn):
    table = routing_engine.get_routing_table(conn)
    assert [z["location_code"] for z in table] == ["HOST", "LAB", "ADM", "LIB", "CANT", "SPRT"]
    assert all(z["primary_code"].startswith("Admin_") and z["backup_code"].startswith("Backup_") for z in table)


def test_extract_location_code():
    assert routing_engine.extract_location_code("LAN-SPRT-4") == "SPRT"


def test_tc14_primary_available_gets_assignment(conn):
    r = routing_engine.route_complaint(conn, _make(conn))
    assert r["outcome"] == routing_engine.ASSIGNED_PRIMARY
    assert r["admin"]["admin_code"] == "Admin_HOST"
    c = complaint_manager.get_by_pk(conn, conn.execute("SELECT MAX(id) AS i FROM complaints").fetchone()["i"])
    assert c["status"] == "Assigned" and c["assigned_time"]


def test_tc15_primary_busy_backup_assigned(conn):
    set_availability(conn, "Admin_HOST", "Busy")
    r = routing_engine.route_complaint(conn, _make(conn))
    assert r["outcome"] == routing_engine.ASSIGNED_BACKUP
    assert r["admin"]["admin_code"] == "Backup_HOST"


def test_inactive_primary_treated_as_unavailable(conn):
    conn.execute("UPDATE administrators SET is_active = 0 WHERE admin_code = 'Admin_LAB'")
    r = routing_engine.route_complaint(conn, _make(conn, "LAN-LAB-1"))
    assert r["admin"]["admin_code"] == "Backup_LAB"


def test_tc16_both_busy_complaint_queued(conn):
    set_availability(conn, "Admin_HOST", "Busy")
    set_availability(conn, "Backup_HOST", "Busy")
    pk = _make(conn)
    r = routing_engine.route_complaint(conn, pk)
    assert r["outcome"] == routing_engine.QUEUED and r["queue_position"] == 1
    c = complaint_manager.get_by_pk(conn, pk)
    assert c["status"] == "Pending" and c["assigned_admin_id"] is None
    assert queue_manager.queue_size(conn, "HOST") == 1


def test_tc17_security_complaint_jumps_queue_fifo_within_priority(conn):
    set_availability(conn, "Admin_HOST", "Busy")
    set_availability(conn, "Backup_HOST", "Busy")
    low = _make(conn, category="Unknown", priority="Low", rank=4, ts="2026-11-13 08:00:00")
    med1 = _make(conn, ts="2026-11-13 08:01:00")
    med2 = _make(conn, ts="2026-11-13 08:02:00")
    sec = _make(conn, category="Security", priority="Critical", rank=1, ts="2026-11-13 08:03:00")
    for pk in (low, med1, med2, sec):
        routing_engine.route_complaint(conn, pk)
    order = [q["complaint_pk"] for q in queue_manager.get_waiting(conn, "HOST")]
    assert order == [sec, med1, med2, low]
    assert queue_manager.get_waiting(conn, "HOST")[0]["queue_position"] == 1


def test_tc18_admin_available_processes_queue_in_priority_order(conn):
    set_availability(conn, "Admin_HOST", "Busy")
    set_availability(conn, "Backup_HOST", "Busy")
    med = _make(conn, ts="2026-11-13 08:00:00")
    sec = _make(conn, category="Security", priority="Critical", rank=1, ts="2026-11-13 08:05:00")
    routing_engine.route_complaint(conn, med)
    routing_engine.route_complaint(conn, sec)
    result = routing_engine.update_administrator_availability(conn, admin_id(conn, "Backup_HOST"), "Available")
    assigned = [a["complaint_id"] for a in result["processed"]]
    assert assigned[0] == complaint_manager.get_by_pk(conn, sec)["complaint_id"]
    assert len(assigned) == 2
    assert queue_manager.queue_size(conn) == 0
    for pk in (med, sec):
        c = complaint_manager.get_by_pk(conn, pk)
        assert c["status"] == "Assigned" and c["admin_code"] == "Backup_HOST"


def test_queue_never_assigns_twice(conn):
    set_availability(conn, "Admin_LIB", "Busy")
    set_availability(conn, "Backup_LIB", "Busy")
    pk = _make(conn, "WIFI-LIB-1")
    routing_engine.route_complaint(conn, pk)
    set_availability(conn, "Admin_LIB", "Available")
    first = routing_engine.process_waiting_queue(conn)
    second = routing_engine.process_waiting_queue(conn)
    assert len(first) == 1 and second == []
    hist = [h["action"] for h in complaint_manager.get_history(conn, pk)]
    assert hist.count("ASSIGNED") == 1


def test_tc19_unknown_zone_forwarded_to_central_admin(conn):
    # Structurally valid legacy/imported record with an unregistered zone code.
    pk = _make(conn, "WIFI-GYM-1")
    r = routing_engine.route_complaint(conn, pk)
    assert r["outcome"] == routing_engine.FORWARDED_CENTRAL
    assert r["admin"]["admin_code"] == "Central_Admin"
    assert conn.execute("SELECT COUNT(*) AS n FROM audit_logs WHERE action = 'CENTRAL_FORWARD'").fetchone()["n"] == 1


def test_unknown_zone_with_busy_central_is_queued_for_central(conn):
    set_availability(conn, "Central_Admin", "Busy")
    r = routing_engine.route_complaint(conn, _make(conn, "LAN-GYM-0"))
    assert r["outcome"] == routing_engine.QUEUED and r["zone_code"] == routing_engine.CENTRAL_ZONE
    res = routing_engine.update_administrator_availability(conn, admin_id(conn, "Central_Admin"), "Available")
    assert len(res["processed"]) == 1


def test_routing_table_update_changes_routing(conn):
    new_primary = admin_id(conn, "Backup_LAB")
    new_backup = admin_id(conn, "Admin_LAB")
    routing_engine.update_routing_entry(conn, "LAB", new_primary, new_backup)
    r = routing_engine.route_complaint(conn, _make(conn, "LAN-LAB-2"))
    assert r["admin"]["admin_code"] == "Backup_LAB"


def test_preview_route_has_no_side_effects(conn):
    before = conn.execute("SELECT COUNT(*) AS n FROM complaint_history").fetchone()["n"]
    p = routing_engine.preview_route(conn, "WIFI-CANT-3")
    assert p["admin"]["admin_code"] == "Admin_CANT"
    assert conn.execute("SELECT COUNT(*) AS n FROM complaint_history").fetchone()["n"] == before
