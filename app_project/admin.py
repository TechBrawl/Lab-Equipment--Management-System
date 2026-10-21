from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
from .models import InventoryAuditLog, InventoryItem, ServiceVendor, StaffUser, SystemSettings
from .models import StaffUser, Equipment, BorrowRequest, MaintenanceAlert

# 1. Custom Form for creating users via Admin Panel
class StaffUserCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Password")

    class Meta:
        model = StaffUser
        fields = ('email', 'role', 'is_staff', 'is_active')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

# 2. Custom Admin Layout Controller
class StaffUserAdmin(UserAdmin):
    add_form = StaffUserCreationForm
    form = UserChangeForm
    
    list_display = ('email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email',)
    ordering = ('email',)
    
    # 🔴 FIX: This tells Django these fields are read-only and prevents the FieldError
    readonly_fields = ('date_joined', 'last_login')
    
    # Layout when viewing/editing an existing staff member
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions & Roles', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Layout when creating a brand new staff member
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'role', 'password', 'is_staff', 'is_active'),
        }),
    )

# Register the corrected admin view
admin.site.register(StaffUser, StaffUserAdmin)



# ... Keep your existing StaffUserAdmin configuration exactly as it is ...

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('equipment_id', 'name', 'is_active', 'date_added')
    list_filter = ('is_active',)
    search_fields = ('equipment_id', 'name')

@admin.register(BorrowRequest)
class BorrowRequestAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'faculty_member', 'status', 'due_date')
    list_filter = ('status', 'request_date')
    search_fields = ('faculty_member', 'equipment__name', 'equipment__equipment_id')

@admin.register(MaintenanceAlert)
class MaintenanceAlertAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'is_active', 'date_reported')
    list_filter = ('is_active',)
    search_fields = ('equipment__equipment_id', 'description')
    
@admin.register(ServiceVendor)
class ServiceVendorAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'contact_person', 'phone', 'specialty')
    search_fields = ('company_name', 'specialty', 'contact_person')
    
@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('item_id', 'name', 'location', 'current_stock', 'maximum_capacity')
    search_fields = ('item_id', 'name')
    
@admin.register(InventoryAuditLog)
class InventoryAuditLogAdmin(admin.ModelAdmin):
    list_display = ('item', 'action_type', 'quantity_change', 'performed_by', 'timestamp')
    list_filter = ('action_type', 'timestamp')
    search_fields = ('item__name', 'item__item_id', 'notes')
    
@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('operational_mode', 'default_loan_duration', 'low_stock_threshold')