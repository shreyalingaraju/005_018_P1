"""Shared pytest fixtures: every test gets its own freshly seeded SQLite file."""
import os
import shutil
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app  # noqa: E402
from config import TestingConfig  # noqa: E402
from database.seed import initialize_database  # noqa: E402
from modules.database import connect  # noqa: E402

STUDENT = ("student@campus.edu", "Student@123")
STUDENT2 = ("rahul@campus.edu", "Student@123")
ADMIN_HOST = ("admin.host@campus.edu", "Admin@123")
BACKUP_HOST = ("backup.host@campus.edu", "Admin@123")
ADMIN_LAB = ("admin.lab@campus.edu", "Admin@123")
CENTRAL = ("central@campus.edu", "Central@123")


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("template") / "template.db"
    initialize_database(str(path), demo_complaints=False, hash_method=TestingConfig.PASSWORD_HASH_METHOD)
    return path


@pytest.fixture
def app(template_db, tmp_path):
    db_path = tmp_path / "test.db"
    shutil.copy(template_db, db_path)
    return create_app(TestingConfig, DATABASE=str(db_path))


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def conn(app):
    c = connect(app.config["DATABASE"])
    yield c
    c.close()


def login(client, creds):
    resp = client.post("/api/auth/login", json={"email": creds[0], "password": creds[1]})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["data"]["user"]


def admin_id(conn, code):
    return conn.execute("SELECT id FROM administrators WHERE admin_code = ?", (code,)).fetchone()["id"]


def set_availability(conn, code, value):
    conn.execute("UPDATE administrators SET availability = ? WHERE admin_code = ?", (value, code))


def submit(client, device="WIFI", location="HOST", floor="2", description="My WiFi is disconnected.",
           name="Aarav Sharma", inst="1RV22CS001"):
    return client.post("/api/complaints", json={
        "name": name, "institutional_id": inst, "device_type": device, "location_code": location,
        "floor": floor, "description": description})
