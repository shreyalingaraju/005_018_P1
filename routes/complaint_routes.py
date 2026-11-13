"""Complaint REST API."""
from flask import Blueprint, g, request

from modules import complaint_manager
from modules.complaint_classifier import CATEGORIES
from modules.database import get_db, transaction
from modules.utils import AppError
from routes.security import json_body, login_required, ok, roles_required
from services.routing_service import submit_complaint

bp = Blueprint("complaints", __name__, url_prefix="/api/complaints")


def _filters():
    status = request.args.get("status") or None
    category = request.args.get("category") or None
    if status and status not in complaint_manager.STATUSES:
        raise AppError("Invalid status filter.", 400)
    if category and category not in CATEGORIES:
        raise AppError("Invalid category filter.", 400)
    return {
        "status": status, "category": category,
        "priority": request.args.get("priority") or None,
        "zone": request.args.get("zone") or None,
        "search": (request.args.get("q") or "").strip()[:60] or None,
    }


def _load_visible(complaint_id):
    db = get_db()
    complaint = complaint_manager.get_complaint(db, complaint_id)
    if complaint is None:
        raise AppError("Complaint not found. Check the complaint ID.", 404)
    if not complaint_manager.can_view(complaint, g.user, g.admin):
        raise AppError("Access denied: you can only view your own complaints.", 403)
    return complaint


@bp.post("")
@roles_required("user")
def create():
    result = submit_complaint(get_db(), g.user, json_body())
    routing = result["routing"]
    if routing["admin"]:
        msg = f"Complaint registered and assigned to {routing['admin']['name']}."
    else:
        msg = "Complaint registered. All administrators are busy - it is waiting in the priority queue."
    return ok(result, 201, msg)


@bp.get("")
@login_required
def list_all():
    """Role-aware listing: users -> own, admins -> assigned, central -> all."""
    db = get_db()
    f = _filters()
    if g.user["role"] == "user":
        rows = complaint_manager.list_complaints(db, user_id=g.user["id"], **f)
    elif g.user["role"] == "administrator":
        rows = complaint_manager.list_complaints(db, admin_id=g.admin["id"] if g.admin else -1, **f)
    else:
        rows = complaint_manager.list_complaints(db, **f)
    return ok({"complaints": rows, "count": len(rows)})


@bp.get("/my")
@roles_required("user")
def my_complaints():
    db = get_db()
    rows = complaint_manager.list_complaints(db, user_id=g.user["id"], **_filters())
    return ok({"complaints": rows, "summary": complaint_manager.status_counts(db, user_id=g.user["id"])})


@bp.get("/<complaint_id>")
@login_required
def detail(complaint_id):
    complaint = _load_visible(complaint_id)
    history = complaint_manager.get_history(get_db(), complaint["id"])
    return ok({"complaint": complaint, "history": history})


@bp.get("/track/<complaint_id>")
@login_required
def track(complaint_id):
    complaint = _load_visible(complaint_id)
    db = get_db()
    queue = db.execute("SELECT queue_position, zone_code FROM waiting_queue WHERE complaint_id = ?",
                       (complaint["id"],)).fetchone()
    return ok({"complaint": complaint, "history": complaint_manager.get_history(db, complaint["id"]),
               "queue": dict(queue) if queue else None})


@bp.get("/<complaint_id>/history")
@login_required
def history(complaint_id):
    complaint = _load_visible(complaint_id)
    return ok({"complaint_id": complaint["complaint_id"],
               "history": complaint_manager.get_history(get_db(), complaint["id"])})


@bp.patch("/<complaint_id>/status")
@roles_required("administrator", "central_admin")
def update_status(complaint_id):
    data = json_body()
    db = get_db()
    with transaction(db):
        complaint = complaint_manager.update_status(db, complaint_id, data.get("status"), g.user, g.admin,
                                                    data.get("remarks"))
    return ok({"complaint": complaint, "history": complaint_manager.get_history(db, complaint["id"])},
              message=f"Status updated to {complaint['status']}.")
