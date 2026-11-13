"""
Regular-expression validator for campus location identifiers.

The regular expression is the language-equivalent of the DFA in dfa_validator:

    ^(WIFI|LAN)-(HOST|LAB|ADM|LIB|CANT|SPRT)-[0-9]$

Formal regular expression (over Σ = {A-Z, 0-9, -}):
    (WIFI + LAN) · - · (HOST + LAB + ADM + LIB + CANT + SPRT) · - · (0+1+…+9)

`re.fullmatch` is used so the WHOLE string must match (no substring search).
"""
import re

IDENTIFIER_PATTERN = r"^(WIFI|LAN)-(HOST|LAB|ADM|LIB|CANT|SPRT)-[0-9]$"
_COMPILED = re.compile(IDENTIFIER_PATTERN)


def validate_identifier_regex(identifier):
    """
    Validate the identifier with the regular expression.

    Returns dict: valid, result, message, pattern, groups.
    """
    if identifier is None:
        identifier = ""
    if not isinstance(identifier, str):
        identifier = str(identifier)

    # Note: `$` in Python also matches before a trailing "\n"; fullmatch prevents that.
    match = _COMPILED.fullmatch(identifier)
    if match:
        device, location = match.groups()
        floor = int(identifier[-1])
        return {
            "valid": True,
            "result": "Valid",
            "identifier": identifier,
            "pattern": IDENTIFIER_PATTERN,
            "message": "Identifier fully matches the regular expression.",
            "groups": {"device_type": device, "location_code": location, "floor": floor},
        }
    return {
        "valid": False,
        "result": "Invalid",
        "identifier": identifier,
        "pattern": IDENTIFIER_PATTERN,
        "message": f"Identifier does not match the pattern {IDENTIFIER_PATTERN}.",
        "groups": None,
    }
