# DFA Design — Location Identifier Validation (BCS503)

## 1. Language

```
L = { D-L-F | D ∈ {WIFI, LAN}, L ∈ {HOST, LAB, ADM, LIB, CANT, SPRT}, F ∈ {0,…,9} }
```

L is finite (2 × 6 × 10 = 60 strings), so it is regular, and a DFA recognises it.

## 2. Formal definition  M = (Q, Σ, δ, q0, F)

| Element | Value |
|---|---|
| Q | {q0 … q30, qD}: 32 states |
| Σ | {A–Z} ∪ {0–9} ∪ {`-`}. Digits are handled as one character class, `DIGIT` |
| q0 | `q0` (Start) |
| F | {`q30`} |
| Dead state | `qD`, which absorbs all input. Any (state, symbol) pair that is not listed below goes to qD |

Implementation: `modules/dfa_validator.py` (`TRANSITIONS` dict, `delta()`, `run_dfa()`, `validate_identifier_dfa()`).
The module **does not import `re`**, and it never checks membership of the whole string against a list. It reads one character at a time, and the transition table alone decides the result.

## 3. States

| State | Meaning | Phase |
|---|---|---|
| q0 | Start | start |
| q1, q2, q3 | read `W`, `WI`, `WIF` | device |
| **q4** | `WIFI` complete | device ✓ |
| q5, q6 | read `L`, `LA` | device |
| **q7** | `LAN` complete | device ✓ |
| q8 | first `-` read | separator 1 |
| q9, q10, q11 → **q12** | `H`, `HO`, `HOS` → `HOST` | location |
| q13 | `L` (shared prefix of LAB/LIB) | location |
| q14 → **q15** | `LA` → `LAB` | location |
| q16 → **q17** | `LI` → `LIB` | location |
| q18, q19 → **q20** | `A`, `AD` → `ADM` | location |
| q21, q22, q23 → **q24** | `C`, `CA`, `CAN` → `CANT` | location |
| q25, q26, q27 → **q28** | `S`, `SP`, `SPR` → `SPRT` | location |
| q29 | second `-` read | separator 2 |
| **q30** | one floor digit read: **ACCEPTING** | accept |
| qD | dead / reject (absorbing) | dead |

## 4. Transition table

| δ | W | I | F | L | A | N | H | O | S | T | B | D | M | C | P | R | - | 0-9 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q0 | q1 | | | q5 | | | | | | | | | | | | | | |
| q1 | | q2 | | | | | | | | | | | | | | | | |
| q2 | | | q3 | | | | | | | | | | | | | | | |
| q3 | | q4 | | | | | | | | | | | | | | | | |
| q4 | | | | | | | | | | | | | | | | | q8 | |
| q5 | | | | | q6 | | | | | | | | | | | | | |
| q6 | | | | | | q7 | | | | | | | | | | | | |
| q7 | | | | | | | | | | | | | | | | | q8 | |
| q8 | | | | q13 | q18 | | q9 | | q25 | | | | | q21 | | | | |
| q9 | | | | | | | | q10 | | | | | | | | | | |
| q10 | | | | | | | | | q11 | | | | | | | | | |
| q11 | | | | | | | | | | q12 | | | | | | | | |
| q12 | | | | | | | | | | | | | | | | | q29 | |
| q13 | | q16 | | | q14 | | | | | | | | | | | | | |
| q14 | | | | | | | | | | | q15 | | | | | | | |
| q15 | | | | | | | | | | | | | | | | | q29 | |
| q16 | | | | | | | | | | | q17 | | | | | | | |
| q17 | | | | | | | | | | | | | | | | | q29 | |
| q18 | | | | | | | | | | | | q19 | | | | | | |
| q19 | | | | | | | | | | | | | q20 | | | | | |
| q20 | | | | | | | | | | | | | | | | | q29 | |
| q21 | | | | | q22 | | | | | | | | | | | | | |
| q22 | | | | | | q23 | | | | | | | | | | | | |
| q23 | | | | | | | | | | q24 | | | | | | | | |
| q24 | | | | | | | | | | | | | | | | | q29 | |
| q25 | | | | | | | | | | | | | | | q26 | | | |
| q26 | | | | | | | | | | | | | | | | q27 | | |
| q27 | | | | | | | | | | q28 | | | | | | | | |
| q28 | | | | | | | | | | | | | | | | | q29 | |
| q29 | | | | | | | | | | | | | | | | | | q30 |
| q30 | *all → qD* | | | | | | | | | | | | | | | | | |
| qD | *all → qD* | | | | | | | | | | | | | | | | | |

Every empty cell means **→ qD**.

## 5. Sample runs

**`WIFI-HOST-2` (accepted)**

```
q0 -W-> q1 -I-> q2 -F-> q3 -I-> q4 ---> q8 -H-> q9 -O-> q10 -S-> q11 -T-> q12 ---> q29 -2-> q30 ✓
```
All input is consumed and q30 ∈ F, so the string is **Valid**.

**`LAN-LAB-12` (rejected)**

```
q0 -L-> q5 -A-> q6 -N-> q7 ---> q8 -L-> q13 -A-> q14 -B-> q15 ---> q29 -1-> q30 -2-> qD ✗
```
q30 has no outgoing transitions, so the second digit sends the run to the dead state. Message: *Invalid floor number. Only one digit from 0 to 9 is allowed.*

**`WIFI-HOST` (rejected)**: the input ends in q12, which is not accepting. Message: *Incomplete identifier: missing floor number.*

## 6. Diagnostics (why a string was rejected)

When the run dies or ends in a non-accepting state, `validate_identifier_dfa` uses the **phase of the last live state** and the offending character to explain the error:

| Input | Where it failed | Error code | Message |
|---|---|---|---|
| `BLUETOOTH-HOST-2` | q0 on `B` | UNSUPPORTED_DEVICE_TYPE | Unsupported device type. Allowed types are WIFI and LAN. |
| `WIFI-XYZ-3` | q8 on `X` | UNSUPPORTED_LOCATION_CODE | Unsupported location code… |
| `WIFI--HOST-2` | q8 on `-` | INCORRECT_SEPARATOR | consecutive hyphens / location missing |
| `WIFI-HOST-A` | q29 on `A` | INVALID_FLOOR | Invalid floor number… |
| `WIFI-HOST-22` | q30 on `2` | INVALID_FLOOR | Invalid floor number… |
| `WIFI-HOST` | ends in q12 | MISSING_FLOOR | Incomplete identifier: missing floor |
| `wifi-host-2` | q0 on `w` | INCORRECT_CAPITALIZATION | must be uppercase |
| `-HOST-2` | q0 on `-` | MISSING_DEVICE_TYPE | Missing device type |
| `WIFI-HOST-2X` | q30 on `X` | EXTRA_CHARACTERS | Extra characters after floor |
| `WIFI-HOST2` | q12 on `2` | INCORRECT_SEPARATOR | hyphen required before floor |
| *(empty)* | ends in q0 | EMPTY_IDENTIFIER | Identifier is empty |

## 7. Equivalent regular expression

```
^(WIFI|LAN)-(HOST|LAB|ADM|LIB|CANT|SPRT)-[0-9]$
```

As a formal regular expression: `(WIFI + LAN)·-·(HOST + LAB + ADM + LIB + CANT + SPRT)·-·(0 + 1 + … + 9)`.

`modules/regex_validator.py` uses `re.fullmatch`, so the whole string must match. A plain `re.match` with `$` would also accept a trailing newline (`"WIFI-HOST-2\n"`); `fullmatch` closes that gap.

**Equivalence evidence:** `tests/test_regex.py` checks that the DFA and the regex agree on:
- every spec example
- all 60 strings of the language
- 150 near-miss strings
- every printable character
- 3,000 random strings

The UI's comparison table (Technical Overview → B) shows the same result live.
