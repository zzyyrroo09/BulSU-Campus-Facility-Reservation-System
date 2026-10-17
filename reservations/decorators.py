from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    """
    Ensures that the current user is authenticated, has an active account,
    and holds the 'ADMIN' role. Non-admins are strictly blocked.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in with administrator credentials.")
            return redirect('login')

        if not hasattr(request.user, 'profile'):
            messages.error(request, "User profile not found. Please contact support.")
            return redirect('login')

        if not request.user.profile.is_active_account:
            messages.error(request, "Your administrator account has been deactivated.")
            return redirect('login')

        if not request.user.profile.is_admin:
            messages.error(request, "Access denied. Administrator privileges required.")
            return redirect('user_portal:dashboard')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def user_required(view_func):
    """
    Ensures that the current user is authenticated, has an active account,
    and holds the 'BASIC_USER' role.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please log in to access the user portal.")
            return redirect('login')

        if not hasattr(request.user, 'profile'):
            messages.error(request, "User profile not found. Please contact support.")
            return redirect('login')

        if not request.user.profile.is_active_account:
            messages.error(request, "Your account has been deactivated. Transactions are blocked.")
            return redirect('login')

        if request.user.profile.is_admin:
            # If an admin lands in portal, redirect them to admin management
            return redirect('admin_panel:dashboard')

        return view_func(request, *args, **kwargs)

    return _wrapped_view
