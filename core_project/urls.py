"""
URL configuration for core_project project.
"""
from django.contrib import admin
from django.urls import path
from app_project import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    
    # --- New Asset Management Routes ---
    path('add_asset/', views.add_asset, name='add_asset'),
    path('edit_equipment/<int:asset_id>/', views.edit_equipment, name='edit_equipment'),
    
    # --- Core Dashboard Routes ---
    path('equipment_registry/', views.equipment_registry, name='equipment_registry'),
    path('borrow_issue/', views.borrow_issue, name='borrow_issue'),
    path('borrow/approve/<int:request_id>/', views.approve_borrow, name='approve_borrow'),
    path('borrow/reject/<int:request_id>/', views.reject_borrow, name='reject_borrow'),
    path('borrow/notice/<int:request_id>/', views.send_overdue_notice, name='send_overdue_notice'),
    path('borrow/return/<int:request_id>/', views.log_return, name='log_return'),
    path('borrow/print-slip/', views.print_issue_slip, name='print_issue_slip'),
    path('maintenance/resolve/<int:alert_id>/', views.resolve_maintenance, name='resolve_maintenance'),
    path('maintenance/vendor/add/', views.add_vendor, name='add_vendor'),
    path('settings/staff/create/', views.create_staff, name='create_staff'),
    
    # --- Auxiliary Module Routes ---
    path('maintenance_desk/', views.maintenance_desk, name='maintenance_desk'),
    path('reports_analytics/', views.reports_analytics, name='reports_analytics'),
    path('inventory_tracking/', views.inventory_tracking, name='inventory_tracking'),
    path('settings_admin/', views.settings_admin, name='settings_admin'),
    
    
    # --- Authentication Routes ---
    path('admin_login/', views.admin_login_view, name='admin_login'),
    path('logout/', views.admin_logout, name='logout'),
]