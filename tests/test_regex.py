"""Part A - regular expression validation and DFA/regex equivalence."""
import itertools
import random
import string

from modules.dfa_validator import validate_identifier_dfa
from modules.regex_validator import IDENTIFIER_PATTERN, validate_identifier_regex
from services.validation_service import compare_many, compare_validators


def test_regex_pattern_is_exact():
    assert IDENTIFIER_PATTERN == r"^(WIFI|LAN)-(HOST|LAB|ADM|LIB|CANT|SPRT)-[0-9]$"


def test_regex_full_match_not_substring():
    assert validate_identifier_regex("WIFI-HOST-2")["valid"]
    assert not validate_identifier_regex("XWIFI-HOST-2")["valid"]
    assert not validate_identifier_regex("WIFI-HOST-2 ")["valid"]
    assert not validate_identifier_regex("WIFI-HOST-2\n")["valid"]
    assert validate_identifier_regex("LAN-CANT-0")["groups"] == {"device_type": "LAN", "location_code": "CANT", "floor": 0}


def test_tc07_dfa_and_regex_agree_on_spec_examples():
    samples = ["WIFI-HOST-2", "LAN-LAB-1", "WIFI-ADM-3", "LAN-LIB-0", "WIFI-CANT-5", "LAN-SPRT-4",
               "WIFI-HOST", "LAN-LAB-12", "BLUETOOTH-HOST-2", "WIFI-XYZ-3", "WIFI--HOST-2",
               "WIFI-HOST-A", "WIFI-HOST-22", "wifi-host-2"]
    report = compare_many(samples)
    assert report["all_agree"]
    assert [r["dfa"] for r in report["rows"]][:6] == ["Valid"] * 6
    assert all(r["dfa"] == "Invalid" for r in report["rows"][6:])


def test_dfa_and_regex_agree_on_random_and_near_miss_strings():
    rng = random.Random(503)
    alphabet = "WIFLANHOSTBDMCPR-0123456789x "
    near = ["-".join(p) for p in itertools.product(["WIFI", "LAN", "WIF", "LANN", "wifi"],
                                                    ["HOST", "LAB", "LIBB", "AD", "CANT", "SPR"],
                                                    ["0", "9", "10", "", "a"])]
    rand = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 14))) for _ in range(3000)]
    for s in near + rand + list(string.printable):
        assert validate_identifier_dfa(s)["valid"] == validate_identifier_regex(s)["valid"], s


def test_compare_validators_reports_both_results():
    r = compare_validators("LAN-LAB-12")
    assert r["match"] and not r["valid"]
    assert r["dfa"]["result"] == "Invalid" and r["regex"]["result"] == "Invalid"
