import os
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

# --- IMPORTS FROM OUR PROJECT FILES ---
from models import db, User, Department, Service, School, Ticket, Attachment, Response, CannedResponse, AuthorizedEmail
from forms import (
    DepartmentSelectionForm, ServiceSelectionForm, GeneralTicketForm, LoginForm,
    IssuanceForm, RepairForm, EmailAccountForm, DpdsForm, DcpForm, OtherIctForm,
    LeaveApplicationForm, CoeForm, ServiceRecordForm, GsisForm, NoPendingCaseForm,
    LocatorSlipForm, AuthorityToTravelForm, OicDesignationForm, SubstituteTeacherForm, AdmForm,
    ProvidentFundForm, IcsForm, RegistrationForm, RequestResetForm, ResetPasswordForm
)

# --- App Initialization and Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.secret_key = 'a-really-long-and-secret-string-nobody-can-guess'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
instance_path = os.path.join(basedir, 'instance')
os.makedirs(instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'eservices.db')
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024

# --- Email Configuration ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'admin@deped.gov.ph' # PALITAN MO ITO
app.config['MAIL_PASSWORD'] = '1234567890123456' # PALITAN MO ITO




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
# === HELPER FUNCTIONS ============================================
# =================================================================

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender=('TCSD e-Services', app.config['MAIL_USERNAME']),
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made.
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
    AUTHORIZED_EMAILS = ['icts.tarlaccity@deped.gov.ph', 'esmeraldo.lingat@deped.gov.ph', 'pedro.penduko@deped.gov.ph']
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
# === MAIN ROUTES =================================================
# =================================================================

@app.route('/')
@login_required
def home():
    """Main dashboard view."""
    tickets = Ticket.query.order_by(Ticket.date_posted.desc()).all()
    return render_template('dashboard.html', tickets=tickets)

@app.route('/ticket/<int:ticket_id>')
@login_required
def ticket_detail(ticket_id):
    """View details of a single ticket."""
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

# PALITAN ANG BUONG LUMANG create_ticket_form FUNCTION NG ITO:

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

    # Ito ang tamang logic para sa auto-filling ng email
    if request.method == 'GET' and current_user.is_authenticated:
        form.requester_email.data = current_user.email

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
        
        flash(f'Your ticket has been created! Your ticket number is {new_ticket_number}.', 'success')
        return redirect(url_for('home'))
        
    return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')

# =================================================================
# === USER AUTHENTICATION ROUTES ==================================
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
# Ilagay ito sa ilalim ng @app.route('/') section sa app.py

@app.route('/my-tickets')
@login_required
def my_tickets():
    """Shows all tickets created by the current logged-in user."""

    # Kukunin natin lahat ng tickets kung saan ang email ng gumawa
    # ay pareho sa email ng kasalukuyang naka-login na user.
    tickets = Ticket.query.filter_by(requester_email=current_user.email)\
                           .order_by(Ticket.date_posted.desc())\
                           .all()

    return render_template('my_tickets.html', tickets=tickets, title='My Tickets')



if __name__ == '__main__':
    app.run(debug=True)