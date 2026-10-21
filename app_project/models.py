from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.conf import settings

class StaffUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Staff members must have an institutional email address.')
        email = self.normalize_email(email)
        
        extra_fields.setdefault('role', 'ASSISTANT')
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class StaffUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('ASSISTANT', 'Lab Assistant'),
        ('ADMIN', 'System Admin'),
    ]

    email = models.EmailField(unique=True, max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ASSISTANT')
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = StaffUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
    

class Equipment(models.Model):
    """
    Represents physical lab equipment available in the registry.
    """
    CATEGORY_CHOICES = [
        ('ELECTRONICS', 'Electronics & Electrical'),
        ('IT_COMPUTERS', 'IT & Computers'),
        ('MECHANICAL', 'Mechanical Tools'),
        ('CHEMISTRY', 'Chemistry & Glassware'),
        ('GENERAL', 'General Accessories'),
    ]
    
    ALLOCATION_CHOICES = [
        ('MAIN_LAB', 'Main Laboratory'),
        ('PHYSICS_LAB', 'Physics Lab'),
        ('CHEM_LAB', 'Chemistry Lab'),
        ('COMPUTER_LAB', 'Computer Lab'),
        ('STORAGE', 'Storage Facility'),
    ]
    
    STATUS_FLAG_CHOICES = [
        ('OPERATIONAL', 'Operational'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('DECOMMISSIONED', 'Decommissioned'),
    ]

    equipment_id = models.CharField(max_length=50, unique=True, help_text="e.g., EQ-OSC-09")
    name = models.CharField(max_length=200, help_text="e.g., Digital Oscilloscope 25MHz")
    
    # New Fields Added
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='GENERAL')
    lab_allocation = models.CharField(max_length=50, choices=ALLOCATION_CHOICES, default='MAIN_LAB')
    status_flag = models.CharField(max_length=50, choices=STATUS_FLAG_CHOICES, default='OPERATIONAL')
    
    date_added = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Equipment"

    def __str__(self):
        return f"{self.name} ({self.equipment_id})"


class BorrowRequest(models.Model):
    """
    Tracks who is borrowing what, and the current status of the transaction.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved / Awaiting'),
        ('ISSUED', 'Issued'),
        ('OVERDUE', 'Overdue'),
        ('RETURNED', 'Returned'),
    ]

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='borrow_history')
    faculty_member = models.CharField(max_length=150, help_text="e.g., Dr. Arvinder Singh") 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_requests'
    )
    
    request_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField(null=True, blank=True)
    return_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.equipment.name} - {self.faculty_member} ({self.get_status_display()})"

class MaintenanceAlert(models.Model):
    """
    Tracks active alerts and maintenance desk tickets.
    """
    URGENCY_CHOICES = [
        ('ROUTINE', 'Routine Recalibration'),
        ('MINOR', 'Minor Component Issue'),
        ('CRITICAL', 'Critical Structural Failure'),
    ]

    STATUS_CHOICES = [
        ('INSPECTION', 'Under Inspection'),
        ('DIAGNOSTICS', 'Diagnostics'),
        ('VENDOR', 'Out at Repair'),
        ('RESOLVED', 'Resolved / Calibrated'),
    ]

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='alerts')
    description = models.TextField(help_text="Failure Structural Notes")
    
    # New tracking fields
    urgency_category = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='ROUTINE')
    assigned_vendor = models.CharField(max_length=100, default='Internal Tech Staff', blank=True)
    status_flow = models.CharField(max_length=20, choices=STATUS_CHOICES, default='INSPECTION')
    maintenance_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    is_active = models.BooleanField(default=True, help_text="Is this alert currently active?")
    date_reported = models.DateTimeField(auto_now_add=True)
    date_resolved = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Alert for {self.equipment.equipment_id} ({self.get_status_flow_display()})"
    
class ServiceVendor(models.Model):
    """
    Directory of external repair and calibration contractors.
    """
    company_name = models.CharField(max_length=150, help_text="e.g., Matrix Labs Corp")
    contact_person = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    specialty = models.CharField(max_length=200, help_text="e.g., Optics, IT Hardware, Calibration")
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name
    
class InventoryItem(models.Model):
    """
    Tracks bulk consumable items and modular components.
    """
    item_id = models.CharField(max_length=50, unique=True, help_text="e.g., #INV-JW-40")
    name = models.CharField(max_length=200, help_text="e.g., Jumper Wires (M-to-M Packs)")
    location = models.CharField(max_length=150, help_text="e.g., CSE Core Lab - Cabinet 1")
    
    current_stock = models.IntegerField(default=0)
    maximum_capacity = models.IntegerField(default=100)
    last_audited = models.DateTimeField(auto_now=True)

    def stock_percentage(self):
        if self.maximum_capacity > 0:
            return int((self.current_stock / self.maximum_capacity) * 100)
        return 0

    def stock_status(self):
        pct = self.stock_percentage()
        if pct <= 20:
            return 'Critical Low'
        elif pct <= 50:
            return 'Reorder Soon'
        return 'Optimal'

    def __str__(self):
        return f"{self.name} ({self.current_stock}/{self.maximum_capacity})"
    
class InventoryAuditLog(models.Model):
    """
    Records a history timeline of stock adjustments for bulk inventory items.
    """
    ACTION_CHOICES = [
        ('RESTOCK', 'Restock Addition (+)'),
        ('CONSUME', 'Stock Consumed (-)'),
        ('AUDIT', 'Manual Verification / Correction'),
    ]

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='audit_logs')
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity_change = models.IntegerField(help_text="Use negative numbers for consumption")
    
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True, help_text="e.g., 'Restocked for Spring Semester'")

    def __str__(self):
        return f"{self.item.item_id} - {self.get_action_type_display()} ({self.quantity_change})"
    
class SystemSettings(models.Model):
    """
    Singleton model to store global system parameters and configurations.
    """
    MODE_CHOICES = [
        ('ACTIVE', 'Active Terminal Flow (Standard)'),
        ('MAINTENANCE', 'System Maintenance Mode'),
        ('RESTRICTED', 'Restricted Access Mode'),
    ]
    
    default_loan_duration = models.IntegerField(default=7, help_text="Default loan duration in days")
    low_stock_threshold = models.IntegerField(default=5, help_text="Threshold for critical low stock warnings")
    operational_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='ACTIVE')

    class Meta:
        verbose_name_plural = "System Settings"

    def save(self, *args, **kwargs):
        self.pk = 1 # Forces this model to only ever have one database row
        super(SystemSettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        # Fetches the single row, or creates it if it doesn't exist yet
        obj, created = cls.objects.get_or_create(pk=1)
        return obj