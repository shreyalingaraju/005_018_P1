"""
Priority management.

Category and priority are kept separate: the classifier decides the category,
this module maps categories to a processing priority used by the waiting queue.
"""
from modules.complaint_classifier import (
    SECURITY, HARDWARE, CONNECTIVITY, CONFIGURATION, UNKNOWN,
)

CRITICAL = "Critical"
HIGH = "High"
MEDIUM = "Medium"
LOW = "Low"

PRIORITIES = (CRITICAL, HIGH, MEDIUM, LOW)

# Lower rank = processed first.
PRIORITY_RANK = {CRITICAL: 1, HIGH: 2, MEDIUM: 3, LOW: 4}

CATEGORY_PRIORITY = {
    SECURITY: CRITICAL,
    HARDWARE: HIGH,
    CONNECTIVITY: MEDIUM,
    CONFIGURATION: MEDIUM,
    UNKNOWN: LOW,
}


def priority_for_category(category):
    return CATEGORY_PRIORITY.get(category, LOW)


def determine_priority(categories):
    """Highest priority among all detected categories."""
    if isinstance(categories, str):
        categories = [categories]
    candidates = [priority_for_category(c) for c in (categories or [UNKNOWN])]
    best = min(candidates, key=lambda p: PRIORITY_RANK[p])
    return {"priority": best, "rank": PRIORITY_RANK[best]}


def sort_key(priority, submitted_at, tie_breaker=0):
    """Ordering key: priority first, then FIFO by submission time."""
    return (PRIORITY_RANK.get(priority, 99), submitted_at, tie_breaker)
