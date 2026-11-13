# API Documentation

Every endpoint returns JSON in one of two shapes:

```json
{ "success": true,  "data": { ... }, "message": "optional" }
{ "success": false, "error": "Human readable message", "code": "OPTIONAL_CODE", "details": { ... } }
```

**Authentication:** a Flask session cookie, set by `/api/auth/login`.

**CSRF:** every `POST`, `PATCH`, `PUT` and `DELETE` request must send the `X-CSRFToken` header. Its value is in `<meta name="csrf-token">` on every page.

**Status codes:**
- 200 / 201: success
- 400: validation error
- 401: not logged in
- 403: wrong role, or not the owner
- 404: not found
- 409: conflict (invalid transition, duplicate)
- 500: server error

Roles: `user` (student/faculty), `administrator`, `central_admin`.

## Authentication
| Method | Path | Role | Body / notes |
|---|---|---|---|
| POST | `/api/auth/register` | public | `name, institutional_id, email, password, confirm_password` → logs in |
| POST | `/api/auth/login` | public | `email, password, next?` → `{user, redirect}` |
| POST | `/api/auth/logout` | any | |
| GET | `/api/auth/me` | logged in | `{user, admin}` (never includes password hashes) |

## Validation & classification (public)
| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/api/validate` | `{identifier}` | DFA result, regex result, `match`, `valid`, `message`, `error_code` |
| POST | `/api/validate/dfa` | `{identifier}` | `valid, result, final_state, final_state_label, message, error_code, trace[], parts` |
| POST | `/api/validate/regex` | `{identifier}` | `valid, result, pattern, message, groups` |
| POST | `/api/validate/compare` | `{identifiers: [...]}` or `{identifier}` | table rows plus `all_agree` |
| GET | `/api/dfa/definition` | — | states, alphabet, transitions, start/accept/dead state, regex |
| POST | `/api/classify` | `{description}` | `category, detected_categories, matched_keywords, explanation, priority` |
| GET | `/api/classify/keywords` | — | keyword dictionary, precedence, category→priority map |

## Complaints
| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/api/complaints` | user | `name, institutional_id, device_type, location_code, floor, description`. The server builds and validates the identifier. Returns 201 with `{complaint, validation, classification, routing}`, 400 for a malformed identifier (nothing is stored), or 409 for a duplicate. |
| GET | `/api/complaints` | any | Depends on role: own (user), assigned (admin), all (central). Filters: `status, category, priority, zone, q` |
| GET | `/api/complaints/my` | user | Own complaints plus a status summary |
| GET | `/api/complaints/<id>` | owner / assigned admin / central | complaint + history |
| GET | `/api/complaints/track/<id>` | same | complaint, history and queue position |
| GET | `/api/complaints/<id>/history` | same | history only |
| PATCH | `/api/complaints/<id>/status` | assigned admin or central | `{status, remarks?}`. Only Assigned→In Progress and In Progress→Resolved are allowed; anything else returns 409 |

## Administrators
| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/admins` | admin, central | All admins with availability and workload |
| POST | `/api/admins` | central | Create an administrator account |
| PATCH | `/api/admins/<id>` | central | `{name?, is_active?}` |
| GET | `/api/admins/me/complaints` | admin, central | Own assigned complaints, summary, own profile |
| GET | `/api/admins/<id>/complaints` | self or central | |
| PATCH | `/api/admins/<id>/availability` | self or central | `{availability: "Available"\|"Busy"}`. Becoming Available processes the waiting queue automatically and returns `processed[]` |

## Routing
| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/routing/zones` | admin, central | Routing table with per-zone totals: assigned, waiting, resolved |
| GET | `/api/routing/table` | logged in | Live routing table |
| PATCH | `/api/routing/table/<CODE>` | central | `{primary_admin_id, backup_admin_id}` |
| GET | `/api/routing/queue?zone=` | admin, central | Waiting queue in processing order |
| POST | `/api/routing/process-queue` | central | `{zone?}` → `assigned[]` in assignment order |
| PATCH | `/api/routing/assignments/<id>` | central | `{admin_id, remarks?}`: manual reassignment, recorded in history |
| GET | `/api/routing/history` | central | Reassignment, backup and queue events, plus the audit log |
| POST | `/api/routing/preview` | logged in | `{identifier}`: dry run of the routing decision |

## Analytics (logged in; optional `?from=YYYY-MM-DD&to=YYYY-MM-DD`)
| Path | Data |
|---|---|
| `/api/analytics/overview` | total, resolved, unresolved, pending, critical, waiting_queue, avg_resolution_hours, resolution_rate |
| `/api/analytics/zones` | per zone: total, resolved, unresolved, critical |
| `/api/analytics/categories` | count per category |
| `/api/analytics/priorities` | count per priority |
| `/api/analytics/status` | count per status |
| `/api/analytics/timeline` | complaints submitted and resolved per day |
| `/api/analytics/report` | all of the above in one call |

## Example

```http
POST /api/complaints
X-CSRFToken: …
{"name":"Aarav Sharma","institutional_id":"1RV22CS001","device_type":"LAN","location_code":"LAB","floor":"3",
 "description":"Unauthorized device attempted to access the network."}
```
```json
{"success":true,"message":"Complaint registered and assigned to Arjun Rao.",
 "data":{"complaint":{"complaint_id":"CNFR-20261113-7K2QZP","status":"Assigned","category":"Security","priority":"Critical",…},
         "validation":{"identifier":"LAN-LAB-3","valid":true,"match":true,"dfa":{"result":"Valid","final_state":"q30",…},"regex":{"result":"Valid",…}},
         "classification":{"category":"Security","matched_keywords":{"Security":["unauthorized device"]},…},
         "routing":{"outcome":"ASSIGNED_PRIMARY","admin":{"name":"Arjun Rao","admin_code":"Admin_LAB"},"steps":[…]}}}
```
