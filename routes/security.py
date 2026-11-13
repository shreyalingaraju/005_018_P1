"""Authentication, role-based access control, CSRF and JSON helpers."""
import hmac
import secrets
from functools import wraps

from flask import (abort, current_app, g, jsonify, redirect, request, session, url_for)

from modules import admin_manager, user_manager
from modules.database import get_db
from modules.utils import AppError

CSRF_SESSION_KEY = "_csrf_token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


# ------------------------------------------------------------------ JSON
def ok(data=None, status=200, message=None):
    body = {"success": True, "data": data}
    if message:
        body["message"] = message
    return jsonify(body), status


def fail(message, status=400, code=None, details=None):
    body = {"success": False, "error": message}
    if code:
        body["code"] = code
    if details:
        body["details"] = details
    return jsonify(body), status


def json_body():
    data = request.get_json(silent=True)
    if data is None:
        data = request.form.to_dict() if request.form else {}
    if not isinstance(data, dict):
        raise AppError("Request body must be a JSON object.", 400)
    return data


def is_api_request():
    return request.path.startswith("/api/")


# ------------------------------------------------------------------ CSRF
def get_csrf_token():
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def csrf_protect():
    if not current_app.config.get("CSRF_ENABLED", True):
        return None
    if request.method not in UNSAFE_METHODS:
        return None
    sent = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
    expected = session.get(CSRF_SESSION_KEY)
    if not sent or not expected or not hmac.compare_digest(sent, expected):
        if is_api_request():
            return fail("CSRF token missing or invalid. Refresh the page and try again.", 400, "CSRF")
        abort(400, "CSRF token missing or invalid.")
    return None


# ------------------------------------------------------------------ Auth
def load_current_user():
    g.user = None
    g.admin = None
    uid = session.get("user_id")
    if uid is None:
        return
    db = get_db()
    user = user_manager.get_user(db, uid)
    if user is None:
        session.clear()
        return
    g.user = user
    if user["role"] in ("administrator", "central_admin"):
        g.admin = admin_manager.get_admin_by_user(db, user["id"])


def login_user(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    get_csrf_token()


def _deny(status, message):
    if is_api_request():
        return fail(message, status, "UNAUTHORIZED" if status == 401 else "FORBIDDEN")
    if status == 401:
        return redirect(url_for("auth.login_page", next=request.path))
    abort(403, message)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("user") is None:
            return _deny(401, "Please log in to continue.")
        return view(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    """Restrict a view to the given roles (enforced server-side)."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.get("user") is None:
                return _deny(401, "Please log in to continue.")
            if g.user["role"] not in roles:
                return _deny(403, "You do not have permission to access this resource.")
            return view(*args, **kwargs)
        return wrapper
    return decorator


def home_for(user):
    if user is None:
        return url_for("auth.login_page")
    if user["role"] == "central_admin":
        return url_for("routing.routing_page")
    if user["role"] == "administrator":
        return url_for("admin.admin_page")
    return url_for("user.dashboard_page")
