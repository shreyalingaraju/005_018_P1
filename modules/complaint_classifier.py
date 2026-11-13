"""
Keyword-based complaint classifier.

All keyword lists and the category precedence live in this module so they can
be edited in one place.  `classify_complaint` accepts optional overrides so
alternative keyword sets can be supplied (e.g. from configuration or tests).

When several categories match, the category with the highest precedence wins:

    Security > Hardware > Configuration > Connectivity > Unknown
"""
import re

SECURITY = "Security"
HARDWARE = "Hardware"
CONFIGURATION = "Configuration"
CONNECTIVITY = "Connectivity"
UNKNOWN = "Unknown"

CATEGORIES = (SECURITY, HARDWARE, CONFIGURATION, CONNECTIVITY, UNKNOWN)

# Highest precedence first.
CATEGORY_PRECEDENCE = (SECURITY, HARDWARE, CONFIGURATION, CONNECTIVITY)

CATEGORY_KEYWORDS = {
    CONNECTIVITY: [
        "disconnected", "disconnect", "no internet", "slow internet", "internet is slow",
        "very slow", "slow", "intermittent", "unstable", "packet loss", "timeout",
        "timed out", "connection lost", "lost connection", "cannot connect",
        "can't connect", "unable to connect", "not connecting", "weak signal",
        "no signal", "keeps dropping", "dropping", "offline", "outage",
        "network down", "high latency", "latency", "lag", "buffering",
    ],
    HARDWARE: [
        "router", "switch", "damaged cable", "broken cable", "cable", "access point",
        "faulty device", "power failure", "hardware failure", "port damaged",
        "damaged port", "broken port", "overheating", "overheat", "lan port",
        "ethernet port", "burnt", "sparking", "no power", "led not glowing",
        "modem", "hub", "antenna",
    ],
    CONFIGURATION: [
        "ip conflict", "wrong ip", "ip address", "dns error", "dns", "gateway",
        "dhcp", "subnet", "misconfiguration", "misconfigured",
        "incorrect configuration", "wrong configuration", "network settings",
        "proxy", "vlan", "apipa", "169.254", "static ip",
    ],
    SECURITY: [
        "unauthorized access", "unauthorised access", "unauthorized device",
        "unauthorised device", "unauthorized", "unauthorised", "suspicious login",
        "hacking", "hacked", "hacker", "intrusion", "malware", "virus",
        "ransomware", "phishing", "suspicious activity", "data breach",
        "spoofing", "spoofed", "security breach", "brute force", "ddos",
        "rogue access point", "mac spoofing", "password stolen", "credential theft",
    ],
}


def _keyword_pattern(keyword):
    # Word-boundary match that tolerates simple inflections (router -> routers).
    return re.compile(r"(?<![a-z0-9])" + re.escape(keyword.lower()) +
                      r"(?:s|es|ed|ing)?(?![a-z0-9])")


def _compile(keywords):
    return {cat: [(kw, _keyword_pattern(kw)) for kw in kws] for cat, kws in keywords.items()}


_COMPILED_DEFAULT = _compile(CATEGORY_KEYWORDS)


def normalize_text(text):
    text = (text or "").lower()
    text = text.replace("’", "'")
    return " ".join(text.split())


def classify_complaint(description, keywords=None, precedence=None):
    """
    Classify a complaint description.

    Returns dict:
        category             final category after precedence resolution
        detected_categories  every category that matched (in precedence order)
        matched_keywords     {category: [keywords]} for every matched category
        all_matched_keywords flat list of matched keywords
        explanation          human readable reasoning
    """
    compiled = _COMPILED_DEFAULT if keywords is None else _compile(keywords)
    order = tuple(precedence) if precedence else CATEGORY_PRECEDENCE
    text = normalize_text(description)

    matched = {}
    for category in order:
        hits = []
        for kw, pattern in compiled.get(category, []):
            if pattern.search(text):
                hits.append(kw)
        # Drop keywords that are fully contained in a longer matched keyword
        # (e.g. "slow" when "slow internet" also matched) for a cleaner report.
        hits = [h for h in hits if not any(h != o and h in o for o in hits)]
        if hits:
            matched[category] = hits

    detected = [c for c in order if c in matched]
    if detected:
        category = detected[0]
        if len(detected) == 1:
            explanation = (f"Matched {category} keyword(s): "
                           f"{', '.join(matched[category])}.")
        else:
            explanation = (f"Multiple categories detected ({', '.join(detected)}). "
                           f"{category} selected by precedence rule "
                           f"{' > '.join(order)} > Unknown.")
    else:
        category = UNKNOWN
        explanation = "No predefined fault keyword matched; assigned to Unknown."

    flat = [kw for c in detected for kw in matched[c]]
    return {
        "category": category,
        "detected_categories": detected or [UNKNOWN],
        "matched_keywords": matched,
        "all_matched_keywords": flat,
        "explanation": explanation,
    }
