"""Combines the DFA and regex validators and compares their verdicts."""
import logging

from modules.dfa_validator import validate_identifier_dfa
from modules.regex_validator import validate_identifier_regex

log = logging.getLogger("campus_netwatch.validation")


def compare_validators(identifier):
    """Run both validators on the same input and report agreement."""
    dfa = validate_identifier_dfa(identifier)
    regex = validate_identifier_regex(identifier)
    agree = dfa["valid"] == regex["valid"]
    if not agree:
        # Should never happen: the two recognisers describe the same language.
        log.error("DFA/regex disagreement for %r: dfa=%s regex=%s",
                  identifier, dfa["result"], regex["result"])
    return {
        "identifier": dfa["identifier"],
        "dfa": dfa,
        "regex": regex,
        "match": agree,
        "match_label": "Yes" if agree else "No",
        "valid": dfa["valid"] and regex["valid"],
        "message": dfa["message"] if not dfa["valid"] else regex["message"] if not regex["valid"]
        else "Identifier is valid (DFA and regular expression agree).",
        "error_code": dfa["error_code"],
    }


def compare_many(identifiers):
    rows = []
    for ident in identifiers[:100]:
        r = compare_validators(ident)
        rows.append({
            "identifier": r["identifier"],
            "dfa": r["dfa"]["result"],
            "dfa_final_state": r["dfa"]["final_state"],
            "regex": r["regex"]["result"],
            "match": r["match_label"],
            "message": r["message"],
        })
    return {"rows": rows, "all_agree": all(r["match"] == "Yes" for r in rows)}


def build_identifier(device_type, location_code, floor):
    """Assemble DEVICE-LOCATION-FLOOR from form values without altering them."""
    return f"{'' if device_type is None else str(device_type)}-" \
           f"{'' if location_code is None else str(location_code)}-" \
           f"{'' if floor is None else str(floor)}"
