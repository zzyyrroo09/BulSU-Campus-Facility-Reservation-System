from django.urls import path
from reservations.views import admin_views

app_name = 'admin_panel'

urlpatterns = [
    # A7. Dashboard
    path('dashboard/', admin_views.dashboard_view, name='dashboard'),

    # A1. Account Management
    path('users/', admin_views.user_list_view, name='user_list'),
    path('users/<int:user_id>/', admin_views.user_detail_view, name='user_detail'),
    path('users/<int:user_id>/toggle-status/', admin_views.user_toggle_status_view, name='user_toggle_status'),

    # A2. Facilities & Amenities
    path('facilities/', admin_views.facility_list_view, name='facility_list'),
    path('facilities/create/', admin_views.facility_create_view, name='facility_create'),
    path('facilities/<int:pk>/edit/', admin_views.facility_edit_view, name='facility_edit'),
    path('facilities/<int:pk>/toggle-active/', admin_views.facility_toggle_active_view, name='facility_toggle_active'),
    path('facilities/<int:pk>/amenities/add/', admin_views.facility_amenity_add_view, name='facility_amenity_add'),
    path('facilities/<int:pk>/amenities/<int:amenity_id>/remove/', admin_views.facility_amenity_remove_view, name='facility_amenity_remove'),
    path('categories/', admin_views.category_list_view, name='category_list'),
    path('amenities/', admin_views.amenity_list_view, name='amenity_list'),

    # A3. Review Queue
    path('queue/', admin_views.review_queue_view, name='review_queue'),
    path('queue/<int:pk>/approve/', admin_views.approve_reservation_view, name='approve_reservation'),
    path('queue/<int:pk>/reject/', admin_views.reject_reservation_view, name='reject_reservation'),

    # A4. Calendar & Rescheduling
    path('calendar/', admin_views.schedule_calendar_view, name='schedule_calendar'),
    path('reschedule/<int:pk>/', admin_views.reschedule_reservation_view, name='reschedule_reservation'),

    # A5. Event Operations & Slips
    path('operations/', admin_views.event_operations_view, name='event_operations'),
    path('operations/<int:pk>/check-in/', admin_views.check_in_view, name='check_in'),
    path('operations/<int:pk>/complete/', admin_views.complete_event_view, name='complete_event'),
    path('operations/<int:pk>/no-show/', admin_views.no_show_view, name='no_show'),
    path('operations/<int:pk>/slip/', admin_views.reservation_slip_view, name='reservation_slip'),

    # A6. Closures
    path('closures/', admin_views.closure_list_view, name='closure_list'),
    path('closures/<int:pk>/archive/', admin_views.closure_archive_view, name='closure_archive'),

    # A7. Reports
    path('reports/', admin_views.reports_view, name='reports'),
    path('reports/export-csv/', admin_views.export_reports_csv, name='export_reports_csv'),

    # A8. Audit Logs & System Settings
    path('audit/', admin_views.audit_log_view, name='audit_log'),
    path('settings/', admin_views.system_settings_view, name='system_settings'),
]
