# Test Report

**Command:** `python -m pytest -v`
**Result:** **82 passed, 0 failed** (about 1 s) on Python 3.13 and Flask 3.1.
**Isolation:** every test gets its own freshly seeded SQLite file, copied from a session template.

## Required test cases (problem statement, item 12)

| No. | Test | Expected | Automated test | Result |
|---|---|---|---|---|
| 1 | `WIFI-HOST-2` | Valid | `test_dfa.py::test_tc01_02_valid_identifiers_accepted[WIFI-HOST-2]` | ✅ Pass |
| 2 | `LAN-LAB-1` | Valid | `test_dfa.py::test_tc01_02_valid_identifiers_accepted[LAN-LAB-1]` | ✅ Pass |
| 3 | `WIFI-XYZ-3` | Invalid location | `test_dfa.py::test_invalid_identifiers…[WIFI-XYZ-3-UNSUPPORTED_LOCATION_CODE]` | ✅ Pass |
| 4 | `BLUETOOTH-HOST-2` | Unsupported device | `…[BLUETOOTH-HOST-2-UNSUPPORTED_DEVICE_TYPE]`, `test_specific_messages` | ✅ Pass |
| 5 | `WIFI-HOST-12` | Invalid floor | `…[WIFI-HOST-12-INVALID_FLOOR]` | ✅ Pass |
| 6 | `WIFI-HOST` | Incomplete identifier | `…[WIFI-HOST-MISSING_FLOOR]` | ✅ Pass |
| 7 | DFA vs regex | Both agree | `test_regex.py::test_tc07…`, `test_dfa_and_regex_agree_on_random_and_near_miss_strings` (3,000+ inputs) | ✅ Pass |
| 8 | "no internet" | Connectivity | `test_classification.py::test_categories[There is no internet…]` | ✅ Pass |
| 9 | "router failure" | Hardware | `test_categories[Router failure…]` | ✅ Pass |
| 10 | "IP conflict" | Configuration | `test_categories[Windows shows an IP conflict…]` | ✅ Pass |
| 11 | "unauthorized access" | Security | `test_categories[Someone got unauthorized access…]` | ✅ Pass |
| 12 | No keywords | Unknown | `test_categories[The projector remote…]` | ✅ Pass |
| 13 | Multiple categories including Security | Security wins | `test_tc13_security_takes_precedence_over_other_categories` | ✅ Pass |
| 14 | Primary available | Primary assigned | `test_routing.py::test_tc14_primary_available_gets_assignment` | ✅ Pass |
| 15 | Primary busy, backup available | Backup assigned | `test_tc15_primary_busy_backup_assigned` | ✅ Pass |
| 16 | Both busy | Queued | `test_tc16_both_busy_complaint_queued` | ✅ Pass |
| 17 | Security complaint in queue | Highest priority (FIFO within a priority) | `test_tc17_security_complaint_jumps_queue_fifo_within_priority` | ✅ Pass |
| 18 | Admin becomes available | Queue processed in priority order | `test_tc18_admin_available_processes_queue_in_priority_order` | ✅ Pass |
| 19 | Unknown zone | Central admin fallback | `test_tc19_unknown_zone_forwarded_to_central_admin` | ✅ Pass |
| 20 | Malformed submission | Rejected, nothing stored | `test_complaints.py::test_tc20_malformed_identifier_rejected_and_not_stored` | ✅ Pass |
| 21 | Status → In Progress | Database updated | `test_tc21_tc22_status_updates_recorded` | ✅ Pass |
| 22 | Status → Resolved | Resolution time recorded | `test_tc21_tc22_status_updates_recorded` | ✅ Pass |
| 23 | User views another user's complaint | 403 | `test_tc23_user_cannot_view_another_users_complaint` | ✅ Pass |
| 24 | Unauthorised admin updates complaint | 403 | `test_tc24_unauthorised_admin_cannot_update_complaint` | ✅ Pass |
| 25 | Analytics endpoint | Matches the database | `test_tc25_analytics_match_database` | ✅ Pass |

## Additional coverage

- **DFA:** all 60 strings of the language are accepted, along with 17 distinct error diagnoses. Further tests cover:
  - the dead state absorbing all further input
  - the trace advancing one character at a time
  - the transition table being deterministic
  - the DFA module not using `re`
- **Regex:** the match is on the whole string, not a substring, and a trailing `\n` is rejected.
- **Classification:** precedence holds Hardware > Configuration > Connectivity. Word boundaries prevent false matches (`flag` does not match `lag`). Keyword sets are configurable.
- **Routing:**
  - inactive admins are skipped
  - queue processing never assigns a complaint twice
  - when Central_Admin is busy, the CENTRAL queue holds the complaint until they are available again
  - editing the routing table changes where complaints go
  - the routing preview writes nothing
- **Security:**
  - role-based access is enforced on pages and APIs
  - CSRF is enforced when enabled
  - password hashes never appear in responses
- **Validation:** registration is validated, duplicate complaints get 409, and invalid status transitions get 409.
- **Integration (`test_integration.py`):**
  - registration → login → submission → DFA → regex → comparison → classification → priority → storage → routing → admin status updates → user tracking → analytics
  - Demo 3 (backup admin) and Demo 4 (queue with Critical first, then automatic draining)
  - every page renders for every role

## Failures found during development and fixed

| Issue | Fix |
|---|---|
| The regex validator unpacked 3 groups from a 2-group pattern | Corrected the unpacking in `regex_validator.py` |
| The sidebar background disappeared on desktop (Bootstrap `offcanvas-lg` forces transparency) | Added `!important` to the sidebar background |
| CDN assets were unreachable offline | Vendored Bootstrap, Bootstrap Icons and Chart.js under `static/vendor` |
| The timeline chart overshot below zero and skipped empty days | Set line tension to 0 and zero-fill every day in the range |

## Manual UI verification

Each interface was opened in headless Chromium for the student, network admin and central admin roles, at desktop (1440 px) and mobile (390 px) widths. No JavaScript errors were reported. Screenshots are in `docs/screenshots/`.
