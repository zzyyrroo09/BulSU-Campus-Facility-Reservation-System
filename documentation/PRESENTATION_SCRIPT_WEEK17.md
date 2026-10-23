# 12-MINUTE LIVE DEMONSTRATION SCRIPT & Q&A DEFENSE
## 5-Member Team Allocation & Live Action Cues
**Course:** IT 401W &bull; Web Programming and Frameworks (Final Project B)  
**Institution:** Bulacan State University &bull; College of Information and Communications Technology  
**Instructor:** Dr. Aaron Paul M. Dela Rosa  
**Time Limit:** Exactly 12 Minutes Live Demonstration + 3 Minutes Q&A  

---

## DEMO TIMELINE AT A GLANCE (5 MEMBERS)

| Speaker | Time Window | Account Used | Core Demonstration Segment |
| :--- | :--- | :--- | :--- |
| **Member 1** | `00:00 - 02:30` | `user1` (Basic User) | Project Architecture Intro, Portal Overview, Facility Catalog & Privacy Safeguard |
| **Member 2** | `02:30 - 05:00` | `user1` (Basic User) | Request Form Validations, Creating Pending Booking & User Cancellation Policy |
| **Member 3** | `05:00 - 07:30` | `admin@bulsu.edu.ph` | Admin Dashboard, Review Queue & Atomic Concurrency / Conflict Locking |
| **Member 4** | `07:30 - 10:00` | `admin@bulsu.edu.ph` | Schedule Calendar, Half-Open Intervals, Rescheduling Audit & Event Operations |
| **Member 5** | `10:00 - 12:00` | `admin@bulsu.edu.ph` | Maintenance Closures, Dynamic ORM Reports (CSV Export) & User Deactivation |

---

## TURN-BY-TURN SCRIPT & ON-SCREEN ACTIONS

### 👤 MEMBER 1: Project Architecture & Student Portal (00:00 &ndash; 02:30)

**[ON-SCREEN ACTION]**: Open browser at `http://127.0.0.1:8000/`. Show the clean BulSU Sign-In screen.

**[SPEAKING SCRIPT]**:
> *"Good day, Dr. Dela Rosa and classmates. Today, our group presents the **Campus Facility Reservation and Event Scheduling System** for BulSU CICT.*
> 
> *Per the strict project requirements, our system **completely excludes Django's built-in `/admin/` and third-party admin wrappers**. We built a 100% custom-coded monolithic MTV architecture with exactly two roles: `ADMIN` and `BASIC_USER`, synchronized to the `Asia/Manila` timezone.*
> 
> *I will begin by demonstrating the Basic User experience."*

**[ON-SCREEN ACTION]**: Log in using `user1` (`UserPass123!`). Land on `/portal/dashboard/`. Show the maroon navbar and clean cards.

**[SPEAKING SCRIPT]**:
> *"When a student or faculty member signs in, they land on the User Portal. I will now navigate to **Browse Facilities**."*

**[ON-SCREEN ACTION]**: Click **Browse Facilities** (`/portal/facilities/`). Filter by category or search "Amphitheater". Click **Check Open Slots** on the CICT Amphitheater.

**[SPEAKING SCRIPT]**:
> *"Here, students inspect venue capacity, operating hours, and amenities. Notice our **Data Privacy Act (RA 10173)** compliance: slots booked by other campus groups appear strictly as **'Occupied / Reserved Slot'**. Our system completely conceals organizer names, student numbers, and event purposes from other students.*
> 
> *I now hand over the demo to Member 2 to demonstrate reservation requests."*

---

### 👤 MEMBER 2: Request Submission & Validation Rules (02:30 &ndash; 05:00)

**[ON-SCREEN ACTION]**: Click **Request a Facility** (`/portal/reserve/`).

**[SPEAKING SCRIPT]**:
> *"Thank you. I will now demonstrate the booking validation engine on the Basic User side.*
> 
> *Our reservation form enforces all institutional domain constraints on the server side."*

**[ON-SCREEN ACTION]**: 
1. Select a facility and enter an attendee count that exceeds capacity &rarr; show the capacity validation error.
2. Enter an end time beyond the facility's daily closing time &rarr; show the operating hours error.
3. Try entering an event duration longer than 4 hours &rarr; show the maximum duration limit error.

**[SPEAKING SCRIPT]**:
> *"As seen here, requests violating capacity, daily operating hours, or the 4-hour duration limit are instantly rejected by our validation services.*
> 
> *I will now submit a valid reservation for an upcoming event."*

**[ON-SCREEN ACTION]**: Enter valid event details (e.g., "Web Development Hackathon", valid date/time). Click **Submit Reservation Request**.

**[SPEAKING SCRIPT]**:
> *"Upon submission, our system generates a unique tracking code. Notice that the request is placed in **`PENDING`** status. Per the specification, submitting a request does **not** prematurely reserve or lock the slot.*
> 
> *Finally, looking at **My Bookings**, users can track review progress and can cancel their pending or approved bookings strictly before the scheduled start time.*
> 
> *I will now sign out so Member 3 can demonstrate the custom administrative workflow."*

**[ON-SCREEN ACTION]**: Click profile &rarr; **Sign Out**.

---

### 👤 MEMBER 3: Admin Review Queue & Concurrency / Conflict Defense (05:00 &ndash; 07:30)

**[ON-SCREEN ACTION]**: Log in as `admin@bulsu.edu.ph` (`AdminPass123!`). Show the dark sidebar and `/manage/dashboard/` with the 4 live cards and Chart.js analytics.

**[SPEAKING SCRIPT]**:
> *"Thank you. I am now logged into our hand-coded **Custom Admin Console** under `/manage/`. Notice the live KPI cards and dynamic monthly trend charts.*
> 
> *I will now proceed to the **Review Queue** to demonstrate our atomic concurrency locking."*

**[ON-SCREEN ACTION]**: Go to **Review Queue** (`/manage/queue/`). Find the pending booking just submitted by Member 2. Click **Approve**.

**[SPEAKING SCRIPT]**:
> *"When an administrator approves a request, our backend runs `approve_reservation_atomic` in `services.py`. It wraps the operation in a database transaction and applies `select_for_update()` row locking on both the `Reservation` and the `Facility`.*
> 
> *Right before committing, it atomically re-checks for half-open interval conflicts. If another administrator or process approved an overlapping slot a millisecond earlier, this transaction will abort and raise a validation error."*

**[ON-SCREEN ACTION]**: Confirm approval &rarr; show the green success banner. Then point out a conflicting booking or attempt an approval on an overlapping slot to show the conflict rejection banner.

**[SPEAKING SCRIPT]**:
> *"Notice also that when rejecting a request, our form strictly enforces an administrative justification reason.*
> 
> *I now pass the floor to Member 4 for the schedule calendar and event operations."*

---

### 👤 MEMBER 4: Schedule Calendar, Rescheduling & Operational Check-In (07:30 &ndash; 10:00)

**[ON-SCREEN ACTION]**: Click **Schedule Calendar** (`/manage/calendar/`).

**[SPEAKING SCRIPT]**:
> *"Thank you. I will now present our auditable calendar and on-site operations console.*
> 
> *In this weekly view, our system demonstrates the **Half-Open Interval Rule** $[start, end)$. Notice these adjacent approved bookings at the Gymnasium: from 08:00 to 11:00, and 11:00 to 14:00. Because the boundary endpoint matches, our collision math recognizes that they do not conflict."*

**[ON-SCREEN ACTION]**: Click **Reschedule** on an approved reservation (`/manage/reschedule/<id>/`).

**[SPEAKING SCRIPT]**:
> *"When administrative rescheduling is necessary, the admin enters the new date/time with a required reason. Crucially, notice the **Historical Change Log table** on the right: our system permanently retains the original scheduled times in `ReservationChange` for complete audit integrity."*

**[ON-SCREEN ACTION]**: Navigate to **Event Operations** (`/manage/operations/`). Click **Check In** on an approved event, then click **Sign-Off Complete**. Click **Print Slip**.

**[SPEAKING SCRIPT]**:
> *"On event day, administrators record physical arrival via **Check-In**, followed by **Completion Sign-Off** with incident notes. 
> 
> By clicking **Print Slip**, our system generates the official BulSU Facility Reservation Slip and Completion Summary, styled for physical printing or PDF export with signature lines for the organizer and administrator.*
> 
> *Member 5 will now demonstrate closures, reports, and user governance."*

---

### 👤 MEMBER 5: Maintenance Closures, Reports & User Governance (10:00 &ndash; 12:00)

**[ON-SCREEN ACTION]**: Go to **Maintenance Closures** (`/manage/closures/`).

**[SPEAKING SCRIPT]**:
> *"Thank you. In **Maintenance Closures**, administrators block venue intervals for sanitation or repairs. If an admin attempts to schedule a closure that overlaps an approved booking, the system rejects it, requiring the booking to be rescheduled or cancelled first."*

**[ON-SCREEN ACTION]**: Navigate to **Utilization Reports** (`/manage/reports/`). Change the date filter range and show numbers updating. Click **Export Report to CSV**.

**[SPEAKING SCRIPT]**:
> *"Under **Utilization Reports**, all metrics—total booked hours, approved count, and completed events—are aggregated dynamically from ORM models using Django's `Sum`, `Count`, and `F` expressions. These are live transactions, not static demonstration values. 
> 
> Clicking **Export Report to CSV** generates an immediate, downloadable audit spreadsheet."*

**[ON-SCREEN ACTION]**: Go to **User Accounts** (`/manage/users/`). Click **Deactivate** on a demo account.

**[SPEAKING SCRIPT]**:
> *"In **User Accounts**, administrators can search and view complete reservation histories. Deactivating an account sets `is_active_account = False`. Our custom `AccountActiveCheckMiddleware` intercepts existing sessions on the very next request and logs the user out, while preserving historical records for university auditability.*
> 
> *Finally, our **Audit Log** records every administrative action with actor, IP address, and timestamp.*
> 
> *This concludes our 12-minute demonstration. We are now ready for Dr. Dela Rosa's Q&A."*

---

## 3-MINUTE Q&A QUICK-REFERENCE CHEAT SHEET

1. **"Why didn't you use Django's built-in Admin?"**
   - *"The syllabus strictly prohibits `admin.site.urls` and packages like Jazzmin. We hand-coded 100% of the admin dashboard, queue, and tables under `/manage/` using Django views and ModelForms to fulfill the 75% custom admin workload requirement."*

2. **"How did you implement concurrency and race condition prevention?"**
   - *"In `reservations/services.py`, `approve_reservation_atomic` executes within `transaction.atomic()` and locks database rows using `select_for_update()` on both the `Reservation` and the `Facility`. It re-verifies $[start, end)$ overlap immediately before committing."*

3. **"Explain the mathematical logic of your conflict detection."**
   - *"Intervals are treated as half-open: $[start, end)$. Two intervals $A$ and $B$ collide if and only if $start_A < end_B \text{ and } end_A > start_B$. If $end_A == start_B$, they meet at a point and do not overlap."*

4. **"How does your application uphold Data Privacy (RA 10173)?"**
   - *"When basic users view calendar availability, occupied slots are sanitized to show only 'Occupied / Reserved Slot' without displaying organizer identities, student numbers, or event details."*

5. **"What happens when a user is deactivated?"**
   - *"Deactivation blocks new sign-ins and uses `AccountActiveCheckMiddleware` to invalidate active sessions immediately. However, past reservation records are preserved to protect audit trail integrity."*
