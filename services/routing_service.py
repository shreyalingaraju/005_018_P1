"""
End-to-end complaint workflow:

validate fields -> build identifier -> DFA -> regex -> compare -> classify ->
priority -> duplicate check -> store (Pending) -> route -> assign / queue.
"""
import re

from modules import complaint_manager, routing_engine
from modules.database import transaction
from modules.utils import AppError
from services.classification_service import analyze_description
from services.validation_service import build_identifier, compare_validators

_INST_ID_RE = re.compile(r"^[A-Za-z0-9]{3,20}$")


def _validate_fields(payload):
    errors = {}
    name = (payload.get("name") or "").strip()
    inst = (payload.get("institutional_id") or "").strip().upper()
    desc = " ".join((payload.get("description") or "").split())
    if not 2 <= len(name) <= 80:
        errors["name"] = "Name must be between 2 and 80 characters."
    if not _INST_ID_RE.match(inst):
        errors["institutional_id"] = "USN / Faculty ID must be 3-20 letters or digits."
    if len(desc) < 10:
        errors["description"] = "Please describe the problem (at least 10 characters)."
    elif len(desc) > 1000:
        errors["description"] = "Description must be at most 1000 characters."
    return name, inst, desc, errors


def resolve_identifier(payload):
    if any(k in payload for k in ("device_type", "location_code", "floor")):
        return build_identifier(payload.get("device_type"), payload.get("location_code"),
                                payload.get("floor"))
    return payload.get("identifier") or ""


def submit_complaint(conn, user, payload):
    name, inst, desc, errors = _validate_fields(payload)
    identifier = resolve_identifier(payload)
    validation = compare_validators(identifier)

    if not validation["valid"]:
        errors["identifier"] = validation["message"]
    if errors:
        # Malformed identifier or bad fields: reject, nothing is written.
        raise AppError(validation["message"] if "identifier" in errors else
                       "Please correct the highlighted fields.", 400,
                       code=validation["error_code"] or "FIELD_VALIDATION",
                       details={"fields": errors, "validation": _validation_summary(validation)})
    if not validation["match"]:
        raise AppError("Internal validator mismatch; complaint rejected for safety.", 500)

    classification = analyze_description(desc)
    parts = validation["dfa"]["parts"]

    with transaction(conn):
        duplicate = complaint_manager.find_open_duplicate(conn, user["id"], identifier, desc)
        if duplicate:
            raise AppError(f"An identical open complaint already exists ({duplicate}).", 409,
                           code="DUPLICATE", details={"complaint_id": duplicate})
        pk = complaint_manager.insert_complaint(conn, {
            "user_id": user["id"], "user_name": name, "institutional_id": inst,
            "device_type": parts["device_type"], "location_code": parts["location_code"],
            "floor_number": parts["floor"], "identifier": identifier, "description": desc,
            "category": classification["category"],
            "matched_keywords": classification["matched_keywords"],
            "detected_categories": classification["detected_categories"],
            "priority": classification["priority"], "priority_rank": classification["priority_rank"],
        }, actor=user)
        routing = routing_engine.route_complaint(conn, pk, actor=user)
        complaint = complaint_manager.get_by_pk(conn, pk)

    return {
        "complaint": complaint,
        "validation": _validation_summary(validation),
        "classification": classification,
        "routing": routing,
    }


def _validation_summary(v):
    return {
        "identifier": v["identifier"],
        "valid": v["valid"],
        "match": v["match"],
        "message": v["message"],
        "error_code": v["error_code"],
        "dfa": {"result": v["dfa"]["result"], "final_state": v["dfa"]["final_state"],
                "final_state_label": v["dfa"]["final_state_label"], "message": v["dfa"]["message"],
                "trace": v["dfa"]["trace"]},
        "regex": {"result": v["regex"]["result"], "pattern": v["regex"]["pattern"],
                  "message": v["regex"]["message"]},
    }
