# CAMPUS NETWATCH
### Campus Network Fault Reporter and Intelligent Complaint Routing System
*Intelligent Campus Network Monitoring & Complaint Management*

This is a full-stack web application. Students and faculty use it to report network faults across six campus zones. It combines:

- **BCS503 Automata Theory:** an explicit DFA and an equivalent regular expression validate location identifiers.
- **BCS502 Computer Networks:** a zone routing table with primary and backup administrators, a central fallback, and a priority waiting queue.
- **A Flask + SQLite web app:** five dashboards and a Technical Overview.

**Stack:** Python Flask · SQLite · HTML5 · CSS3 · Bootstrap 5 · JavaScript · Chart.js.
The numbered requirements specify Flask and SQLite, so they take precedence over the "MERN" suggestion.

---

## 1. Setup (Windows, step by step)

You need **Python 3.10 or newer**. During installation, tick *"Add python.exe to PATH"*.

Open **PowerShell** or the VS Code terminal in the project folder and run:

```bash
python -m venv venv
```

```bash
venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

- On first run, the database `database/campus_network.db` is **created and seeded automatically**.
- No internet is needed: Bootstrap, Bootstrap Icons and Chart.js are bundled in `static/vendor`.

*macOS/Linux:* use `python3` and `source venv/bin/activate` instead.

### Useful commands

Run all tests (82 tests):

```bash
python -m pytest -v
```

Reset the database with fresh demo data:

```bash
python database/seed.py --reset
```

Reset the database with **no** sample complaints, for a clean demo:

```bash
python database/seed.py --reset --empty
```

Stop the server before you reset. Optional environment variables:
- `CNFR_PORT`: port (default 5000)
- `CNFR_DATABASE`: database path
- `CNFR_SECRET_KEY`: secret key
- `CNFR_SECURE_COOKIES=1`: secure cookies, for HTTPS deployments

## 2. Demo login credentials

| Role | Email | Password |
|---|---|---|
| Student | `student@campus.edu` | `Student@123` |
| Faculty | `faculty@campus.edu` | `Faculty@123` |
| Student 2 | `rahul@campus.edu` | `Student@123` |
| Central Administrator | `central@campus.edu` | `Central@123` |
| Primary admin, Hostels (Admin_HOST) | `admin.host@campus.edu` | `Admin@123` |
| Backup admin, Hostels (Backup_HOST) | `backup.host@campus.edu` | `Admin@123` |
| Other zones | `admin.<zone>@campus.edu` / `backup.<zone>@campus.edu`, where zone is one of `lab, adm, lib, cant, sprt` | `Admin@123` |

The login page has clickable demo-credential shortcuts.

### Routing table (seed data, editable in Routing Management)

| Code | Zone | Primary | Backup |
|---|---|---|---|
| HOST | Hostels | Admin_HOST (Ravi Kumar) | Backup_HOST (Sneha Patil) |
| LAB | Laboratories | Admin_LAB (Arjun Rao) | Backup_LAB (Kavya Menon) |
| ADM | Admin Block | Admin_ADM (Suresh Gowda) | Backup_ADM (Ananya Das) |
| LIB | Library | Admin_LIB (Vikram Singh) | Backup_LIB (Divya Hegde) |
| CANT | Canteen | Admin_CANT (Manoj Reddy) | Backup_CANT (Pooja Shetty) |
| SPRT | Sports Complex | Admin_SPRT (Karthik Iyer) | Backup_SPRT (Neha Joshi) |
| *(unregistered)* | — | **Central_Admin** (Dr. Meera Krishnan) | — |

## 3. How it works

### DFA (see `docs/dfa_design.md`)
- 32 states: `q0` is the start state, `q30` is the only accepting state, and `qD` is the dead state.
- An explicit transition dictionary drives it, one character at a time, with **no regex inside it**.
- When it rejects an identifier, it reports the exact reason, for example: *"Unsupported device type. Allowed types are WIFI and LAN."*

### Regular expression
- The pattern is `^(WIFI|LAN)-(HOST|LAB|ADM|LIB|CANT|SPRT)-[0-9]$`, applied with `re.fullmatch`.
- Every submission runs through **both** validators, and the two results are compared.

### Classification and priority
- Keyword dictionaries live in `modules/complaint_classifier.py`.
- **All** matching categories are detected, then precedence picks one: **Security > Hardware > Configuration > Connectivity > Unknown**.
- Priority by category:

  | Category | Priority |
  |---|---|
  | Security | Critical |
  | Hardware | High |
  | Connectivity, Configuration | Medium |
  | Unknown | Low |

### Routing algorithm (`modules/routing_engine.py`)
```
identifier ─► extract prefix ─► routing-table lookup
     unknown prefix ─► Central_Admin (or the CENTRAL queue if busy)
     primary Available? ─► assign primary
     backup  Available? ─► assign backup
     else ─► priority waiting queue (Critical→High→Medium→Low, FIFO within each)
admin switches to Available ─► queue for their zone drained automatically
```
Statuses follow `Pending → Assigned → In Progress → Resolved`. Every transition is time-stamped and saved in `complaint_history`. Invalid transitions are rejected with HTTP 409.

More documentation: `docs/architecture.md` (design and schema), `docs/api_documentation.md`, `docs/test_report.md`.

## 4. Interfaces

| Interface | URL | Role |
|---|---|---|
| Login / Register | `/login`, `/register` | public |
| Complaint submission (live identifier, DFA/regex and category preview) | `/complaints/new` | student/faculty |
| User dashboard (cards, search, filters, details, timeline) | `/dashboard` | student/faculty |
| Track complaint by ID | `/track` | all |
| Network administrator dashboard (availability, start/resolve) | `/admin` | administrators (central admin sees all) |
| Routing management (zones, routing table editor, queue, reassignment, audit) | `/routing` | central admin |
| Analytics (Chart.js, date filters, table view) | `/analytics` | all logged in |
| Technical Overview (DFA visualiser, regex, classifier, routing trace) | `/technical` | all logged in |

Screenshots are in `docs/screenshots/`.

## 5. Hackathon demonstration guide (about 8 minutes)

Before you start, run `python database/seed.py --reset`, then `python app.py`. Use two browser windows, one normal and one private, so you can stay logged in as two roles at once.

1. **Demo 6 first (DFA and regex), to set the context.** Log in as the student and open **Technical Overview**.
   - Click `WIFI-HOST-2` to watch the state-by-state animation reach q30.
   - Click `LAN-LAB-12` to watch the run fall into qD, with the reason shown.
   - Open tab **B**: every row of the comparison table shows *Match = Yes*.
2. **Demo 1: a successful complaint.**
   - Open **Report a Fault** and choose WIFI / HOST / 2.
   - Enter *"My WiFi is disconnected and internet is very slow."* and submit.
   - The result panel shows the complaint ID, DFA q30, regex Valid, agreement, Connectivity with its keywords, Medium priority, and assignment to **Ravi Kumar (Admin_HOST)**.
3. **Demo 2: a security complaint.**
   - Choose LAN / LAB / 3 and enter *"Unauthorized device attempted to access the network."*
   - It is classified **Security / Critical** and assigned to Arjun Rao.
4. **Demo 3: the primary admin is busy.**
   - In the private window, log in as `admin.host@campus.edu` and click **Busy**.
   - As the student, submit another HOST complaint. It goes to **Sneha Patil (Backup_HOST)**.
5. **Demo 4: all admins are busy.**
   - Log in as `backup.host@campus.edu` and click **Busy**. Alternatively, as `central@campus.edu`, use *Set Busy* in Routing Management.
   - As the student, submit several HOST complaints: *"Router lights blinking red"*, *"Slow internet in room 12"*, and last *"Suspicious login detected on my account"*. Each one shows *Waiting for assignment*.
   - As central admin, open **Routing Management → Waiting queue**. The Security complaint is at position 1, even though it was submitted last.
   - Set Admin_HOST to **Available**. The toast confirms the queue was processed automatically, Critical first, and the queue is now empty.
6. **Demo 5: resolution.**
   - As `admin.host@campus.edu`, open **My Work Queue**.
   - Click **Start** (In Progress), then **Resolve**, adding a remark.
   - As the student, open the dashboard and click the complaint ID. The timeline shows Pending → Assigned → In Progress → Resolved.
   - Open **Analytics**: the resolved/unresolved figures have updated.
7. **(Optional) Malformed identifier.** In Technical Overview → D, trace `BLUETOOTH-HOST-2`, or post it to the API. It is rejected and no record is created.

## 6. Requirement completion checklist

Each item is marked complete only after it was verified by the automated tests and in the browser.

**Automata Theory**
- [x] Explicit DFA with a transition table, accepting and dead states (`modules/dfa_validator.py`)
- [x] Equivalent regex with full-string matching (`modules/regex_validator.py`)
- [x] DFA vs regex comparison, as an API and a UI table
- [x] Invalid identifier detection with specific messages: missing or unsupported device, location or floor, separators, capitalization, extra characters, incomplete identifiers
- [x] Interactive DFA visualisation with step-by-step animation

**Complaint classification**
- [x] Connectivity / Hardware / Configuration / Security / Unknown
- [x] Multiple keywords handled, with Security precedence
- [x] Priority assignment, kept separate from category and used by the queue

**Computer Networks**
- [x] Six-zone routing table stored in SQLite and editable
- [x] Primary, then backup administrator allocation, with availability checks
- [x] Priority waiting queue (FIFO within each priority), drained automatically and transaction-safe
- [x] Central administrator fallback for unknown zones
- [x] Status lifecycle with history and timestamps

**Frontend**
- [x] Registration and login with role-based access control
- [x] Complaint submission page
- [x] User dashboard
- [x] Administrator dashboard
- [x] Routing management dashboard
- [x] Analytics dashboard
- [x] Technical Overview
- [x] Responsive layout (checked at 390 px and 1440 px)

**Backend and database**
- [x] Flask app factory with blueprints and a REST JSON API
- [x] SQLite with foreign keys, indexes and transactions; created automatically
- [x] Hashed passwords, sessions, CSRF protection, parameterised SQL, security headers
- [x] Complaint history, audit log, duplicate prevention

**Testing**
- [x] 82 automated tests covering all 25 required cases, all executed and passing
- [x] Integration workflow and exceptional scenarios verified

## 7. Project structure

```
app.py              Flask app factory and entry point
config.py           Configuration (dev + testing)
database/           schema.sql, seed.py (init + demo data), campus_network.db (generated)
modules/            DFA, regex, classifier, priority, routing engine, queue, admins, complaints, analytics, users, db
services/           validation / classification / routing (submission pipeline) services
routes/             auth, user, complaint, admin, routing, analytics, technical blueprints + security helpers
templates/          Jinja2 pages (base layout + 9 pages)
static/             css/style.css, js/*.js, vendor/ (Bootstrap, Icons, Chart.js)
tests/              pytest suite (82 tests)
docs/               architecture, DFA design, API, test report, screenshots
```
