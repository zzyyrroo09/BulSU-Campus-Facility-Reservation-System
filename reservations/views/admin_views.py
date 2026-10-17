import csv
from datetime import datetime, date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.db.models import Count, Sum, F, Q

from reservations.models import (
    Profile, FacilityCategory, Facility, Amenity, FacilityAmenity,
    Reservation, ClosureBlock, ReservationChange, EventRecord,
    AuditLog, SystemSetting
)
from reservations.forms import (
    FacilityForm, FacilityCategoryForm, AmenityForm, FacilityAmenityForm,
    AdminRescheduleForm, ClosureBlockForm, SystemSettingForm
)
from reservations.decorators import admin_required
from reservations.services import (
    log_audit, approve_reservation_atomic, reject_reservation,
    reschedule_reservation_atomic, create_closure_block,
    check_in_event, complete_event, record_no_show, cancel_reservation
)


# ==========================================
# A7. DASHBOARD & LIVE METRICS
# ==========================================
@admin_required
def dashboard_view(request):
    """
    Administrator dashboard with 4 live metric cards, operational shortcuts,
    and Chart.js monthly trend data.
    """
    now = timezone.now()
    
    # 4 Live Cards
    pending_count = Reservation.objects.filter(status='PENDING').count()
    approved_upcoming_count = Reservation.objects.filter(
        status='APPROVED', start_time__gte=now
    ).count()
    completed_events_count = Reservation.objects.filter(status='COMPLETED').count()
    active_facilities_count = Facility.objects.filter(is_active=True).count()

    # Recent Pending Queue
    recent_pending = Reservation.objects.filter(
        status='PENDING'
    ).select_related('user', 'facility').order_by('created_at')[:5]

    # Today's Operations
    today_start = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()))
    today_end = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
    todays_events = Reservation.objects.filter(
        status__in=['APPROVED', 'CHECKED_IN'],
        start_time__gte=today_start,
        start_time__lte=today_end
    ).select_related('user', 'facility').order_by('start_time')

    # Monthly Trend Data (Last 6 Months)
    monthly_labels = []
    monthly_counts = []
    for i in range(5, -1, -1):
        target_month_date = (now.date().replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        month_label = target_month_date.strftime('%b %Y')
        next_month = (target_month_date + timedelta(days=32)).replace(day=1)
        
        c = Reservation.objects.filter(
            created_at__gte=timezone.make_aware(datetime.combine(target_month_date, datetime.min.time())),
            created_at__lt=timezone.make_aware(datetime.combine(next_month, datetime.min.time()))
        ).count()
        monthly_labels.append(month_label)
        monthly_counts.append(c)

    # Facility Usage Distribution
    facility_usage = Facility.objects.annotate(
        booking_count=Count('reservations', filter=Q(reservations__status__in=['APPROVED', 'CHECKED_IN', 'COMPLETED']))
    ).order_by('-booking_count')[:6]

    facility_labels = [f.name for f in facility_usage]
    facility_counts = [f.booking_count for f in facility_usage]

    context = {
        'pending_count': pending_count,
        'approved_upcoming_count': approved_upcoming_count,
        'completed_events_count': completed_events_count,
        'active_facilities_count': active_facilities_count,
        'recent_pending': recent_pending,
        'todays_events': todays_events,
        'monthly_labels': monthly_labels,
        'monthly_counts': monthly_counts,
        'facility_labels': facility_labels,
        'facility_counts': facility_counts,
    }
    return render(request, 'admin/dashboard.html', context)


# ==========================================
# A1. ACCOUNT MANAGEMENT
# ==========================================
@admin_required
def user_list_view(request):
    """
    List, search, filter basic-user accounts.
    Show reservation count and active status.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    profiles = Profile.objects.filter(role='BASIC_USER').select_related('user').annotate(
        total_reservations=Count('user__reservations')
    ).order_by('user__last_name', 'user__first_name')

    if query:
        profiles = profiles.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(department__icontains=query)
        )

    if status_filter == 'active':
        profiles = profiles.filter(is_active_account=True)
    elif status_filter == 'inactive':
        profiles = profiles.filter(is_active_account=False)

    paginator = Paginator(profiles, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'admin/users/user_list.html', {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter
    })


@admin_required
def user_detail_view(request, user_id):
    """
    View user details and full reservation history.
    """
    profile = get_object_or_404(Profile.objects.select_related('user'), user_id=user_id, role='BASIC_USER')
    reservations = Reservation.objects.filter(user=profile.user).select_related('facility').order_by('-created_at')

    return render(request, 'admin/users/user_detail.html', {
        'target_profile': profile,
        'reservations': reservations
    })


@admin_required
def user_toggle_status_view(request, user_id):
    """
    Activate or deactivate basic-user accounts.
    Deactivation blocks new sign-ins and active sessions without deleting records.
    """
    profile = get_object_or_404(Profile.objects.select_related('user'), user_id=user_id, role='BASIC_USER')

    if request.method == 'POST':
        profile.is_active_account = not profile.is_active_account
        profile.save()

        action = "ACTIVATED" if profile.is_active_account else "DEACTIVATED"
        messages.success(request, f"User account {profile.user.username} has been {action}.")

        log_audit(
            actor=request.user,
            action_type='USER_STATUS_CHANGE',
            reference_model='User',
            reference_id=profile.user.id,
            description=f"{action} account for user {profile.user.username} ({profile.user.email}).",
            ip_address=request.META.get('REMOTE_ADDR')
        )

    return redirect('admin_panel:user_detail', user_id=profile.user.id)


# ==========================================
# A2. FACILITIES AND AMENITIES
# ==========================================
@admin_required
def facility_list_view(request):
    """
    List all facilities with category, capacity, operating hours, and active status.
    """
    facilities = Facility.objects.select_related('category').prefetch_related(
        'facility_amenities__amenity'
    ).order_by('category__name', 'name')

    categories = FacilityCategory.objects.all()
    return render(request, 'admin/facilities/facility_list.html', {
        'facilities': facilities,
        'categories': categories
    })


@admin_required
def facility_create_view(request):
    """
    Create a new campus facility.
    """
    if request.method == 'POST':
        form = FacilityForm(request.POST)
        if form.is_valid():
            facility = form.save()
            messages.success(request, f"Facility '{facility.name}' ({facility.code}) created successfully.")
            log_audit(
                actor=request.user,
                action_type='CREATE_FACILITY',
                reference_model='Facility',
                reference_id=facility.id,
                description=f"Created facility {facility.name} [{facility.code}].",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return redirect('admin_panel:facility_list')
    else:
        form = FacilityForm()

    return render(request, 'admin/facilities/facility_form.html', {'form': form, 'title': 'Create Facility'})


@admin_required
def facility_edit_view(request, pk):
    """
    Edit facility details and operating hours.
    """
    facility = get_object_or_404(Facility, pk=pk)
    if request.method == 'POST':
        form = FacilityForm(request.POST, instance=facility)
        if form.is_valid():
            form.save()
            messages.success(request, f"Facility '{facility.name}' updated successfully.")
            log_audit(
                actor=request.user,
                action_type='UPDATE_FACILITY',
                reference_model='Facility',
                reference_id=facility.id,
                description=f"Updated facility {facility.name} [{facility.code}].",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return redirect('admin_panel:facility_list')
    else:
        form = FacilityForm(instance=facility)

    amenities = facility.facility_amenities.select_related('amenity')
    amenity_form = FacilityAmenityForm()

    return render(request, 'admin/facilities/facility_form.html', {
        'form': form,
        'facility': facility,
        'amenities': amenities,
        'amenity_form': amenity_form,
        'title': f"Edit Facility: {facility.name}"
    })


@admin_required
def facility_toggle_active_view(request, pk):
    """
    Archive / unarchive facility (toggles is_active).
    Preserves facilities referenced by past reservations.
    """
    facility = get_object_or_404(Facility, pk=pk)
    if request.method == 'POST':
        facility.is_active = not facility.is_active
        facility.save()
        status_str = "activated" if facility.is_active else "archived"
        messages.success(request, f"Facility '{facility.name}' has been {status_str}.")
        log_audit(
            actor=request.user,
            action_type='TOGGLE_FACILITY_ACTIVE',
            reference_model='Facility',
            reference_id=facility.id,
            description=f"Set facility {facility.name} active flag to {facility.is_active}.",
            ip_address=request.META.get('REMOTE_ADDR')
        )
    return redirect('admin_panel:facility_list')


@admin_required
def facility_amenity_add_view(request, pk):
    """
    Associate an amenity with quantity to a facility.
    """
    facility = get_object_or_404(Facility, pk=pk)
    if request.method == 'POST':
        form = FacilityAmenityForm(request.POST)
        if form.is_valid():
            amenity = form.cleaned_data['amenity']
            quantity = form.cleaned_data['quantity']
            assoc, created = FacilityAmenity.objects.update_or_create(
                facility=facility,
                amenity=amenity,
                defaults={'quantity': quantity}
            )
            messages.success(request, f"Amenity '{amenity.name}' linked to {facility.name}.")
    return redirect('admin_panel:facility_edit', pk=facility.pk)


@admin_required
def facility_amenity_remove_view(request, pk, amenity_id):
    """
    Remove an amenity from a facility.
    """
    facility = get_object_or_404(Facility, pk=pk)
    FacilityAmenity.objects.filter(facility=facility, amenity_id=amenity_id).delete()
    messages.info(request, "Amenity removed from facility.")
    return redirect('admin_panel:facility_edit', pk=facility.pk)


@admin_required
def category_list_view(request):
    """
    Manage facility categories.
    """
    categories = FacilityCategory.objects.annotate(facility_count=Count('facilities'))
    if request.method == 'POST':
        form = FacilityCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' created.")
            return redirect('admin_panel:category_list')
    else:
        form = FacilityCategoryForm()

    return render(request, 'admin/facilities/category_list.html', {
        'categories': categories,
        'form': form
    })


@admin_required
def amenity_list_view(request):
    """
    Manage amenity catalog.
    """
    amenities = Amenity.objects.annotate(usage_count=Count('facility_links'))
    if request.method == 'POST':
        form = AmenityForm(request.POST)
        if form.is_valid():
            amenity = form.save()
            messages.success(request, f"Amenity '{amenity.name}' added to catalog.")
            return redirect('admin_panel:amenity_list')
    else:
        form = AmenityForm()

    return render(request, 'admin/facilities/amenity_list.html', {
        'amenities': amenities,
        'form': form
    })


# ==========================================
# A3. REQUEST REVIEW AND APPROVAL QUEUE
# ==========================================
@admin_required
def review_queue_view(request):
    """
    Searchable, paginated review queue filtered by facility, status, and date.
    """
    facility_id = request.GET.get('facility')
    status = request.GET.get('status', 'PENDING')
    date_str = request.GET.get('date')

    reservations = Reservation.objects.select_related('user', 'facility', 'facility__category')

    if status and status != 'ALL':
        reservations = reservations.filter(status=status)

    if facility_id:
        reservations = reservations.filter(facility_id=facility_id)

    if date_str:
        try:
            filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            start_range = timezone.make_aware(datetime.combine(filter_date, datetime.min.time()))
            end_range = timezone.make_aware(datetime.combine(filter_date, datetime.max.time()))
            reservations = reservations.filter(start_time__gte=start_range, start_time__lte=end_range)
        except ValueError:
            pass

    reservations = reservations.order_by('start_time')
    paginator = Paginator(reservations, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    facilities = Facility.objects.all()

    return render(request, 'admin/queue/review_queue.html', {
        'page_obj': page_obj,
        'facilities': facilities,
        'selected_facility': facility_id,
        'selected_status': status,
        'selected_date': date_str
    })


@admin_required
def approve_reservation_view(request, pk):
    """
    Atomically approve a reservation with row locking and real-time conflict checking.
    """
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        try:
            res = approve_reservation_atomic(
                reservation_id=pk,
                admin_user=request.user,
                reason=reason
            )
            messages.success(
                request,
                f"Reservation {res.tracking_code} for '{res.title}' approved successfully!"
            )
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('admin_panel:review_queue')


@admin_required
def reject_reservation_view(request, pk):
    """
    Reject a pending reservation with required justification reason.
    """
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "A reason is strictly required to reject a reservation request.")
            return redirect('admin_panel:review_queue')

        try:
            res = reject_reservation(
                reservation_id=pk,
                admin_user=request.user,
                reason=reason
            )
            messages.info(request, f"Reservation {res.tracking_code} has been rejected.")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('admin_panel:review_queue')


# ==========================================
# A4. CALENDAR AND APPROVED RESCHEDULING
# ==========================================
@admin_required
def schedule_calendar_view(request):
    """
    Display daily and weekly facility schedules with clear visual status labels.
    """
    facility_id = request.GET.get('facility')
    date_str = request.GET.get('date')

    if date_str:
        try:
            view_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            view_date = timezone.now().date()
    else:
        view_date = timezone.now().date()

    # Calculate week window (Monday to Sunday)
    start_of_week = view_date - timedelta(days=view_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    dt_start = timezone.make_aware(datetime.combine(start_of_week, datetime.min.time()))
    dt_end = timezone.make_aware(datetime.combine(end_of_week, datetime.max.time()))

    reservations = Reservation.objects.filter(
        start_time__gte=dt_start,
        start_time__lte=dt_end,
        status__in=['APPROVED', 'CHECKED_IN', 'COMPLETED', 'NO_SHOW']
    ).select_related('facility', 'user')

    closures = ClosureBlock.objects.filter(
        is_active=True,
        start_time__gte=dt_start,
        start_time__lte=dt_end
    ).select_related('facility')

    if facility_id:
        reservations = reservations.filter(facility_id=facility_id)
        closures = closures.filter(facility_id=facility_id)

    facilities = Facility.objects.all()

    # Days of the week list
    week_days = [start_of_week + timedelta(days=i) for i in range(7)]

    return render(request, 'admin/calendar/schedule_calendar.html', {
        'view_date': view_date,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'week_days': week_days,
        'reservations': reservations,
        'closures': closures,
        'facilities': facilities,
        'selected_facility': facility_id,
        'prev_week': (view_date - timedelta(days=7)).isoformat(),
        'next_week': (view_date + timedelta(days=7)).isoformat(),
    })


@admin_required
def reschedule_reservation_view(request, pk):
    """
    Admin rescheduling of an Approved booking with reason, retaining original time in history.
    Revalidates capacity, operating hours, closures, and conflicts.
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('facility', 'user'), pk=pk
    )

    if reservation.status != 'APPROVED':
        messages.error(request, "Only APPROVED reservations may be rescheduled.")
        return redirect('admin_panel:schedule_calendar')

    if request.method == 'POST':
        form = AdminRescheduleForm(request.POST)
        if form.is_valid():
            booking_date = form.cleaned_data['booking_date']
            start_val = form.cleaned_data['start_time_input']
            end_val = form.cleaned_data['end_time_input']
            reason = form.cleaned_data['reason']

            tz = timezone.get_current_timezone()
            new_start = timezone.make_aware(datetime.combine(booking_date, start_val), tz)
            new_end = timezone.make_aware(datetime.combine(booking_date, end_val), tz)

            try:
                reschedule_reservation_atomic(
                    reservation_id=reservation.id,
                    new_start=new_start,
                    new_end=new_end,
                    admin_user=request.user,
                    reason=reason
                )
                messages.success(
                    request,
                    f"Reservation {reservation.tracking_code} rescheduled successfully to {new_start:%b %d, %Y %H:%M}."
                )
                return redirect('admin_panel:schedule_calendar')
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
    else:
        # Prepopulate with current scheduled date/time
        form = AdminRescheduleForm(initial={
            'booking_date': reservation.start_time.date(),
            'start_time_input': reservation.start_time.time(),
            'end_time_input': reservation.end_time.time(),
        })

    change_history = reservation.reschedule_history.select_related('actor')

    return render(request, 'admin/calendar/reschedule_form.html', {
        'reservation': reservation,
        'form': form,
        'change_history': change_history
    })


# ==========================================
# A5. EVENT MONITORING AND OPERATIONS
# ==========================================
@admin_required
def event_operations_view(request):
    """
    Operations console: record check-in, completion, no-show, and print slips.
    """
    now = timezone.now()
    today_start = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()))
    today_end = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))

    active_operations = Reservation.objects.filter(
        status__in=['APPROVED', 'CHECKED_IN'],
        start_time__lte=today_end
    ).select_related('facility', 'user').order_by('start_time')

    recent_completed = Reservation.objects.filter(
        status__in=['COMPLETED', 'NO_SHOW']
    ).select_related('facility', 'user').order_by('-updated_at')[:10]

    return render(request, 'admin/operations/operations_list.html', {
        'active_operations': active_operations,
        'recent_completed': recent_completed,
        'now': now
    })


@admin_required
def check_in_view(request, pk):
    """
    Check-in an event. Permitted only for Approved bookings.
    """
    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        try:
            res, record = check_in_event(
                reservation_id=pk,
                admin_user=request.user,
                notes=notes
            )
            messages.success(request, f"Booking {res.tracking_code} checked in successfully.")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('admin_panel:event_operations')


@admin_required
def complete_event_view(request, pk):
    """
    Mark an event as COMPLETED. Requires prior check-in.
    """
    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        try:
            res, record = complete_event(
                reservation_id=pk,
                admin_user=request.user,
                notes=notes
            )
            messages.success(request, f"Event {res.tracking_code} marked as COMPLETED.")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('admin_panel:event_operations')


@admin_required
def no_show_view(request, pk):
    """
    Record No-Show. Allowed only after scheduled end time.
    """
    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        try:
            res, record = record_no_show(
                reservation_id=pk,
                admin_user=request.user,
                notes=notes
            )
            messages.warning(request, f"Reservation {res.tracking_code} marked as NO-SHOW.")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('admin_panel:event_operations')


@admin_required
def reservation_slip_view(request, pk):
    """
    Printable reservation slip and completion summary.
    Includes full event details, actor signatures, and verification timestamps.
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('facility', 'facility__category', 'user', 'decision_actor'),
        pk=pk
    )
    event_record = getattr(reservation, 'event_record', None)
    reschedule_history = reservation.reschedule_history.select_related('actor')

    return render(request, 'admin/operations/reservation_slip.html', {
        'reservation': reservation,
        'event_record': event_record,
        'reschedule_history': reschedule_history
    })


# ==========================================
# A6. CLOSURE PERIODS AND AVAILABILITY
# ==========================================
@admin_required
def closure_list_view(request):
    """
    List and manage facility maintenance/closure blocks.
    """
    closures = ClosureBlock.objects.select_related('facility', 'created_by').order_by('-start_time')

    if request.method == 'POST':
        form = ClosureBlockForm(request.POST)
        if form.is_valid():
            facility = form.cleaned_data['facility']
            c_date = form.cleaned_data['closure_date']
            s_time = form.cleaned_data['start_time_input']
            e_time = form.cleaned_data['end_time_input']
            reason = form.cleaned_data['reason']

            tz = timezone.get_current_timezone()
            start_dt = timezone.make_aware(datetime.combine(c_date, s_time), tz)
            end_dt = timezone.make_aware(datetime.combine(c_date, e_time), tz)

            try:
                create_closure_block(
                    facility=facility,
                    start_time=start_dt,
                    end_time=end_dt,
                    reason=reason,
                    admin_user=request.user
                )
                messages.success(request, f"Maintenance closure created for {facility.name}.")
                return redirect('admin_panel:closure_list')
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
    else:
        form = ClosureBlockForm()

    return render(request, 'admin/closures/closure_list.html', {
        'closures': closures,
        'form': form
    })


@admin_required
def closure_archive_view(request, pk):
    """
    Archive an unused or completed closure block with audit record.
    """
    closure = get_object_or_404(ClosureBlock, pk=pk)
    if request.method == 'POST':
        closure.is_active = False
        closure.save()
        messages.info(request, f"Closure block for {closure.facility.name} has been archived.")
        log_audit(
            actor=request.user,
            action_type='ARCHIVE_CLOSURE',
            reference_model='ClosureBlock',
            reference_id=closure.id,
            description=f"Archived closure for {closure.facility.name} ({closure.reason}).",
            ip_address=request.META.get('REMOTE_ADDR')
        )
    return redirect('admin_panel:closure_list')


# ==========================================
# A7. REPORTS & EXPORTS
# ==========================================
@admin_required
def reports_view(request):
    """
    Dynamic date-filtered reservation and utilization reports with ORM aggregations.
    Calculates booked hours, completed events, and utilization rates per facility.
    """
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')

    now = timezone.now()
    if date_from_str:
        try:
            d_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            d_from = (now - timedelta(days=30)).date()
    else:
        d_from = (now - timedelta(days=30)).date()

    if date_to_str:
        try:
            d_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            d_to = now.date()
    else:
        d_to = now.date()

    dt_start = timezone.make_aware(datetime.combine(d_from, datetime.min.time()))
    dt_end = timezone.make_aware(datetime.combine(d_to, datetime.max.time()))

    # Reservations in range
    reservations = Reservation.objects.filter(
        start_time__gte=dt_start,
        start_time__lte=dt_end
    ).select_related('facility', 'user')

    # Aggregations per facility
    facility_stats = []
    for fac in Facility.objects.all():
        fac_res = reservations.filter(facility=fac)
        total_requests = fac_res.count()
        approved_count = fac_res.filter(status='APPROVED').count()
        completed_count = fac_res.filter(status='COMPLETED').count()
        rejected_count = fac_res.filter(status='REJECTED').count()
        no_show_count = fac_res.filter(status='NO_SHOW').count()

        # Calculate booked hours for occupied slots
        occupied = fac_res.filter(status__in=['APPROVED', 'CHECKED_IN', 'COMPLETED', 'NO_SHOW'])
        booked_hours = sum(r.duration_hours for r in occupied)

        facility_stats.append({
            'facility': fac,
            'total_requests': total_requests,
            'approved_count': approved_count,
            'completed_count': completed_count,
            'rejected_count': rejected_count,
            'no_show_count': no_show_count,
            'booked_hours': round(booked_hours, 2),
        })

    total_bookings = sum(s['total_requests'] for s in facility_stats)
    total_completed = sum(s['completed_count'] for s in facility_stats)
    total_hours = sum(s['booked_hours'] for s in facility_stats)

    context = {
        'date_from': d_from.isoformat(),
        'date_to': d_to.isoformat(),
        'facility_stats': facility_stats,
        'total_bookings': total_bookings,
        'total_completed': total_completed,
        'total_hours': round(total_hours, 2),
    }
    return render(request, 'admin/reports/reports_dashboard.html', context)


@admin_required
def export_reports_csv(request):
    """
    CSV export endpoint for date-filtered facility utilization report.
    """
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')

    now = timezone.now()
    d_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else (now - timedelta(days=30)).date()
    d_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else now.date()

    dt_start = timezone.make_aware(datetime.combine(d_from, datetime.min.time()))
    dt_end = timezone.make_aware(datetime.combine(d_to, datetime.max.time()))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="facility_utilization_{d_from}_to_{d_to}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Facility Code', 'Facility Name', 'Category', 'Capacity',
        'Total Requests', 'Approved', 'Completed Events', 'Rejected', 'No Show', 'Total Booked Hours'
    ])

    reservations = Reservation.objects.filter(start_time__gte=dt_start, start_time__lte=dt_end)

    for fac in Facility.objects.select_related('category').all():
        fac_res = reservations.filter(facility=fac)
        total_reqs = fac_res.count()
        appr = fac_res.filter(status='APPROVED').count()
        comp = fac_res.filter(status='COMPLETED').count()
        rej = fac_res.filter(status='REJECTED').count()
        ns = fac_res.filter(status='NO_SHOW').count()
        hours = sum(r.duration_hours for r in fac_res.filter(status__in=['APPROVED', 'CHECKED_IN', 'COMPLETED', 'NO_SHOW']))

        writer.writerow([
            fac.code, fac.name, fac.category.name, fac.capacity,
            total_reqs, appr, comp, rej, ns, round(hours, 2)
        ])

    return response


# ==========================================
# A8. AUDIT HISTORY AND SYSTEM SETTINGS
# ==========================================
@admin_required
def audit_log_view(request):
    """
    Searchable, admin-only audit trail page.
    """
    query = request.GET.get('q', '').strip()
    action_type = request.GET.get('action', '').strip()

    logs = AuditLog.objects.select_related('actor').order_by('-timestamp')

    if query:
        logs = logs.filter(
            Q(description__icontains=query) |
            Q(reference_id__icontains=query) |
            Q(actor__username__icontains=query)
        )

    if action_type:
        logs = logs.filter(action_type=action_type)

    paginator = Paginator(logs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Distinct action types for filter dropdown
    distinct_actions = AuditLog.objects.values_list('action_type', flat=True).distinct()

    return render(request, 'admin/audit/audit_log.html', {
        'page_obj': page_obj,
        'query': query,
        'action_type': action_type,
        'distinct_actions': distinct_actions
    })


@admin_required
def system_settings_view(request):
    """
    Manage system limits: max event duration and advance booking window.
    """
    settings_obj = SystemSetting.get_settings()
    if request.method == 'POST':
        form = SystemSettingForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "System settings updated successfully.")
            log_audit(
                actor=request.user,
                action_type='UPDATE_SYSTEM_SETTINGS',
                reference_model='SystemSetting',
                reference_id=settings_obj.id,
                description=f"Updated settings: max duration={settings_obj.max_event_duration_hours}h, advance window={settings_obj.advance_booking_window_days}d.",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return redirect('admin_panel:system_settings')
    else:
        form = SystemSettingForm(instance=settings_obj)

    return render(request, 'admin/settings/system_settings.html', {'form': form})
