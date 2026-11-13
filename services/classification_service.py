"""Classification + priority in one call."""
from modules.complaint_classifier import classify_complaint
from modules.priority_manager import determine_priority


def analyze_description(description):
    result = classify_complaint(description)
    prio = determine_priority(result["detected_categories"])
    result["priority"] = prio["priority"]
    result["priority_rank"] = prio["rank"]
    return result
