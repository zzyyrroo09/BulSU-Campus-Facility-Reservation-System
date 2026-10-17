from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q

from reservations.models import Facility, FacilityCategory, Reservation, ClosureBlock
from reservations.forms import UserProfileForm, ReservationRequestForm
from reservations.decorators import user_required
from reservations.services import cancel_reservation


@user_required
def dashboard_view(request):
    """
    User portal homepage: live cards for user's personal requests, upcoming bookings,
    and shortcut to facility catalog.
    """
    now = timezone.now()
    my_reservations = Reservation.objects.filter(user=request.user)

    pending_count = my_reservations.filter(status='PENDING').count()
    upcoming_approved = my_reservations.filter(status='APPROVED', start_time__gte=now).count()
    completed_count = my_reservations.filter(status='COMPLETED').count()

    recent_bookings = my_reservations.select_related('facility').order_by('-created_at')[:5]

    return render(request, 'user/dashboard.html', {
        'pending_count': pending_count,
        'upcoming_approved': upcoming_approved,
        'completed_count': completed_count,
        'recent_bookings': recent_bookings,
    })


@user_required
def profile_view(request):
    """
    U1: View and update personal profile details.
    Role and activation status are strictly uneditable by the user.
    """
    profile = request.user.profile
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile details have been updated successfully.")
            return redirect('user_portal:profile')
    else:
        form = UserProfileForm(instance=profile, user=request.user)

    return render(request, 'user/profile.html', {'form': form, 'profile': profile})


@user_required
def facility_catalog_view(request):
    """
    U2: Browse active facilities by category and capacity, inspect amenities and schedules.
    """
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')
    min_capacity = request.GET.get('min_capacity')

    facilities = Facility.objects.filter(is_active=True).select_related('category').prefetch_related(
        'facility_amenities__amenity'
    )

    if query:
        facilities = facilities.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(location__icontains=query) |
            Q(description__icontains=query)
        )

    if category_id:
        facilities = facilities.filter(category_id=category_id)

    if min_capacity:
        try:
            facilities = facilities.filter(capacity__gte=int(min_capacity))
        except ValueError:
            pass

    categories = FacilityCategory.objects.filter(is_active=True)

    return render(request, 'user/facilities/facility_catalog.html', {
        'facilities': facilities,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'min_capacity': min_capacity
    })


@user_required
def facility_detail_view(request, pk):
    """
    U2: View facility specs, amenities, and available time slots.
    PRIVACY REQUIREMENT: Show unavailable slots without revealing other users,
    event details, or internal notes.
    """
    facility = get_object_or_404(
        Facility.objects.prefetch_related('facility_amenities__amenity'),
        pk=pk, is_active=True
    )

    date_str = request.GET.get('date')
    if date_str:
        try:
            schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            schedule_date = timezone.now().date()
    else:
        schedule_date = timezone.now().date()

    day_start = timezone.make_aware(datetime.combine(schedule_date, datetime.min.time()))
    day_end = timezone.make_aware(datetime.combine(schedule_date, datetime.max.time()))

    # Anonymized busy blocks
    booked_slots = Reservation.objects.filter(
        facility=facility,
        status__in=['APPROVED', 'CHECKED_IN'],
        start_time__gte=day_start,
        start_time__lte=day_end
    ).order_by('start_time')

    closure_slots = ClosureBlock.objects.filter(
        facility=facility,
        is_active=True,
        start_time__gte=day_start,
        start_time__lte=day_end
    ).order_by('start_time')

    # Build sanitized occupied list (No names, no event titles, no private details)
    sanitized_busy_blocks = []
    for b in booked_slots:
        sanitized_busy_blocks.append({
            'start_time': b.start_time,
            'end_time': b.end_time,
            'label': 'Occupied / Reserved Slot',
            'type': 'booking'
        })
    for c in closure_slots:
        sanitized_busy_blocks.append({
            'start_time': c.start_time,
            'end_time': c.end_time,
            'label': 'Facility Maintenance / Closed',
            'type': 'closure'
        })

    sanitized_busy_blocks.sort(key=lambda x: x['start_time'])

    return render(request, 'user/facilities/facility_detail.html', {
        'facility': facility,
        'schedule_date': schedule_date,
        'busy_blocks': sanitized_busy_blocks,
        'next_day': (schedule_date + timedelta(days=1)).isoformat(),
        'prev_day': (schedule_date - timedelta(days=1)).isoformat(),
    })


@user_required
def submit_reservation_view(request, facility_id=None):
    """
    U3: Submit a reservation request.
    Validates capacity, operating hours, closure periods, and booking limits.
    Submission creates PENDING status and does NOT reserve or approve the time slot.
    """
    initial_data = {}
    if facility_id:
        facility = get_object_or_404(Facility, pk=facility_id, is_active=True)
        initial_data['facility'] = facility

    if request.method == 'POST':
        form = ReservationRequestForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.user = request.user
            reservation.start_time = form.cleaned_data['computed_start_time']
            reservation.end_time = form.cleaned_data['computed_end_time']
            reservation.status = 'PENDING'
            reservation.save()

            messages.success(
                request,
                f"Reservation request for '{reservation.title}' submitted successfully! "
                f"Your tracking code is: {reservation.tracking_code}. "
                "An administrator will review your request shortly."
            )
            return redirect('user_portal:reservation_detail', pk=reservation.pk)
    else:
        form = ReservationRequestForm(initial=initial_data)

    return render(request, 'user/reservations/reservation_form.html', {'form': form})


@user_required
def my_reservations_view(request):
    """
    U4: View only own booking details and status.
    """
    status_filter = request.GET.get('status', '').strip()

    reservations = Reservation.objects.filter(
        user=request.user
    ).select_related('facility').order_by('-start_time')

    if status_filter:
        reservations = reservations.filter(status=status_filter)

    paginator = Paginator(reservations, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'user/reservations/my_reservations.html', {
        'page_obj': page_obj,
        'status_filter': status_filter
    })


@user_required
def reservation_detail_view(request, pk):
    """
    U4: Detailed status tracking for own reservation.
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('facility', 'facility__category', 'decision_actor'),
        pk=pk, user=request.user
    )
    reschedule_history = reservation.reschedule_history.select_related('actor')

    return render(request, 'user/reservations/reservation_detail.html', {
        'reservation': reservation,
        'reschedule_history': reschedule_history
    })


@user_required
def cancel_reservation_view(request, pk):
    """
    U4: Cancel own Pending or Approved bookings strictly before their start time.
    """
    reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        try:
            cancel_reservation(
                reservation_id=reservation.id,
                user=request.user,
                reason=reason or "Cancelled by user"
            )
            messages.info(request, f"Your reservation ({reservation.tracking_code}) has been cancelled.")
            return redirect('user_portal:my_reservations')
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return render(request, 'user/reservations/cancel_confirm.html', {'reservation': reservation})
