"""Network administrator pages and API."""
from flask import Blueprint, current_app, g, render_template

from modules import admin_manager, complaint_manager, routing_engine
from modules.database import get_db, transaction
from modules.utils import AppError
from routes.security import json_body, ok, roles_required

bp = Blueprint("admin", __name__)


@bp.get("/admin")
@roles_required("administrator", "central_admin")
def admin_page():
    return render_template("admin_dashboard.html")


@bp.get("/api/admins")
@roles_required("administrator", "central_admin")
def list_admins():
    return ok({"admins": admin_manager.list_admins(get_db())})


@bp.post("/api/admins")
@roles_required("central_admin")
def create_admin():
    db = get_db()
    with transaction(db):
        admin = admin_manager.create_admin(db, json_body(), g.user, current_app.config.get("PASSWORD_HASH_METHOD"))
    return ok({"admin": admin}, 201, f"Administrator {admin['name']} created.")


@bp.patch("/api/admins/<int:admin_id>")
@roles_required("central_admin")
def update_admin(admin_id):
    db = get_db()
    with transaction(db):
        admin = admin_manager.update_admin(db, admin_id, json_body(), g.user)
        processed = routing_engine.process_waiting_queue(db, actor=g.user) if admin["is_active"] else []
    return ok({"admin": admin, "processed": processed}, message="Administrator updated.")


@bp.get("/api/admins/me/complaints")
@roles_required("administrator", "central_admin")
def my_complaints():
    db = get_db()
    if g.admin is None:
        raise AppError("No administrator profile is linked to this account.", 404)
    rows = complaint_manager.list_complaints(db, admin_id=g.admin["id"])
    return ok({"admin": admin_manager.get_admin(db, g.admin["id"]), "complaints": rows,
               "summary": complaint_manager.status_counts(db, admin_id=g.admin["id"])})


@bp.get("/api/admins/<int:admin_id>/complaints")
@roles_required("administrator", "central_admin")
def admin_complaints(admin_id):
    if g.user["role"] != "central_admin" and (g.admin is None or g.admin["id"] != admin_id):
        raise AppError("Access denied: you can only view your own assigned complaints.", 403)
    db = get_db()
    if admin_manager.get_admin(db, admin_id) is None:
        raise AppError("Administrator not found.", 404)
    return ok({"complaints": complaint_manager.list_complaints(db, admin_id=admin_id),
               "summary": complaint_manager.status_counts(db, admin_id=admin_id)})


@bp.patch("/api/admins/<int:admin_id>/availability")
@roles_required("administrator", "central_admin")
def set_availability(admin_id):
    if g.user["role"] != "central_admin" and (g.admin is None or g.admin["id"] != admin_id):
        raise AppError("Access denied: you can only change your own availability.", 403)
    status = json_body().get("availability")
    result = routing_engine.update_administrator_availability(get_db(), admin_id, status, g.user)
    n = len(result["processed"])
    msg = f"Availability set to {status}."
    if n:
        msg += f" {n} waiting complaint(s) were assigned automatically."
    return ok(result, message=msg)
