"""Part A - DFA construction and simulation."""
import itertools

import pytest

from modules import dfa_validator as dfa
from modules.dfa_validator import validate_identifier_dfa

VALID = ["WIFI-HOST-2", "LAN-LAB-1", "WIFI-ADM-3", "LAN-LIB-0", "WIFI-CANT-5", "LAN-SPRT-4", "WIFI-SPRT-9"]


@pytest.mark.parametrize("identifier", VALID)
def test_tc01_02_valid_identifiers_accepted(identifier):
    r = validate_identifier_dfa(identifier)
    assert r["valid"] and r["result"] == "Valid"
    assert r["final_state"] == "q30"
    assert r["error_code"] is None


def test_all_60_language_strings_accepted():
    for dev, loc, fl in itertools.product(dfa.ALLOWED_DEVICES, dfa.ALLOWED_LOCATIONS, range(10)):
        assert validate_identifier_dfa(f"{dev}-{loc}-{fl}")["valid"]


@pytest.mark.parametrize("identifier,code", [
    ("WIFI-XYZ-3", dfa.E_UNSUPPORTED_LOCATION),        # TC03
    ("BLUETOOTH-HOST-2", dfa.E_UNSUPPORTED_DEVICE),    # TC04
    ("WIFI-HOST-12", dfa.E_INVALID_FLOOR),             # TC05
    ("WIFI-HOST", dfa.E_MISSING_FLOOR),                # TC06 incomplete
    ("LAN-LAB-12", dfa.E_INVALID_FLOOR),
    ("WIFI--HOST-2", dfa.E_SEPARATOR),
    ("WIFI-HOST-A", dfa.E_INVALID_FLOOR),
    ("WIFI-HOST-22", dfa.E_INVALID_FLOOR),
    ("wifi-host-2", dfa.E_CASE),
    ("", dfa.E_EMPTY),
    ("-HOST-2", dfa.E_MISSING_DEVICE),
    ("WIFI-", dfa.E_MISSING_LOCATION),
    ("WIFI-HOST-", dfa.E_MISSING_FLOOR),
    ("WIFI-HOST2", dfa.E_SEPARATOR),
    ("WIFI-HOST-2X", dfa.E_EXTRA),
    ("ETH-LAB-1", dfa.E_UNSUPPORTED_DEVICE),
    ("WIFI HOST 2", dfa.E_WHITESPACE),
])
def test_invalid_identifiers_rejected_with_specific_error(identifier, code):
    r = validate_identifier_dfa(identifier)
    assert not r["valid"]
    assert r["error_code"] == code, r["message"]
    assert r["message"]


def test_specific_messages():
    assert validate_identifier_dfa("BLUETOOTH-HOST-2")["message"] == \
        "Unsupported device type. Allowed types are WIFI and LAN."
    assert validate_identifier_dfa("WIFI-HOST-12")["message"] == \
        "Invalid floor number. Only one digit from 0 to 9 is allowed."


def test_dead_state_is_absorbing_and_trace_is_character_by_character():
    r = validate_identifier_dfa("WIXI-HOST-2")
    assert r["final_state"] == dfa.DEAD_STATE
    assert [t["char"] for t in r["trace"]] == ["W", "I", "X"]  # stops once in qD
    assert r["trace"][-1]["to"] == "qD"
    ok = validate_identifier_dfa("LAN-LIB-0")
    assert [t["from"] for t in ok["trace"]][:3] == ["q0", "q5", "q6"]
    assert len(ok["trace"]) == len("LAN-LIB-0")


def test_transition_table_is_deterministic_and_complete():
    for state, row in dfa.TRANSITIONS.items():
        assert state in dfa.STATES
        for sym, nxt in row.items():
            assert nxt in dfa.STATES
    assert dfa.delta("q0", "Z") == dfa.DEAD_STATE
    assert dfa.delta("q29", "7") == "q30"
    definition = dfa.get_dfa_definition()
    assert definition["start_state"] == "q0" and definition["accept_states"] == ["q30"]


def test_dfa_module_does_not_use_regex():
    import inspect
    src = inspect.getsource(dfa)
    assert "import re" not in src and "re.match" not in src
