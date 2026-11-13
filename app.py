"""
CAMPUS NETWATCH - Campus Network Fault Reporter and Intelligent Complaint Routing System.

Run:  python app.py      (then open http://127.0.0.1:5000)
"""
import logging
import os

from flask import Flask, g, render_template
from werkzeug.exceptions import HTTPException

from config import Config
from database.seed import initialize_database
from modules.database import close_db
from modules.utils import AppError
from routes import (admin_routes, analytics_routes, auth_routes, complaint_routes, routing_routes,
                    technical_routes, user_routes)
from routes.security import csrf_protect, fail, get_csrf_token, is_api_request, load_current_user


def create_app(config_object=Config, **overrides):
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.config.update(overrides)
    app.json.sort_keys = False

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Create and seed the database automatically if it does not exist.
    if initialize_database(app.config["DATABASE"], app.config["SEED_DEMO_COMPLAINTS"],
                           app.config.get("PASSWORD_HASH_METHOD")):
        app.logger.info("Initialised new database at %s", app.config["DATABASE"])

    app.teardown_appcontext(close_db)

    @app.before_request
    def _before():
        load_current_user()
        return csrf_protect()

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if is_api_request():
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.context_processor
    def _inject():
        return {"csrf_token": get_csrf_token, "current_user": g.get("user"), "current_admin": g.get("admin"),
                "app_name": app.config["APP_NAME"], "app_tagline": app.config["APP_TAGLINE"]}

    for module in (auth_routes, user_routes, complaint_routes, admin_routes, routing_routes,
                   analytics_routes, technical_routes):
        app.register_blueprint(module.bp)

    @app.errorhandler(AppError)
    def _app_error(err):
        if is_api_request():
            return fail(err.message, err.status, err.code, err.details)
        return render_template("error.html", code=err.status, message=err.message), err.status

    @app.errorhandler(HTTPException)
    def _http_error(err):
        if is_api_request():
            return fail(err.description or err.name, err.code)
        return render_template("error.html", code=err.code, message=err.description), err.code

    @app.errorhandler(Exception)
    def _unhandled(err):
        app.logger.exception("Unhandled error: %s", err)
        if is_api_request():
            return fail("Internal server error.", 500)
        return render_template("error.html", code=500, message="Something went wrong."), 500

    return app


if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("CNFR_HOST", "127.0.0.1")
    port = int(os.environ.get("CNFR_PORT", "5000"))
    app.run(host=host, port=port, debug=os.environ.get("CNFR_DEBUG", "0") == "1")
