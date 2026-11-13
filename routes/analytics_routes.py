"""Analytics page and API (all values computed from SQLite)."""
from datetime import date

from flask import Blueprint, render_template, request

from modules import analytics
from modules.database import get_db
from modules.utils import AppError
from routes.security import login_required, ok

bp = Blueprint("analytics", __name__)


def _range():
    out = []
    for key in ("from", "to"):
        value = request.args.get(key) or None
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                raise AppError(f"Invalid '{key}' date; use YYYY-MM-DD.", 400)
        out.append(value)
    return out


@bp.get("/analytics")
@login_required
def analytics_page():
    return render_template("analytics_dashboard.html")


@bp.get("/api/analytics/overview")
@login_required
def overview():
    return ok(analytics.overview(get_db(), *_range()))


@bp.get("/api/analytics/zones")
@login_required
def zones():
    return ok(analytics.by_zone(get_db(), *_range()))


@bp.get("/api/analytics/categories")
@login_required
def categories():
    return ok(analytics.by_category(get_db(), *_range()))


@bp.get("/api/analytics/priorities")
@login_required
def priorities():
    return ok(analytics.by_priority(get_db(), *_range()))


@bp.get("/api/analytics/status")
@login_required
def status():
    return ok(analytics.by_status(get_db(), *_range()))


@bp.get("/api/analytics/timeline")
@login_required
def timeline():
    return ok(analytics.timeline(get_db(), *_range()))


@bp.get("/api/analytics/report")
@login_required
def report():
    return ok(analytics.full_report(get_db(), *_range()))
