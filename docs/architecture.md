# Architecture

## Layers

```
Browser (Bootstrap 5 + vanilla JS + Chart.js)
        │  fetch() JSON + X-CSRFToken
        ▼
routes/      Flask blueprints: HTTP, auth/RBAC, JSON envelopes
        │
services/    Workflows that combine modules
        │      validation_service      DFA + regex + comparison
        │      classification_service  classifier + priority
        │      routing_service         full submission pipeline
        ▼
modules/     Domain logic (no Flask imports apart from database.get_db)
        │      dfa_validator   regex_validator   complaint_classifier   priority_manager
        │      routing_engine  queue_manager     admin_manager          complaint_manager
        │      analytics       user_manager      database               utils
        ▼
SQLite (database/campus_network.db): the source of truth
```

## Submission pipeline (`services/routing_service.submit_complaint`)

1. Validate the form fields (name, USN/Faculty ID, description).
2. Build the identifier `DEVICE-LOCATION-FLOOR` from the submitted values. The values are not normalised, so `wifi` is rejected rather than silently fixed.
3. Validate the identifier with the DFA.
4. Validate it with the regex.
5. Compare the two results. If the identifier is invalid, return **HTTP 400 and write nothing**.
6. Classify the description. This gives the category, all detected categories and the matched keywords.
7. Assign a priority. The highest priority among the detected categories wins.
8. Inside **one `BEGIN IMMEDIATE` transaction**:
   - check for an open duplicate complaint
   - insert the complaint as `Pending` and add a history row
   - call `routing_engine.route_complaint`
9. Return the complaint, the validation trace, the classification and the routing steps.

## Routing algorithm (`modules/routing_engine.py`)

| Function | Responsibility |
|---|---|
| `extract_location_code(identifier)` | Return the middle token, which is the routing prefix |
| `get_zone_administrators(conn, code)` | Look up `routing_table` ⋈ `campus_zones` (returns `None` for an unknown zone) |
| `check_administrator_availability(conn, id)` | `availability = 'Available' AND is_active = 1` |
| `route_complaint(conn, pk)` | Primary → backup → queue; an unknown zone goes to Central_Admin |
| `process_waiting_queue(conn, zone)` | Drain the queue Critical → High → Medium → Low, FIFO within each priority |
| `update_administrator_availability(conn, id, status)` | Set availability; when it becomes Available, process every zone that admin serves |
| `update_routing_entry`, `reassign_complaint`, `preview_route` | Management actions and a dry run for the Technical Overview |

The same idea in networking terms: the location code is the destination prefix, the primary admin is the next hop, the backup admin is the fallback route, Central_Admin is the default route, and the waiting queue is a priority queue (strict priority, FIFO within a class).

### Concurrency and transaction safety
- Every write path runs inside `transaction()`, which issues `BEGIN IMMEDIATE`. SQLite therefore serialises writers.
- `complaint_manager.mark_assigned` updates with `WHERE status='Pending' AND assigned_admin_id IS NULL` and checks `rowcount == 1`. A complaint can never be assigned twice, even if two queue processors race.
- Assignment deletes the complaint's `waiting_queue` row in the same transaction.

## Design decisions

| Decision | Reason |
|---|---|
| Flask + SQLite, not MERN | The numbered requirements (items 8 and 10) specify Flask/SQLite. "MERN" appears only as a *suggested* stack. |
| The DFA and regex accept only the six public codes | This follows the spec. The unknown-zone fallback covers legacy/imported records and future zones, and is shown in `tests/test_routing.py::test_tc19…`. Public submissions can never bypass validation. |
| If Central_Admin is busy, unknown-zone complaints wait in a `CENTRAL` queue | The complaint is never dropped. It is assigned automatically when Central_Admin becomes Available. |
| Availability is manual and does not change when a complaint is assigned | The problem statement describes Available/Busy as an option the administrator controls. When an admin becomes Available, *all* waiting complaints in their zone are assigned, highest priority first. |
| Both `campus_zones` and `routing_table` store the primary/backup admins | The schema requested both tables. `routing_table` drives routing, and the two are always updated together in one transaction. |
| Reassignment can move an *In Progress* complaint back to *Assigned* | A reassignment hands the work to a new owner. The move is recorded as a `REASSIGNED` history row. |
| Duplicate prevention | The same user, identifier and normalised description while still unresolved returns HTTP 409. |
| Libraries are vendored in `static/vendor` | The demo works without internet access, for example on unreliable venue Wi-Fi. |
| CSRF uses a session token in a `<meta>` tag, sent as the `X-CSRFToken` header | All state-changing requests are `fetch()` calls with a JSON body. |

## Database schema (see `database/schema.sql`)

| Table | Purpose |
|---|---|
| `users` | Accounts (user / administrator / central_admin), scrypt password hashes |
| `administrators` | Admin profile: code, zone, role (primary/backup/central), availability, active flag |
| `campus_zones` | The six zones, with the current primary/backup admins |
| `routing_table` | Zone → primary/backup admin mapping (source of truth for routing) |
| `complaints` | Complaint records, including category, keywords JSON, priority and rank, status timestamps |
| `complaint_history` | Every status change, assignment, queue event and reassignment |
| `waiting_queue` | Complaints waiting for an admin (zone, priority, rank, position) |
| `audit_logs` | Availability changes, routing updates, central forwards, queue processing, reassignments |

Foreign keys are enforced with `PRAGMA foreign_keys = ON`. Indexes cover user, admin, status, location and submission time, plus the queue ordering.
