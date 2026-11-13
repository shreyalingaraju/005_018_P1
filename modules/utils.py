"""Small shared helpers."""
import json
from datetime import datetime

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_str():
    return datetime.now().strftime(TIME_FORMAT)


def to_json(value):
    return json.dumps(value, ensure_ascii=False)


def from_json(value, default):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class AppError(Exception):
    """Business-rule error carrying an HTTP status and optional details."""

    def __init__(self, message, status=400, code=None, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.details = details or {}


def write_audit(conn, action, entity_type, entity_id=None, details=None, actor=None):
    """Insert an audit-log row. `actor` is a user dict (or None for System)."""
    conn.execute(
        "INSERT INTO audit_logs (actor_user_id, actor_name, action, entity_type, entity_id, details, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            actor["id"] if actor else None,
            actor["name"] if actor else "System",
            action, entity_type,
            str(entity_id) if entity_id is not None else None,
            details, now_str(),
        ),
    )
