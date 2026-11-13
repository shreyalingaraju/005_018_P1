"""
Database initialisation and demo seed data.

Usage (from the project root):
    python database/seed.py            # create DB if missing (keeps existing data)
    python database/seed.py --reset    # drop and recreate with demo data
    python database/seed.py --reset --empty   # recreate without sample complaints
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules import complaint_manager, user_manager  # noqa: E402
from modules.database import connect, create_schema, is_initialized, transaction  # noqa: E402
from modules.routing_engine import DEFAULT_ROUTING_CONFIG  # noqa: E402
from modules.utils import TIME_FORMAT, now_str  # noqa: E402

DEFAULT_DB = os.path.join(ROOT, "database", "campus_network.db")

# --------------------------------------------------------------------------- #
# Demo accounts (documented in README.md)
# --------------------------------------------------------------------------- #
DEMO_USERS = [
    ("Aarav Sharma", "1RV22CS001", "student@campus.edu", "Student@123"),
    ("Dr. Priya Nair", "FAC1023", "faculty@campus.edu", "Faculty@123"),
    ("Rahul Verma", "1RV22CS045", "rahul@campus.edu", "Student@123"),
]

ADMIN_NAMES = {
    "Admin_HOST": "Ravi Kumar", "Backup_HOST": "Sneha Patil",
    "Admin_LAB": "Arjun Rao", "Backup_LAB": "Kavya Menon",
    "Admin_ADM": "Suresh Gowda", "Backup_ADM": "Ananya Das",
    "Admin_LIB": "Vikram Singh", "Backup_LIB": "Divya Hegde",
    "Admin_CANT": "Manoj Reddy", "Backup_CANT": "Pooja Shetty",
    "Admin_SPRT": "Karthik Iyer", "Backup_SPRT": "Neha Joshi",
}
ADMIN_PASSWORD = "Admin@123"
CENTRAL = ("Central_Admin", "Dr. Meera Krishnan", "central@campus.edu", "Central@123")

# (user email, identifier, description, days_ago, final_status, hours_to_resolve)
DEMO_COMPLAINTS = [
    ("student@campus.edu", "WIFI-HOST-1", "WiFi keeps dropping every few minutes in my room, connection lost frequently.", 13, "Resolved", 5),
    ("rahul@campus.edu", "LAN-LAB-2", "The switch in lab 2 is overheating and two ports are not working.", 12, "Resolved", 20),
    ("faculty@campus.edu", "WIFI-ADM-1", "Getting an IP conflict warning on my laptop in the admin office.", 11, "Resolved", 3),
    ("student@campus.edu", "WIFI-LIB-0", "Suspicious login attempts noticed on the library WiFi portal.", 10, "Resolved", 2),
    ("rahul@campus.edu", "WIFI-CANT-0", "Very weak signal near the canteen counter, pages timeout.", 9, "Resolved", 9),
    ("faculty@campus.edu", "LAN-ADM-2", "DHCP is not giving an address on the LAN in room 204.", 8, "Resolved", 6),
    ("student@campus.edu", "LAN-HOST-3", "Damaged cable on the hostel third floor, LAN not working.", 7, "In Progress", None),
    ("rahul@campus.edu", "WIFI-SPRT-1", "No internet in the indoor stadium during the event.", 6, "Resolved", 12),
    ("faculty@campus.edu", "WIFI-LAB-4", "Malware warning popped up after connecting to the lab network.", 5, "In Progress", None),
    ("student@campus.edu", "WIFI-LIB-2", "The library access point light is off and nobody can connect.", 4, "Assigned", None),
    ("rahul@campus.edu", "LAN-SPRT-0", "The printer in the sports office stopped responding to everyone.", 3, "Resolved", 4),
    ("faculty@campus.edu", "WIFI-CANT-1", "Intermittent connectivity and high latency in the canteen seating area.", 2, "Assigned", None),
    ("student@campus.edu", "WIFI-HOST-2", "DNS error on every website in the hostel block, wrong gateway set.", 1, "Assigned", None),
]


def seed_core(conn, hash_method=None):
    """Users, administrators, campus zones and routing table."""
    with transaction(conn):
        for name, inst, email, pw in DEMO_USERS:
            user_manager.create_user(conn, name, inst, email, pw, "user", hash_method)

        admin_ids = {}
        code, name, email, pw = CENTRAL
        uid = user_manager.create_user(conn, name, "NOCCENTRAL", email, pw, "central_admin", hash_method)
        admin_ids[code] = conn.execute(
            "INSERT INTO administrators (user_id, admin_code, name, email, assigned_zone, admin_role, created_at) "
            "VALUES (?, ?, ?, ?, 'CENTRAL', 'central', ?)", (uid, code, name, email, now_str())).lastrowid

        for zone_code, cfg in DEFAULT_ROUTING_CONFIG.items():
            for role in ("primary", "backup"):
                code = cfg[role]
                name = ADMIN_NAMES[code]
                email = f"{'admin' if role == 'primary' else 'backup'}.{zone_code.lower()}@campus.edu"
                inst = f"NA{'P' if role == 'primary' else 'B'}{zone_code}"
                uid = user_manager.create_user(conn, name, inst, email, ADMIN_PASSWORD,
                                               "administrator", hash_method)
                admin_ids[code] = conn.execute(
                    "INSERT INTO administrators (user_id, admin_code, name, email, assigned_zone, admin_role, "
                    "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uid, code, name, email, zone_code, role, now_str())).lastrowid

            zone_id = conn.execute(
                "INSERT INTO campus_zones (location_code, location_name, primary_admin_id, backup_admin_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (zone_code, cfg["name"], admin_ids[cfg["primary"]], admin_ids[cfg["backup"]], now_str())).lastrowid
            conn.execute(
                "INSERT INTO routing_table (zone_id, primary_admin_id, backup_admin_id, updated_at) VALUES (?, ?, ?, ?)",
                (zone_id, admin_ids[cfg["primary"]], admin_ids[cfg["backup"]], now_str()))


def seed_demo_complaints(conn):
    """Push realistic complaints through the REAL pipeline, then back-date them."""
    from services.routing_service import submit_complaint

    central = user_manager.public_user(conn.execute(
        "SELECT * FROM users WHERE role = 'central_admin' ORDER BY id LIMIT 1").fetchone())
    base = datetime.now()
    for email, ident, desc, days_ago, final_status, hours in DEMO_COMPLAINTS:
        user = user_manager.public_user(conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())
        dev, loc, floor = ident.split("-")
        result = submit_complaint(conn, user, {
            "name": user["name"], "institutional_id": user["institutional_id"],
            "device_type": dev, "location_code": loc, "floor": floor, "description": desc})
        cid = result["complaint"]["complaint_id"]
        pk = result["complaint"]["id"]
        if final_status in ("In Progress", "Resolved"):
            complaint_manager.update_status(conn, cid, "In Progress", central, None, "Technician dispatched.")
        if final_status == "Resolved":
            complaint_manager.update_status(conn, cid, "Resolved", central, None, "Issue fixed and verified.")

        # Back-date timestamps so analytics show a realistic history.
        submitted = base - timedelta(days=days_ago, hours=(days_ago * 3) % 7)
        assigned = submitted + timedelta(minutes=2)
        in_prog = submitted + timedelta(hours=1)
        resolved = submitted + timedelta(hours=hours) if hours else None
        fmt = lambda d: d.strftime(TIME_FORMAT) if d else None  # noqa: E731
        new_cid = f"CNFR-{submitted.strftime('%Y%m%d')}-{cid[-6:]}"
        with transaction(conn):
            conn.execute(
                "UPDATE complaints SET complaint_id = ?, submission_time = ?, assigned_time = ?, "
                "in_progress_time = CASE WHEN in_progress_time IS NULL THEN NULL ELSE ? END, "
                "resolved_time = CASE WHEN resolved_time IS NULL THEN NULL ELSE ? END, updated_at = ? "
                "WHERE id = ?",
                (new_cid, fmt(submitted), fmt(assigned), fmt(in_prog), fmt(resolved),
                 fmt(resolved or in_prog if final_status != "Assigned" else assigned), pk))
            for h in conn.execute("SELECT id, action, new_status FROM complaint_history WHERE complaint_id = ?",
                                  (pk,)).fetchall():
                ts = {"CREATED": submitted, "ASSIGNED": assigned, "FORWARDED_CENTRAL": assigned}.get(h["action"])
                if h["action"] == "STATUS_CHANGE":
                    ts = in_prog if h["new_status"] == "In Progress" else resolved
                conn.execute("UPDATE complaint_history SET changed_at = ? WHERE id = ?", (fmt(ts), h["id"]))
    # Audit entries created while seeding are not meaningful for the demo.
    conn.execute("DELETE FROM audit_logs")


def initialize_database(path, demo_complaints=True, hash_method=None, reset=False):
    """Create the database if needed. Returns True if it was (re)created."""
    if reset and os.path.exists(path):
        os.remove(path)
    conn = connect(path)
    try:
        if is_initialized(conn):
            return False
        create_schema(conn)
        seed_core(conn, hash_method)
        if demo_complaints:
            seed_demo_complaints(conn)
        return True
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Initialise the Campus NetWatch database.")
    parser.add_argument("--db", default=os.environ.get("CNFR_DATABASE", DEFAULT_DB))
    parser.add_argument("--reset", action="store_true", help="delete and recreate the database")
    parser.add_argument("--empty", action="store_true", help="do not create sample complaints")
    args = parser.parse_args()
    created = initialize_database(args.db, demo_complaints=not args.empty, reset=args.reset)
    print(("Database created and seeded: " if created else "Database already initialised: ") + args.db)


if __name__ == "__main__":
    main()
