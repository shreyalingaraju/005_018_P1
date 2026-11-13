"""Part D - end-to-end workflow through the HTTP API (all demo scenarios)."""
from tests.conftest import ADMIN_HOST, BACKUP_HOST, CENTRAL, STUDENT, admin_id, login, submit


def test_full_workflow_register_to_resolution(client, conn):
    # Registration -> login (session) -> submission
    r = client.post("/api/auth/register", json={"name": "Integration User", "institutional_id": "1RV22IS777",
                                                "email": "it@campus.edu", "password": "Netw0rk!!",
                                                "confirm_password": "Netw0rk!!"})
    assert r.status_code == 201
    r = submit(client, "LAN", "HOST", "3", "Unauthorized device attempted to access the network.",
               name="Integration User", inst="1RV22IS777")
    assert r.status_code == 201
    d = r.get_json()["data"]
    cid = d["complaint"]["complaint_id"]
    # identifier generation + DFA + regex + comparison
    assert d["validation"]["identifier"] == "LAN-HOST-3"
    assert d["validation"]["dfa"]["final_state"] == "q30" and d["validation"]["match"]
    # classification + priority + storage + routing
    assert d["classification"]["category"] == "Security" and d["complaint"]["priority"] == "Critical"
    assert d["routing"]["outcome"] == "ASSIGNED_PRIMARY"
    stored = conn.execute("SELECT * FROM complaints WHERE complaint_id = ?", (cid,)).fetchone()
    assert stored["status"] == "Assigned" and stored["category"] == "Security"

    # Administrator works the complaint
    login(client, ADMIN_HOST)
    mine = client.get("/api/admins/me/complaints").get_json()["data"]["complaints"]
    assert cid in [c["complaint_id"] for c in mine]
    assert client.patch(f"/api/complaints/{cid}/status", json={"status": "In Progress"}).status_code == 200
    assert client.patch(f"/api/complaints/{cid}/status", json={"status": "Resolved"}).status_code == 200

    # User tracking reflects the update
    client.post("/api/auth/login", json={"email": "it@campus.edu", "password": "Netw0rk!!"})
    t = client.get(f"/api/complaints/track/{cid}").get_json()["data"]
    assert t["complaint"]["status"] == "Resolved"
    assert [h["new_status"] for h in t["history"]] == ["Pending", "Assigned", "In Progress", "Resolved"]

    # Analytics update
    o = client.get("/api/analytics/overview").get_json()["data"]
    assert o["resolved"] == 1 and o["critical"] == 1 and o["avg_resolution_hours"] is not None


def test_demo3_and_demo4_busy_backup_queue_and_auto_processing(client, conn):
    # Demo 3: primary busy -> backup
    login(client, ADMIN_HOST)
    host_primary = admin_id(conn, "Admin_HOST")
    assert client.patch(f"/api/admins/{host_primary}/availability", json={"availability": "Busy"}).status_code == 200
    login(client, STUDENT)
    r = submit(client, description="WiFi keeps dropping near the reading room.").get_json()["data"]
    assert r["routing"]["outcome"] == "ASSIGNED_BACKUP" and r["routing"]["admin"]["admin_code"] == "Backup_HOST"

    # Demo 4: all busy -> queue; security gets top priority (multiple simultaneous complaints)
    login(client, BACKUP_HOST)
    client.patch(f"/api/admins/{admin_id(conn, 'Backup_HOST')}/availability", json={"availability": "Busy"})
    login(client, STUDENT)
    ids = []
    for desc in ["Slow internet in room 12.", "The fan is noisy in the corridor area.",
                 "Router lights are blinking red.", "Suspicious login detected on my account."]:
        resp = submit(client, description=desc).get_json()
        assert resp["data"]["routing"]["outcome"] == "QUEUED"
        ids.append(resp["data"]["complaint"]["complaint_id"])
    login(client, CENTRAL)
    queue = client.get("/api/routing/queue?zone=HOST").get_json()["data"]["queue"]
    assert [q["priority"] for q in queue] == ["Critical", "High", "Medium", "Low"]
    assert queue[0]["complaint_id"] == ids[3]

    # Primary comes back -> queue drained automatically, highest priority first
    login(client, ADMIN_HOST)
    res = client.patch(f"/api/admins/{host_primary}/availability", json={"availability": "Available"}).get_json()
    order = [a["priority"] for a in res["data"]["processed"]]
    assert order == ["Critical", "High", "Medium", "Low"]
    assert client.get("/api/routing/queue").status_code == 200
    assert conn.execute("SELECT COUNT(*) AS n FROM waiting_queue").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM complaints WHERE status = 'Pending'").fetchone()["n"] == 0


def test_routing_dashboard_endpoints(client, conn):
    login(client, CENTRAL)
    zones = client.get("/api/routing/zones").get_json()["data"]["zones"]
    assert len(zones) == 6
    r = client.patch("/api/routing/table/CANT", json={"primary_admin_id": admin_id(conn, "Backup_CANT"),
                                                      "backup_admin_id": admin_id(conn, "Admin_CANT")})
    assert r.status_code == 200
    assert client.patch("/api/routing/table/CANT", json={"primary_admin_id": 2, "backup_admin_id": 2}).status_code == 400
    assert client.post("/api/routing/process-queue", json={}).status_code == 200
    hist = client.get("/api/routing/history").get_json()["data"]
    assert any(a["action"] == "ROUTING_UPDATED" for a in hist["audit"])


def test_pages_render_for_each_role(client):
    for creds, pages in [(STUDENT, ["/dashboard", "/complaints/new", "/track", "/analytics", "/technical"]),
                         (ADMIN_HOST, ["/admin", "/track", "/analytics", "/technical"]),
                         (CENTRAL, ["/routing", "/admin", "/analytics", "/technical"])]:
        login(client, creds)
        for p in pages:
            assert client.get(p).status_code == 200, p


def test_validation_and_classification_apis(client):
    r = client.post("/api/validate/compare", json={"identifiers": ["WIFI-HOST-2", "LAN-LAB-12"]}).get_json()
    assert r["data"]["all_agree"] and [x["dfa"] for x in r["data"]["rows"]] == ["Valid", "Invalid"]
    assert client.post("/api/classify", json={"description": "IP conflict"}).get_json()["data"]["category"] == "Configuration"
    assert client.get("/api/dfa/definition").get_json()["data"]["dfa"]["dead_state"] == "qD"
