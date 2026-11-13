"""Complaint API, status lifecycle and authorisation."""
import re

from tests.conftest import (ADMIN_HOST, ADMIN_LAB, CENTRAL, STUDENT, STUDENT2, admin_id, login,
                            set_availability, submit)


def _count(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM complaints").fetchone()["n"]


def test_tc20_malformed_identifier_rejected_and_not_stored(client, conn):
    login(client, STUDENT)
    for dev, loc, floor in [("BLUETOOTH", "HOST", "2"), ("WIFI", "XYZ", "3"), ("WIFI", "HOST", "12"),
                            ("wifi", "host", "2"), ("WIFI", "HOST", "")]:
        r = submit(client, dev, loc, floor)
        assert r.status_code == 400
        body = r.get_json()
        assert body["success"] is False and body["details"]["validation"]["valid"] is False
    assert _count(conn) == 0
    assert submit(client, "BLUETOOTH").get_json()["error"] == "Unsupported device type. Allowed types are WIFI and LAN."


def test_submission_response_contains_full_pipeline(client):
    login(client, STUDENT)
    r = submit(client, description="My WiFi is disconnected and internet is very slow.")
    assert r.status_code == 201
    d = r.get_json()["data"]
    assert re.fullmatch(r"CNFR-\d{8}-[A-Z0-9]{6}", d["complaint"]["complaint_id"])
    assert d["validation"]["dfa"]["result"] == "Valid" and d["validation"]["regex"]["result"] == "Valid"
    assert d["validation"]["match"] is True
    assert d["classification"]["category"] == "Connectivity"
    assert d["complaint"]["priority"] == "Medium"
    assert d["routing"]["admin"]["admin_code"] == "Admin_HOST"
    assert d["complaint"]["status"] == "Assigned"


def test_field_validation_and_duplicates(client):
    login(client, STUDENT)
    r = submit(client, description="short")
    assert r.status_code == 400 and "description" in r.get_json()["details"]["fields"]
    assert submit(client, description="Router keeps rebooting in hostel").status_code == 201
    dup = submit(client, description="Router keeps rebooting in hostel")
    assert dup.status_code == 409


def test_tc21_tc22_status_updates_recorded(client, conn):
    login(client, STUDENT)
    cid = submit(client, description="Switch port damaged on second floor").get_json()["data"]["complaint"]["complaint_id"]
    login(client, ADMIN_HOST)
    r = client.patch(f"/api/complaints/{cid}/status", json={"status": "In Progress", "remarks": "On my way"})
    assert r.status_code == 200
    row = conn.execute("SELECT status, in_progress_time FROM complaints WHERE complaint_id = ?", (cid,)).fetchone()
    assert row["status"] == "In Progress" and row["in_progress_time"]
    r = client.patch(f"/api/complaints/{cid}/status", json={"status": "Resolved", "remarks": "Port replaced"})
    assert r.status_code == 200
    row = conn.execute("SELECT status, resolved_time FROM complaints WHERE complaint_id = ?", (cid,)).fetchone()
    assert row["status"] == "Resolved" and row["resolved_time"]
    hist = client.get(f"/api/complaints/{cid}/history").get_json()["data"]["history"]
    assert [h["new_status"] for h in hist] == ["Pending", "Assigned", "In Progress", "Resolved"]


def test_invalid_status_transitions_rejected(client):
    login(client, STUDENT)
    cid = submit(client).get_json()["data"]["complaint"]["complaint_id"]
    login(client, ADMIN_HOST)
    assert client.patch(f"/api/complaints/{cid}/status", json={"status": "Resolved"}).status_code == 409
    assert client.patch(f"/api/complaints/{cid}/status", json={"status": "Pending"}).status_code == 409
    assert client.patch(f"/api/complaints/{cid}/status", json={"status": "Bogus"}).status_code == 400


def test_tc23_user_cannot_view_another_users_complaint(client):
    login(client, STUDENT)
    cid = submit(client).get_json()["data"]["complaint"]["complaint_id"]
    login(client, STUDENT2)
    assert client.get(f"/api/complaints/track/{cid}").status_code == 403
    assert client.get(f"/api/complaints/{cid}").status_code == 403
    assert client.get("/api/complaints/my").get_json()["data"]["complaints"] == []


def test_tc24_unauthorised_admin_cannot_update_complaint(client):
    login(client, STUDENT)
    cid = submit(client).get_json()["data"]["complaint"]["complaint_id"]
    login(client, ADMIN_LAB)  # not assigned to this HOST complaint
    r = client.patch(f"/api/complaints/{cid}/status", json={"status": "In Progress"})
    assert r.status_code == 403
    login(client, STUDENT)
    assert client.patch(f"/api/complaints/{cid}/status", json={"status": "In Progress"}).status_code == 403
    login(client, CENTRAL)  # central admin may manage any complaint
    assert client.patch(f"/api/complaints/{cid}/status", json={"status": "In Progress"}).status_code == 200


def test_role_based_page_and_api_access(client):
    assert client.get("/dashboard").status_code == 302
    assert client.get("/api/complaints").status_code == 401
    login(client, STUDENT)
    assert client.get("/admin").status_code == 403
    assert client.get("/routing").status_code == 403
    assert client.get("/api/admins").status_code == 403
    assert client.patch("/api/admins/1/availability", json={"availability": "Busy"}).status_code == 403
    login(client, ADMIN_HOST)
    assert client.get("/routing").status_code == 403
    assert client.get("/admin").status_code == 200
    other = 3  # some other administrator
    assert client.patch(f"/api/admins/{other}/availability", json={"availability": "Busy"}).status_code == 403


def test_password_hash_never_exposed(client):
    user = login(client, STUDENT)
    assert "password_hash" not in user
    assert "password_hash" not in client.get("/api/auth/me").get_data(as_text=True)
    login(client, CENTRAL)
    assert "password_hash" not in client.get("/api/admins").get_data(as_text=True)


def test_registration_and_login(client):
    r = client.post("/api/auth/register", json={"name": "New Student", "institutional_id": "1rv23cs999",
                                                "email": "new@campus.edu", "password": "Passw0rd!",
                                                "confirm_password": "Passw0rd!"})
    assert r.status_code == 201 and r.get_json()["data"]["user"]["institutional_id"] == "1RV23CS999"
    assert client.post("/api/auth/register", json={"name": "X", "institutional_id": "a", "email": "bad",
                                                   "password": "1", "confirm_password": "2"}).status_code == 400
    assert client.post("/api/auth/login", json={"email": "new@campus.edu", "password": "wrong"}).status_code == 401


def test_csrf_required_when_enabled(template_db, tmp_path):
    import shutil
    from app import create_app
    from config import TestingConfig
    db = tmp_path / "csrf.db"
    shutil.copy(template_db, db)
    app = create_app(TestingConfig, DATABASE=str(db), CSRF_ENABLED=True)
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": STUDENT[0], "password": STUDENT[1]}).status_code == 400
    c.get("/login")
    with c.session_transaction() as s:
        token = s["_csrf_token"]
    r = c.post("/api/auth/login", json={"email": STUDENT[0], "password": STUDENT[1]}, headers={"X-CSRFToken": token})
    assert r.status_code == 200


def test_tc25_analytics_match_database(client, conn):
    login(client, STUDENT)
    submit(client, description="Unauthorized device attempted to access the network.", location="LAB")
    submit(client, description="Router failure near the warden office.")
    cid = submit(client, device="LAN", location="LIB", floor="0", description="No internet on the LAN.").get_json()["data"]["complaint"]["complaint_id"]
    login(client, CENTRAL)
    client.patch(f"/api/complaints/{cid}/status", json={"status": "In Progress"})
    client.patch(f"/api/complaints/{cid}/status", json={"status": "Resolved"})
    data = client.get("/api/analytics/report").get_json()["data"]
    o = data["overview"]
    assert (o["total"], o["resolved"], o["unresolved"], o["critical"]) == (3, 1, 2, 1)
    zones = {z["location_code"]: z["total"] for z in data["zones"]}
    assert zones == {"HOST": 1, "LAB": 1, "ADM": 0, "LIB": 1, "CANT": 0, "SPRT": 0}
    cats = {c["label"]: c["count"] for c in data["categories"]}
    assert cats["Security"] == 1 and cats["Hardware"] == 1 and cats["Connectivity"] == 1
    assert client.get("/api/analytics/overview?from=2000-01-01&to=2000-01-02").get_json()["data"]["total"] == 0
    assert client.get("/api/analytics/overview?from=bad").status_code == 400
    assert o["total"] == conn.execute("SELECT COUNT(*) AS n FROM complaints").fetchone()["n"]


def test_admin_availability_endpoint_processes_queue(client, conn):
    set_availability(conn, "Admin_HOST", "Busy")
    set_availability(conn, "Backup_HOST", "Busy")
    login(client, STUDENT)
    r = submit(client).get_json()
    assert r["data"]["routing"]["outcome"] == "QUEUED"
    assert "waiting" in r["message"]
    login(client, ADMIN_HOST)
    res = client.patch(f"/api/admins/{admin_id(conn, 'Admin_HOST')}/availability", json={"availability": "Available"})
    assert res.status_code == 200 and len(res.get_json()["data"]["processed"]) == 1


def test_central_reassignment_recorded_in_history(client, conn):
    login(client, STUDENT)
    cid = submit(client).get_json()["data"]["complaint"]["complaint_id"]
    login(client, CENTRAL)
    target = admin_id(conn, "Backup_HOST")
    r = client.patch(f"/api/routing/assignments/{cid}", json={"admin_id": target, "remarks": "Load balancing"})
    assert r.status_code == 200 and r.get_json()["data"]["complaint"]["admin_code"] == "Backup_HOST"
    hist = client.get(f"/api/complaints/{cid}/history").get_json()["data"]["history"]
    assert hist[-1]["action"] == "REASSIGNED" and "Load balancing" in hist[-1]["remarks"]
