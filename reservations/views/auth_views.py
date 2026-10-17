from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from reservations.forms import UserRegistrationForm


def home_redirect_view(request):
    """
    Landing / root redirect.
    Directs authenticated users to their respective role dashboards.
    Unauthenticated users are directed to login.
    """
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile and profile.is_admin:
            return redirect('admin_panel:dashboard')
        return redirect('user_portal:dashboard')
    return redirect('login')


def login_redirect_view(request):
    """
    Role-based redirect after successful login.
    Admins -> /manage/dashboard/
    Basic Users -> /portal/dashboard/
    """
    if not request.user.is_authenticated:
        return redirect('login')

    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_admin:
        return redirect('admin_panel:dashboard')
    return redirect('user_portal:dashboard')


def login_view(request):
    """
    Shared authentication endpoint for both BASIC_USER and ADMIN.
    Enforces active-account verification.
    """
    if request.user.is_authenticated:
        return redirect('login_redirect')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            profile = getattr(user, 'profile', None)

            if profile and not profile.is_active_account:
                messages.error(
                    request,
                    "This account has been deactivated by the system administrator. Sign-in blocked."
                )
                return render(request, 'auth/login.html', {'form': form})

            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('login_redirect')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'auth/login.html', {'form': form})


def register_view(request):
    """
    Public registration view.
    STRICT COMPLIANCE: Hardcoded to create only BASIC_USER role.
    Admin self-promotion is architecturally blocked.
    """
    if request.user.is_authenticated:
        return redirect('login_redirect')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Account registered successfully! You may now log in.")
            return redirect('login')
        else:
            messages.error(request, "Please correct the registration errors below.")
    else:
        form = UserRegistrationForm()

    return render(request, 'auth/register.html', {'form': form})


def logout_view(request):
    """
    Shared logout view.
    """
    auth_logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')
