from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import (
    Facility, Reservation, ClosureBlock,
    ReservationChange, EventRecord, AuditLog, SystemSetting
)


def log_audit(actor, action_type, reference_model, reference_id, description, ip_address=None):
    """
    Creates an immutable audit log record.
    """
    return AuditLog.objects.create(
        actor=actor if (actor and actor.is_authenticated) else None,
        action_type=action_type,
        reference_model=reference_model,
        reference_id=str(reference_id),
        description=description,
        ip_address=ip_address
    )


def check_slot_conflict(facility, start_time, end_time, exclude_reservation_id=None):
    """
    Evaluates half-open overlap [start, end) against:
      1. Active ClosureBlocks for the facility.
      2. Existing reservations with status in ['APPROVED', 'CHECKED_IN'].
    
    Half-open interval overlap math:
      Interval A [start, end) conflicts with Interval B [B_start, B_end)
      if and only if: start < B_end AND end > B_start.
      Adjacent intervals where end_A == start_B do NOT conflict.

    Returns:
      (has_conflict: bool, conflicting_object, conflict_type: str)
    """
    # 1. Check active facility closures
    overlapping_closures = ClosureBlock.objects.filter(
        facility=facility,
        is_active=True,
        start_time__lt=end_time,
        end_time__gt=start_time
    )
    if overlapping_closures.exists():
        closure = overlapping_closures.first()
        return True, closure, f"Closure Block ({closure.reason})"

    # 2. Check approved or checked-in reservations
    overlapping_reservations = Reservation.objects.filter(
        facility=facility,
        status__in=['APPROVED', 'CHECKED_IN'],
        start_time__lt=end_time,
        end_time__gt=start_time
    )
    if exclude_reservation_id:
        overlapping_reservations = overlapping_reservations.exclude(id=exclude_reservation_id)

    if overlapping_reservations.exists():
        res = overlapping_reservations.first()
        return True, res, f"Approved Reservation ({res.tracking_code})"

    return False, None, None


def validate_booking_rules(facility, start_time, end_time, participants_count, enforce_future=True):
    """
    Enforces academic and technical domain constraints:
      - End time strictly after start time.
      - Same-day operating hours (no overnight events).
      - Fits entirely within facility operating hours.
      - Participants count between 1 and facility.capacity.
      - Duration does not exceed max_event_duration_hours.
      - Advance booking window adherence.
    """
    settings = SystemSetting.get_settings()
    now = timezone.now()

    if end_time <= start_time:
        raise ValidationError("End time must be strictly after start time.")

    # Future requirement
    if enforce_future and start_time <= now:
        raise ValidationError("Reservation start time must be in the future.")

    # Same calendar day (no overnight bookings)
    if start_time.date() != end_time.date():
        raise ValidationError("Overnight bookings are not permitted. Events must start and end on the same calendar day.")

    # Operating hours
    if start_time.time() < facility.operating_start_time or end_time.time() > facility.operating_end_time:
        raise ValidationError(
            f"Requested time is outside facility operating hours ({facility.operating_start_time:%H:%M} to {facility.operating_end_time:%H:%M})."
        )

    # Capacity
    if participants_count < 1:
        raise ValidationError("Participants count must be at least 1.")
    if participants_count > facility.capacity:
        raise ValidationError(
            f"Participant count ({participants_count}) exceeds facility capacity ({facility.capacity})."
        )

    # Maximum duration
    duration_hours = (end_time - start_time).total_seconds() / 3600
    if duration_hours > settings.max_event_duration_hours:
        raise ValidationError(
            f"Event duration ({duration_hours:.1f} hrs) exceeds the maximum allowed limit of {settings.max_event_duration_hours} hours."
        )

    # Advance booking window
    max_advance_date = now + timedelta(days=settings.advance_booking_window_days)
    if enforce_future and start_time > max_advance_date:
        raise ValidationError(
            f"Bookings cannot be scheduled more than {settings.advance_booking_window_days} days in advance."
        )


def approve_reservation_atomic(reservation_id, admin_user, reason=""):
    """
    Atomically approves a PENDING reservation using select_for_update() row locking.
    Prevents race conditions when two administrators attempt to approve competing
    reservations for the same slot simultaneously.
    """
    with transaction.atomic():
        try:
            reservation = Reservation.objects.select_for_update().get(id=reservation_id)
        except Reservation.DoesNotExist:
            raise ValidationError("Reservation does not exist.")

        # Lock the facility to synchronize concurrent requests for the same facility
        facility = Facility.objects.select_for_update().get(id=reservation.facility_id)

        if reservation.status != 'PENDING':
            raise ValidationError(
                f"Cannot approve reservation: Status is currently '{reservation.get_status_display()}'. Only PENDING requests may be approved."
            )

        # Atomically recheck conflicts right before committing
        has_conflict, conflicting_obj, conflict_type = check_slot_conflict(
            facility=facility,
            start_time=reservation.start_time,
            end_time=reservation.end_time,
            exclude_reservation_id=reservation.id
        )

        if has_conflict:
            raise ValidationError(
                f"Approval conflict: The requested slot overlaps with an existing {conflict_type}."
            )

        reservation.status = 'APPROVED'
        reservation.decision_actor = admin_user
        reservation.decision_timestamp = timezone.now()
        reservation.decision_reason = reason or "Approved by facility administrator."
        reservation.save()

        log_audit(
            actor=admin_user,
            action_type='APPROVE_RESERVATION',
            reference_model='Reservation',
            reference_id=reservation.id,
            description=f"Approved reservation {reservation.tracking_code} for facility {facility.name}."
        )

        return reservation


def reject_reservation(reservation_id, admin_user, reason):
    """
    Rejects a PENDING reservation with a mandatory administrator reason.
    """
    if not reason or not reason.strip():
        raise ValidationError("A specific rejection reason is required.")

    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(id=reservation_id)
        if reservation.status != 'PENDING':
            raise ValidationError(f"Only PENDING requests can be rejected (current: {reservation.status}).")

        reservation.status = 'REJECTED'
        reservation.decision_actor = admin_user
        reservation.decision_timestamp = timezone.now()
        reservation.decision_reason = reason.strip()
        reservation.save()

        log_audit(
            actor=admin_user,
            action_type='REJECT_RESERVATION',
            reference_model='Reservation',
            reference_id=reservation.id,
            description=f"Rejected reservation {reservation.tracking_code}. Reason: {reason.strip()}"
        )

        return reservation


def reschedule_reservation_atomic(reservation_id, new_start, new_end, admin_user, reason):
    """
    Reschedules an APPROVED reservation. Revalidates operating hours, capacity,
    and conflicts. Atomically preserves historical scheduling data in ReservationChange.
    """
    if not reason or not reason.strip():
        raise ValidationError("A justification reason is required for rescheduling.")

    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(id=reservation_id)
        facility = Facility.objects.select_for_update().get(id=reservation.facility_id)

        if reservation.status != 'APPROVED':
            raise ValidationError("Only APPROVED reservations can be rescheduled.")

        # Validate operating hours and limits (without enforce_future to allow demonstration adjustments)
        validate_booking_rules(
            facility=facility,
            start_time=new_start,
            end_time=new_end,
            participants_count=reservation.participants_count,
            enforce_future=False
        )

        # Check half-open conflict
        has_conflict, conflicting_obj, conflict_type = check_slot_conflict(
            facility=facility,
            start_time=new_start,
            end_time=new_end,
            exclude_reservation_id=reservation.id
        )
        if has_conflict:
            raise ValidationError(f"Rescheduling conflict: New time slot overlaps with {conflict_type}.")

        # Record audit change
        ReservationChange.objects.create(
            reservation=reservation,
            previous_start=reservation.start_time,
            previous_end=reservation.end_time,
            new_start=new_start,
            new_end=new_end,
            reason=reason.strip(),
            actor=admin_user
        )

        # Update reservation
        reservation.start_time = new_start
        reservation.end_time = new_end
        reservation.save()

        log_audit(
            actor=admin_user,
            action_type='RESCHEDULE_RESERVATION',
            reference_model='Reservation',
            reference_id=reservation.id,
            description=f"Rescheduled {reservation.tracking_code} to {new_start:%Y-%m-%d %H:%M} - {new_end:%H:%M}. Reason: {reason.strip()}"
        )

        return reservation


def create_closure_block(facility, start_time, end_time, reason, admin_user):
    """
    Creates a maintenance/closure time block per facility.
    Strict Requirement A6: Rejects a closure that overlaps an Approved or Checked In booking
    until the admin explicitly reschedules or cancels that booking with a reason.
    """
    if end_time <= start_time:
        raise ValidationError("Closure end time must be after start time.")
    if not reason or not reason.strip():
        raise ValidationError("A reason for the closure is required.")

    # Check for conflicting approved or checked-in bookings
    conflicts = Reservation.objects.filter(
        facility=facility,
        status__in=['APPROVED', 'CHECKED_IN'],
        start_time__lt=end_time,
        end_time__gt=start_time
    )

    if conflicts.exists():
        first = conflicts.first()
        raise ValidationError(
            f"Cannot create closure block: Overlaps with active booking '{first.title}' [{first.tracking_code}] "
            f"scheduled from {first.start_time:%Y-%m-%d %H:%M} to {first.end_time:%H:%M}. "
            "Please reschedule or cancel that booking first."
        )

    closure = ClosureBlock.objects.create(
        facility=facility,
        start_time=start_time,
        end_time=end_time,
        reason=reason.strip(),
        is_active=True,
        created_by=admin_user
    )

    log_audit(
        actor=admin_user,
        action_type='CREATE_CLOSURE',
        reference_model='ClosureBlock',
        reference_id=closure.id,
        description=f"Created closure for {facility.name} from {start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}. Reason: {reason}"
    )

    return closure


def check_in_event(reservation_id, admin_user, actual_start=None, notes=""):
    """
    Records physical check-in and event start. Check-in is permitted only for APPROVED bookings.
    """
    now = timezone.now()
    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(id=reservation_id)
        if reservation.status != 'APPROVED':
            raise ValidationError(f"Check-in permitted only for APPROVED bookings (current: {reservation.status}).")

        reservation.status = 'CHECKED_IN'
        reservation.save()

        record, created = EventRecord.objects.get_or_create(
            reservation=reservation,
            defaults={
                'check_in_time': now,
                'actual_start_time': actual_start or now,
                'operational_status': 'CHECKED_IN',
                'incident_notes': notes
            }
        )
        if not created:
            record.check_in_time = now
            record.actual_start_time = actual_start or now
            record.operational_status = 'CHECKED_IN'
            if notes:
                record.incident_notes = f"{record.incident_notes}\n{notes}".strip()
            record.save()

        log_audit(
            actor=admin_user,
            action_type='CHECK_IN_EVENT',
            reference_model='Reservation',
            reference_id=reservation.id,
            description=f"Checked in booking {reservation.tracking_code} for {reservation.facility.name}."
        )

        return reservation, record


def complete_event(reservation_id, admin_user, actual_end=None, notes=""):
    """
    Completes an event. Prevents completion before check-in.
    Enforces rule: actual end cannot precede actual start.
    """
    now = timezone.now()
    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(id=reservation_id)
        if reservation.status != 'CHECKED_IN':
            raise ValidationError("Completion is only allowed for events that have been CHECKED_IN.")

        try:
            record = reservation.event_record
        except EventRecord.DoesNotExist:
            raise ValidationError("Event record missing. Please check in first.")

        end_ts = actual_end or now
        if record.actual_start_time and end_ts < record.actual_start_time:
            raise ValidationError("Actual end time cannot precede actual start time.")

        reservation.status = 'COMPLETED'
        reservation.save()

        record.actual_end_time = end_ts
        record.operational_status = 'COMPLETED'
        if notes:
            record.incident_notes = f"{record.incident_notes}\n{notes}".strip()
        record.save()

        log_audit(
            actor=admin_user,
            action_type='COMPLETE_EVENT',
            reference_model='Reservation',
            reference_id=reservation.id,
            description=f"Completed event {reservation.tracking_code}."
        )

        return reservation, record


def record_no_show(reservation_id, admin_user, notes=""):
    """
    Records No-Show. Permitted only after scheduled end time for a booking without check-in.
    """
    now = timezone.now()
    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(id=reservation_id)
        if reservation.status != 'APPROVED':
            raise ValidationError("No-Show can only be recorded for APPROVED reservations.")

        if now < reservation.end_time:
            raise ValidationError("No-Show may only be recorded after the scheduled end time has passed.")

        reservation.status = 'NO_SHOW'
        reservation.save()

        record, created = EventRecord.objects.get_or_create(
            reservation=reservation,
            defaults={
                'operational_status': 'NO_SHOW',
                'incident_notes': notes or "Marked as No-Show by administrator after scheduled end."
            }
        )
        if not created:
            record.operational_status = 'NO_SHOW'
            record.incident_notes = notes or "Marked as No-Show by administrator."
            record.save()

        log_audit(
            actor=admin_user,
            action_type='RECORD_NO_SHOW',
            reference_model='Reservation',
            reference_id=reservation.id,
            description=f"Marked reservation {reservation.tracking_code} as NO_SHOW."
        )

        return reservation, record


def cancel_reservation(reservation_id, user, reason=""):
    """
    Cancels a reservation.
    Basic users can cancel only their own PENDING or APPROVED booking strictly before start time.
    Admins can cancel with reason.
    """
    now = timezone.now()
    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(id=reservation_id)
        is_admin = hasattr(user, 'profile') and user.profile.is_admin

        if not is_admin:
            # Basic user rules
            if reservation.user != user:
                raise ValidationError("You do not have permission to cancel this reservation.")
            if reservation.status not in ['PENDING', 'APPROVED']:
                raise ValidationError(f"Cannot cancel a booking with status '{reservation.get_status_display()}'.")
            if now >= reservation.start_time:
                raise ValidationError("Reservations can only be cancelled strictly before the event start time.")
        else:
            if reservation.status in ['COMPLETED', 'NO_SHOW', 'CANCELLED', 'REJECTED']:
                raise ValidationError("Cannot cancel a reservation that has already reached a terminal state.")

        previous_status = reservation.status
        reservation.status = 'CANCELLED'
        reservation.decision_actor = user
        reservation.decision_timestamp = now
        reservation.decision_reason = reason or ("Cancelled by user" if not is_admin else "Cancelled by admin")
        reservation.save()

        log_audit(
            actor=user,
            action_type='CANCEL_RESERVATION',
            reference_model='Reservation',
            reference_id=reservation.id,
            description=f"Cancelled reservation {reservation.tracking_code} (previous status: {previous_status}). Reason: {reason}"
        )

        return reservation
