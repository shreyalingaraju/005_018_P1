"""Priority management."""
from modules.priority_manager import PRIORITY_RANK, determine_priority, priority_for_category


def test_category_to_priority_mapping():
    assert priority_for_category("Security") == "Critical"
    assert priority_for_category("Hardware") == "High"
    assert priority_for_category("Connectivity") == "Medium"
    assert priority_for_category("Configuration") == "Medium"
    assert priority_for_category("Unknown") == "Low"


def test_highest_priority_wins_for_multiple_categories():
    assert determine_priority(["Connectivity", "Hardware"])["priority"] == "High"
    assert determine_priority(["Connectivity", "Security"]) == {"priority": "Critical", "rank": 1}


def test_rank_order():
    assert PRIORITY_RANK["Critical"] < PRIORITY_RANK["High"] < PRIORITY_RANK["Medium"] < PRIORITY_RANK["Low"]
