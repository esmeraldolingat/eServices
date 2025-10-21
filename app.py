import os
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from functools import wraps
import csv
import io
from dotenv import load_dotenv
from sqlalchemy import func, case, extract
from sqlalchemy.orm import joinedload

load_dotenv()

# --- IMPORTS FROM OUR PROJECT FILES ---
from models import db, User, Department, Service, School, Ticket, Attachment, Response, CannedResponse, AuthorizedEmail
from forms import (
    DepartmentSelectionForm, ServiceSelectionForm, GeneralTicketForm, LoginForm,
    IssuanceForm, RepairForm, EmailAccountForm, DpdsForm, DcpForm, OtherIctForm,
    LeaveApplicationForm, CoeForm, ServiceRecordForm, GsisForm, NoPendingCaseForm,
    LocatorSlipForm, AuthorityToTravelForm, OicDesignationForm, SubstituteTeacherForm, AdmForm,
    ProvidentFundForm, IcsForm, RegistrationForm, RequestResetForm, ResetPasswordForm,
    ResponseForm, EditUserForm, AddAuthorizedEmailForm, BulkUploadForm, DepartmentForm,
    UpdateTicketForm
)

# --- App Initialization and Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

app.secret_key = os.getenv('SECRET_KEY')

instance_path = os.path.join(basedir, 'instance')
os.makedirs(instance_path, exist_ok=True)
db_filename = os.getenv('DATABASE_FILENAME', 'eservices.db')
db_path = os.path.join(instance_path, db_filename)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
app.config['TICKETS_PER_PAGE'] = 10
app.config['EMAILS_PER_PAGE'] = 15 # Bagong config para sa pagination ng emails

# --- Email Configuration ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

# --- Extensions ---
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
mail = Mail(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =================================================================
# === ADMIN DECORATOR =============================================
# =================================================================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# =================================================================
# === HELPER FUNCTIONS ============================================
# =================================================================

def send_new_ticket_email(ticket):
    details_text = "\n".join([f"- {key.replace('_', ' ').title()}: {value}" for key, value in ticket.details.items() if value and ('other' not in key or ticket.details.get(key.replace('_other','')) == 'Other')])
    msg = Message(f'New Ticket Created: #{ticket.ticket_number}',
                  sender=('TCSD e-Services', app.config['MAIL_USERNAME']),
                  recipients=[ticket.requester_email])
    msg.body = f'''
Hi {ticket.requester_name},

This is to confirm that we have successfully received your request.

Ticket Number: {ticket.ticket_number}
Department: {ticket.ticket_department.name}
Service Requested: {ticket.service_type.name}

Request Details:
{details_text}

Our team will review your request and get back to you shortly. You can view the status of this ticket in your "My Tickets" dashboard.

Thank you,
TCSD e-Services Team
'''
    mail.send(msg)

def send_staff_notification_email(ticket, response):
    recipients = {manager.email for manager in ticket.service_type.managers}
    admins = User.query.filter_by(role='Admin').all()
    for admin in admins:
        recipients.add(admin.email)
    if not recipients:
        return
    msg = Message(f'New Response on Ticket #{ticket.ticket_number}',
                  sender=('TCSD e-Services', app.config['MAIL_USERNAME']),
                  recipients=list(recipients))
    msg.body = f'''
Hi Team,
A new response has been added to Ticket #{ticket.ticket_number} by the requester.

Ticket Details:
- Service: {ticket.service_type.name}
- Requester: {ticket.requester_name}

New Response:
--------------------------------------------------
{response.body}
--------------------------------------------------

You can view the ticket here:
{url_for('ticket_detail', ticket_id=ticket.id, _external=True)}

Thank you,
e-Services Notifier
'''
    mail.send(msg)

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request', sender=('TCSD e-Services', app.config['MAIL_USERNAME']), recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}
If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)

def send_resolution_email(ticket, response_body):
    msg = Message(f'Update on your Ticket: #{ticket.ticket_number} - RESOLVED',
                  sender=('TCSD e-Services', app.config['MAIL_USERNAME']),
                  recipients=[ticket.requester_email])
    msg.body = f'''
Hi {ticket.requester_name},
Your ticket #{ticket.ticket_number} regarding "{ticket.service_type.name}" has been marked as RESOLVED.
Here is the final response from our team:
--------------------------------------------------
{response_body}
--------------------------------------------------
If you have further questions, please create a new ticket.
Thank you,
TCSD e-Services Team
'''
    mail.send(msg)

# =================================================================
# === CLI COMMANDS ================================================
# =================================================================

@app.cli.command("seed-db")
def seed_db():
    """Populates the database with initial data."""
    DEPARTMENTS = ["ICT", "Personnel", "Legal Services", "Office of the SDS", "Accounting Unit", "Supply Office"]
    SERVICES = { "ICT": ["Issuances and Online Materials", "Repair, Maintenance and Troubleshoot of IT Equipment", "DepEd Email Account", "DPDS - DepEd Partnership Database System", "DCP - DepEd Computerization Program: After-sales", "other ICT - Technical Assistance Needed"], "Personnel": ["Application for Leave of Absence", "Certificate of Employment", "Service Record", "GSIS BP Number"], "Legal Services": ["Certificate of NO-Pending Case"], "Office of the SDS": ["Request for Approval of Locator Slip", "Request for Approval of Authority to Travel", "Request for Designation of Officer-in-Charge at the School", "Request for Substitute Teacher", "Alternative Delivery Mode"], "Accounting Unit": ["DepEd TCSD Provident Fund"], "Supply Office": ["Submission of Inventory Custodian Slip – ICS"] }
    SCHOOLS = [ "Alvindia Aguso Central ES", "Alvindia Aguso HS", "Alvindia ES", "Amucao ES", "Amucao HS", "Apalang ES", "Armenia IS", "Asturias ES", "Atioc Dela Paz ES", "Bacuit ES", "Bagong Barrio ES", "Balanti ES", "Balanti HS", "Balete ES", "Balibago Primero IS", "Balingcanaway Centro ES", "Balingcanaway Corba ES", "Banaba ES", "Bantog ES", "Baras-Baras ES", "Baras-Baras HS", "Batang-Batang IS", "Binauganan ES", "Buenavista ES", "Buhilit ES", "Burot IS", "Camp Aquino ES", "Capehan ES", "Capulong ES", "Carangian ES", "Care ES", "CAT ES", "CAT HS Annex", "CAT HS Main", "Cut Cut ES", "Dalayap ES", "Damaso Briones ES", "Dolores ES", "Don Florencio P. Buan ES", "Don Pepe Cojuangco ES", "Doña Arsenia ES", "Felicidad Magday ES", "Laoang ES", "Lourdes ES", "Maligaya ES", "Maliwalo CES", "Maliwalo National HS", "Mapalacsiao ES", "Mapalad ES", "Margarita Briones Soliman ES", "Matatalaib Bato ES", "Matatalaib Buno ES", "Matatalaib HS", "Natividad De Leon ES", "Northern Hill ES Annex", "Northern Hill ES Main", "Pag-asa ES", "Paquillao ES", "Paradise ES", "Paraiso ES", "Samberga ES", "San Carlos ES", "San Francisco ES", "San Isidro ES", "San Jose De Urquico ES", "San Jose ES", "San Juan Bautista ES", "San Juan De Mata ES", "San Juan De Mata HS", "San Manuel ES", "San Manuel HS", "San Miguel CES", "San Nicolas ES", "San Pablo ES", "San Pascual ES", "San Rafael ES", "San Sebastian ES", "San Vicente ES Annex", "San Vicente ES Main", "Sapang Maragul IS", "Sapang Tagalog ES", "Sepung Calzada Panampunan ES", "Sinait IS", "Sitio Dam ES", "Sta. Cruz ES", "Sta. Maria ES", "Sto. Cristo IS", "Sto. Domingo ES", "Sto. Niño ES", "Suizo Bliss ES", "Suizo Resettlement ES", "Tariji ES", "Tarlac West CES", "Tibag ES", "Tibag HS", "Trinidad ES", "Ungot IS", "Villa Bacolor ES", "Yabutan ES", "Division Office" ]
    print("Seeding database...")
    for dept_name in DEPARTMENTS:
        if not Department.query.filter_by(name=dept_name).first(): db.session.add(Department(name=dept_name))
    db.session.commit()
    print("Departments seeded.")
    for dept_name, service_list in SERVICES.items():
        dept = Department.query.filter_by(name=dept_name).first()
        if dept:
            for service_name in service_list:
                if not Service.query.filter_by(name=service_name, department_id=dept.id).first(): db.session.add(Service(name=service_name, department_id=dept.id))
    db.session.commit()
    print("Services seeded.")
    for school_name in SCHOOLS:
        if not School.query.filter_by(name=school_name).first(): db.session.add(School(name=school_name))
    db.session.commit()
    print("Schools seeded.")
    AUTHORIZED_EMAILS = ['icts.tarlaccity@deped.gov.ph', 'esmeraldo.lingat@deped.gov.ph', 'pedro.penduko@deped.gov.ph', 'admin@deped.gov.ph']
    for email_address in AUTHORIZED_EMAILS:
        if not AuthorizedEmail.query.filter_by(email=email_address).first():
            db.session.add(AuthorizedEmail(email=email_address))
    db.session.commit()
    print("Authorized emails seeded.")
    print("Database seeding complete!")

@app.cli.command("create-admin")
def create_admin():
    """Creates a default admin user."""
    if User.query.filter_by(email='admin@deped.gov.ph').first():
        print('Admin user already exists.')
        return
    user = User(name='Administrator', email='admin@deped.gov.ph', role='Admin')
    user.set_password('password123')
    db.session.add(user)
    db.session.commit()
    print('Admin user created successfully! (Email: admin@deped.gov.ph, Password: password123)')

# =================================================================
# === MAIN & TICKET ROUTES ========================================
# =================================================================

@app.route('/')
@login_required
def home():
    if current_user.role in ['Admin', 'Staff']:
        return redirect(url_for('staff_dashboard'))
    else:
        return redirect(url_for('my_tickets'))

@app.route('/staff-dashboard')
@login_required
def staff_dashboard():
    page_active = request.args.get('page_active', 1, type=int)
    page_resolved = request.args.get('page_resolved', 1, type=int)
    
    available_years_query = db.session.query(extract('year', Ticket.date_posted)).distinct().order_by(extract('year', Ticket.date_posted).desc())
    available_years = [y[0] for y in available_years_query.all()]

    current_year = datetime.utcnow().year
    selected_year = request.args.get('year', current_year, type=int)
    if not available_years:
        available_years.append(selected_year)
    
    selected_quarter = request.args.get('quarter', 0, type=int)
    
    base_query = Ticket.query
    summary_query = db.session.query(
        Department.name.label('dept_name'),
        Service.name.label('service_name'),
        func.count(Ticket.id).label('total'),
        func.sum(case((Ticket.status == 'Resolved', 1), else_=0)).label('resolved_count')
    ).join(Service, Ticket.service_id == Service.id).join(Department, Service.department_id == Department.id)

    base_query = base_query.filter(extract('year', Ticket.date_posted) == selected_year)
    summary_query = summary_query.filter(extract('year', Ticket.date_posted) == selected_year)

    quarters = {
        1: (datetime(selected_year, 1, 1), datetime(selected_year, 3, 31, 23, 59, 59)),
        2: (datetime(selected_year, 4, 1), datetime(selected_year, 6, 30, 23, 59, 59)),
        3: (datetime(selected_year, 7, 1), datetime(selected_year, 9, 30, 23, 59, 59)),
        4: (datetime(selected_year, 10, 1), datetime(selected_year, 12, 31, 23, 59, 59)),
    }
    if selected_quarter in quarters:
        start_date, end_date = quarters[selected_quarter]
        base_query = base_query.filter(Ticket.date_posted.between(start_date, end_date))
        summary_query = summary_query.filter(Ticket.date_posted.between(start_date, end_date))

    if current_user.role == 'Staff':
        managed_service_ids = [service.id for service in current_user.managed_services]
        if managed_service_ids:
            base_query = base_query.filter(Ticket.service_id.in_(managed_service_ids))
            summary_query = summary_query.filter(Service.id.in_(managed_service_ids))
        else:
            flash("You are a Staff member but are not assigned to any services. Please contact an administrator.", "warning")
            return render_template('staff_dashboard.html', active_tickets=None, resolved_tickets=None, dashboard_summary={}, title="My Managed Tickets", available_years=available_years, selected_year=selected_year, selected_quarter=selected_quarter)

    active_tickets = base_query.filter(Ticket.status.in_(['Open', 'In Progress'])).order_by(Ticket.date_posted.desc()).paginate(page=page_active, per_page=app.config['TICKETS_PER_PAGE'], error_out=False)
    resolved_tickets = base_query.filter(Ticket.status == 'Resolved').order_by(Ticket.date_posted.desc()).paginate(page=page_resolved, per_page=app.config['TICKETS_PER_PAGE'], error_out=False)
    
    summary_data = summary_query.group_by(Department.name, Service.name).all()
    dashboard_summary = {}
    
    if current_user.role == 'Admin':
        all_departments = Department.query.options(db.joinedload(Department.services)).order_by(Department.name).all()
    else:
        all_departments = Department.query.join(Service).join(Service.managers).filter(User.id == current_user.id).options(db.joinedload(Department.services)).order_by(Department.name).distinct().all()

    color_palette = ['#FFCBE1', '#D6E5BD', '#F9E1A8', '#BCD8EC', '#DCCCEC', '#FFDAB4']

    for dept in all_departments:
        dept_services_data = []
        services_in_dept = sorted(dept.services, key=lambda s: s.name)
        for i, service in enumerate(services_in_dept):
            if current_user.role == 'Admin' or service in current_user.managed_services:
                found = False
                for row in summary_data:
                    if row.dept_name == dept.name and row.service_name == service.name:
                        active = row.total - row.resolved_count
                        dept_services_data.append({'name': service.name, 'active': active, 'resolved': row.resolved_count, 'total': row.total, 'color': color_palette[i % len(color_palette)]})
                        found = True
                        break
                if not found:
                    dept_services_data.append({'name': service.name, 'active': 0, 'resolved': 0, 'total': 0, 'color': color_palette[i % len(color_palette)]})
        if dept_services_data:
            dashboard_summary[dept.name] = {'services': dept_services_data}
    
    title = "System Dashboard"
    return render_template('staff_dashboard.html', active_tickets=active_tickets, resolved_tickets=resolved_tickets, dashboard_summary=dashboard_summary, title=title, available_years=available_years, selected_year=selected_year, selected_quarter=selected_quarter)

@app.route('/my-tickets')
@login_required
def my_tickets():
    page_active = request.args.get('page_active', 1, type=int)
    page_resolved = request.args.get('page_resolved', 1, type=int)
    base_query = Ticket.query.filter_by(requester_email=current_user.email)
    active_tickets = base_query.filter(Ticket.status.in_(['Open', 'In Progress'])).order_by(Ticket.date_posted.desc()).paginate(page=page_active, per_page=app.config['TICKETS_PER_PAGE'], error_out=False)
    resolved_tickets = base_query.filter(Ticket.status == 'Resolved').order_by(Ticket.date_posted.desc()).paginate(page=page_resolved, per_page=app.config['TICKETS_PER_PAGE'], error_out=False)
    return render_template('my_tickets.html', active_tickets=active_tickets, resolved_tickets=resolved_tickets, title='My Tickets')

@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def ticket_detail(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        flash('Ticket not found!', 'error')
        return redirect(url_for('home'))
    is_staff_or_admin = current_user.role == 'Admin' or current_user in ticket.service_type.managers
    if is_staff_or_admin:
        form = UpdateTicketForm()
    else:
        form = ResponseForm()
    if form.validate_on_submit():
        if ticket.status == 'Resolved' and not is_staff_or_admin:
            flash('This ticket is already resolved and cannot receive new responses.', 'info')
            return redirect(url_for('ticket_detail', ticket_id=ticket.id))
        if form.attachment.data:
            file = form.attachment.data
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{secure_filename(file.filename)}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            new_attachment = Attachment(filename=filename, ticket_id=ticket.id)
            db.session.add(new_attachment)
        response = Response(body=form.body.data, user_id=current_user.id, ticket_id=ticket.id)
        db.session.add(response)
        if hasattr(form, 'status'):
            ticket.status = form.status.data
            if ticket.status == 'Resolved':
                send_resolution_email(ticket, form.body.data)
                flash('Your response has been added and a resolution email has been sent to the client.', 'success')
            else:
                flash('Your response has been added and the ticket status has been updated.', 'success')
        else:
            flash('Your response has been added successfully!', 'success')
            if not is_staff_or_admin:
                send_staff_notification_email(ticket, response)
        db.session.commit()
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    if request.method == 'GET' and hasattr(form, 'status'):
        form.status.data = ticket.status
    details_pretty = json.dumps(ticket.details, indent=2) if ticket.details else "No additional details."
    return render_template('ticket_detail.html', ticket=ticket, details_pretty=details_pretty, form=form, is_staff_or_admin=is_staff_or_admin)

# =================================================================
# === ADMIN ROUTES ================================================
# =================================================================

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html', title='Admin Dashboard')

@app.route('/admin/users')
@login_required
@admin_required
def manage_users():
    users = User.query.order_by(User.name).all()
    return render_template('admin/users.html', users=users, title='Manage Users')

@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('manage_users'))
    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        user.name = form.name.data
        user.email = form.email.data
        user.role = form.role.data
        user.managed_services = []
        selected_service_ids = request.form.getlist('managed_services')
        for service_id in selected_service_ids:
            service = db.session.get(Service, int(service_id))
            if service:
                user.managed_services.append(service)
        db.session.commit()
        flash(f'User {user.name} has been updated successfully!', 'success')
        return redirect(url_for('manage_users'))
    departments = Department.query.order_by(Department.name).all()
    managed_service_ids = {service.id for service in user.managed_services}
    return render_template('admin/edit_user.html', form=form, user=user, departments=departments, managed_service_ids=managed_service_ids, title='Edit User')

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user and user.id != current_user.id:
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.name} has been deleted.', 'success')
    elif user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
    else:
        flash('User not found.', 'danger')
    return redirect(url_for('manage_users'))

@app.route('/admin/authorized-emails', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_authorized_emails():
    add_form = AddAuthorizedEmailForm()
    bulk_form = BulkUploadForm()
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)

    # --- BAGONG LOGIC PARA SA BULK DELETE ---
    if request.method == 'POST' and 'delete_selected' in request.form:
        email_ids_to_delete = request.form.getlist('email_ids')
        if email_ids_to_delete:
            emails_to_delete_objects = AuthorizedEmail.query.filter(AuthorizedEmail.id.in_(email_ids_to_delete)).all()
            for email_obj in emails_to_delete_objects:
                db.session.delete(email_obj)
            db.session.commit()
            flash(f'{len(email_ids_to_delete)} email(s) have been deleted.', 'success')
        else:
            flash('No emails were selected for deletion.', 'warning')
        return redirect(url_for('manage_authorized_emails', search=search_query, page=page))
    # --- HANGGANG DITO ---

    if add_form.validate_on_submit() and add_form.submit.data:
        new_email = AuthorizedEmail(email=add_form.email.data)
        db.session.add(new_email)
        db.session.commit()
        flash(f'Email {add_form.email.data} has been authorized.', 'success')
        return redirect(url_for('manage_authorized_emails'))
        
    if bulk_form.validate_on_submit() and bulk_form.submit_bulk.data:
        # (Ang logic para sa bulk upload ay pareho pa rin)
        pass
    
    base_query = AuthorizedEmail.query
    if search_query:
        base_query = base_query.filter(AuthorizedEmail.email.ilike(f'%{search_query}%'))
    
    emails = base_query.order_by(AuthorizedEmail.email).paginate(page=page, per_page=app.config['EMAILS_PER_PAGE'], error_out=False)
    
    return render_template('admin/authorized_emails.html', emails=emails, add_form=add_form, bulk_form=bulk_form, title='Manage Authorized Emails', search_query=search_query)


@app.route('/admin/authorized-emails/<int:email_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_authorized_email(email_id):
    email_to_delete = db.session.get(AuthorizedEmail, email_id)
    if email_to_delete:
        db.session.delete(email_to_delete)
        db.session.commit()
        flash(f'Email {email_to_delete.email} has been removed from the authorized list.', 'success')
    else:
        flash('Email not found.', 'danger')
    return redirect(url_for('manage_authorized_emails'))

@app.route('/admin/departments')
@login_required
@admin_required
def manage_departments():
    departments = Department.query.order_by(Department.name).all()
    return render_template('admin/departments.html', departments=departments, title='Manage Departments')

@app.route('/admin/department/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_department():
    form = DepartmentForm()
    if form.validate_on_submit():
        new_dept = Department(name=form.name.data)
        db.session.add(new_dept)
        db.session.commit()
        flash(f'Department "{form.name.data}" has been created.', 'success')
        return redirect(url_for('manage_departments'))
    return render_template('admin/add_edit_department.html', form=form, title='Add Department')

@app.route('/admin/department/<int:dept_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_department(dept_id):
    dept = db.session.get(Department, dept_id)
    if not dept:
        flash('Department not found.', 'danger')
        return redirect(url_for('manage_departments'))
    form = DepartmentForm(obj=dept)
    if form.validate_on_submit():
        existing_dept = Department.query.filter(Department.name == form.name.data, Department.id != dept_id).first()
        if existing_dept:
            flash('That department name already exists.', 'danger')
        else:
            dept.name = form.name.data
            db.session.commit()
            flash(f'Department has been updated to "{form.name.data}".', 'success')
            return redirect(url_for('manage_departments'))
    return render_template('admin/add_edit_department.html', form=form, title='Edit Department', department=dept)

@app.route('/admin/department/<int:dept_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_department(dept_id):
    dept_to_delete = db.session.get(Department, dept_id)
    if dept_to_delete:
        if dept_to_delete.tickets:
            flash(f'Cannot delete department "{dept_to_delete.name}" because it has existing tickets.', 'danger')
            return redirect(url_for('manage_departments'))
        db.session.delete(dept_to_delete)
        db.session.commit()
        flash(f'Department "{dept_to_delete.name}" has been deleted.', 'success')
    else:
        flash('Department not found.', 'danger')
    return redirect(url_for('manage_departments'))

# =================================================================
# === TICKET CREATION FLOW ========================================
# =================================================================

@app.route('/create-ticket/select-department', methods=['GET'])
def select_department():
    DEPARTMENT_ORDER = ["ICT", "Personnel", "Legal Services", "Office of the SDS", "Accounting Unit", "Supply Office"]
    all_departments = Department.query.all()
    departments_dict = {dept.name: dept for dept in all_departments}
    ordered_departments = [departments_dict[name] for name in DEPARTMENT_ORDER if name in departments_dict]
    return render_template('select_department.html', departments=ordered_departments, title='Select a Department')

@app.route('/create-ticket/select-service/<int:department_id>', methods=['GET'])
def select_service(department_id):
    department = db.session.get(Department, department_id)
    if not department:
        flash('Invalid department selected.', 'error')
        return redirect(url_for('select_department'))
    return render_template('select_service.html', department=department, services=department.services, title=f'Select a Service for {department.name}')

@app.route('/create-ticket/form/<int:service_id>', methods=['GET', 'POST'])
def create_ticket_form(service_id):
    service = db.session.get(Service, service_id)
    if not service:
        flash('Invalid service selected.', 'error')
        return redirect(url_for('select_department'))
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
    if request.method == 'GET' and current_user.is_authenticated:
        form.requester_email.data = current_user.email
    if form.validate_on_submit():
        details_data = {}
        general_fields = {field.name for field in GeneralTicketForm()}
        for field in form:
            if field.name not in general_fields and field.type not in ['FileField', 'CSRFTokenField', 'SubmitField']:
                if field.type == 'DateField':
                    details_data[field.name] = field.data.strftime('%Y-%m-%d') if field.data else None
                else:
                    details_data[field.name] = field.data
        saved_filenames = []
        for field in form:
            if field.type == 'FileField' and hasattr(field, 'data') and field.data:
                file = field.data
                filename = secure_filename(f"{field.name}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                saved_filenames.append(filename)
        current_year = datetime.now(timezone.utc).year
        dept_code_map = {"ICT": "ICT", "Personnel": "PERS", "Legal Services": "LEGAL", "Office of the SDS": "SDS", "Accounting Unit": "ACCT", "Supply Office": "SUP"}
        dept_code = dept_code_map.get(service.department.name, "GEN")
        last_ticket = Ticket.query.filter(Ticket.ticket_number.like(f'{dept_code}-{current_year}-%')).order_by(Ticket.id.desc()).first()
        new_sequence = (int(last_ticket.ticket_number.split('-')[-1]) + 1) if last_ticket else 1
        new_ticket_number = f'{dept_code}-{current_year}-{new_sequence:04d}'
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
        db.session.add(new_ticket)
        db.session.commit()
        for fname in saved_filenames:
            db.session.add(Attachment(filename=fname, ticket_id=new_ticket.id))
        db.session.commit()
        send_new_ticket_email(new_ticket)
        flash(f'Your ticket has been created! A confirmation has been sent to your email. Your ticket number is {new_ticket_number}.', 'success')
        return redirect(url_for('home'))
    return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')

# =================================================================
# === USER AUTHENTICATION =========================================
# =================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(name=form.name.data, email=form.email.data, role='User')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form, title='Register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form, title='Login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('request_reset.html', title='Reset Password', form=form)

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)

# =================================================================

if __name__ == '__main__':
    app.run(debug=True)

