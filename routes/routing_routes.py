"""Routing management (central administrator) pages and API."""
from flask import Blueprint, g, render_template, request

from modules import queue_manager, routing_engine
from modules.database import get_db
from modules.utils import AppError
from routes.security import json_body, login_required, ok, roles_required

bp = Blueprint("routing", __name__)


@bp.get("/routing")
@roles_required("central_admin")
def routing_page():
    return render_template("routing_dashboard.html")


@bp.get("/api/routing/zones")
@roles_required("administrator", "central_admin")
def zones():
    return ok(routing_engine.get_zone_overview(get_db()))


@bp.get("/api/routing/table")
@login_required
def table():
    return ok({"routing_table": routing_engine.get_routing_table(get_db())})


@bp.patch("/api/routing/table/<location_code>")
@roles_required("central_admin")
def update_table(location_code):
    data = json_body()
    result = routing_engine.update_routing_entry(get_db(), location_code.upper(), data.get("primary_admin_id"),
                                                 data.get("backup_admin_id"), g.user)
    return ok(result, message=f"Routing entry for {location_code.upper()} updated.")


@bp.get("/api/routing/queue")
@roles_required("administrator", "central_admin")
def queue():
    return ok({"queue": queue_manager.get_waiting(get_db(), request.args.get("zone") or None)})


@bp.post("/api/routing/process-queue")
@roles_required("central_admin")
def process_queue():
    zone = (json_body().get("zone") or None)
    assigned = routing_engine.process_waiting_queue(get_db(), zone, g.user)
    msg = f"{len(assigned)} complaint(s) assigned from the queue." if assigned else \
        "No complaints could be assigned (queue empty or administrators busy)."
    return ok({"assigned": assigned}, message=msg)


@bp.patch("/api/routing/assignments/<complaint_id>")
@roles_required("central_admin")
def reassign(complaint_id):
    data = json_body()
    if not data.get("admin_id"):
        raise AppError("admin_id is required.", 400)
    complaint = routing_engine.reassign_complaint(get_db(), complaint_id, data["admin_id"], g.user,
                                                  data.get("remarks"))
    return ok({"complaint": complaint}, message=f"Complaint reassigned to {complaint['admin_name']}.")


@bp.get("/api/routing/history")
@roles_required("central_admin")
def reassignment_history():
    db = get_db()
    rows = db.execute(
        "SELECT h.changed_at, h.action, h.remarks, h.changed_by_name, c.complaint_id, c.identifier "
        "FROM complaint_history h JOIN complaints c ON c.id = h.complaint_id "
        "WHERE h.action IN ('REASSIGNED', 'FORWARDED_CENTRAL', 'QUEUED') "
        "OR (h.action = 'ASSIGNED' AND (h.remarks LIKE '%backup%' OR h.remarks LIKE '%waiting queue%')) "
        "ORDER BY h.changed_at DESC, h.id DESC LIMIT 50").fetchall()
    audit = db.execute("SELECT created_at, actor_name, action, entity_type, entity_id, details "
                       "FROM audit_logs ORDER BY id DESC LIMIT 50").fetchall()
    return ok({"history": [dict(r) for r in rows], "audit": [dict(r) for r in audit]})


@bp.post("/api/routing/preview")
@login_required
def preview():
    from services.validation_service import compare_validators
    identifier = json_body().get("identifier") or ""
    validation = compare_validators(identifier)
    if not validation["valid"]:
        raise AppError(validation["message"], 400, code=validation["error_code"])
    return ok(routing_engine.preview_route(get_db(), identifier))
