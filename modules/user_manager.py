"""User accounts: registration, authentication and safe serialisation."""
import re

from werkzeug.security import check_password_hash, generate_password_hash

from modules.utils import AppError, now_str

ROLES = ("user", "administrator", "central_admin")
ROLE_LABELS = {
    "user": "Student / Faculty",
    "administrator": "Network Administrator",
    "central_admin": "Central Administrator",
}

DEFAULT_HASH_METHOD = "scrypt"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_INST_ID_RE = re.compile(r"^[A-Za-z0-9]{3,20}$")


def hash_password(password, method=None):
    return generate_password_hash(password, method=method or DEFAULT_HASH_METHOD)


def verify_password(password_hash, password):
    return check_password_hash(password_hash, password or "")


def public_user(row):
    """Return a user dict without the password hash."""
    if row is None:
        return None
    data = dict(row)
    data.pop("password_hash", None)
    data["role_label"] = ROLE_LABELS.get(data.get("role"), data.get("role"))
    return data


def validate_registration(data):
    errors = {}
    name = (data.get("name") or "").strip()
    inst = (data.get("institutional_id") or "").strip().upper()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm = data.get("confirm_password")

    if not 2 <= len(name) <= 80:
        errors["name"] = "Full name must be between 2 and 80 characters."
    if not _INST_ID_RE.match(inst):
        errors["institutional_id"] = "USN / Faculty ID must be 3-20 letters or digits."
    if not _EMAIL_RE.match(email) or len(email) > 120:
        errors["email"] = "Enter a valid email address."
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errors["password"] = "Password must be at least 8 characters and contain letters and digits."
    if confirm is not None and confirm != password:
        errors["confirm_password"] = "Passwords do not match."
    return {"name": name, "institutional_id": inst, "email": email, "password": password}, errors


def create_user(conn, name, institutional_id, email, password, role="user", hash_method=None):
    if role not in ROLES:
        raise AppError("Invalid role.", 400)
    if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise AppError("An account with this email already exists.", 409,
                       details={"email": "Email already registered."})
    if conn.execute("SELECT 1 FROM users WHERE institutional_id = ?", (institutional_id,)).fetchone():
        raise AppError("An account with this USN / Faculty ID already exists.", 409,
                       details={"institutional_id": "ID already registered."})
    cur = conn.execute(
        "INSERT INTO users (name, institutional_id, email, password_hash, role, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, institutional_id, email, hash_password(password, hash_method), role, now_str()),
    )
    return cur.lastrowid


def register_user(conn, data, hash_method=None):
    clean, errors = validate_registration(data)
    if errors:
        raise AppError("Please correct the highlighted fields.", 400, details=errors)
    user_id = create_user(conn, clean["name"], clean["institutional_id"], clean["email"],
                          clean["password"], "user", hash_method)
    return get_user(conn, user_id)


def get_user(conn, user_id):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row)


def authenticate(conn, email, password):
    email = (email or "").strip().lower()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not verify_password(row["password_hash"], password):
        return None
    return public_user(row)
