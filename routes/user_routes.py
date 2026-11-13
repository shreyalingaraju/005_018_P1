"""Student / faculty pages."""
from flask import Blueprint, render_template

from routes.security import login_required, roles_required

bp = Blueprint("user", __name__)


@bp.get("/dashboard")
@roles_required("user")
def dashboard_page():
    return render_template("user_dashboard.html")


@bp.get("/complaints/new")
@roles_required("user")
def submit_page():
    return render_template("submit_complaint.html")


@bp.get("/track")
@login_required
def track_page():
    return render_template("track_complaint.html")
