"""Part A - complaint classification."""
import pytest

from modules.complaint_classifier import classify_complaint


@pytest.mark.parametrize("text,category", [
    ("There is no internet in my room since morning.", "Connectivity"),        # TC08
    ("Router failure in the lab, nothing works.", "Hardware"),                   # TC09
    ("Windows shows an IP conflict on my laptop.", "Configuration"),            # TC10
    ("Someone got unauthorized access to the lab server.", "Security"),         # TC11
    ("The projector remote is missing from the hall.", "Unknown"),              # TC12
    ("My WiFi is disconnected and internet is very slow.", "Connectivity"),
    ("DHCP not assigning address, wrong gateway.", "Configuration"),
    ("Access point is overheating and switches off.", "Hardware"),
])
def test_categories(text, category):
    assert classify_complaint(text)["category"] == category


def test_tc13_security_takes_precedence_over_other_categories():
    r = classify_complaint("My WiFi is disconnected and someone attempted unauthorized access via the router.")
    assert r["category"] == "Security"
    assert r["detected_categories"] == ["Security", "Hardware", "Connectivity"]
    assert "unauthorized access" in r["matched_keywords"]["Security"]
    assert "precedence" in r["explanation"]


def test_precedence_hardware_over_configuration_over_connectivity():
    assert classify_complaint("Switch broken and DNS error, slow internet")["category"] == "Hardware"
    assert classify_complaint("DNS error and slow internet")["category"] == "Configuration"


def test_unknown_has_no_keywords_and_is_case_insensitive():
    r = classify_complaint("Lights flicker in corridor")
    assert r["category"] == "Unknown" and r["all_matched_keywords"] == []
    assert classify_complaint("ROUTER IS DEAD")["category"] == "Hardware"


def test_word_boundaries_avoid_false_positives():
    # 'lag' must not match 'flag'; 'hub' must not match 'github'
    assert classify_complaint("Please flag my github issue")["category"] == "Unknown"


def test_custom_keyword_configuration():
    r = classify_complaint("printer jam", keywords={"Hardware": ["printer"]}, precedence=["Hardware"])
    assert r["category"] == "Hardware"
