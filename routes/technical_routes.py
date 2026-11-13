"""Technical overview page plus validation / classification APIs."""
from flask import Blueprint, render_template

from modules.complaint_classifier import CATEGORY_KEYWORDS, CATEGORY_PRECEDENCE
from modules.dfa_validator import get_dfa_definition, validate_identifier_dfa
from modules.priority_manager import CATEGORY_PRIORITY
from modules.regex_validator import IDENTIFIER_PATTERN, validate_identifier_regex
from modules.utils import AppError
from routes.security import json_body, login_required, ok
from services.classification_service import analyze_description
from services.validation_service import compare_many, compare_validators

bp = Blueprint("technical", __name__)


def _identifier():
    value = json_body().get("identifier")
    if value is not None and not isinstance(value, str):
        raise AppError("identifier must be a string.", 400)
    if value is not None and len(value) > 100:
        raise AppError("identifier is too long.", 400)
    return value or ""


@bp.get("/technical")
@login_required
def technical_page():
    return render_template("dfa_visualizer.html")


@bp.get("/api/dfa/definition")
def dfa_definition():
    return ok({"dfa": get_dfa_definition(), "regex": IDENTIFIER_PATTERN})


@bp.post("/api/validate")
def validate():
    return ok(compare_validators(_identifier()))


@bp.post("/api/validate/dfa")
def validate_dfa():
    return ok(validate_identifier_dfa(_identifier()))


@bp.post("/api/validate/regex")
def validate_regex():
    return ok(validate_identifier_regex(_identifier()))


@bp.post("/api/validate/compare")
def validate_compare():
    data = json_body()
    identifiers = data.get("identifiers")
    if isinstance(identifiers, list):
        if not all(isinstance(i, str) and len(i) <= 100 for i in identifiers):
            raise AppError("identifiers must be a list of strings.", 400)
        return ok(compare_many(identifiers))
    return ok(compare_validators(_identifier()))


@bp.post("/api/classify")
def classify():
    text = json_body().get("description") or ""
    if not isinstance(text, str) or len(text) > 1000:
        raise AppError("description must be a string of at most 1000 characters.", 400)
    return ok(analyze_description(text))


@bp.get("/api/classify/keywords")
def keywords():
    return ok({"keywords": CATEGORY_KEYWORDS, "precedence": list(CATEGORY_PRECEDENCE) + ["Unknown"],
               "priority_map": CATEGORY_PRIORITY})
