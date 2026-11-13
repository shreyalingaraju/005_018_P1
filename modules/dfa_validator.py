"""
Deterministic Finite Automaton (DFA) for campus location identifiers.

Language accepted:
    DEVICE_TYPE-LOCATION_CODE-FLOOR
    DEVICE_TYPE   ∈ {WIFI, LAN}
    LOCATION_CODE ∈ {HOST, LAB, ADM, LIB, CANT, SPRT}
    FLOOR         ∈ {0..9}   (exactly one digit)

Formal definition  M = (Q, Σ, δ, q0, F)
    Q  = {q0 … q30, qD}           (see STATES)
    Σ  = {A-Z} ∪ {0-9} ∪ {'-'}    (digits are collapsed into the class DIGIT)
    δ  = TRANSITIONS              (any missing entry goes to the dead state qD)
    q0 = START_STATE
    F  = {q30}

This module deliberately does NOT use regular expressions or list membership
tests on the whole string: the identifier is consumed one character at a time
and only the transition table decides acceptance.
"""

START_STATE = "q0"
ACCEPT_STATES = frozenset({"q30"})
DEAD_STATE = "qD"
DIGIT = "DIGIT"  # character class for 0-9

# --------------------------------------------------------------------------- #
# States: id -> (label, phase)
# phase is used for diagnostics and for the visualiser.
# --------------------------------------------------------------------------- #
STATES = {
    "q0": ("Start", "start"),
    # Device type: WIFI
    "q1": ("W", "device"),
    "q2": ("WI", "device"),
    "q3": ("WIF", "device"),
    "q4": ("WIFI ✓", "device_done"),
    # Device type: LAN
    "q5": ("L", "device"),
    "q6": ("LA", "device"),
    "q7": ("LAN ✓", "device_done"),
    # First separator
    "q8": ("Separator 1", "sep1"),
    # Location: HOST
    "q9": ("H", "location"),
    "q10": ("HO", "location"),
    "q11": ("HOS", "location"),
    "q12": ("HOST ✓", "location_done"),
    # Location: LAB / LIB (shared prefix L)
    "q13": ("L", "location"),
    "q14": ("LA", "location"),
    "q15": ("LAB ✓", "location_done"),
    "q16": ("LI", "location"),
    "q17": ("LIB ✓", "location_done"),
    # Location: ADM
    "q18": ("A", "location"),
    "q19": ("AD", "location"),
    "q20": ("ADM ✓", "location_done"),
    # Location: CANT
    "q21": ("C", "location"),
    "q22": ("CA", "location"),
    "q23": ("CAN", "location"),
    "q24": ("CANT ✓", "location_done"),
    # Location: SPRT
    "q25": ("S", "location"),
    "q26": ("SP", "location"),
    "q27": ("SPR", "location"),
    "q28": ("SPRT ✓", "location_done"),
    # Second separator and floor
    "q29": ("Separator 2", "sep2"),
    "q30": ("Floor ✓ (ACCEPT)", "accept"),
    # Trap state
    "qD": ("Dead / Reject", "dead"),
}

# --------------------------------------------------------------------------- #
# Transition function δ(state, symbol) -> state
# --------------------------------------------------------------------------- #
TRANSITIONS = {
    "q0": {"W": "q1", "L": "q5"},
    "q1": {"I": "q2"},
    "q2": {"F": "q3"},
    "q3": {"I": "q4"},
    "q4": {"-": "q8"},
    "q5": {"A": "q6"},
    "q6": {"N": "q7"},
    "q7": {"-": "q8"},
    "q8": {"H": "q9", "L": "q13", "A": "q18", "C": "q21", "S": "q25"},
    "q9": {"O": "q10"},
    "q10": {"S": "q11"},
    "q11": {"T": "q12"},
    "q12": {"-": "q29"},
    "q13": {"A": "q14", "I": "q16"},
    "q14": {"B": "q15"},
    "q15": {"-": "q29"},
    "q16": {"B": "q17"},
    "q17": {"-": "q29"},
    "q18": {"D": "q19"},
    "q19": {"M": "q20"},
    "q20": {"-": "q29"},
    "q21": {"A": "q22"},
    "q22": {"N": "q23"},
    "q23": {"T": "q24"},
    "q24": {"-": "q29"},
    "q25": {"P": "q26"},
    "q26": {"R": "q27"},
    "q27": {"T": "q28"},
    "q28": {"-": "q29"},
    "q29": {DIGIT: "q30"},
    "q30": {},  # accepting state: any further input leads to qD
    "qD": {},   # dead state: absorbing
}

ALLOWED_DEVICES = ("WIFI", "LAN")
ALLOWED_LOCATIONS = ("HOST", "LAB", "ADM", "LIB", "CANT", "SPRT")

# Error codes (stable identifiers used by the API / tests)
E_EMPTY = "EMPTY_IDENTIFIER"
E_CASE = "INCORRECT_CAPITALIZATION"
E_WHITESPACE = "WHITESPACE_NOT_ALLOWED"
E_MISSING_DEVICE = "MISSING_DEVICE_TYPE"
E_UNSUPPORTED_DEVICE = "UNSUPPORTED_DEVICE_TYPE"
E_MISSING_LOCATION = "MISSING_LOCATION_CODE"
E_UNSUPPORTED_LOCATION = "UNSUPPORTED_LOCATION_CODE"
E_MISSING_FLOOR = "MISSING_FLOOR"
E_INVALID_FLOOR = "INVALID_FLOOR"
E_SEPARATOR = "INCORRECT_SEPARATOR"
E_EXTRA = "EXTRA_CHARACTERS"
E_INCOMPLETE = "INCOMPLETE_IDENTIFIER"
E_INVALID_CHAR = "INVALID_CHARACTER"

MAX_TRACE_LENGTH = 64

MSG_DEVICE = "Unsupported device type. Allowed types are WIFI and LAN."
MSG_LOCATION = ("Unsupported location code. Allowed codes are "
                "HOST, LAB, ADM, LIB, CANT and SPRT.")
MSG_FLOOR = "Invalid floor number. Only one digit from 0 to 9 is allowed."


def symbol_of(ch):
    """Map an input character to an alphabet symbol (digits -> DIGIT class)."""
    if "0" <= ch <= "9":
        return DIGIT
    return ch


def phase_of(state):
    return STATES[state][1]


def delta(state, ch):
    """Transition function. Returns DEAD_STATE when no transition exists."""
    return TRANSITIONS.get(state, {}).get(symbol_of(ch), DEAD_STATE)


def _is_lower(ch):
    return "a" <= ch <= "z"


def _is_upper(ch):
    return "A" <= ch <= "Z"


def _diagnose_dead(state, ch, position):
    """Explain why the automaton entered the dead state from `state` on `ch`."""
    phase = phase_of(state)
    where = f" (character '{ch}' at position {position + 1})"

    if ch.isspace():
        return E_WHITESPACE, "Whitespace is not allowed in the identifier" + where + "."
    if _is_lower(ch):
        return E_CASE, ("Incorrect capitalization. The identifier must be in "
                        "uppercase, e.g. WIFI-HOST-2" + where + ".")

    if phase == "start":
        if ch == "-":
            return E_MISSING_DEVICE, "Missing device type. The identifier must start with WIFI or LAN."
        if _is_upper(ch) or symbol_of(ch) == DIGIT:
            return E_UNSUPPORTED_DEVICE, MSG_DEVICE
    elif phase in ("device", "device_done"):
        if ch == "-" and phase == "device":
            return E_UNSUPPORTED_DEVICE, MSG_DEVICE
        if _is_upper(ch) or symbol_of(ch) == DIGIT:
            return E_UNSUPPORTED_DEVICE, MSG_DEVICE
    elif phase == "sep1":
        if ch == "-":
            return E_SEPARATOR, ("Incorrect separator placement: consecutive hyphens "
                                 "found and the location code is missing.")
        if _is_upper(ch) or symbol_of(ch) == DIGIT:
            return E_UNSUPPORTED_LOCATION, MSG_LOCATION
    elif phase == "location":
        if _is_upper(ch) or ch == "-" or symbol_of(ch) == DIGIT:
            return E_UNSUPPORTED_LOCATION, MSG_LOCATION
    elif phase == "location_done":
        if symbol_of(ch) == DIGIT:
            return E_SEPARATOR, ("Incorrect separator placement: a hyphen is required "
                                 "between the location code and the floor.")
        if _is_upper(ch):
            return E_UNSUPPORTED_LOCATION, MSG_LOCATION
    elif phase == "sep2":
        if ch == "-":
            return E_SEPARATOR, ("Incorrect separator placement: consecutive hyphens "
                                 "found and the floor number is missing.")
        return E_INVALID_FLOOR, MSG_FLOOR
    elif phase == "accept":
        if symbol_of(ch) == DIGIT:
            return E_INVALID_FLOOR, MSG_FLOOR
        return E_EXTRA, "Extra characters found after the floor number" + where + "."

    return E_INVALID_CHAR, f"Invalid character '{ch}' at position {position + 1}."


def _diagnose_incomplete(state):
    """Explain why the input ended in a non-accepting state."""
    phase = phase_of(state)
    if phase == "start":
        return E_EMPTY, "Identifier is empty. Expected format DEVICE-LOCATION-FLOOR, e.g. WIFI-HOST-2."
    if phase == "device":
        return E_UNSUPPORTED_DEVICE, ("Incomplete identifier: device type is incomplete. "
                                      + MSG_DEVICE)
    if phase == "device_done":
        return E_MISSING_LOCATION, ("Incomplete identifier: missing location code and floor "
                                    "(expected e.g. WIFI-HOST-2).")
    if phase == "sep1":
        return E_MISSING_LOCATION, "Incomplete identifier: missing location code."
    if phase == "location":
        return E_UNSUPPORTED_LOCATION, "Incomplete identifier: location code is incomplete. " + MSG_LOCATION
    if phase == "location_done":
        return E_MISSING_FLOOR, "Incomplete identifier: missing floor number (0-9)."
    if phase == "sep2":
        return E_MISSING_FLOOR, "Incomplete identifier: missing floor number after the hyphen."
    return E_INCOMPLETE, "Incomplete identifier."


def run_dfa(identifier):
    """
    Simulate the DFA over `identifier`.

    Returns (final_state, trace, dead_info) where trace is a list of
    transition records and dead_info is (state_before_dead, char, index)
    or None if the DFA never entered the dead state.
    """
    state = START_STATE
    trace = []
    dead_info = None
    for index, ch in enumerate(identifier):
        nxt = delta(state, ch)
        if len(trace) < MAX_TRACE_LENGTH:
            trace.append({
                "step": index + 1,
                "char": ch,
                "symbol": symbol_of(ch),
                "from": state,
                "to": nxt,
            })
        if nxt == DEAD_STATE and dead_info is None:
            dead_info = (state, ch, index)
        state = nxt
        if state == DEAD_STATE:
            # qD is absorbing; the remaining input cannot change the outcome.
            break
    return state, trace, dead_info


def _extract_parts(trace):
    """Recover the device/location/floor tokens from an accepting run."""
    device, location, floor = [], [], []
    for t in trace:
        phase = phase_of(t["to"])
        if phase in ("device", "device_done"):
            device.append(t["char"])
        elif phase in ("location", "location_done"):
            location.append(t["char"])
        elif phase == "accept":
            floor.append(t["char"])
    return {
        "device_type": "".join(device),
        "location_code": "".join(location),
        "floor": int("".join(floor)) if floor else None,
    }


def validate_identifier_dfa(identifier):
    """
    Validate a location identifier with the DFA.

    Returns a dict:
        valid        bool
        result       "Valid" | "Invalid"
        final_state  id of the state where processing finished
        final_state_label
        message      human readable explanation
        error_code   None or one of the E_* constants
        trace        list of transitions taken
        parts        extracted tokens when valid
    """
    if identifier is None:
        identifier = ""
    if not isinstance(identifier, str):
        identifier = str(identifier)

    final_state, trace, dead_info = run_dfa(identifier)
    valid = final_state in ACCEPT_STATES

    if valid:
        error_code = None
        message = "Identifier accepted by the DFA (reached accepting state q30)."
        parts = _extract_parts(trace)
    elif dead_info is not None:
        error_code, message = _diagnose_dead(*dead_info)
        parts = None
    else:
        error_code, message = _diagnose_incomplete(final_state)
        parts = None

    return {
        "valid": valid,
        "result": "Valid" if valid else "Invalid",
        "identifier": identifier,
        "final_state": final_state,
        "final_state_label": STATES[final_state][0],
        "message": message,
        "error_code": error_code,
        "trace": trace,
        "parts": parts,
    }


def get_dfa_definition():
    """Serializable formal definition, used by the visualiser and docs."""
    alphabet = sorted({sym for row in TRANSITIONS.values() for sym in row})
    return {
        "states": [
            {"id": sid, "label": label, "phase": phase,
             "accepting": sid in ACCEPT_STATES, "dead": sid == DEAD_STATE,
             "initial": sid == START_STATE}
            for sid, (label, phase) in STATES.items()
        ],
        "alphabet": alphabet,
        "start_state": START_STATE,
        "accept_states": sorted(ACCEPT_STATES),
        "dead_state": DEAD_STATE,
        "transitions": [
            {"from": src, "symbol": sym, "to": dst}
            for src, row in TRANSITIONS.items() for sym, dst in row.items()
        ],
        "note": "Every (state, symbol) pair not listed transitions to the dead state qD.",
    }
