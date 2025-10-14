import os
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

# --- IMPORTS FROM OUR PROJECT FILES ---
from models import db, User, Department, Service, School, Ticket, Attachment, Response, CannedResponse
from forms import (
    DepartmentSelectionForm, ServiceSelectionForm, GeneralTicketForm, LoginForm,
    IssuanceForm, RepairForm, EmailAccountForm, DpdsForm, DcpForm, OtherIctForm,
    LeaveApplicationForm, CoeForm, ServiceRecordForm, GsisForm, NoPendingCaseForm
)

# --- App Initialization and Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SECRET_KEY'] = 'a-really-long-and-secret-string-nobody-can-guess'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
instance_path = os.path.join(basedir, 'instance')
os.makedirs(instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'eservices.db')
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024

# --- Extensions ---
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# (CLI Commands like seed-db and create-admin remain unchanged)
# ...

# =================================================================
# === MAIN ROUTES =================================================
# =================================================================

@app.route('/')
@login_required
def home():
    tickets = Ticket.query.order_by(Ticket.date_posted.desc()).all()
    return render_template('dashboard.html', tickets=tickets)

@app.route('/ticket/<int:ticket_id>')
@login_required
def ticket_detail(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        flash('Ticket not found!', 'error')
        return redirect(url_for('home'))
    details_pretty = json.dumps(ticket.details, indent=2) if ticket.details else "No additional details."
    return render_template('ticket_detail.html', ticket=ticket, details_pretty=details_pretty)

# =================================================================
# === 3-STEP TICKET CREATION FLOW =================================
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
    }
    FormClass = form_map.get(service.name, GeneralTicketForm)
    form = FormClass()

    if form.validate_on_submit():
        details_data = {}
        general_fields = {field.name for field in GeneralTicketForm()}
        for field in form:
            if field.name not in general_fields:
                if field.type == 'DateField':
                    details_data[field.name] = field.data.strftime('%Y-%m-%d') if field.data else None
                elif field.type not in ['FileField', 'CSRFTokenField', 'SubmitField']:
                    details_data[field.name] = field.data

        saved_filenames = []
        for field in form:
            if field.type == 'FileField' and hasattr(field, 'data') and field.data:
                file = field.data
                filename = secure_filename(f"{field.name}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                saved_filenames.append(filename)

        current_year = datetime.now(timezone.utc).year
        last_ticket = Ticket.query.order_by(Ticket.id.desc()).first()
        new_sequence = (int(last_ticket.ticket_number.split('-')[-1]) + 1) if last_ticket else 1
        new_ticket_number = f'TCSD-{current_year}-{new_sequence:04d}'

        new_ticket = Ticket(
            ticket_number=new_ticket_number, requester_name=form.requester_name.data,
            requester_email=form.requester_email.data, requester_contact=form.requester_contact.data,
            school_id=form.school.data, department_id=service.department.id,
            service_id=service.id, status='Open', details=details_data
        )
        db.session.add(new_ticket)
        db.session.commit()

        for fname in saved_filenames:
            db.session.add(Attachment(filename=fname, ticket_id=new_ticket.id))
        db.session.commit()

        flash(f'Your ticket has been created! Your ticket number is {new_ticket_number}.', 'success')
        return redirect(url_for('home'))

    return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')

# =================================================================
# === USER AUTHENTICATION ROUTES ==================================
# =================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form, title='Login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# =================================================================

if __name__ == '__main__':
    app.run(debug=True)