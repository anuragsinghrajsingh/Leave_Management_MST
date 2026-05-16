from django.urls import path, include
from . import views
from django.contrib import admin

urlpatterns = [
    # path('', views.login_view, name='login'),
    
    # path('admin/', admin.site.urls),
    path('', views.app_loading, name='app_loading'),
    path('portal/', views.role_select, name='role_select'),
    
    path('admin-login/', views.admin_login_loading, name='admin_login'),
    path('admin-login/form/', views.admin_login, name='admin_login_form'),
    path('admin-login/dashboard-loading/', views.admin_dashboard_loading_page, name='admin_dashboard_loading_page'),
    path('admin-logout/loading/', views.admin_logout_loading_page, name='admin_logout_loading_page'),
    path('admin-login/workspace/', views.admin_workspace_loading, name='admin_workspace_loading'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('logout/loading/', views.logout_loading, name='logout_loading'),

    # Custom Logout only for the Admin we have bypassed the traditional logout and made custom admin logout to redirect to admin login page
    path("admin-logout/", views.logout_view, name="admin_logout_custom"), 

    path('hr-login/', views.hr_login_loading, name='hr_login'),
    path('hr-login/form/', views.hr_login, name='hr_login_form'),
    path('hr-login/dashboard-loading/', views.hr_dashboard_loading_page, name='hr_dashboard_loading_page'),
    path('hr-logout/loading/', views.hr_logout_loading_page, name='hr_logout_loading_page'),
    path('hr-login/workspace/', views.hr_workspace_loading, name='hr_workspace_loading'),
    path('hr-dashboard/', views.hr_dashboard, name='hr_dashboard'),
    path('manage-all/', views.manage_all, name='manage_all'),
    path('api/manage-all/employee/<int:user_id>/', views.manage_all_employee_detail, name='manage_all_employee_detail'),
    path('api/hr-notifications/', views.hr_notifications, name='hr_notifications'),
    path('api/employee-notifications/', views.employee_notifications, name='employee_notifications'),
    path('api/notifications/read/', views.notifications_mark_read, name='notifications_mark_read'),
    path('api/notifications/seen/', views.notifications_mark_seen, name='notifications_mark_seen'),
    path('api/communications/', views.communications_feed, name='communications_feed'),
    path('api/communications/send/', views.communications_send, name='communications_send'),
    path('api/communications/read/', views.communications_mark_read, name='communications_mark_read'),
    path('api/communications/seen/', views.communications_mark_seen, name='communications_mark_seen'),
    path('employees/', views.employee_details, name='employee_details'),
    path('employees/delete/<int:user_id>/', views.delete_employee, name='delete_employee'),
    path('employees/archive/<int:user_id>/', views.download_employee_archive, name='download_employee_archive'),
    path('employees/update/<int:user_id>/', views.update_employee_contact_field, name='update_employee_contact_field'),
    path('reports/', views.reports, name='reports'),
    path('approve-leave/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('reject-leave/<int:leave_id>/', views.reject_leave, name='reject_leave'),


    path("profile/", views.profile_view, name="profile"),
    path("edit-employee/<int:user_id>/", views.edit_employee_profile, name="edit_employee_profile"),



    path('employee-login/', views.employee_login_loading, name='employee_login'),
    path('employee-login/form/', views.employee_login, name='employee_login_form'),
    path('employee-login/dashboard-loading/', views.employee_dashboard_loading_page, name='employee_dashboard_loading_page'),
    path('employee-logout/loading/', views.employee_logout_loading_page, name='employee_logout_loading_page'),
    path('employee-login/workspace/', views.employee_workspace_loading, name='employee_workspace_loading'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('apply_leave/', views.apply_leave, name='apply_leave'),
    path('my_leave/', views.my_leave, name='my_leave'),
    # path("leave-calendar/", views.leave_calendar, name="leave_calendar"),
    path("leave-calendar-data/", views.leave_calendar_data, name="leave_calendar_data"),
    
    path('delete-leave/<int:leave_id>/', views.delete_leave, name='delete_leave'),
    path('edit-leave/<int:leave_id>/', views.edit_leave, name='edit_leave'),
    # path("apply-leave-filters/", views.apply_leave_filters, name="apply_leave_filters"),
    
    path('delete-leave/<int:leave_id>/', views.delete_leave, name='delete_leave'),
    path('edit-leave/<int:leave_id>/', views.edit_leave, name='edit_leave'),
    # path("apply-leave-filters/", views.apply_leave_filters, name="apply_leave_filters"),
    # path("remove-leave-filter/", views.remove_leave_filter, name="remove_leave_filter"),
    path("apply-status-filter/<str:status>/", views.apply_status_filter, name="apply_status_filter"),
    path("clear-status-filter/<str:status>/", views.clear_status_filter, name="clear_status_filter"),
    path("clear-status-filter-field/<str:status>/<str:field>/", views.clear_status_filter_field, name="clear_status_filter_field"),
    
    
    path('api/get-next-id/<str:role>/', views.get_next_id_api, name='get_next_id_api'),
    path('logout/', views.logout_view, name='logout'),
]
