# Campus Facility Reservation and Event Scheduling System
**Bulacan State University &bull; College of Information and Communications Technology**  
*IT 401W: Web Programming and Frameworks &bull; Final Project B*  
**Instructor:** Dr. Aaron Paul M. Dela Rosa  

---

## 1. Project Overview & Architecture

The **Campus Facility Reservation and Event Scheduling System** is a monolithic Python/Django web application engineered to regulate institutional facility bookings, scheduling conflicts, event check-in/completion lifecycles, and operational reporting across the university campus.

### Strict Academic & Technical Compliance Highlights
1. **100% Custom Admin Interface**: The built-in Django administration package (`django.contrib.admin`, `admin.site.urls`, and third-party admin wrappers like Jazzmin or Grappelli) is **strictly excluded and prohibited**. The admin interface is custom-engineered using Django views, ModelForms, custom ORM queries, and Bootstrap 5 templates.
2. **Two-Role Scope**: Exactly two roles exist:
   - `ADMIN` &mdash; Full administrative rights over facilities, approvals, rescheduling, closures, account activation, reports, and system settings.
   - `BASIC_USER` &mdash; Campus organizers requesting facilities, tracking personal bookings, and viewing schedule availability.
3. **Workload Distribution**: Approximately 75% custom admin side (`/manage/`) and 25% basic user portal (`/portal/`).
4. **Half-Open Interval Collision Logic**: All time windows operate as half-open intervals: $[start, end)$. Two bookings overlap if and only if:
   $$\text{start}_A < \text{end}_B \quad \text{and} \quad \text{end}_A > \text{start}_B$$
   Adjacent reservations sharing an exact endpoint ($\text{end}_A = \text{start}_B$) do **not** conflict.
5. **Session-Level Deactivation Invalidation**: Middleware immediately intercepts deactivated user sessions and terminates active sessions to prevent transaction submission.
6. **Timezone Awareness**: The entire platform operates in `Asia/Manila` (UTC+8) with full `USE_TZ = True` enforcement.

---

## 2. Demonstration Credentials

| User Level | Username / Email | Password | Role & Department |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@bulsu.edu.ph` | `AdminPass123!` | System Administrator &bull; CICT Dean Office |
| **Basic User 1** | `user1` (or `user1@bulsu.edu.ph`) | `UserPass123!` | Faculty / Student Organizer &bull; CICT |
| **Basic User 2** | `user2` (or `user2@bulsu.edu.ph`) | `UserPass123!` | Organizer &bull; College of Engineering |
| *Users 3 to 8* | `user3` &ndash; `user8` | `UserPass123!` | Various colleges and student councils |

---

## 3. Quick Start & Execution Guide

### Prerequisites
- Python 3.10+ (Tested on Python 3.14.6)
- Virtual environment (`.venv`)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Apply Migrations
```bash
python manage.py migrate
```

### Step 3: Seed Demonstration Dataset
Populate the database with the required minimum dataset (4 categories, 6 facilities, 9 amenities, 1 admin, 8 users, 5 closures, 27 reservations across all lifecycle statuses, and 12 event operational records):
```bash
python manage.py seed_facility_data
```

### Step 4: Run Automated Verification Tests
Verify half-open interval math, atomic concurrency locking, operational transitions, and RBAC rules:
```bash
python manage.py test reservations
```

### Step 5: Start the Development Server
```bash
python manage.py runserver
```
Navigate to: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 4. Route & Feature Map

### Shared Authentication
- `/` &mdash; Role-based smart redirect
- `/login/` &mdash; Shared authentication endpoint
- `/register/` &mdash; Public registration (hardcoded strictly to `BASIC_USER`)
- `/logout/` &mdash; Session invalidation

### Custom Admin Console (`/manage/`, Protected by `@admin_required`)
- **A7 Dashboard**: `/manage/dashboard/` &mdash; 4 live cards, Chart.js monthly trend and facility usage charts.
- **A1 Accounts**: `/manage/users/` &mdash; User listing, search, deactivation (session-invalidating), and full reservation history.
- **A2 Facilities**: `/manage/facilities/` &mdash; Facility catalog, operating hours, capacity, amenities linkings, and archiving.
- **A3 Queue**: `/manage/queue/` &mdash; Review queue with atomic row-level approval locking (`select_for_update()`) and required rejection reasons.
- **A4 Calendar & Reschedule**: `/manage/calendar/` & `/manage/reschedule/<id>/` &mdash; Weekly schedule and auditable admin rescheduling with historical change logging.
- **A5 Operations**: `/manage/operations/` & `/manage/operations/<id>/slip/` &mdash; Physical check-in, completion sign-off, no-show recording, and official printable reservation slip.
- **A6 Closures**: `/manage/closures/` &mdash; Maintenance time blocks with overlap rejection.
- **A7 Reports**: `/manage/reports/` & `/manage/reports/export-csv/` &mdash; Dynamic date-filtered utilization metrics and CSV export.
- **A8 Audit & Settings**: `/manage/audit/` & `/manage/settings/` &mdash; Searchable audit logs and institutional limit settings.

### Basic User Portal (`/portal/`, Protected by `@user_required`)
- **U1 Profile**: `/portal/profile/` &mdash; Personal contact updates (role/status non-editable).
- **U2 Facilities**: `/portal/facilities/` & `/portal/facilities/<id>/` &mdash; Venue browsing and privacy-safe availability view (blocks show as "Occupied" without leaking user identities).
- **U3 Request**: `/portal/reserve/` &mdash; Reservation submission (operating hours, capacity, advance window, max duration validation). Creates `PENDING` status.
- **U4 Tracking**: `/portal/my-reservations/` & `/portal/my-reservations/<id>/cancel/` &mdash; Booking tracking and cancellation strictly before event start time.

---

## 5. Technical Design & Concurrency Strategy

- **Concurrency & Locking**: In `reservations/services.py`, `approve_reservation_atomic` and `reschedule_reservation_atomic` employ `transaction.atomic()` combined with `select_for_update()` row locking on both the `Reservation` and `Facility` records. This ensures that when two administrators attempt to approve competing requests for the same venue/slot, only the first transaction commits while the second is blocked and re-evaluated, raising a `ValidationError`.
- **Database Engine**: Uses SQLite for clean local demonstration (configured with a 20-second connection timeout). Fully compatible with PostgreSQL or MySQL in production.
