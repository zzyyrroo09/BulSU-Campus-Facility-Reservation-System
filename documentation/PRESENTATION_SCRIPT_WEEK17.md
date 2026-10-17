# WEEK 17 PRESENTATION SCRIPT & Q&A DEFENSE CHEAT SHEET
## Campus Facility Reservation and Event Scheduling System
**Course:** IT 401W &bull; Web Programming and Frameworks (Final Project B)  
**Instructor:** Dr. Aaron Paul M. Dela Rosa  
**Time Limit:** 12 Minutes Demonstration + 3 Minutes Q&A  

---

## 12-MINUTE DEMONSTRATION SCHEDULE

### Minutes 00:00 &ndash; 02:00: Member 1 &mdash; Project Purpose & Architecture
- **Speaking Points:**
  - Introduce the group and the project: *"Campus Facility Reservation and Event Scheduling System for Bulacan State University CICT."*
  - State the core challenge: *"Eliminating campus venue double-bookings, preventing unauthorized admin escalation, and providing auditable operational tracking."*
  - Emphasize architectural compliance:
    - Zero usage of Django admin (`admin.site.urls` and auto-generators are strictly excluded).
    - Monolithic MTV architecture with two roles: `ADMIN` and `BASIC_USER`.
    - Real-time time synchronization in `Asia/Manila`.
  - Show the shared login screen (`/login/`) and explain role-based routing.

---

### Minutes 02:00 &ndash; 04:00: Member 2 &mdash; Basic User Portal & Privacy Safeguard
- **Speaking Points:**
  - Log in as `user1` (`UserPass123!`). Show the student dashboard (`/portal/dashboard/`).
  - Demonstrate **Facility Catalog (`/portal/facilities/`)**:
    - Filter by category and capacity (e.g., CICT Amphitheater, University Gymnasium).
    - Open the daily slot schedule.
  - **Key Rubric Defense (PO-n Privacy):**
    - Point out that occupied slots show strictly as `"Occupied / Reserved Slot"` without disclosing other students' names, event titles, or internal memos.
  - Show **Profile (`/portal/profile/`)**:
    - Edit contact details; highlight that the role and activation status fields are strictly uneditable by users.

---

### Minutes 04:00 &ndash; 06:00: Member 3 &mdash; Reservation Request & Business Rules Validation
- **Speaking Points:**
  - Navigate to **Request a Facility (`/portal/reserve/`)**.
  - Demonstrate form validation constraints:
    - Attempt to submit an event exceeding capacity &rarr; blocked.
    - Attempt to book beyond facility operating hours &rarr; blocked.
    - Attempt to request an event longer than 4 hours (system limit) &rarr; blocked.
  - Submit a valid booking request.
  - Show that submission results in a **`PENDING`** state with a unique tracking code (e.g., `RES-XXXXXX`) and does **not** prematurely reserve the slot.
  - Sign out.

---

### Minutes 06:00 &ndash; 08:00: Member 4 &mdash; Custom Admin Review Queue & Concurrency Locking
- **Speaking Points:**
  - Log in as `admin@bulsu.edu.ph` (`AdminPass123!`). Show the custom admin dashboard (`/manage/dashboard/`).
  - Navigate to the **Review Queue (`/manage/queue/`)**.
  - **Key Rubric Defense (PO-e / PO-g Concurrency & Atomic Locking):**
    - Show two competing requests for the same facility/slot.
    - Approve the first request: show the atomic row-level locking modal and successful approval.
    - Attempt to approve the second competing request: show the system intercepting and blocking it with an approval conflict warning!
  - Reject an unfeasible request, showing that an administrative reason is mandatory.

---

### Minutes 08:00 &ndash; 10:00: Member 5 &mdash; Schedule Calendar, Rescheduling & Operations
- **Speaking Points:**
  - Navigate to **Schedule Calendar (`/manage/calendar/`)**:
    - Show the weekly view with color-coded slots.
    - Show **adjacent bookings** (e.g., 08:00–11:00 and 11:00–14:00) meeting at the same boundary without conflict (Half-Open Interval Rule: $[start, end)$).
  - Open **Reschedule (`/manage/reschedule/<id>/`)**:
    - Change the event time with an administrative reason.
    - Show the **Historical Change Log table** demonstrating that the original scheduled time is preserved in the audit history.
  - Navigate to **Event Operations (`/manage/operations/`)**:
    - Click **Check In** on an approved event.
    - Click **Sign-Off Complete**.
    - Click **Print Slip** &rarr; open the official printable BulSU Reservation Slip & Completion Summary with signature lines!

---

### Minutes 10:00 &ndash; 12:00: Member 6 &mdash; Maintenance Closures, Reports, Audit & Settings
- **Speaking Points:**
  - Show **Maintenance Closures (`/manage/closures/`)**:
    - Demonstrate overlap rejection when attempting to block a venue with active bookings.
  - Show **Utilization Reports (`/manage/reports/`)**:
    - Adjust the date filter: explain that total booked hours and completed events are computed dynamically from ORM models (not static numbers).
    - Click **Export Report to CSV** and open the downloaded file.
  - Show **User Accounts (`/manage/users/`)**:
    - Demonstrate deactivation, explaining that it invalidates active sessions without deleting past records.
  - Conclude with **Audit Logs (`/manage/audit/`)** and **System Settings (`/manage/settings/`)**.

---

## 3-MINUTE Q&A DEFENSE PREPARATION (ANTICIPATED QUESTIONS)

### Q1: "Why did your group completely remove Django Admin instead of using it?"
> **Answer:** *"The project specification strictly prohibits `django.contrib.admin`, `admin.site.urls`, and third-party admin generators. In accordance with the 75% custom admin workload requirement, we hand-coded 100% of our admin views, forms, templates, and navigation under `/manage/`, enforcing role checks using our custom `@admin_required` decorator."*

### Q2: "How does your system prevent race conditions during competing approvals?"
> **Answer:** *"In `reservations/services.py`, our `approve_reservation_atomic` function wraps the approval in `transaction.atomic()` and applies `select_for_update()` row locking on both the target `Reservation` and the `Facility`. Right before committing, it re-evaluates half-open interval conflicts $[start, end)$. If another approval succeeded a millisecond earlier, the second transaction is blocked and raises a `ValidationError`."*

### Q3: "What mathematical logic governs your conflict detection?"
> **Answer:** *"We treat intervals as half-open: $[start, end)$. Two intervals $A$ and $B$ collide if and only if $start_A < end_B$ and $end_A > start_B$. This ensures that adjacent reservations meeting at the exact same minute—such as an 08:00 to 10:00 booking followed by a 10:00 to 12:00 booking—do not conflict."*

### Q4: "How does your system comply with the Data Privacy Act (RA 10173)?"
> **Answer:** *"Under the principle of proportionality, basic users inspecting venue availability see unavailable time blocks strictly labeled as 'Occupied / Reserved Slot'. Other students' names, student numbers, event purposes, and administrative notes are scrubbed from the response to prevent data leakage."*

### Q5: "How does deactivating a user protect the system?"
> **Answer:** *"Deactivating a user sets `is_active_account = False` while preserving their past reservation history for institutional auditability. Our custom `AccountActiveCheckMiddleware` checks this flag on every HTTP request; if a deactivated user attempts to submit a transaction via an existing session, the middleware terminates the session, logs them out, and redirects to login."*
