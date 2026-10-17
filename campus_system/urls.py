"""
URL configuration for Campus Facility Reservation and Event Scheduling System.
STRICT COMPLIANCE: Built-in Django admin (admin.site.urls) is strictly prohibited.
"""

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from reservations.views import auth_views

urlpatterns = [
    # Root and Authentication
    path('', auth_views.home_redirect_view, name='home'),
    path('login/', auth_views.login_view, name='login'),
    path('register/', auth_views.register_view, name='register'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('login-redirect/', auth_views.login_redirect_view, name='login_redirect'),
    
    # Custom 100% Group-Built Admin Interface (75% development workload)
    path('manage/', include('reservations.urls_admin', namespace='admin_panel')),
    
    # Custom Basic User Portal (25% development workload)
    path('portal/', include('reservations.urls_user', namespace='user_portal')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
