from datetime import time, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.urls import reverse

from reservations.models import (
    Profile, FacilityCategory, Facility, Reservation,
    ClosureBlock, EventRecord, SystemSetting, ReservationChange
)
from reservations.services import (
    check_slot_conflict, approve_reservation_atomic,
    reschedule_reservation_atomic, create_closure_block,
    check_in_event, complete_event, record_no_show, cancel_reservation
)


class ConcurrencyAndIntervalTestCase(TestCase):
    """
    Test half-open interval collision math and atomic reservation approval locks.
    """
    def setUp(self):
        self.tz = timezone.get_current_timezone()
        self.category = FacilityCategory.objects.create(name="Lecture Halls")
        self.facility = Facility.objects.create(
            code="HALL-01",
            category=self.category,
            name="Testing Lecture Hall",
            location="Building A",
            capacity=100,
            operating_start_time=time(8, 0),
            operating_end_time=time(20, 0),
            is_active=True
        )
        self.admin = User.objects.create_user(username="admin_test", password="pass")
        Profile.objects.create(user=self.admin, role='ADMIN', is_active_account=True)

        self.user1 = User.objects.create_user(username="user1_test", password="pass")
        Profile.objects.create(user=self.user1, role='BASIC_USER', is_active_account=True)

        self.user2 = User.objects.create_user(username="user2_test", password="pass")
        Profile.objects.create(user=self.user2, role='BASIC_USER', is_active_account=True)

        self.test_date = (timezone.now() + timedelta(days=2)).date()

    def test_half_open_adjacent_intervals_no_conflict(self):
        """
        Rule 1: Two intervals [start, end) do NOT conflict if end_A == start_B.
        Adjacent reservations meeting at the same endpoint must succeed.
        """
        slot_a_start = timezone.make_aware(timezone.datetime.combine(self.test_date, time(8, 0)), self.tz)
        slot_a_end = timezone.make_aware(timezone.datetime.combine(self.test_date, time(10, 0)), self.tz)

        slot_b_start = slot_a_end  # exactly 10:00
        slot_b_end = timezone.make_aware(timezone.datetime.combine(self.test_date, time(12, 0)), self.tz)

        # Create and approve Slot A
        res_a = Reservation.objects.create(
            tracking_code="RES-TEST-A",
            user=self.user1,
            facility=self.facility,
            title="Event A",
            purpose="Testing A",
            participants_count=30,
            start_time=slot_a_start,
            end_time=slot_a_end,
            status='APPROVED'
        )

        # Slot B check should report NO conflict
        has_conflict, obj, ctype = check_slot_conflict(
            facility=self.facility,
            start_time=slot_b_start,
            end_time=slot_b_end
        )
        self.assertFalse(has_conflict, "Adjacent interval sharing endpoint must not report a conflict.")

    def test_overlapping_intervals_do_conflict(self):
        """
        Rule 1 & 2: Intervals [08:00, 10:30) and [10:00, 12:00) overlap by 30 mins and MUST conflict.
        """
        slot_a_start = timezone.make_aware(timezone.datetime.combine(self.test_date, time(8, 0)), self.tz)
        slot_a_end = timezone.make_aware(timezone.datetime.combine(self.test_date, time(10, 30)), self.tz)

        slot_b_start = timezone.make_aware(timezone.datetime.combine(self.test_date, time(10, 0)), self.tz)
        slot_b_end = timezone.make_aware(timezone.datetime.combine(self.test_date, time(12, 0)), self.tz)

        Reservation.objects.create(
            tracking_code="RES-TEST-EXISTING",
            user=self.user1,
            facility=self.facility,
            title="Existing Booking",
            purpose="Occupying slot",
            participants_count=30,
            start_time=slot_a_start,
            end_time=slot_a_end,
            status='APPROVED'
        )

        has_conflict, obj, ctype = check_slot_conflict(
            facility=self.facility,
            start_time=slot_b_start,
            end_time=slot_b_end
        )
        self.assertTrue(has_conflict)

    def test_competing_approvals_only_one_succeeds(self):
        """
        Rule 3: Competing approvals for the same slot: only one succeeds.
        Second approval must raise ValidationError.
        """
        st = timezone.make_aware(timezone.datetime.combine(self.test_date, time(13, 0)), self.tz)
        et = timezone.make_aware(timezone.datetime.combine(self.test_date, time(15, 0)), self.tz)

        res1 = Reservation.objects.create(
            tracking_code="RES-COMPETE-1",
            user=self.user1,
            facility=self.facility,
            title="Competing Booking 1",
            purpose="Presentation 1",
            participants_count=40,
            start_time=st,
            end_time=et,
            status='PENDING'
        )

        res2 = Reservation.objects.create(
            tracking_code="RES-COMPETE-2",
            user=self.user2,
            facility=self.facility,
            title="Competing Booking 2",
            purpose="Presentation 2",
            participants_count=50,
            start_time=st,
            end_time=et,
            status='PENDING'
        )

        # First approval succeeds
        appr1 = approve_reservation_atomic(res1.id, self.admin, "Approved first.")
        self.assertEqual(appr1.status, 'APPROVED')

        # Second approval for conflicting slot MUST fail atomically
        with self.assertRaises(ValidationError):
            approve_reservation_atomic(res2.id, self.admin, "Attempted competing approval.")

        res2.refresh_from_db()
        self.assertEqual(res2.status, 'PENDING')

    def test_closure_conflict_rejection(self):
        """
        Rule A6: Cannot create a closure that overlaps an APPROVED booking.
        """
        st = timezone.make_aware(timezone.datetime.combine(self.test_date, time(16, 0)), self.tz)
        et = timezone.make_aware(timezone.datetime.combine(self.test_date, time(18, 0)), self.tz)

        Reservation.objects.create(
            tracking_code="RES-APPROVED-ACTIVE",
            user=self.user1,
            facility=self.facility,
            title="Confirmed Session",
            purpose="Study session",
            participants_count=20,
            start_time=st,
            end_time=et,
            status='APPROVED'
        )

        # Attempt to create maintenance closure overlapping this booking
        with self.assertRaises(ValidationError):
            create_closure_block(
                facility=self.facility,
                start_time=st,
                end_time=et,
                reason="Emergency maintenance",
                admin_user=self.admin
            )

    def test_event_operational_lifecycle(self):
        """
        Rule A5: Check-in only for APPROVED. Cannot complete before check-in.
        """
        st = timezone.make_aware(timezone.datetime.combine(self.test_date, time(8, 0)), self.tz)
        et = timezone.make_aware(timezone.datetime.combine(self.test_date, time(10, 0)), self.tz)

        res = Reservation.objects.create(
            tracking_code="RES-OP-TEST",
            user=self.user1,
            facility=self.facility,
            title="Operational Test",
            purpose="Lifecycle testing",
            participants_count=15,
            start_time=st,
            end_time=et,
            status='APPROVED'
        )

        # Cannot complete before check-in
        with self.assertRaises(ValidationError):
            complete_event(res.id, self.admin)

        # Check-in succeeds
        res, rec = check_in_event(res.id, self.admin, notes="Checked in on schedule.")
        self.assertEqual(res.status, 'CHECKED_IN')
        self.assertEqual(rec.operational_status, 'CHECKED_IN')

        # Completion succeeds after check-in
        res, rec = complete_event(res.id, self.admin, notes="All completed cleanly.")
        self.assertEqual(res.status, 'COMPLETED')
        self.assertEqual(rec.operational_status, 'COMPLETED')


class RBACSecurityTestCase(TestCase):
    """
    Test access control, role boundaries, and deactivated account blocks.
    """
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username="admin_rbac", password="Password123!")
        Profile.objects.create(user=self.admin, role='ADMIN', is_active_account=True)

        self.user = User.objects.create_user(username="user_rbac", password="Password123!")
        Profile.objects.create(user=self.user, role='BASIC_USER', is_active_account=True)

    def test_basic_user_blocked_from_admin_console(self):
        """
        Basic users must be blocked from /manage/ and redirected with an error.
        """
        self.client.login(username="user_rbac", password="Password123!")
        response = self.client.get('/manage/dashboard/')
        # Redirected to user portal dashboard with access denied
        self.assertEqual(response.status_code, 302)
        self.assertIn('/portal/dashboard/', response.url)

    def test_deactivated_account_session_invalidation(self):
        """
        Deactivated user session must be immediately invalidated.
        """
        self.client.login(username="user_rbac", password="Password123!")
        # Verify authenticated access
        res = self.client.get('/portal/dashboard/')
        self.assertEqual(res.status_code, 200)

        # Deactivate user account
        profile = self.user.profile
        profile.is_active_account = False
        profile.save()

        # Subsequent request must be caught by middleware, logged out, and redirected to login
        res_after = self.client.get('/portal/dashboard/')
        self.assertEqual(res_after.status_code, 302)
        self.assertIn('/login/', res_after.url)
