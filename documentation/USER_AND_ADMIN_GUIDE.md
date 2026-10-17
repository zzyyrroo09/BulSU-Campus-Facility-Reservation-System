# CAMPUS FACILITY RESERVATION AND EVENT SCHEDULING SYSTEM
## User and Administrator Operations Manual
**Bulacan State University &bull; College of Information and Communications Technology**  
*IT 401W: Web Programming and Frameworks (Final Project B)*  

---

## PART 1: BASIC USER MANUAL (STUDENTS & FACULTY)
*Access Path: `http://127.0.0.1:8000/portal/`*

### 1. Account Access & Registration
- **Registration (`/register/`)**: Fill in your username, institutional email, full name, college/department, contact number, and password. Public registration automatically provisions the **Basic User** role.
- **Sign In (`/login/`)**: Enter your credentials. You will be redirected to the Student / Faculty Portal Dashboard (`/portal/dashboard/`).
- **Profile Management (`/portal/profile/`)**: Update your personal contact number or college affiliation. Role and account status are strictly read-only.

### 2. Browsing Venues & Inspecting Availability
- Navigate to **Browse Facilities** (`/portal/facilities/`).
- Search facilities by keyword (e.g., "Amphitheater", "Gymnasium"), filter by category, or specify a minimum attendee capacity.
- Click **Check Open Slots** on any facility to view the daily schedule.
- **Privacy Notice**: Scheduled slots booked by other campus groups appear as `"Occupied / Reserved Slot"`. Student names, event titles, and personal organizer details are protected and never disclosed.

### 3. Requesting a Facility Reservation
- Navigate to **Request a Facility** (`/portal/reserve/`).
- Select the desired venue, attendee count, event title, and detailed purpose.
- Choose an event date and a start/end time.
- **Validation Rules**:
  - The requested time must fall within the facility's daily operating hours.
  - Duration cannot exceed the maximum permitted limit (default: 4 hours).
  - Date cannot be beyond the advance booking window (default: 30 days).
  - Overnight events are prohibited; start and end must occur on the same calendar day.
- Click **Submit Reservation Request**. Your booking will be queued in **`PENDING`** state awaiting administrative approval.

### 4. Tracking & Cancelling Bookings
- Go to **My Bookings** (`/portal/my-reservations/`) to track request status.
- You can cancel any **`PENDING`** or **`APPROVED`** reservation strictly before the event start time.

---

## PART 2: ADMINISTRATOR MANUAL (CUSTOM ADMIN CONSOLE)
*Access Path: `http://127.0.0.1:8000/manage/`*

### 1. Dashboard Overview (`/manage/dashboard/`)
- View **4 Live Metric Cards**: Pending Requests, Approved Upcoming Bookings, Completed Events, and Active Facilities.
- Monitor the **Monthly Booking Request Trend** and **Facility Utilization Distribution** charts.
- Review quick shortcuts for today's operational check-ins.

### 2. Review Queue & Atomic Approvals (`/manage/queue/`)
- Review submitted requests filtered by facility, status, or date.
- **Approve Request**: Click **Approve**. The system atomically locks the database records (`select_for_update`) and re-verifies that no overlapping approved booking or active maintenance closure exists before committing.
- **Reject Request**: Click **Reject**. An administrative justification reason is mandatory.

### 3. Schedule Calendar & Rescheduling (`/manage/calendar/`)
- Inspect daily and weekly schedules across all facilities with color-coded status badges.
- **Reschedule an Approved Booking**:
  - Click **Reschedule** on an approved reservation.
  - Specify the new date and time with a mandatory justification reason.
  - The original schedule is preserved in an audit change log (`ReservationChange`), and the slot is re-validated against conflicts and operating hours.

### 4. Event Operations & Printable Slips (`/manage/operations/`)
- **Check-In**: On the event day, click **Check In** to verify physical organizer arrival and log pre-event conditions.
- **Complete Event**: Once concluded, click **Sign-Off Complete** to record actual end times and facility inspection notes.
- **Print Reservation Slip**: Click **Slip** to generate the official university reservation slip and completion summary with signature lines ready for physical filing or PDF export.

### 5. Maintenance Closures (`/manage/closures/`)
- Schedule maintenance, deep cleaning, or emergency repair time blocks.
- **Anti-Conflict Protection**: If a closure overlaps an existing Approved or Checked-In booking, creation is rejected until the booking is rescheduled or cancelled.
- Click **Archive** to release an unused maintenance hold.

### 6. Utilization Reports & CSV Export (`/manage/reports/`)
- Filter utilization metrics by date range.
- Total requests, approved bookings, completed events, and occupied hours are aggregated dynamically from ORM models.
- Click **Export Report to CSV** to download an audit-ready spreadsheet.

### 7. User Account Management (`/manage/users/`)
- Search users by name, email, or department.
- View individual booking history.
- Click **Deactivate** to suspend account privileges. Deactivation immediately invalidates active sessions and prevents new transactions without deleting past historical data.

### 8. System Settings & Audit Logs (`/manage/settings/` & `/manage/audit/`)
- **System Settings**: Adjust global booking constraints: Maximum Event Duration (hours) and Advance Booking Window (days).
- **Audit Logs**: Search immutable logs recording every administrative approval, rejection, reschedule, and user status change.
