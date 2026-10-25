# Software Test Cases & Verification Matrix
**Course:** IT 401W: Web Programming and Frameworks &bull; Final Project B  
**Instructor:** Dr. Aaron Paul M. Dela Rosa  
**System:** BulSU CICT Campus Facility Reservation and Event Scheduling System  
**Test Suite:** Django Automated Unit & Integration Testing (`reservations/tests.py`)  

---

### 1. Test Execution Summary
* **Total Automated Test Cases:** 10
* **Passed:** 10
* **Failed:** 0
* **Execution Status:** 100% PASS (Verified on Python 3.14 / Django 6.1)
* **Testing Command:** `python manage.py test reservations -v 2`

---

### 2. Formal System Test Case Table

| Test Case ID | Test Category & Rule | Test Scenario & Objective | Input / Action | Expected Result | Actual Result | Status |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-01** | **Interval Math**<br>*(Part 5 Rule 1)* | **Adjacent Slots Sharing Endpoint**<br>Verify $[start, end)$ half-open logic permits adjacent events with 0-minute gap. | Booking A: `08:00 AM – 10:00 AM`<br>Booking B: `10:00 AM – 12:00 PM` for same facility. | No collision detected; both requests are valid and can be approved. | Overlap check returns `False`. Both approved without conflict. | <span style="color:green;font-weight:bold;">PASSED</span> |
| **TC-02** | **Interval Math**<br>*(Part 5 Rule 2)* | **Overlapping Booking Collision**<br>Verify intervals overlapping by even 1 minute are detected and rejected. | Booking A: `08:00 AM – 10:30 AM`<br>Booking B: `10:00 AM – 12:00 PM` (30 min overlap). | Overlap detected ($start_A < end_B \land end_A > start_B$); collision flagged. | Collision detected. Second booking cannot be approved. | <span style="color:green;font-weight:bold;">PASSED</span> |
| **TC-03** | **Concurrency**<br>*(Part 5 Rule 3)* | **Competing Approvals (Atomic Lock)**<br>Verify `select_for_update()` prevents race condition double-booking. | Two concurrent admin approval threads target overlapping pending requests. | Database row locks serializes transactions; 1st succeeds, 2nd fails safely. | Exactly 1 booking status becomes `APPROVED`; competing request rejected. | <span style="color:green;font-weight:bold;">PASSED</span> |
| **TC-04** | **Maintenance**<br>*(Part 5 Rule A6)* | **Closure Overlap with Booking**<br>Verify maintenance block cannot be scheduled over approved event. | Admin attempts to create maintenance closure overlapping an `APPROVED` booking. | System rejects closure creation and returns operational conflict message. | `ValidationError` raised with explicit conflict notification. | <span style="color:green;font-weight:bold;">PASSED</span> |
| **TC-05** | **Lifecycle**<br>*(Part 5 Rule A5)* | **Event Check-In & Completion Workflow**<br>Verify physical lifecycle enforcement: Check-in before Completion. | 1. Attempt complete on approved booking.<br>2. Execute check-in.<br>3. Execute completion. | Completion blocked prior to check-in. Completion permitted only after check-in. | State machine enforces `APPROVED` $\rightarrow$ `CHECKED_IN` $\rightarrow$ `COMPLETED`. | <span style="color:green;font-weight:bold;">PASSED</span> |
| **TC-06** | **Security & RBAC**<br>*(Part 4 Role Rule)* | **Basic User Blocked from Admin**<br>Verify non-admin users cannot access `/manage/*` admin endpoints. | Authenticated `BASIC_USER` sends GET request to `/manage/dashboard/`. | Access denied; user redirected to Student Portal with error message. | HTTP 302 redirect with security error notice; 0% admin leakage. | <span style="color:green;font-weight:bold;">PASSED</span> |
| **TC-07** | **Security & RBAC**<br>*(Part 4 Role Rule)* | **Deactivated User Session Invalidation**<br>Verify deactivation middleware terminates active browser sessions. | Admin deactivates account; deactivated user attempts to submit a reservation. | Session invalidated immediately; user logged out and redirected to login. | HTTP 302 redirect to `/login/` with deactivated notice. | <span style="color:green;font-weight:bold;">PASSED</span> |
| **TC-08** | **Time Pickers & UI**<br>*(AM/PM Compliance)* | **12-Hour AM/PM Input Parsing**<br>Verify form accepts standard AM/PM time strings (e.g. "08:00 AM", "05:00 PM"). | User enters `"08:00 AM"` and `"05:00 PM"` in reservation form. | Clean parsing into Python `datetime.time(8, 0)` and `datetime.time(17, 0)`. | Clean parsing with 0 validation errors. | <span style="color:green;font-weight:bold;">PASSED</span> |
| **TC-09** | **Time Pickers & UI**<br>*(Operating Hours)* | **Out-of-Hours AM/PM Error Messaging**<br>Verify error messages for out-of-bounds hours are displayed in AM/PM. | User requests booking from `06:00 AM – 08:00 AM` for facility opening at `08:00 AM`. | `ValidationError` displayed quoting facility operating hours in `g:i A`. | Validation error: "Operating hours are 8:00 AM to 5:00 PM". | <span style="color:green;font-weight:bold;">PASSED</span> |
| **TC-10** | **Calendar & Fault Tolerance**<br>*(Query Sanitization)* | **Calendar Empty Query Parameter Handling**<br>Verify week navigation does not throw `ValueError` when facility param is empty. | User navigates weeks with query parameters `?date=2026-10-23&facility=`. | View sanitizes parameter, defaults to all facilities, and renders 7-day grid. | HTTP 200 OK rendered cleanly without server exception. | <span style="color:green;font-weight:bold;">PASSED</span> |

---

### 3. Conclusion
All 10 critical functional, operational, concurrency, and security rules specified in the IT 401W project guidelines have been systematically tested and verified.
