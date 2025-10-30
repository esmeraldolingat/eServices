# eservices_app/admin/routes.py

# --- Standard Flask & SQLAlchemy Imports ---
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, jsonify, Response) # Added Response for export
from flask_login import login_required, current_user
from sqlalchemy import func, case, extract, or_, text
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
import io # For export
import csv # For export
import json # For _get_services_for_department

# --- Imports from our App Package ---
from .. import db, limiter # Import db and limiter
from ..models import (User, Department, Service, School, Ticket, Attachment,
                      CannedResponse, AuthorizedEmail, PersonalCannedResponse,
                      Response as TicketResponse) # Import all needed models
from ..forms import (EditUserForm, AddAuthorizedEmailForm, BulkUploadForm,
                   DepartmentForm, ServiceForm, CannedResponseForm,
                   PersonalCannedResponseForm) # Import necessary forms
from ..decorators import admin_required, staff_or_admin_required # Import decorators

# --- Create Blueprint ---
admin_bp = Blueprint('admin', __name__, template_folder='templates', url_prefix='/admin')

# === STAFF/ADMIN DASHBOARD ===

@admin_bp.route('/staff-dashboard')
@login_required
def staff_dashboard():
    # --- Check Role ---
    if current_user.role not in ['Admin', 'Staff']:
        flash('Access denied.', 'danger')
        current_app.logger.warning(f"Unauthorized access to staff dashboard by user {current_user.email}")
        return redirect(url_for('main.home'))

    # --- Request Arguments ---
    page_active = request.args.get('page_active', 1, type=int)
    page_resolved = request.args.get('page_resolved', 1, type=int)
    page_school = request.args.get('page_school', 1, type=int) # <-- IDINAGDAG ITO
    search_query = request.args.get('search', '').strip()
    default_view = 'all_managed' if current_user.role == 'Staff' else 'all_system'
    filter_view = request.args.get('filter_view', default_view)
    selected_year = request.args.get('year', datetime.utcnow().year, type=int)
    selected_quarter = request.args.get('quarter', 0, type=int)

    # --- Year/Quarter Setup ---
    available_years_query = db.session.query(extract('year', Ticket.date_posted)).distinct().order_by(extract('year', Ticket.date_posted).desc())
    available_years = [y[0] for y in available_years_query.all()]
    current_year = datetime.utcnow().year
    if not available_years: available_years.append(current_year)
    elif selected_year not in available_years: selected_year = available_years[0]
    quarters = {
        1: (datetime(selected_year, 1, 1, tzinfo=timezone.utc), datetime(selected_year, 3, 31, 23, 59, 59, tzinfo=timezone.utc)),
        2: (datetime(selected_year, 4, 1, tzinfo=timezone.utc), datetime(selected_year, 6, 30, 23, 59, 59, tzinfo=timezone.utc)),
        3: (datetime(selected_year, 7, 1, tzinfo=timezone.utc), datetime(selected_year, 9, 30, 23, 59, 59, tzinfo=timezone.utc)),
        4: (datetime(selected_year, 10, 1, tzinfo=timezone.utc), datetime(selected_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
    }

    # --- Base Ticket Query & Filtering ---
    ticket_base_query = Ticket.query.options(db.joinedload(Ticket.school), db.joinedload(Ticket.service_type))
    managed_service_ids = None
    title = ""

    if current_user.role == 'Staff':
        managed_service_ids = [service.id for service in current_user.managed_services]
        if not managed_service_ids:
            flash("You are not assigned to any services. Contact admin.", "warning")
            current_app.logger.warning(f"Staff user {current_user.email} has no services.")
            # Render empty dashboard gracefully
            empty_paginate = db.paginate(db.select(Ticket).where(db.false()), page=1, per_page=current_app.config['TICKETS_PER_PAGE'], error_out=False)
            return render_template('staff_dashboard.html', 
                                 active_tickets=empty_paginate, resolved_tickets=empty_paginate, 
                                 dashboard_summary={}, school_summary={}, 
                                 paginated_schools=empty_paginate, # <-- IDINAGDAG ITO
                                 title="My Managed Tickets", available_years=available_years, 
                                 selected_year=selected_year, selected_quarter=selected_quarter, 
                                 search_query=search_query, filter_view=filter_view)

        ticket_base_query = ticket_base_query.filter(Ticket.service_id.in_(managed_service_ids))
        if filter_view == 'my_assigned':
            ticket_base_query = ticket_base_query.filter(Ticket.assigned_staff_id == current_user.id)
            title = "My Assigned Tickets"
        else:
            title = "My Managed Services Tickets"
            filter_view = 'all_managed'
    else: # Admin
        if filter_view == 'my_assigned':
            ticket_base_query = ticket_base_query.filter(Ticket.assigned_staff_id == current_user.id)
            title = "My Assigned Tickets"
        else:
            title = "All System Tickets"
            filter_view = 'all_system'

    # --- Apply Search or Date Filters ---
    if search_query:
        search_term = f"%{search_query}%"
        ticket_base_query = ticket_base_query.join(School, Ticket.school_id == School.id, isouter=True).filter(
            or_(Ticket.ticket_number.ilike(search_term), Ticket.requester_name.ilike(search_term), School.name.ilike(search_term)))
    else:
        ticket_base_query = ticket_base_query.filter(extract('year', Ticket.date_posted) == selected_year)
        if selected_quarter in quarters:
            start_date, end_date = quarters[selected_quarter]
            ticket_base_query = ticket_base_query.filter(Ticket.date_posted.between(start_date, end_date))

    # --- Paginate Tickets ---
    status_order = case((Ticket.status == 'Open', 1), (Ticket.status == 'In Progress', 2), else_=3)
    active_tickets = db.paginate(ticket_base_query.filter(Ticket.status.in_(['Open', 'In Progress'])).order_by(status_order, Ticket.date_posted.desc()), page=page_active, per_page=current_app.config['TICKETS_PER_PAGE'], error_out=False)
    resolved_tickets = db.paginate(ticket_base_query.filter(Ticket.status == 'Resolved').order_by(Ticket.date_posted.desc()), page=page_resolved, per_page=current_app.config['TICKETS_PER_PAGE'], error_out=False)

    # --- Generate Summaries (Only if not searching) ---
    dashboard_summary = {}
    school_summary = {}
    
    # --- SIMULA NG PAGBABAGO SA SCHOOL SUMMARY ---
    # Gawing 'empty_paginate' muna para sigurado
    paginated_schools = db.paginate(db.select(School).where(db.false()), page=1, per_page=10, error_out=False)

    if not search_query:
        # === Department Summary ===
        dept_summary_query = db.session.query(
            Department.name.label('dept_name'),
            Service.name.label('service_name'),
            Service.id.label('service_id'),
            func.count(Ticket.id).label('total'),
            func.sum(case((Ticket.status == 'Resolved', 1), else_=0)).label('resolved_count')
        ).select_from(Ticket).join(Service, Ticket.service_id == Service.id).join(Department, Service.department_id == Department.id)

        # Apply common filters
        dept_summary_query = dept_summary_query.filter(extract('year', Ticket.date_posted) == selected_year)
        if selected_quarter in quarters:
            start_date, end_date = quarters[selected_quarter]
            dept_summary_query = dept_summary_query.filter(Ticket.date_posted.between(start_date, end_date))
        if managed_service_ids is not None:
             dept_summary_query = dept_summary_query.filter(Service.id.in_(managed_service_ids))
        if filter_view == 'my_assigned':
            dept_summary_query = dept_summary_query.filter(Ticket.assigned_staff_id == current_user.id)
        dept_summary_data = dept_summary_query.group_by(Department.name, Service.name, Service.id).all()

        # Process Department Summary Data
        if current_user.role == 'Admin':
            all_departments = Department.query.options(db.joinedload(Department.services)).order_by(Department.name).all()
        else: # Staff
            all_departments = Department.query.join(Service).filter(Service.id.in_(managed_service_ids)).options(db.joinedload(Department.services.and_(Service.id.in_(managed_service_ids)))).order_by(Department.name).distinct().all()
        color_palette = ['#FE9321', '#6FE3CC', '#185D7A', '#C8DB2A', '#EF4687', '#5BC0DE', '#F0AD4E', '#D9534F']
        for dept in all_departments:
            dept_services_data = []
            department_total_tickets = 0
            services_in_dept = sorted([s for s in dept.services if managed_service_ids is None or s.id in managed_service_ids], key=lambda s: s.name)
            for i, service in enumerate(services_in_dept):
                found = next((row for row in dept_summary_data if row.dept_name == dept.name and row.service_id == service.id), None)
                if found:
                    res, tot = found.resolved_count, found.total; act = tot - res
                    dept_services_data.append({'name': service.name, 'active': act, 'resolved': res, 'total': tot,'resolved_percent': int(res / tot * 100) if tot else 0,'color': color_palette[i % len(color_palette)]})
                    department_total_tickets += tot
                else:
                    dept_services_data.append({'name': service.name, 'active': 0, 'resolved': 0, 'total': 0, 'resolved_percent': 0, 'color': color_palette[i % len(color_palette)]})
            if dept_services_data:
                dashboard_summary[dept.name] = {'services': dept_services_data,'department_total': department_total_tickets,'service_count': len(dept_services_data)}

        # === School Summary (Bagong Logic na may Pagination) ===
        
        # Step A: Kunin ang paginated list ng mga School objects na may tickets
        # !!!!! ITO ANG INAYOS NA QUERY !!!!!
        school_name_query = db.session.query(School, func.count(Ticket.id).label('total_tickets')) \
            .select_from(Ticket).join(School, Ticket.school_id == School.id) \
            .join(Service, Ticket.service_id == Service.id) # Kailangan i-join para sa filters

        # Ilagay ang common filters (Year, Quarter)
        school_name_query = school_name_query.filter(extract('year', Ticket.date_posted) == selected_year)
        if selected_quarter in quarters:
            start_date, end_date = quarters[selected_quarter]
            school_name_query = school_name_query.filter(Ticket.date_posted.between(start_date, end_date))
        
        # Ilagay ang role filters (managed_service_ids, my_assigned)
        if managed_service_ids is not None:
            school_name_query = school_name_query.filter(Service.id.in_(managed_service_ids))
        if filter_view == 'my_assigned':
            school_name_query = school_name_query.filter(Ticket.assigned_staff_id == current_user.id)
            
        # Group by school object at i-order base sa dami ng tickets (DESC)
        school_name_query = school_name_query.group_by(School.id).order_by(db.text('total_tickets DESC'), School.name)
        
        # I-paginate ang query (10 schools bawat page)
        paginated_schools = db.paginate(school_name_query, page=page_school, per_page=10, error_out=False)
        
        # Kunin ang listahan ng school names para sa page na ito *lamang*
        # !!!!! ITO ANG INAYOS NA LIST COMPREHENSION !!!!!
        # Ang 'item' ay isa na ngayong Row object (na may keys 'School' at 'total_tickets')
        # Kaya ang tamang pag-access ay item.School.name
        current_page_school_names = [item.name for item in paginated_schools.items]

        # Step B: Kunin ang details para sa mga schools na nasa page na ito *lamang*
        if current_page_school_names:
            school_summary_details_query = db.session.query(
                School.name.label('school_name'),
                Service.name.label('service_name'),
                Service.id.label('service_id'),
                func.count(Ticket.id).label('total'),
                func.sum(case((Ticket.status == 'Resolved', 1), else_=0)).label('resolved_count')
            ).select_from(Ticket).join(Service, Ticket.service_id == Service.id).join(School, Ticket.school_id == School.id)

            # Ilagay ulit ang common filters
            school_summary_details_query = school_summary_details_query.filter(extract('year', Ticket.date_posted) == selected_year)
            if selected_quarter in quarters:
                start_date, end_date = quarters[selected_quarter]
                school_summary_details_query = school_summary_details_query.filter(Ticket.date_posted.between(start_date, end_date))
            
            # Ilagay ulit ang role filters
            if managed_service_ids is not None:
                school_summary_details_query = school_summary_details_query.filter(Service.id.in_(managed_service_ids))
            if filter_view == 'my_assigned':
                school_summary_details_query = school_summary_details_query.filter(Ticket.assigned_staff_id == current_user.id)
            
            # Filter para sa schools na nasa page na ito *lamang*
            school_summary_details_query = school_summary_details_query.filter(School.name.in_(current_page_school_names))
            
            school_summary_data_flat = school_summary_details_query.group_by(School.name, Service.name, Service.id).order_by(School.name, Service.name).all()

            # I-proseso ang data (pareho sa dati, pero mas mabilis na)
            # !!!!! ITO ANG INAYOS NA BAHAGI !!!!!
            # Gagamitin natin ang paginated_schools.items para makuha ang tamang total_tickets
            for item in paginated_schools.items:
                school_obj = item
                total_count = school_summary.get(item.name, {}).get('total_school_tickets', 0)
                school_summary[school_obj.name] = {'total_school_tickets': total_count, 'services': []}

            for row in school_summary_data_flat:
                s_name = row.school_name
                if s_name in school_summary: # Check kung baka wala (kahit dapat meron)
                    res, tot = row.resolved_count, row.total; act = tot - res
                    school_summary[s_name]['services'].append({'name': row.service_name, 'active': act, 'resolved': res, 'total': tot})
                    # HINDI NA KAILANGAN ITO: school_summary[s_name]['total_school_tickets'] += tot (dahil nakuha na natin sa Step A)
    
    else: # Kung may search_query, i-define lang si paginated_schools as empty
         paginated_schools = db.paginate(db.select(School).where(db.false()), page=1, per_page=10, error_out=False)
    
    # --- TAPOS NG PAGBABAGO ---


    # --- Render Template ---
    return render_template('staff_dashboard.html', # Assuming this is in eservices_app/templates/
                           active_tickets=active_tickets, resolved_tickets=resolved_tickets,
                           dashboard_summary=dashboard_summary, school_summary=school_summary,
                           paginated_schools=paginated_schools, # <-- IPINASA ITO
                           title=title, available_years=available_years,
                           selected_year=selected_year, selected_quarter=selected_quarter,
                           search_query=search_query, filter_view=filter_view)

# === TICKET EXPORT (ADMIN) ===
# ... (walang pagbabago mula dito pababa) ...

@admin_bp.route('/export-tickets')
@login_required
@admin_required # Use the decorator imported from ..decorators
def export_tickets():
    search_query = request.args.get('search', '').strip()
    selected_year = request.args.get('year', datetime.utcnow().year, type=int)
    selected_quarter = request.args.get('quarter', 0, type=int)

    export_query = Ticket.query.options(
        joinedload(Ticket.school),
        joinedload(Ticket.service_type).joinedload(Service.department) # Load relationships
    ).order_by(Ticket.date_posted.desc())

    # Apply filters matching dashboard (without pagination)
    if search_query:
        search_term = f"%{search_query}%"
        export_query = export_query.join(School, Ticket.school_id == School.id, isouter=True).filter(
            or_(Ticket.ticket_number.ilike(search_term), Ticket.requester_name.ilike(search_term), School.name.ilike(search_term)))
    else:
        export_query = export_query.filter(extract('year', Ticket.date_posted) == selected_year)
        # Use the same quarters dict as dashboard for consistency
        quarters = {
            1: (datetime(selected_year, 1, 1, tzinfo=timezone.utc), datetime(selected_year, 3, 31, 23, 59, 59, tzinfo=timezone.utc)),
            2: (datetime(selected_year, 4, 1, tzinfo=timezone.utc), datetime(selected_year, 6, 30, 23, 59, 59, tzinfo=timezone.utc)),
            3: (datetime(selected_year, 7, 1, tzinfo=timezone.utc), datetime(selected_year, 9, 30, 23, 59, 59, tzinfo=timezone.utc)),
            4: (datetime(selected_year, 10, 1, tzinfo=timezone.utc), datetime(selected_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
        }
        if selected_quarter in quarters:
            start_date, end_date = quarters[selected_quarter]
            export_query = export_query.filter(Ticket.date_posted.between(start_date, end_date))

    tickets_to_export = export_query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    header = ['Ticket Number', 'Status', 'Requester Name', 'Requester Email', 'School/Office', 'Department', 'Service', 'Date Submitted', 'Assigned Staff'] # Added Assigned Staff
    writer.writerow(header)

    for ticket in tickets_to_export:
        row = [
            ticket.ticket_number, ticket.status, ticket.requester_name, ticket.requester_email,
            ticket.school.name if ticket.school else 'N/A',
            ticket.service_type.department.name if ticket.service_type and ticket.service_type.department else 'N/A', # Check if loaded
            ticket.service_type.name if ticket.service_type else 'N/A', # Check if loaded
            ticket.date_posted.strftime('%Y-%m-%d %H:%M:%S'),
            ticket.assigned_staff.name if ticket.assigned_staff else 'Unassigned' # Get assigned staff name
        ]
        writer.writerow(row)

    output.seek(0)
    response = Response(output.getvalue(), mimetype='text/csv')
    # Generate filename with date/time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    response.headers["Content-Disposition"] = f"attachment;filename=tickets_export_{timestamp}.csv"
    current_app.logger.info(f"Admin {current_user.email} exported tickets based on current filters.")
    return response

# === TICKET DELETION (ADMIN) ===

@admin_bp.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_ticket(ticket_id):
    ticket_to_delete = db.session.get(Ticket, ticket_id)
    if ticket_to_delete:
        ticket_number = ticket_to_delete.ticket_number
        db.session.delete(ticket_to_delete) # Cascade should handle related items
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.email} deleted ticket {ticket_number}")
        flash(f'Ticket {ticket_number} deleted.', 'success')
        # Redirect back to admin dashboard
        return redirect(url_for('admin.staff_dashboard'))
    else:
        flash('Ticket not found.', 'danger')
        current_app.logger.warning(f"Admin {current_user.email} tried deleting non-existent ticket ID: {ticket_id}")
        return redirect(url_for('admin.staff_dashboard'))


# === ADMIN DASHBOARD (Placeholder) ===

@admin_bp.route('/dashboard') # Changed from /admin/dashboard to just /dashboard (relative to /admin prefix)
@login_required
@admin_required
def admin_dashboard():
    # Use admin/dashboard.html from templates folder
    return render_template('admin/dashboard.html', title='Admin Dashboard')


# === USER MANAGEMENT (ADMIN) ===

@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    users = User.query.order_by(User.name).all()
    # Use admin/users.html from templates folder
    return render_template('admin/users.html', users=users, title='Manage Users')

@admin_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        current_app.logger.warning(f"Admin {current_user.email} tried editing non-existent user ID: {user_id}")
        return redirect(url_for('admin.manage_users')) # Correct redirect endpoint

    form = EditUserForm(obj=user) # Use obj=user for pre-filling

    if form.validate_on_submit():
        user.name = form.name.data
        # Ensure email uniqueness if changed
        if user.email != form.email.data:
             existing_user = User.query.filter(User.email == form.email.data, User.id != user_id).first()
             if existing_user:
                  flash('That email address is already registered.', 'danger')
                  # Reload necessary data for template
                  departments = Department.query.options(joinedload(Department.services)).order_by(Department.name).all()
                  managed_service_ids = {service.id for service in user.managed_services}
                  return render_template('admin/edit_user.html', form=form, user=user, departments=departments, managed_service_ids=managed_service_ids, title='Edit User')
        user.email = form.email.data
        user.role = form.role.data

        # Update managed services
        user.managed_services = [] # Clear existing
        selected_service_ids = request.form.getlist('managed_services')
        services = Service.query.filter(Service.id.in_(selected_service_ids)).all()
        user.managed_services = services # Assign the list of service objects

        db.session.commit()
        current_app.logger.info(f"Admin {current_user.email} updated user profile for {user.email}")
        flash(f'User {user.name} updated successfully!', 'success')
        return redirect(url_for('admin.manage_users')) # Correct redirect endpoint

    # Load data needed for the template (services for checkboxes)
    departments = Department.query.options(joinedload(Department.services)).order_by(Department.name).all()
    managed_service_ids = {service.id for service in user.managed_services} # Set for faster lookup in template

    # Use admin/edit_user.html from templates folder
    return render_template('admin/edit_user.html', form=form, user=user, departments=departments, managed_service_ids=managed_service_ids, title='Edit User')

@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user and user.id != current_user.id:
        user_email = user.email
        # Consider what happens to tickets assigned to this user (set to NULL due to model definition)
        db.session.delete(user)
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.email} deleted user {user_email}")
        flash(f'User {user.name} deleted.', 'success')
    elif user and user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        current_app.logger.warning(f"Admin {current_user.email} tried deleting own account.")
    else:
        flash('User not found.', 'danger')
        current_app.logger.warning(f"Admin {current_user.email} tried deleting non-existent user ID: {user_id}")
    return redirect(url_for('admin.manage_users')) # Correct redirect endpoint


# === AUTHORIZED EMAIL MANAGEMENT (ADMIN) ===

@admin_bp.route('/authorized-emails', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_authorized_emails():
    add_form = AddAuthorizedEmailForm()
    bulk_form = BulkUploadForm()
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)

    # Handle Delete Selected Action
    if request.method == 'POST' and 'delete_selected' in request.form:
        email_ids = request.form.getlist('email_ids')
        if email_ids:
            count = AuthorizedEmail.query.filter(AuthorizedEmail.id.in_(email_ids)).delete(synchronize_session=False)
            db.session.commit()
            current_app.logger.info(f"Admin {current_user.email} deleted {count} authorized emails via bulk.")
            flash(f'{count} email(s) deleted.', 'success')
        else:
            flash('No emails selected.', 'warning')
        return redirect(url_for('admin.manage_authorized_emails', search=search_query, page=page))

    # Handle Add Single Email
    if add_form.validate_on_submit() and add_form.submit.data:
        new_email = AuthorizedEmail(email=add_form.email.data)
        db.session.add(new_email)
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.email} added authorized email: {add_form.email.data}")
        flash(f'Email {add_form.email.data} authorized.', 'success')
        return redirect(url_for('admin.manage_authorized_emails')) # Redirect to clear form

    # Handle Bulk Upload
    if bulk_form.validate_on_submit() and bulk_form.submit_bulk.data:
        csv_file = bulk_form.csv_file.data
        added, skipped = 0, 0
        try:
            stream = io.StringIO(csv_file.read().decode("UTF8"), newline=None)
            csv_reader = csv.reader(stream)
            emails_to_add = []
            existing_emails = {email.email for email in AuthorizedEmail.query.all()} # Load existing emails once
            for row in csv_reader:
                if row and row[0].strip():
                    email = row[0].strip().lower() # Normalize email
                    if email not in existing_emails:
                        emails_to_add.append(AuthorizedEmail(email=email))
                        existing_emails.add(email) # Add to set to prevent duplicates within the file
                        added += 1
                    else:
                        skipped += 1
            if emails_to_add:
                db.session.bulk_save_objects(emails_to_add)
                db.session.commit()
            current_app.logger.info(f"Admin {current_user.email} bulk email upload. Added: {added}, Skipped: {skipped}.")
            flash(f'Bulk upload complete. Added: {added}. Skipped: {skipped}.', 'info')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error bulk email upload by {current_user.email}: {e}", exc_info=True)
            flash(f'Error processing bulk upload: {e}', 'danger')
        return redirect(url_for('admin.manage_authorized_emails')) # Redirect to clear form

    # Display List (GET request or after POST redirect)
    query = AuthorizedEmail.query
    if search_query:
        query = query.filter(AuthorizedEmail.email.ilike(f'%{search_query}%'))
    emails = db.paginate(query.order_by(AuthorizedEmail.email), page=page, per_page=current_app.config['EMAILS_PER_PAGE'], error_out=False)

    # Use admin/authorized_emails.html from templates folder
    return render_template('admin/authorized_emails.html', emails=emails, add_form=add_form, bulk_form=bulk_form, title='Manage Authorized Emails', search_query=search_query)

@admin_bp.route('/authorized-emails/<int:email_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_authorized_email(email_id):
    email_obj = db.session.get(AuthorizedEmail, email_id)
    if email_obj:
        email_addr = email_obj.email
        db.session.delete(email_obj)
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.email} deleted authorized email: {email_addr}")
        flash(f'Email {email_addr} removed.', 'success')
    else:
        flash('Email not found.', 'danger')
        current_app.logger.warning(f"Admin {current_user.email} tried deleting non-existent auth email ID: {email_id}")
    # Preserve search/page context on redirect if possible
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    return redirect(url_for('admin.manage_authorized_emails', search=search_query, page=page))


# === DEPARTMENT MANAGEMENT (ADMIN) ===

@admin_bp.route('/departments')
@login_required
@admin_required
def manage_departments():
    departments = Department.query.order_by(Department.name).all()
    # Use admin/departments.html
    return render_template('admin/departments.html', departments=departments, title='Manage Departments')

@admin_bp.route('/department/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_department():
    form = DepartmentForm()
    if form.validate_on_submit():
        dept_name = form.name.data
        new_dept = Department(name=dept_name)
        db.session.add(new_dept)
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.email} added department: {dept_name}")
        flash(f'Department "{dept_name}" created.', 'success')
        return redirect(url_for('admin.manage_departments')) # Correct redirect
    # Use admin/add_edit_department.html
    return render_template('admin/add_edit_department.html', form=form, title='Add Department')

@admin_bp.route('/department/<int:dept_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_department(dept_id):
    dept = db.session.get(Department, dept_id)
    if not dept:
        flash('Department not found.', 'danger')
        current_app.logger.warning(f"Admin {current_user.email} tried editing non-existent dept ID: {dept_id}")
        return redirect(url_for('admin.manage_departments'))

    original_name = dept.name
    form = DepartmentForm(obj=dept)

    if form.validate_on_submit():
        new_name = form.name.data
        if new_name != original_name:
            existing = Department.query.filter(Department.name == new_name, Department.id != dept_id).first()
            if existing:
                flash('That department name already exists.', 'danger')
                # Use admin/add_edit_department.html
                return render_template('admin/add_edit_department.html', form=form, title='Edit Department', department=dept)
        dept.name = new_name
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.email} updated dept {dept_id} name to '{new_name}'")
        flash(f'Department updated to "{new_name}".', 'success')
        return redirect(url_for('admin.manage_departments'))

    # Use admin/add_edit_department.html
    return render_template('admin/add_edit_department.html', form=form, title='Edit Department', department=dept)

@admin_bp.route('/department/<int:dept_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_department(dept_id):
    dept = db.session.get(Department, dept_id)
    if dept:
        dept_name = dept.name
        # Check dependencies (Services, Tickets, CannedResponses)
        if dept.services:
            flash(f'Cannot delete "{dept_name}": has services.', 'danger')
            current_app.logger.warning(f"Admin {current_user.email} failed delete dept '{dept_name}': has services.")
        elif dept.tickets: # Should ideally be caught by services check
             flash(f'Cannot delete "{dept_name}": has tickets.', 'danger')
             current_app.logger.warning(f"Admin {current_user.email} failed delete dept '{dept_name}': has tickets.")
        elif dept.canned_responses:
             flash(f'Cannot delete "{dept_name}": has canned responses.', 'danger')
             current_app.logger.warning(f"Admin {current_user.email} failed delete dept '{dept_name}': has canned resp.")
        else:
            db.session.delete(dept)
            db.session.commit()
            current_app.logger.info(f"Admin {current_user.email} deleted department: {dept_name}")
            flash(f'Department "{dept_name}" deleted.', 'success')
            return redirect(url_for('admin.manage_departments'))
    else:
        flash('Department not found.', 'danger')
        current_app.logger.warning(f"Admin {current_user.email} tried deleting non-existent dept ID: {dept_id}")
    return redirect(url_for('admin.manage_departments'))


# === SERVICE MANAGEMENT (ADMIN) ===

@admin_bp.route('/services')
@login_required
@admin_required
def manage_services():
    services = Service.query.join(Department).options(joinedload(Service.department)).order_by(Department.name, Service.name).all()
    # Use admin/manage_services.html
    return render_template('admin/manage_services.html', services=services, title='Manage Services')

@admin_bp.route('/service/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_service():
    form = ServiceForm()
    form.department_id.choices = [(0, '-- Select Department --')] + [(d.id, d.name) for d in Department.query.order_by('name')]

    if form.validate_on_submit():
        if form.department_id.data == 0:
            flash('Please select a valid department.', 'danger')
        else:
            existing = Service.query.filter_by(name=form.name.data, department_id=form.department_id.data).first()
            if existing:
                flash(f'Service "{form.name.data}" already exists in this department.', 'danger')
            else:
                new_service = Service(name=form.name.data, department_id=form.department_id.data)
                db.session.add(new_service)
                db.session.commit()
                current_app.logger.info(f"Admin {current_user.email} added service '{new_service.name}'")
                flash(f'Service "{new_service.name}" created.', 'success')
                return redirect(url_for('admin.manage_services'))

    # Use admin/add_edit_service.html
    return render_template('admin/add_edit_service.html', form=form, title='Add Service')

@admin_bp.route('/service/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_service(service_id):
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found.', 'danger')
        return redirect(url_for('admin.manage_services'))

    form = ServiceForm(obj=service)
    form.department_id.choices = [(d.id, d.name) for d in Department.query.order_by('name')]

    if form.validate_on_submit():
        if form.department_id.data == 0:
             flash('Please select a valid department.', 'danger')
        else:
            # Check uniqueness only if name or department changed
            if service.name != form.name.data or service.department_id != form.department_id.data:
                existing = Service.query.filter(Service.name == form.name.data, Service.department_id == form.department_id.data, Service.id != service_id).first()
                if existing:
                    flash(f'Service "{form.name.data}" already exists in this department.', 'danger')
                else: # No conflict, proceed with update
                    service.name = form.name.data
                    service.department_id = form.department_id.data
                    db.session.commit()
                    current_app.logger.info(f"Admin {current_user.email} updated service ID {service_id}")
                    flash(f'Service "{service.name}" updated.', 'success')
                    return redirect(url_for('admin.manage_services'))
            else: # No changes made
               flash('No changes detected for the service.', 'info')
               return redirect(url_for('admin.manage_services'))

    # Pre-fill department on GET if not POST validation error
    if request.method == 'GET':
        form.department_id.data = service.department_id

    # Use admin/add_edit_service.html
    return render_template('admin/add_edit_service.html', form=form, title='Edit Service', service=service)

@admin_bp.route('/service/<int:service_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_service(service_id):
    service = db.session.get(Service, service_id)
    if service:
        service_name = service.name
        # Check dependencies
        if service.tickets:
            flash(f'Cannot delete "{service_name}": has tickets.', 'danger')
            current_app.logger.warning(f"Admin {current_user.email} failed delete service '{service_name}': has tickets.")
        elif service.canned_responses: # Check system canned responses
             flash(f'Cannot delete "{service_name}": has system canned responses.', 'danger')
             current_app.logger.warning(f"Admin {current_user.email} failed delete service '{service_name}': has canned resp.")
        # Check association table (managers) - optional, deleting service might just remove association
        # elif service.managers.count() > 0: ...
        else:
            # Delete related canned responses explicitly if cascade doesn't cover service_id=None change potential
            # CannedResponse.query.filter_by(service_id=service_id).delete() # Already handled? Check model.
            db.session.delete(service)
            db.session.commit()
            current_app.logger.info(f"Admin {current_user.email} deleted service: {service_name}")
            flash(f'Service "{service_name}" deleted.', 'success')
            return redirect(url_for('admin.manage_services'))
    else:
        flash('Service not found.', 'danger')
        current_app.logger.warning(f"Admin {current_user.email} tried deleting non-existent service ID: {service_id}")
    return redirect(url_for('admin.manage_services'))


# === SYSTEM CANNED RESPONSE MANAGEMENT (ADMIN) ===

@admin_bp.route('/canned-responses')
@login_required
@admin_required
def manage_canned_responses():
    responses = CannedResponse.query.join(Department).options(joinedload(CannedResponse.department), joinedload(CannedResponse.service)).order_by(Department.name, CannedResponse.title).all()
    # Use admin/canned_responses.html
    return render_template('admin/canned_responses.html', responses=responses, title='Manage Canned Responses')

@admin_bp.route('/canned-response/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_canned_response():
    form = CannedResponseForm()
    # Populate choices dynamically
    form.department_id.choices = [(0, '-- Select Department --')] + [(d.id, d.name) for d in Department.query.order_by('name')]
    form.service_id.choices = [(0, '-- General (All Services) --')] # Default

    if request.method == 'POST':
        # Repopulate service choices based on selected department in POST data
        dept_id = request.form.get('department_id', type=int)
        if dept_id and dept_id != 0:
            services = Service.query.filter_by(department_id=dept_id).order_by('name').all()
            form.service_id.choices.extend([(s.id, s.name) for s in services])

        if form.validate_on_submit():
            if form.department_id.data == 0:
                 flash('Please select a valid department.', 'danger')
            else:
                service_id_val = form.service_id.data if form.service_id.data != 0 else None
                # Check for duplicates before adding
                existing = CannedResponse.query.filter_by(title=form.title.data, department_id=form.department_id.data, service_id=service_id_val).first()
                if existing:
                    flash(f'A canned response with this title already exists for this department/service.', 'warning')
                else:
                    new_response = CannedResponse(title=form.title.data, body=form.body.data, department_id=form.department_id.data, service_id=service_id_val)
                    db.session.add(new_response)
                    db.session.commit()
                    current_app.logger.info(f"Admin {current_user.email} added canned response: '{form.title.data}'")
                    flash(f'Canned response "{form.title.data}" created.', 'success')
                    return redirect(url_for('admin.manage_canned_responses')) # Correct endpoint

    # Use admin/add_edit_canned_response.html
    return render_template('admin/add_edit_canned_response.html', form=form, title='Add Canned Response')



@admin_bp.route('/canned-response/<int:response_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_canned_response(response_id):
    response_obj = db.session.get(CannedResponse, response_id)
    if not response_obj:
        flash('Canned response not found.', 'danger')
        return redirect(url_for('admin.manage_canned_responses'))

    form = CannedResponseForm(obj=response_obj)
    form.department_id.choices = [(d.id, d.name) for d in Department.query.order_by('name')]

    # Populate initial service choices based on the response's current department
    current_dept_id = response_obj.department_id
    services = Service.query.filter_by(department_id=current_dept_id).order_by('name').all()
    form.service_id.choices = [(0, '-- General (All Services) --')] + [(s.id, s.name) for s in services]

    if request.method == 'POST':
        # Repopulate service choices based on selected department in POST data
        dept_id = request.form.get('department_id', type=int)
        if dept_id and dept_id != 0:
            services_post = Service.query.filter_by(department_id=dept_id).order_by('name').all()
            form.service_id.choices = [(0, '-- General (All Services) --')] + [(s.id, s.name) for s in services_post]

        if form.validate_on_submit():
             if form.department_id.data == 0:
                    flash('Please select a valid department.', 'danger')
             else:
                service_id_val = form.service_id.data if form.service_id.data != 0 else None

                # --- SIMULA NG PAG-AYOS (Bug fix para sa Canned Response) ---

                # 1. Alamin muna kung may nagbago BA TALAGA (kasama ang body)
                has_changed = (
                    response_obj.title != form.title.data or
                    response_obj.body != form.body.data or 
                    response_obj.department_id != form.department_id.data or
                    response_obj.service_id != service_id_val
                )

                if not has_changed:
                    flash('No changes detected for the canned response.', 'info')
                    return redirect(url_for('admin.manage_canned_responses'))

                # 2. Ngayong alam nating may nagbago, i-check kung may duplicate sa mga UNIQUE fields
                has_unique_fields_changed = (
                    response_obj.title != form.title.data or
                    response_obj.department_id != form.department_id.data or
                    response_obj.service_id != service_id_val
                )

                if has_unique_fields_changed:
                    existing = CannedResponse.query.filter(
                        CannedResponse.title == form.title.data,
                        CannedResponse.department_id == form.department_id.data,
                        CannedResponse.service_id == service_id_val,
                        CannedResponse.id != response_id
                    ).first()
                    if existing:
                        flash(f'Another canned response with this title already exists for this department/service.', 'warning')
                        # Kailangan i-render ulit ang template para makita ang error
                        return render_template('admin/add_edit_canned_response.html', form=form, title='Edit Canned Response', response_id=response_id)
                
                # 3. Kung walang duplicate (o kung body lang ang nagbago), i-save na lahat.
                response_obj.title = form.title.data
                response_obj.body = form.body.data
                response_obj.department_id = form.department_id.data
                response_obj.service_id = service_id_val
                
                db.session.commit()  # <-- Ito na ang magse-save ng pagbabago sa body
                
                current_app.logger.info(f"Admin {current_user.email} updated canned response ID {response_id}")
                flash(f'Canned response "{form.title.data}" updated.', 'success')
                return redirect(url_for('admin.manage_canned_responses'))
                
                # --- TAPOS NG PAG-AYOS ---

    # Pre-fill service_id on GET request
    if request.method == 'GET':
        form.service_id.data = response_obj.service_id if response_obj.service_id else 0

    # Use admin/add_edit_canned_response.html
    return render_template('admin/add_edit_canned_response.html', form=form, title='Edit Canned Response', response_id=response_id)



@admin_bp.route('/_get_services_for_department/<int:dept_id>')
@login_required
@admin_required
def _get_services_for_department(dept_id):
    """Helper route to dynamically load services for a department."""
    if dept_id == 0:
        return jsonify([]) # Return empty list if '-- Select --' is chosen
    services = Service.query.filter_by(department_id=dept_id).order_by('name').all()
    service_array = [{"id": s.id, "name": s.name} for s in services]
    # Add the 'General' option at the beginning
    service_array.insert(0, {"id": 0, "name": "-- General (All Services) --"})
    # Use jsonify for proper JSON response
    return jsonify(service_array)


@admin_bp.route('/canned-response/<int:response_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_canned_response(response_id):
    response_obj = db.session.get(CannedResponse, response_id)
    if response_obj:
        response_title = response_obj.title
        db.session.delete(response_obj)
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.email} deleted canned response: '{response_title}'")
        flash(f'Canned response "{response_title}" deleted.', 'success')
    else:
        flash('Canned response not found.', 'danger')
        current_app.logger.warning(f"Admin {current_user.email} tried deleting non-existent canned response ID: {response_id}")
    return redirect(url_for('admin.manage_canned_responses')) # Correct endpoint


# === PERSONAL CANNED RESPONSE MANAGEMENT (Staff/Admin) ===

@admin_bp.route('/my-responses', methods=['GET', 'POST'])
@login_required
@staff_or_admin_required # Use the new decorator
def manage_my_responses():
    form = PersonalCannedResponseForm()
    ticket_id = request.args.get('ticket_id') # For back button context

    if form.validate_on_submit():
        # Check for duplicates for the current user
        existing = PersonalCannedResponse.query.filter_by(user_id=current_user.id, title=form.title.data).first()
        if existing:
            flash('You already have a personal response with this title.', 'warning')
        else:
            new_response = PersonalCannedResponse(title=form.title.data, body=form.body.data, owner=current_user)
            db.session.add(new_response)
            db.session.commit()
            current_app.logger.info(f"User {current_user.email} added personal response: '{form.title.data}'")
            flash('Personal response saved!', 'success')
        # Redirect to clear form and show updated list
        return redirect(url_for('admin.manage_my_responses', ticket_id=ticket_id))

    my_responses = PersonalCannedResponse.query.filter_by(user_id=current_user.id).order_by(PersonalCannedResponse.title).all()

    # Assuming template is 'admin/manage_my_responses.html' or similar
    return render_template('manage_my_responses.html', title='My Personal Responses', form=form, my_responses=my_responses, ticket_id=ticket_id)

@admin_bp.route('/my-responses/<int:response_id>/edit', methods=['GET', 'POST'])
@login_required
@staff_or_admin_required
def edit_my_response(response_id):
    response_obj = db.session.get(PersonalCannedResponse, response_id)
    ticket_id = request.args.get('ticket_id')

    if not response_obj or response_obj.user_id != current_user.id:
        flash('Response not found or permission denied.', 'danger')
        current_app.logger.warning(f"User {current_user.email} tried editing unauthorized personal response ID: {response_id}")
        return redirect(url_for('admin.manage_my_responses', ticket_id=ticket_id))

    form = PersonalCannedResponseForm(obj=response_obj)

    if form.validate_on_submit():
        # Check for duplicate titles (excluding the current one)
        if response_obj.title != form.title.data:
            existing = PersonalCannedResponse.query.filter(
                PersonalCannedResponse.user_id == current_user.id,
                PersonalCannedResponse.title == form.title.data,
                PersonalCannedResponse.id != response_id
            ).first()
            if existing:
                flash('You already have another personal response with this title.', 'warning')
            else: # No conflict or no change in title
                response_obj.title = form.title.data
                response_obj.body = form.body.data
                db.session.commit()
                current_app.logger.info(f"User {current_user.email} updated personal response ID {response_id}")
                flash('Personal response updated.', 'success')
                return redirect(url_for('admin.manage_my_responses', ticket_id=ticket_id))
        else: # Title didn't change, just update body
             response_obj.body = form.body.data
             db.session.commit()
             current_app.logger.info(f"User {current_user.email} updated personal response ID {response_id}")
             flash('Personal response updated.', 'success')
             return redirect(url_for('admin.manage_my_responses', ticket_id=ticket_id))


    # Assuming template is 'admin/edit_my_response.html' or similar
    return render_template('edit_my_response.html', title='Edit Personal Response', form=form, response_id=response_id, ticket_id=ticket_id)

@admin_bp.route('/my-responses/<int:response_id>/delete', methods=['POST'])
@login_required
@staff_or_admin_required
def delete_my_response(response_id):
    response_obj = db.session.get(PersonalCannedResponse, response_id)
    ticket_id = request.args.get('ticket_id')

    if response_obj and response_obj.user_id == current_user.id:
        response_title = response_obj.title
        db.session.delete(response_obj)
        db.session.commit()
        current_app.logger.info(f"User {current_user.email} deleted personal response: '{response_title}'")
        flash('Personal response deleted.', 'success')
    else:
        flash('Response not found or permission denied.', 'danger')
        current_app.logger.warning(f"User {current_user.email} tried deleting unauthorized personal response ID: {response_id}")

    return redirect(url_for('admin.manage_my_responses', ticket_id=ticket_id))


# === AJAX Endpoint for Polling ===

@admin_bp.route('/check-new-tickets')
@login_required
@staff_or_admin_required # Only staff/admin need to poll
def check_new_tickets():
    since_iso = request.args.get('since', datetime.min.replace(tzinfo=timezone.utc).isoformat())
    try:
        since_dt = datetime.fromisoformat(since_iso.replace('Z', '+00:00'))
        if since_dt.tzinfo is None: since_dt = since_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        since_dt = datetime.min.replace(tzinfo=timezone.utc)

    base_query = Ticket.query.filter(Ticket.date_posted > since_dt)
    managed_service_ids = None

    if current_user.role == 'Staff':
        managed_service_ids = [service.id for service in current_user.managed_services]
        if not managed_service_ids:
            return jsonify({'new_count': 0, 'latest_timestamp': since_iso})
        base_query = base_query.filter(Ticket.service_id.in_(managed_service_ids))

    new_count = base_query.count()
    latest_ticket = base_query.order_by(Ticket.date_posted.desc()).first()
    latest_timestamp_iso = latest_ticket.date_posted.isoformat() if latest_ticket else since_iso

    return jsonify({'new_count': new_count, 'latest_timestamp': latest_timestamp_iso})
