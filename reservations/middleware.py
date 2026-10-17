from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect


class AccountActiveCheckMiddleware:
    """
    Session-level active check middleware.
    Blocks deactivated users from submitting any transactions or accessing protected routes
    through an existing session by actively invalidating the session and logging them out.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Check user.is_active or profile.is_active_account
            profile = getattr(request.user, 'profile', None)
            if profile and not profile.is_active_account:
                logout(request)
                messages.error(
                    request,
                    "Your account has been deactivated by the administrator. Active session terminated."
                )
                return redirect('login')

        response = self.get_response(request)
        return response
