from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import StaffUser, Equipment, BorrowRequest, MaintenanceAlert, ServiceVendor, InventoryItem, InventoryAuditLog, SystemSettings
from django.db.models import Q 
from django.db.models import Sum
import csv
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum

@login_required(login_url='admin_login')
def home(request):
    total_equipment = Equipment.objects.filter(is_active=True).count()
    pending_requests = BorrowRequest.objects.filter(status='PENDING').count()
    overdue_returns = BorrowRequest.objects.filter(status='OVERDUE').count()
    active_alerts = MaintenanceAlert.objects.filter(is_active=True).count()

    priority_activities = BorrowRequest.objects.exclude(status='RETURNED').order_by('-request_date')[:5]
    all_equipment = Equipment.objects.all().order_by('name')

    context = {
        'total_equipment': total_equipment,
        'pending_requests': pending_requests,
        'overdue_returns': overdue_returns,
        'active_alerts': active_alerts,
        'priority_activities': priority_activities,
        'all_equipment': all_equipment,  
        'capacity_used_pct': 68, 
    }
    return render(request, 'home.html', context)

@login_required(login_url='admin_login')
def approve_borrow(request, request_id):
    borrow_ticket = get_object_or_404(BorrowRequest, id=request_id)
    borrow_ticket.status = 'APPROVED'
    borrow_ticket.processed_by = request.user
    borrow_ticket.save()
    messages.success(request, f"Request approved for {borrow_ticket.faculty_member}.")
    return redirect('home')

@login_required(login_url='admin_login')
def reject_borrow(request, request_id):
    borrow_ticket = get_object_or_404(BorrowRequest, id=request_id)
    borrow_ticket.delete() 
    messages.warning(request, "Borrow assignment reference successfully dropped.")
    return redirect('home')

@login_required(login_url='admin_login')
def send_overdue_notice(request, request_id):
    borrow_ticket = get_object_or_404(BorrowRequest, id=request_id)
    messages.info(request, f"Workstation reminder notification dispatched to {borrow_ticket.faculty_member}.")
    return redirect('home')

@login_required(login_url='admin_login')
def add_asset(request):
    if request.method == 'POST':
        equipment_id = request.POST.get('equipment_id').strip().upper()
        name = request.POST.get('name').strip()
        category = request.POST.get('category')
        lab_allocation = request.POST.get('lab_allocation')
        status_flag = request.POST.get('status_flag')
        is_active = request.POST.get('is_active') == 'on' 

        if Equipment.objects.filter(equipment_id=equipment_id).exists():
            messages.error(request, f"Configuration Fault: Resource registry with ID {equipment_id} already exists.")
            return render(request, 'add_asset.html')

        Equipment.objects.create(
            equipment_id=equipment_id,
            name=name,
            category=category,
            lab_allocation=lab_allocation,
            status_flag=status_flag,
            is_active=is_active
        )
        messages.success(request, f"Inventory Node '{name}' has been successfully provisioned to the registry.")
        return redirect('home')
        
    return render(request, 'add_asset.html')
@login_required(login_url='admin_login')
def edit_equipment(request, asset_id):
    asset = get_object_or_404(Equipment, id=asset_id)
    
    if request.method == 'POST':
        equipment_id = request.POST.get('equipment_id').strip().upper()
        name = request.POST.get('name').strip()
        
        # Block conflicting serials if renamed to an ID already claimed by another asset
        if Equipment.objects.filter(equipment_id=equipment_id).exclude(id=asset_id).exists():
            messages.error(request, f"Registry Collision: Identity code {equipment_id} is already in use.")
            # 🔴 FIX: Stay on the edit page if there is an error, rather than redirecting
            return render(request, 'edit_equipment.html', {'asset': asset})

        asset.equipment_id = equipment_id
        asset.name = name
        asset.category = request.POST.get('category')
        asset.lab_allocation = request.POST.get('lab_allocation')
        asset.status_flag = request.POST.get('status_flag')
        asset.is_active = request.POST.get('is_active') == 'on'
        asset.save()

        messages.success(request, f"Asset properties for node '{equipment_id}' updated successfully.")
        return redirect('equipment_registry') # 🔴 Tweaked to return you to the registry table after a successful edit
        
    # 🔴 THE MAIN FIX: Render the edit page and pass the asset data to it
    return render(request, 'edit_equipment.html', {'asset': asset})


@login_required(login_url='admin_login')
def equipment_registry(request):
    # 1. Get all equipment by default, sorted newest first
    equipment_list = Equipment.objects.all().order_by('-date_added')
    
    # 2. Capture filter parameters from the URL (GET request)
    search_query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    
    # 3. Apply Search Filter (checks both name and ID)
    if search_query:
        equipment_list = equipment_list.filter(
            Q(name__icontains=search_query) | 
            Q(equipment_id__icontains=search_query)
        )
    
    # 4. Apply Category Filter
    if category_filter:
        equipment_list = equipment_list.filter(category=category_filter)
        
    # 5. Apply Status Filter
    if status_filter:
        equipment_list = equipment_list.filter(status_flag=status_filter)
        
    context = {
        'equipment_list': equipment_list,
        'search_query': search_query,
        'category_filter': category_filter,
        'status_filter': status_filter,
        # Pass the model choices so the dropdowns can generate automatically
        'categories': Equipment.CATEGORY_CHOICES,
        'statuses': Equipment.STATUS_FLAG_CHOICES,
    }
    return render(request, 'equipment_registry.html', context)

@login_required(login_url='admin_login')
def borrow_issue(request):
    # --- Process the Instant Desk Handover Form ---
    if request.method == 'POST':
        equip_id = request.POST.get('equipment_id').strip().upper()
        # Clean out any '#' if the user typed it manually
        equip_id = equip_id.replace('#', '') 
        borrower_id = request.POST.get('borrower_id').strip()
        return_date = request.POST.get('return_date')

        try:
            # 1. Verify the equipment exists in the registry
            equipment = Equipment.objects.get(equipment_id=equip_id)
            
            # 2. Create an instantly 'ISSUED' ticket
            BorrowRequest.objects.create(
                equipment=equipment,
                faculty_member=borrower_id,
                status='ISSUED',
                processed_by=request.user,
                due_date=return_date if return_date else None
            )
            messages.success(request, f"Direct Issue Authorized: {equipment.name} handed over to {borrower_id}.")
            
        except Equipment.DoesNotExist:
            messages.error(request, f"Scan Failed: Equipment ID '{equip_id}' was not found in the registry.")
            
        return redirect('borrow_issue')

    # --- Fetch Data for the View (GET Request) ---
    pending_requests = BorrowRequest.objects.filter(status='PENDING').order_by('request_date')
    active_handovers = BorrowRequest.objects.filter(status__in=['APPROVED', 'ISSUED', 'OVERDUE']).order_by('-request_date')
    
    # Calculate stats for the bottom right performance card
    active_deployments_count = BorrowRequest.objects.filter(status__in=['ISSUED', 'OVERDUE']).count()
    overdue_risk_count = BorrowRequest.objects.filter(status='OVERDUE').count()

    context = {
        'pending_requests': pending_requests,
        'active_handovers': active_handovers,
        'active_deployments_count': active_deployments_count,
        'overdue_risk_count': overdue_risk_count,
    }
    return render(request, 'borrow_issue.html', context)


# --- Optional but Recommended Fixes for your existing Action buttons ---
@login_required(login_url='admin_login')
def approve_borrow(request, request_id):
    borrow_ticket = get_object_or_404(BorrowRequest, id=request_id)
    borrow_ticket.status = 'APPROVED'
    borrow_ticket.processed_by = request.user
    borrow_ticket.save()
    messages.success(request, f"Request approved for {borrow_ticket.faculty_member}.")
    # Redirects back to wherever the user clicked the button from
    return redirect(request.META.get('HTTP_REFERER', 'home')) 

@login_required(login_url='admin_login')
def reject_borrow(request, request_id):
    borrow_ticket = get_object_or_404(BorrowRequest, id=request_id)
    borrow_ticket.delete() 
    messages.warning(request, "Borrow assignment reference successfully dropped.")
    return redirect(request.META.get('HTTP_REFERER', 'home'))

@login_required(login_url='admin_login')
def log_return(request, request_id):
    # Fetch the specific borrow ticket
    borrow_ticket = get_object_or_404(BorrowRequest, id=request_id)
    
    if request.method == 'POST':
        # Update status to RETURNED and stamp the exact return time
        borrow_ticket.status = 'RETURNED'
        borrow_ticket.return_date = timezone.now()
        borrow_ticket.save()
        
        # Send a success message back to the UI
        messages.success(request, f"Return Logged: {borrow_ticket.equipment.name} received back from {borrow_ticket.faculty_member}.")
        return redirect('borrow_issue')
        
    # If it is a GET request, render the confirmation form page
    return render(request, 'log_return.html', {'ticket': borrow_ticket})

@login_required(login_url='admin_login')
def print_issue_slip(request):
    # Fetch all active handovers (Approved, Issued, or Overdue)
    active_handovers = BorrowRequest.objects.filter(
        status__in=['APPROVED', 'ISSUED', 'OVERDUE']
    ).order_by('faculty_member')
    
    context = {
        'active_handovers': active_handovers,
        'print_date': timezone.now(),
    }
    
    # Renders a minimal, print-friendly layout
    return render(request, 'print_slip.html', context)


@login_required(login_url='admin_login')
def maintenance_desk(request):
    # --- 1. Process the "Log Breakage Event" Form (POST Request) ---
    if request.method == 'POST':
        # Grab the submitted data and clean it (remove hashtags)
        equip_id = request.POST.get('equipment_id').strip().upper().replace('#', '')
        urgency = request.POST.get('urgency_category')
        notes = request.POST.get('failure_notes')

        try:
            # Find the equipment in the database
            equipment = Equipment.objects.get(equipment_id=equip_id)
            
            # Create the alert ticket
            MaintenanceAlert.objects.create(
                equipment=equipment,
                urgency_category=urgency,
                description=notes,
                status_flow='INSPECTION',
                is_active=True
            )
            
            # Auto-update the equipment's global status to 'Under Maintenance'
            equipment.status_flag = 'MAINTENANCE'
            equipment.save()
            
            messages.success(request, f"Breakage Event Logged: {equipment.name} moved to maintenance stream.")
        except Equipment.DoesNotExist:
            # If they typed a serial number that doesn't exist
            messages.error(request, f"Submission Failed: Equipment ID '{equip_id}' not found in registry.")
            
        return redirect('maintenance_desk')

    # --- 2. Fetch Data & Calculate Metrics (GET Request) ---
    active_streams = MaintenanceAlert.objects.filter(is_active=True).order_by('-date_reported')
    under_inspection = MaintenanceAlert.objects.filter(is_active=True, status_flow__in=['INSPECTION', 'DIAGNOSTICS']).count()
    sent_to_vendor = MaintenanceAlert.objects.filter(is_active=True, status_flow='VENDOR').count()
    
    current_month = timezone.now().month
    calibrated_this_month = MaintenanceAlert.objects.filter(is_active=False, status_flow='RESOLVED', date_resolved__month=current_month).count()
    
    total_cost_dict = MaintenanceAlert.objects.aggregate(Sum('maintenance_cost'))
    total_cost = total_cost_dict['maintenance_cost__sum'] or 0.00
    
    # Fetch all active vendors for the popup
    vendors = ServiceVendor.objects.all().order_by('company_name')

    context = {
        'active_streams': active_streams,
        'under_inspection': under_inspection,
        'sent_to_vendor': sent_to_vendor,
        'calibrated_this_month': calibrated_this_month,
        'total_cost': total_cost,
        'vendors': vendors, 
    }
    return render(request, 'maintenance_desk.html', context)


@login_required(login_url='admin_login')
def resolve_maintenance(request, alert_id):
    """Marks a maintenance ticket as complete and restores the equipment."""
    alert = get_object_or_404(MaintenanceAlert, id=alert_id)
    
    # Close ticket
    alert.is_active = False
    alert.status_flow = 'RESOLVED'
    alert.date_resolved = timezone.now()
    alert.save()

    # Restore equipment to operational status globally
    alert.equipment.status_flag = 'OPERATIONAL'
    alert.equipment.save()

    messages.success(request, f"Maintenance Complete: {alert.equipment.name} is now fully operational.")
    return redirect('maintenance_desk')

@login_required(login_url='admin_login')
def add_vendor(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name').strip()
        contact_person = request.POST.get('contact_person').strip()
        phone = request.POST.get('phone').strip()
        email = request.POST.get('email').strip()
        specialty = request.POST.get('specialty').strip()

        ServiceVendor.objects.create(
            company_name=company_name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            specialty=specialty
        )
        messages.success(request, f"Vendor Directory Updated: '{company_name}' is now registered.")
        
    return redirect('maintenance_desk')


@login_required(login_url='admin_login')
def reports_analytics(request):
    # --- Handle the Data Export Form Submission ---
    if request.method == 'POST':
        export_format = request.POST.get('output_format', 'pdf')
        target_metric = request.POST.get('target_metric')
        
        if export_format == 'csv':
            # Create the HttpResponse object with the appropriate CSV header
            response = HttpResponse(content_type='text/csv')
            filename = f'LabOS_Export_{target_metric}_{timezone.now().strftime("%Y%m%d")}.csv'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            writer = csv.writer(response)
            
            # Generate rows based on the selected dropdown context
            if target_metric == 'utilization':
                writer.writerow(['Equipment ID', 'Name', 'Category', 'Lab Allocation', 'Status'])
                for equip in Equipment.objects.all():
                    writer.writerow([
                        equip.equipment_id, 
                        equip.name, 
                        equip.get_category_display(), 
                        equip.get_lab_allocation_display(), 
                        equip.get_status_flag_display()
                    ])
            elif target_metric == 'overdue':
                writer.writerow(['Faculty / Borrower', 'Equipment Name', 'Serial ID', 'Expected Return', 'Status'])
                for req in BorrowRequest.objects.filter(status='OVERDUE'):
                    writer.writerow([
                        req.faculty_member, 
                        req.equipment.name, 
                        req.equipment.equipment_id, 
                        req.due_date, 
                        req.get_status_display()
                    ])
            elif target_metric == 'maintenance':
                writer.writerow(['Equipment', 'Vendor', 'Failure Notes', 'Cost (INR)', 'Resolved Date'])
                for alert in MaintenanceAlert.objects.filter(status_flow='RESOLVED'):
                    writer.writerow([
                        alert.equipment.name, 
                        alert.assigned_vendor, 
                        alert.description, 
                        alert.maintenance_cost, 
                        alert.date_resolved
                    ])
            else:
                writer.writerow(['No data scope selected or valid for this export.'])
                
            return response
            
        else:
            # Fallback for PDF selection (since PDF generation usually requires external libraries like ReportLab)
            messages.warning(request, "PDF compilation engine is currently under maintenance. Please select 'Raw Data CSV' format.")
            return redirect('reports_analytics')

    # --- Calculate Dynamic KPIs (GET Request) ---
    
    # 1. Utilization Rate
    total_equip = Equipment.objects.filter(is_active=True).count()
    active_deployments = BorrowRequest.objects.filter(status__in=['APPROVED', 'ISSUED', 'OVERDUE']).count()
    utilization_rate = round((active_deployments / total_equip * 100), 1) if total_equip > 0 else 0.0

    # 2. Overdue Return Frequency
    total_historical_requests = BorrowRequest.objects.count()
    total_overdue = BorrowRequest.objects.filter(status='OVERDUE').count()
    overdue_freq = round((total_overdue / total_historical_requests * 100), 1) if total_historical_requests > 0 else 0.0

    # 3. Total Calibrated Systems
    calibrated_systems = MaintenanceAlert.objects.filter(status_flow='RESOLVED').count()
    
    # Fallback to base equipment count if maintenance tickets haven't been utilized much yet
    if calibrated_systems == 0:
        calibrated_systems = Equipment.objects.filter(status_flag='OPERATIONAL').count()

    context = {
        'utilization_rate': utilization_rate,
        'overdue_freq': overdue_freq,
        'calibrated_systems': calibrated_systems,
    }
    return render(request, 'reports_analytics.html', context)

@login_required(login_url='admin_login')
def inventory_tracking(request):
    # --- Handle QR Scanner Form Submission ---
    if request.method == 'POST':
        messages.warning(request, "QR Scanner Module is currently under maintenance. Please use manual database entry via the Registry.")
        return redirect('inventory_tracking')

    # --- Fetch Data & Calculate Metrics (GET Request) ---
    inventory_items = InventoryItem.objects.all().order_by('name')
    
    total_units = sum(item.current_stock for item in inventory_items)
    total_capacity = sum(item.maximum_capacity for item in inventory_items)
    accounted_pct = int((total_units / total_capacity * 100)) if total_capacity > 0 else 100
    critical_items_count = sum(1 for item in inventory_items if item.stock_percentage() <= 20)

    # 🔴 NEW: Fetch the 50 most recent audit logs for the timeline
    audit_logs = InventoryAuditLog.objects.all().order_by('-timestamp')[:50]

    context = {
        'inventory_items': inventory_items,
        'total_units': total_units,
        'accounted_pct': accounted_pct,
        'critical_items_count': critical_items_count,
        'audit_logs': audit_logs, # 🔴 Add this to context
    }
    return render(request, 'inventory_tracking.html', context)


@login_required(login_url='admin_login')
def settings_admin(request):
    # 1. Load the single instance of our global settings
    settings_obj = SystemSettings.load()

    # 2. Handle POST request (Updating the Global Parameters)
    if request.method == 'POST':
        try:
            settings_obj.default_loan_duration = int(request.POST.get('default_loan_duration'))
            settings_obj.low_stock_threshold = int(request.POST.get('low_stock_threshold'))
            settings_obj.operational_mode = request.POST.get('operational_mode')
            settings_obj.save()
            messages.success(request, "System Global Parameters updated successfully.")
        except ValueError:
            messages.error(request, "Validation Error: Numeric fields require valid integers.")
        
        return redirect('settings_admin')

    # 3. Fetch Data for the GET request (Staff Table)
    # Exclude superusers from the basic view if you only want to show staff/assistants
    staff_members = StaffUser.objects.all().order_by('email')

    context = {
        'staff_members': staff_members,
        'settings': settings_obj,
    }
    return render(request, 'settings_admin.html', context)

@login_required(login_url='admin_login')
def create_staff(request):
    # Security check: Only allow existing ADMINs to create new staff accounts
    if request.user.role != 'ADMIN':
        messages.error(request, "Access Denied: Only System Admins can create new staff accounts.")
        return redirect('settings_admin')

    if request.method == 'POST':
        email = request.POST.get('email').strip().lower()
        role = request.POST.get('role')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # 1. Validation Checks
        if password != confirm_password:
            messages.error(request, "Validation Error: Passwords do not match.")
            return render(request, 'create_staff.html')

        if StaffUser.objects.filter(email=email).exists():
            messages.error(request, f"Conflict: An account with {email} already exists.")
            return render(request, 'create_staff.html')

        # 2. Determine Django Backend Access based on Role
        is_staff = (role == 'ADMIN')
        is_superuser = (role == 'ADMIN')

        # 3. Securely Create User (Uses your custom manager which hashes the password)
        StaffUser.objects.create_user(
            email=email,
            password=password,
            role=role,
            is_staff=is_staff,
            is_superuser=is_superuser
        )
        
        messages.success(request, f"Authorization Granted: Staff account for {email} created successfully.")
        return redirect('settings_admin')

    # GET Request: Render the form
    return render(request, 'create_staff.html')

def admin_login_view(request):
    if request.user.is_authenticated:
        if request.user.role == 'ADMIN':
            return redirect('/admin/')
        return redirect('/') 

    if request.method == 'POST':
        selected_role = request.POST.get('userRole')
        email = request.POST.get('email')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')

        user = authenticate(request, username=email, password=password)

        if user is not None:
            if user.role != selected_role:
                messages.error(
                    request, 
                    f"Access Denied: Account lacks {selected_role.replace('_', ' ').title()} access keys."
                )
                return render(request, 'admin_login.html')

            login(request, user)

            if not remember_me:
                request.session.set_expiry(0) 
            else:
                request.session.set_expiry(1209600) 

            if user.role == 'ADMIN':
                return redirect('/admin/')
            else:
                return redirect('/') 

        else:
            messages.error(request, "Invalid credentials. Please verify your staff email and password.")

    return render(request, 'admin_login.html')

def admin_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('admin_login')