"""Login, registration and session endpoints."""
from flask import Blueprint, current_app, g, redirect, render_template, request, session

from modules import user_manager
from modules.database import get_db, transaction
from routes.security import fail, home_for, json_body, login_required, login_user, ok

bp = Blueprint("auth", __name__)


def _safe_next(target):
    # Only allow local redirects to prevent open-redirects.
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


# ------------------------------------------------------------------ pages
@bp.get("/")
def index():
    if g.user:
        return redirect(home_for(g.user))
    return redirect("/login")


@bp.get("/login")
def login_page():
    if g.user:
        return redirect(home_for(g.user))
    return render_template("login.html", next=_safe_next(request.args.get("next")))


@bp.get("/register")
def register_page():
    if g.user:
        return redirect(home_for(g.user))
    return render_template("register.html")


@bp.get("/logout")
def logout_page():
    session.clear()
    return redirect("/login")


# ------------------------------------------------------------------ API
@bp.post("/api/auth/register")
def api_register():
    data = json_body()
    db = get_db()
    with transaction(db):
        user = user_manager.register_user(db, data, current_app.config.get("PASSWORD_HASH_METHOD"))
    login_user(user)
    return ok({"user": user, "redirect": home_for(user)}, 201, "Registration successful.")


@bp.post("/api/auth/login")
def api_login():
    data = json_body()
    user = user_manager.authenticate(get_db(), data.get("email"), data.get("password"))
    if user is None:
        return fail("Invalid email or password.", 401, "INVALID_CREDENTIALS")
    login_user(user)
    target = _safe_next(data.get("next")) or home_for(user)
    return ok({"user": user, "redirect": target}, message=f"Welcome back, {user['name']}!")


@bp.post("/api/auth/logout")
def api_logout():
    session.clear()
    return ok({"redirect": "/login"}, message="Logged out.")


@bp.get("/api/auth/me")
@login_required
def api_me():
    return ok({"user": g.user, "admin": g.admin})
