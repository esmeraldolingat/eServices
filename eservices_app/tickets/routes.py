# eservices_app/tickets/routes.py

import os
import json
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, json)
from flask_login import login_required, current_user
from sqlalchemy import case, or_, extract
from werkzeug.utils import secure_filename
from datetime import datetime, timezone

# Import galing sa parent package (eservices_app)
from .. import db
from ..models import (User, Department, Service, School, Ticket, Attachment,
                      CannedResponse, PersonalCannedResponse, Response as TicketResponse)
# Import *LAHAT* ng ticket forms
from ..forms import (DepartmentSelectionForm, ServiceSelectionForm, GeneralTicketForm,
                     IssuanceForm, RepairForm, EmailAccountForm, DpdsForm, DcpForm, OtherIctForm,
                     LeaveApplicationForm, CoeForm, ServiceRecordForm, GsisForm, NoPendingCaseForm,
                     LocatorSlipForm, AuthorityToTravelForm, OicDesignationForm, SubstituteTeacherForm, AdmForm,
                     ProvidentFundForm, IcsForm, ResponseForm, UpdateTicketForm)
# Import email helper functions
from ..helpers import send_new_ticket_email, send_staff_notification_email, send_resolution_email

# --- Create Blueprint ---
# Walang url_prefix dito para manatili ang /my-tickets at /ticket/<id>
tickets_bp = Blueprint('tickets', __name__, template_folder='templates')


# === MY TICKETS (User Dashboard) ===

@tickets_bp.route('/my-tickets')
@login_required
def my_tickets():
    page_active = request.args.get('page_active', 1, type=int)
    page_resolved = request.args.get('page_resolved', 1, type=int)
    search_query = request.args.get('search', '').strip()

    base_query = Ticket.query.filter_by(requester_email=current_user.email)

    if search_query:
        search_term = f"%{search_query}%"
        base_query = base_query.join(Service).filter(
            or_(
                Ticket.ticket_number.ilike(search_term),
                Service.name.ilike(search_term)
            )
        )

    status_order = case(
        (Ticket.status == 'Open', 1),
        (Ticket.status == 'In Progress', 2),
        else_=3
    )

    active_tickets = db.paginate(base_query.filter(Ticket.status.in_(['Open', 'In Progress'])).order_by(status_order, Ticket.date_posted.desc()),
                                 page=page_active, per_page=current_app.config['TICKETS_PER_PAGE'], error_out=False)
    resolved_tickets = db.paginate(base_query.filter(Ticket.status == 'Resolved').order_by(Ticket.date_posted.desc()),
                                   page=page_resolved, per_page=current_app.config['TICKETS_PER_PAGE'], error_out=False)

    return render_template('my_tickets.html', active_tickets=active_tickets, resolved_tickets=resolved_tickets, title='My Tickets', search_query=search_query)


# === TICKET DETAIL (User and Staff/Admin) ===

@tickets_bp.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def ticket_detail(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        flash('Ticket not found!', 'error')
        current_app.logger.warning(f"Attempt to access non-existent ticket ID: {ticket_id}")
        return redirect(url_for('main.home'))

    is_staff_or_admin = current_user.role == 'Admin' or (current_user.role == 'Staff' and ticket.service_type in current_user.managed_services)

    if is_staff_or_admin:
        form = UpdateTicketForm()
        try:
            assignable_staff = ticket.service_type.managers.order_by(User.name).all()
            form.assigned_staff.choices = [(user.id, user.name) for user in assignable_staff]
            form.assigned_staff.choices.insert(0, (0, '-- Unassigned --'))
        except Exception as e:
            current_app.logger.error(f"Error fetching assignable staff for service {ticket.service_id}: {e}")
            form.assigned_staff.choices = [(0, '-- Error Loading Staff --')]
    else:
        if ticket.requester_email != current_user.email:
            flash('You do not have permission to view this ticket.', 'danger')
            current_app.logger.warning(f"Unauthorized attempt by {current_user.email} to view ticket {ticket_id}")
            return redirect(url_for('main.home'))
        form = ResponseForm()

    # Canned Response Query
    system_canned_responses = []
    personal_canned_responses = []
    if is_staff_or_admin:
        system_canned_responses = CannedResponse.query.filter(
            CannedResponse.department_id == ticket.department_id,
            or_(
                CannedResponse.service_id == ticket.service_id,
                CannedResponse.service_id == None
            )
        ).order_by(CannedResponse.service_id.desc(), CannedResponse.title).all()
        personal_canned_responses = PersonalCannedResponse.query.filter_by(user_id=current_user.id).order_by(PersonalCannedResponse.title).all()

    if form.validate_on_submit():
        if ticket.status == 'Resolved' and not is_staff_or_admin:
            flash('This ticket is already resolved and cannot receive new responses.', 'info')
            return redirect(url_for('tickets.ticket_detail', ticket_id=ticket.id))

        # File Validation
        file_to_save_object = None
        filename_to_save_in_db = None
        # Kunin ang configs mula sa current_app
        MAX_FILE_SIZE_BYTES = current_app.config['MAX_FILE_SIZE_MB'] * 1024 * 1024
        # TANDAAN: Kailangan mong i-define ang ALLOWED_EXTENSIONS sa iyong __init__.py config
        # o i-hardcode dito kung saan mo ito kailangan. Let's assume pdf for now.
        ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'} # Example, kunin sa forms.py kung mas maganda

        if form.attachment.data:
            file = form.attachment.data
            filename = secure_filename(file.filename)
            try:
                file.seek(0, os.SEEK_END); file_size = file.tell(); file.seek(0)
                if file_size == 0:
                    flash(f"Attachment '{filename}' is empty.", 'warning')
                elif file_size > MAX_FILE_SIZE_BYTES:
                    flash(f"Attachment '{filename}' exceeds {current_app.config['MAX_FILE_SIZE_MB']}MB limit.", 'danger')
                    return redirect(url_for('tickets.ticket_detail', ticket_id=ticket.id))
            except Exception as e:
                current_app.logger.error(f"Error checking attachment size ticket {ticket_id}: {e}")
                flash(f"Could not check size of '{filename}'.", 'danger')
                return redirect(url_for('tickets.ticket_detail', ticket_id=ticket.id))

            if file_size > 0 and filename and ('.' not in filename or filename.rsplit('.', 1)[1].lower() not in ALLOWED_EXTENSIONS):
                flash(f"Attachment file type for '{filename}' not allowed.", 'danger')
                return redirect(url_for('tickets.ticket_detail', ticket_id=ticket.id))

            if file_size > 0:
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
                filename_to_save_in_db = f"{timestamp}_{filename}"
                file_to_save_object = file

        # Save Logic
        try:
            response_was_added = False
            status_was_changed = False
            assignment_was_changed = False
            new_response_object = None

            if file_to_save_object and filename_to_save_in_db:
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename_to_save_in_db)
                file_to_save_object.save(save_path)
                current_app.logger.info(f"Saved attachment: {filename_to_save_in_db} for ticket {ticket_id}")
                db.session.add(Attachment(filename=filename_to_save_in_db, ticket_id=ticket.id))

            if form.body.data and form.body.data.strip():
                # Check kung staff/admin form para kunin ang is_internal
                is_internal = form.is_internal.data if hasattr(form, 'is_internal') else False
                new_response = TicketResponse(body=form.body.data, user_id=current_user.id, ticket_id=ticket.id, is_internal=is_internal)
                db.session.add(new_response)
                response_was_added = True
                new_response_object = new_response

            if hasattr(form, 'status'): # Staff/Admin form
                old_status = ticket.status
                new_status = form.status.data
                if old_status != new_status:
                    ticket.status = new_status
                    status_was_changed = True
                    current_app.logger.info(f"Ticket {ticket_id} status changed: '{old_status}' -> '{new_status}' by {current_user.email}")

                new_staff_id = form.assigned_staff.data
                if new_staff_id == 0 and ticket.assigned_staff_id is not None:
                    ticket.assigned_staff_id = None
                    assignment_was_changed = True
                    flash('Ticket unassigned.', 'info')
                    current_app.logger.info(f"Ticket {ticket_id} unassigned by {current_user.email}")
                elif new_staff_id != 0 and new_staff_id != ticket.assigned_staff_id:
                    new_staff = db.session.get(User, new_staff_id)
                    if new_staff and new_staff in ticket.service_type.managers:
                        ticket.assigned_staff_id = new_staff_id
                        assignment_was_changed = True
                        flash(f'Ticket assigned to {new_staff.name}.', 'success')
                        current_app.logger.info(f"Ticket {ticket_id} assigned to {new_staff.email} by {current_user.email}")
                    else:
                        flash('Invalid staff member selected.', 'danger')
                
                # Flash messages for Staff/Admin
                if status_was_changed:
                    if new_status == 'Resolved':
                        email_body = form.body.data if response_was_added and not new_response_object.is_internal else "Your ticket has been resolved."
                        if not new_response_object or not new_response_object.is_internal:
                            send_resolution_email(ticket, email_body)
                        flash('Ticket resolved and notification sent (if applicable).', 'success')
                    else:
                        flash(f'Ticket status updated to {new_status}.', 'success')
                elif response_was_added and not status_was_changed:
                    flash('Response added successfully!', 'success')
                elif not response_was_added and not status_was_changed and not assignment_was_changed:
                    flash('No changes were made.', 'info')

            else: # User form
                if response_was_added:
                    flash('Response added successfully!', 'success')
                    if not is_staff_or_admin and new_response_object:
                        send_staff_notification_email(ticket, new_response_object)

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving response/assignment ticket {ticket_id}: {e}", exc_info=True)
            flash('An error occurred while saving. Please try again.', 'danger')

        return redirect(url_for('tickets.ticket_detail', ticket_id=ticket.id))

    # GET Request Logic
    if request.method == 'GET' and hasattr(form, 'status'):
        form.status.data = ticket.status
        form.assigned_staff.data = ticket.assigned_staff_id if ticket.assigned_staff_id else 0

    details_pretty = json.dumps(ticket.details, indent=2) if ticket.details else "No additional details."

    return render_template('ticket_detail.html', ticket=ticket, details_pretty=details_pretty, form=form, is_staff_or_admin=is_staff_or_admin, system_canned_responses=system_canned_responses, personal_canned_responses=personal_canned_responses)


# === TICKET CREATION PROCESS ===

@tickets_bp.route('/create-ticket/select-department', methods=['GET'])
def select_department():
    DEPARTMENT_ORDER = ["ICT", "Personnel", "Legal Services", "Office of the SDS", "Accounting Unit", "Supply Office"]
    all_departments = Department.query.all()
    departments_dict = {dept.name: dept for dept in all_departments}
    ordered_departments = [departments_dict[name] for name in DEPARTMENT_ORDER if name in departments_dict]
    return render_template('select_department.html', departments=ordered_departments, title='Select a Department')

@tickets_bp.route('/create-ticket/select-service/<int:department_id>', methods=['GET'])
def select_service(department_id):
    department = db.session.get(Department, department_id)
    if not department:
        flash('Invalid department selected.', 'error')
        return redirect(url_for('tickets.select_department')) # Correct redirect
    return render_template('select_service.html', department=department, services=department.services, title=f'Select a Service for {department.name}')

@tickets_bp.route('/create-ticket/form/<int:service_id>', methods=['GET', 'POST'])
def create_ticket_form(service_id):
    service = db.session.get(Service, service_id)
    if not service:
        flash('Invalid service selected.', 'error')
        return redirect(url_for('tickets.select_department')) # Correct redirect

    # Form Mapping
    form_map = {
        'Issuances and Online Materials': IssuanceForm, 'Repair, Maintenance and Troubleshoot of IT Equipment': RepairForm,
        'DepEd Email Account': EmailAccountForm, 'DPDS - DepEd Partnership Database System': DpdsForm,
        'DCP - DepEd Computerization Program: After-sales': DcpForm, 'other ICT - Technical Assistance Needed': OtherIctForm,
        'Application for Leave of Absence': LeaveApplicationForm, 'Certificate of Employment': CoeForm,
        'Service Record': ServiceRecordForm, 'GSIS BP Number': GsisForm,
        'Certificate of NO-Pending Case': NoPendingCaseForm,
        'Request for Approval of Locator Slip': LocatorSlipForm,
        'Request for Approval of Authority to Travel': AuthorityToTravelForm,
        'Request for Designation of Officer-in-Charge at the School': OicDesignationForm,
        'Request for Substitute Teacher': SubstituteTeacherForm,
        'Alternative Delivery Mode': AdmForm,
        'DepEd TCSD Provident Fund': ProvidentFundForm,
        'Submission of Inventory Custodian Slip – ICS': IcsForm,
    }
    FormClass = form_map.get(service.name, GeneralTicketForm)
    form = FormClass()

    # Pre-fill form if logged in
    if request.method == 'GET' and current_user.is_authenticated:
        form.requester_email.data = current_user.email
        form.requester_name.data = current_user.name

    if form.validate_on_submit():
        # File Validation Logic
        files_to_save = {}
        validation_passed = True
        MAX_FILE_SIZE_BYTES = current_app.config['MAX_FILE_SIZE_MB'] * 1024 * 1024
        # Note: You should define ALLOWED_EXTENSIONS globally or pass it properly
        ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'} # Example

        for field in form:
            if field.type == 'FileField' and field.data:
                file = field.data
                filename = secure_filename(file.filename)
                field_label = field.label.text
                try:
                    file.seek(0, os.SEEK_END); file_size = file.tell(); file.seek(0)
                    if file_size == 0:
                        flash(f"File '{filename}' for '{field_label}' is empty.", 'warning')
                        validation_passed = False
                    elif file_size > MAX_FILE_SIZE_BYTES:
                        flash(f"File '{filename}' ({field_label}) exceeds {current_app.config['MAX_FILE_SIZE_MB']}MB limit.", 'danger')
                        validation_passed = False
                except Exception as e:
                    current_app.logger.error(f"Error checking file size for '{filename}': {e}")
                    flash(f"Could not check size of '{filename}'.", 'danger')
                    validation_passed = False
                
                if filename and ('.' not in filename or filename.rsplit('.', 1)[1].lower() not in ALLOWED_EXTENSIONS):
                    flash(f"File type for '{filename}' ({field_label}) not allowed.", 'danger')
                    validation_passed = False
                
                if validation_passed and file_size > 0:
                    files_to_save[field.name] = file

        if not validation_passed:
            return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')

        # Collect Details Data
        details_data = {}
        general_fields = {f.name for f in GeneralTicketForm()}
        for field in form:
            if field.name not in general_fields and field.type not in ['FileField', 'CSRFTokenField', 'SubmitField']:
                if field.type == 'DateField':
                    details_data[field.name] = field.data.strftime('%Y-%m-%d') if field.data else None
                else:
                    details_data[field.name] = field.data

        # Save Files and Ticket
        saved_filenames_map = {}
        try:
            for field_name, file_to_save in files_to_save.items():
                original_filename = secure_filename(file_to_save.filename)
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
                filename_to_save = f"{timestamp}_{field_name}_{original_filename}"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename_to_save)
                file_to_save.save(save_path)
                saved_filenames_map[field_name] = filename_to_save
                current_app.logger.info(f"Saved file: {filename_to_save}")
        except Exception as e:
            current_app.logger.error(f"Error saving files for new ticket: {e}", exc_info=True)
            flash('Error saving attachments. Please try again.', 'danger')
            return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')

        # Ticket Number Generation
        current_year = datetime.now(timezone.utc).year
        dept_code_map = {"ICT": "ICT", "Personnel": "PERS", "Legal Services": "LEGAL", "Office of the SDS": "SDS", "Accounting Unit": "ACCT", "Supply Office": "SUP"}
        dept_code = dept_code_map.get(service.department.name, "GEN")
        last_ticket = Ticket.query.filter(Ticket.ticket_number.like(f'{dept_code}-{current_year}-%')).order_by(Ticket.id.desc()).first()
        new_sequence = (int(last_ticket.ticket_number.split('-')[-1]) + 1) if last_ticket else 1
        new_ticket_number = f'{dept_code}-{current_year}-{new_sequence:04d}'

        # Create and Save Ticket
        new_ticket = Ticket(
            ticket_number=new_ticket_number,
            requester_name=form.requester_name.data,
            requester_email=form.requester_email.data,
            requester_contact=form.requester_contact.data,
            school_id=form.school.data,
            department_id=service.department.id,
            service_id=service.id,
            status='Open',
            details=details_data
        )
        try:
            db.session.add(new_ticket)
            db.session.commit() # Commit to get new_ticket.id
            
            # Save Attachment Records
            for saved_filename in saved_filenames_map.values():
                db.session.add(Attachment(filename=saved_filename, ticket_id=new_ticket.id))
            db.session.commit() # Commit attachments
            
            current_app.logger.info(f"New ticket {new_ticket_number} created by {form.requester_email.data}")
            send_new_ticket_email(new_ticket)
            flash(f'Ticket created! Confirmation sent. Your ticket number is {new_ticket_number}.', 'success')
            
            if current_user.is_authenticated:
                return redirect(url_for('tickets.my_tickets')) # Correct redirect
            else:
                return redirect(url_for('tickets.select_department')) # Correct redirect
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"DB error creating ticket {new_ticket_number}: {e}", exc_info=True)
            flash('Database error creating ticket. Please try again.', 'danger')
            # Optional: Delete saved files here
            return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')

    return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')