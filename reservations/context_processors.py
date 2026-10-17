from .models import SystemSetting, Reservation


def system_context(request):
    """
    Context processor providing dynamic system parameters and notifications across templates.
    """
    context = {
        'system_setting': SystemSetting.get_settings(),
    }

    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        context['user_profile'] = profile

        if profile and profile.is_admin:
            context['pending_queue_count'] = Reservation.objects.filter(status='PENDING').count()

    return context
