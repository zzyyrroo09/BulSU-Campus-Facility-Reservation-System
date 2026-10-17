import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


class Profile(models.Model):
    """
    Extends Django Auth User with Role-Based Access Control and Profile Fields.
    STRICT COMPLIANCE: Exactly two roles ('BASIC_USER', 'ADMIN').
    """
    ROLE_CHOICES = (
        ('BASIC_USER', 'Basic User'),
        ('ADMIN', 'Administrator'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='BASIC_USER')
    contact_number = models.CharField(max_length=30, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')
    is_active_account = models.BooleanField(
        default=True,
        help_text="Controls if the user can sign in and submit transactions."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == 'ADMIN'

    @property
    def is_basic_user(self):
        return self.role == 'BASIC_USER'


class FacilityCategory(models.Model):
    """
    Logical grouping of campus facilities (e.g., Academic, Athletic, Multi-purpose).
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Facility Category"
        verbose_name_plural = "Facility Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Facility(models.Model):
    """
    Campus facilities available for booking.
    """
    code = models.CharField(max_length=30, unique=True, help_text="Unique facility code (e.g. GYM-01)")
    category = models.ForeignKey(FacilityCategory, on_delete=models.PROTECT, related_name='facilities')
    name = models.CharField(max_length=150)
    location = models.CharField(max_length=200)
    capacity = models.PositiveIntegerField(help_text="Maximum allowed attendees")
    description = models.TextField(blank=True, default='')
    operating_start_time = models.TimeField(help_text="Daily opening time (e.g., 08:00)")
    operating_end_time = models.TimeField(help_text="Daily closing time (e.g., 18:00 or 21:00)")
    is_active = models.BooleanField(default=True, help_text="Active status for booking availability")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Facility"
        verbose_name_plural = "Facilities"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        if self.operating_start_time and self.operating_end_time:
            if self.operating_start_time >= self.operating_end_time:
                raise ValidationError("Operating start time must precede operating end time.")


class Amenity(models.Model):
    """
    Catalog of equipment, audiovisual systems, and resources associated with facilities.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = "Amenity"
        verbose_name_plural = "Amenities"
        ordering = ['name']

    def __str__(self):
        return self.name


class FacilityAmenity(models.Model):
    """
    Association table between Facilities and Amenities with specific quantities.
    """
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='facility_amenities')
    amenity = models.ForeignKey(Amenity, on_delete=models.PROTECT, related_name='facility_links')
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('facility', 'amenity')
        verbose_name = "Facility Amenity"
        verbose_name_plural = "Facility Amenities"

    def __str__(self):
        return f"{self.facility.name} - {self.amenity.name} (Qty: {self.quantity})"


class Reservation(models.Model):
    """
    Primary reservation lifecycle record.
    Status transitions:
      PENDING -> APPROVED or REJECTED or CANCELLED
      APPROVED -> CHECKED_IN or NO_SHOW or CANCELLED
      CHECKED_IN -> COMPLETED
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('CHECKED_IN', 'Checked In'),
        ('COMPLETED', 'Completed'),
        ('NO_SHOW', 'No Show'),
    )

    tracking_code = models.CharField(max_length=36, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='reservations')
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name='reservations')
    title = models.CharField(max_length=200)
    purpose = models.TextField()
    participants_count = models.PositiveIntegerField()
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    
    # Decision audit fields
    decision_actor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='decided_reservations'
    )
    decision_timestamp = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reservation"
        verbose_name_plural = "Reservations"
        ordering = ['-start_time']

    def __str__(self):
        return f"[{self.tracking_code}] {self.title} - {self.facility.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            self.tracking_code = f"RES-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def duration_hours(self):
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return round(delta.total_seconds() / 3600, 2)
        return 0.0

    @property
    def is_past(self):
        return timezone.now() > self.end_time

    @property
    def can_be_cancelled_by_user(self):
        """Basic users can cancel PENDING or APPROVED reservations strictly before start time."""
        return self.status in ['PENDING', 'APPROVED'] and timezone.now() < self.start_time

    @property
    def can_be_checked_in(self):
        """Admin can check in only an APPROVED booking on or before the event window."""
        now = timezone.now()
        # Allows check-in on event day if approved
        return self.status == 'APPROVED' and now.date() == self.start_time.date()

    @property
    def can_be_completed(self):
        return self.status == 'CHECKED_IN'

    @property
    def can_be_marked_no_show(self):
        """No Show may be recorded only after scheduled end for a booking without check-in."""
        return self.status == 'APPROVED' and timezone.now() > self.end_time


class ClosureBlock(models.Model):
    """
    Facility maintenance, cleaning, or emergency closure time blocks.
    Active closures block overlapping reservations.
    """
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='closure_blocks')
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    reason = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_closures')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Closure Block"
        verbose_name_plural = "Closure Blocks"
        ordering = ['-start_time']

    def __str__(self):
        status = "Active" if self.is_active else "Archived"
        return f"{self.facility.name} Closure ({status}): {self.reason}"


class ReservationChange(models.Model):
    """
    Audit log for admin-initiated rescheduling of APPROVED reservations.
    Preserves original scheduled time in full history.
    """
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='reschedule_history')
    previous_start = models.DateTimeField()
    previous_end = models.DateTimeField()
    new_start = models.DateTimeField()
    new_end = models.DateTimeField()
    reason = models.TextField()
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='reschedule_actions')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reservation Reschedule Change"
        verbose_name_plural = "Reservation Reschedule Changes"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Reschedule for {self.reservation.tracking_code} by {self.actor.username} at {self.timestamp}"


class EventRecord(models.Model):
    """
    Operational record tracking physical execution, attendance, actual timestamps, and incident logs.
    """
    OPERATIONAL_STATUS_CHOICES = (
        ('CHECKED_IN', 'Checked In'),
        ('COMPLETED', 'Completed'),
        ('NO_SHOW', 'No Show'),
    )

    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='event_record')
    check_in_time = models.DateTimeField(null=True, blank=True)
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    operational_status = models.CharField(
        max_length=20, choices=OPERATIONAL_STATUS_CHOICES, default='CHECKED_IN'
    )
    incident_notes = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Event Record"
        verbose_name_plural = "Event Records"

    def __str__(self):
        return f"Event Record for {self.reservation.tracking_code} ({self.operational_status})"


class AuditLog(models.Model):
    """
    Comprehensive immutable audit trail of critical administrative and security events.
    """
    actor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs'
    )
    action_type = models.CharField(max_length=50, db_index=True)
    reference_model = models.CharField(max_length=50)
    reference_id = models.CharField(max_length=50)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ['-timestamp']

    def __str__(self):
        actor_name = self.actor.username if self.actor else "System"
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {actor_name} -> {self.action_type}: {self.description[:50]}"


class SystemSetting(models.Model):
    """
    Configurable system parameters: max event duration and advance booking window.
    Singleton design pattern.
    """
    max_event_duration_hours = models.PositiveIntegerField(
        default=4, help_text="Maximum duration permitted for an event in hours."
    )
    advance_booking_window_days = models.PositiveIntegerField(
        default=30, help_text="Maximum days in advance a user can submit a reservation."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return f"System Limits: {self.max_event_duration_hours}h max, {self.advance_booking_window_days}d window"

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj
