from django.urls import path
from reservations.views import user_views

app_name = 'user_portal'

urlpatterns = [
    # U1. Dashboard & Profile
    path('dashboard/', user_views.dashboard_view, name='dashboard'),
    path('profile/', user_views.profile_view, name='profile'),

    # U2. Facilities & Availability
    path('facilities/', user_views.facility_catalog_view, name='facility_catalog'),
    path('facilities/<int:pk>/', user_views.facility_detail_view, name='facility_detail'),

    # U3. Request Submission
    path('reserve/', user_views.submit_reservation_view, name='reserve'),
    path('reserve/<int:facility_id>/', user_views.submit_reservation_view, name='reserve_facility'),

    # U4. Track & Cancel
    path('my-reservations/', user_views.my_reservations_view, name='my_reservations'),
    path('my-reservations/<int:pk>/', user_views.reservation_detail_view, name='reservation_detail'),
    path('my-reservations/<int:pk>/cancel/', user_views.cancel_reservation_view, name='cancel_reservation'),
]
