# DIGITAL EVIDENCE PACKAGE & SCREENSHOTS DIRECTORY
**Course:** IT 401W &bull; Web Programming and Frameworks (Final Project B)  
**Instructor:** Dr. Aaron Paul M. Dela Rosa  

---

### Evidence Directory Structure
This folder contains the operational evidence and test verification artifacts required for the digital submission archive:

1. **`TEST_EXECUTION_RESULTS.txt`**: Complete terminal test log proving that all 7 core domain rules, concurrency row-locking tests, and RBAC security tests passed.
2. **`DATABASE_SEED_LOGS.txt`**: Execution log proving idempotent database generation of 4 categories, 6 facilities, 9 amenities, 1 admin, 8 users, 5 closures, 27 reservations, and 12 event records.
3. **`screenshots/`**: Recommended operational screenshots:
   - `01_login_screen.png`: Shared login view with role redirection.
   - `02_user_catalog_privacy.png`: Basic User view showing occupied slots scrubbed as "Occupied / Reserved Slot".
   - `03_user_booking_validation.png`: Booking form showing capacity/hours validation.
   - `04_admin_dashboard.png`: Custom admin console with 4 live cards and Chart.js analytics.
   - `05_admin_review_queue.png`: Review queue with atomic approval modal and row locking.
   - `06_approval_conflict_warning.png`: System preventing an approval overlapping an active maintenance closure or existing booking.
   - `07_schedule_calendar_adjacent.png`: Weekly calendar showing adjacent bookings sharing endpoints $[start, end)$.
   - `08_reschedule_audit_log.png`: Reschedule form displaying historical original times in `ReservationChange`.
   - `09_printable_reservation_slip.png`: Official BulSU reservation slip and completion summary with signature lines.
   - `10_utilization_reports_csv.png`: Date-filtered reports with ORM totals and exported CSV spreadsheet.
