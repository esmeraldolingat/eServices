import os
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
# At the top of app.py, update your forms import
from forms import (
    DepartmentSelectionForm, ServiceSelectionForm, GeneralTicketForm, LoginForm,
    IssuanceForm, RepairForm, EmailAccountForm, DpdsForm, DcpForm, OtherIctForm
)
from werkzeug.utils import secure_filename # Add this import for file uploads

# --- IMPORTS MULA SA IBANG FILES ---
# Import natin ang db object at LAHAT ng models mula sa models.py
from models import db, User, Department, Service, School, Ticket, Attachment, Response, CannedResponse
# Import natin ang mga forms mula sa forms.py (isang beses lang)
from forms import DepartmentSelectionForm, ServiceSelectionForm, GeneralTicketForm, LoginForm, RepairForm

# --- App Initialization and Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SECRET_KEY'] = 'a-really-long-and-secret-string-nobody-can-guess'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database Config - Ensure the instance folder exists
instance_path = os.path.join(basedir, 'instance')
os.makedirs(instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'eservices.db')

# File Upload Config
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB limit

# --- Extensions ---
# I-connect natin ang db object sa ating app
db.init_app(app)
migrate = Migrate(app, db)

# --- LOGIN MANAGER SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =================================================================
# === CLI COMMANDS (Para sa setup) ================================
# =================================================================

@app.cli.command("seed-db")
def seed_db():
    """Populates the database with initial data."""
    DEPARTMENTS = ["ICT", "Personnel", "Legal Services", "Office of the SDS", "Accounting Unit", "Supply Office"]
    SERVICES = { "ICT": ["Issuances and Online Materials", "Repair, Maintenance and Troubleshoot of IT Equipment", "DepEd Email Account", "DPDS - DepEd Partnership Database System", "DCP - DepEd Computerization Program: After-sales", "other ICT - Technical Assistance Needed"], "Personnel": ["Application for Leave of Absence", "Certificate of Employment", "Service Record", "GSIS BP Number"], "Legal Services": ["Certificate of NO-Pending Case"], "Office of the SDS": ["Request for Approval of Locator Slip", "Request for Approval of Authority to Travel", "Request for Designation of Officer-in-Charge at the School", "Request for Substitute Teacher", "Alternative Delivery Mode"], "Accounting Unit": ["DepEd TCSD Provident Fund"], "Supply Office": ["Submission of Inventory Custodian Slip – ICS"] }
    SCHOOLS = [ "Alvindia Aguso Central ES", "Alvindia Aguso HS", "Alvindia ES", "Amucao ES", "Amucao HS", "Apalang ES", "Armenia IS", "Asturias ES", "Atioc Dela Paz ES", "Bacuit ES", "Bagong Barrio ES", "Balanti ES", "Balanti HS", "Balete ES", "Balibago Primero IS", "Balingcanaway Centro ES", "Balingcanaway Corba ES", "Banaba ES", "Bantog ES", "Baras-Baras ES", "Baras-Baras HS", "Batang-Batang IS", "Binauganan ES", "Buenavista ES", "Buhilit ES", "Burot IS", "Camp Aquino ES", "Capehan ES", "Capulong ES", "Carangian ES", "Care ES", "CAT ES", "CAT HS Annex", "CAT HS Main", "Cut Cut ES", "Dalayap ES", "Damaso Briones ES", "Dolores ES", "Don Florencio P. Buan ES", "Don Pepe Cojuangco ES", "Doña Arsenia ES", "Felicidad Magday ES", "Laoang ES", "Lourdes ES", "Maligaya ES", "Maliwalo CES", "Maliwalo National HS", "Mapalacsiao ES", "Mapalad ES", "Margarita Briones Soliman ES", "Matatalaib Bato ES", "Matatalaib Buno ES", "Matatalaib HS", "Natividad De Leon ES", "Northern Hill ES Annex", "Northern Hill ES Main", "Pag-asa ES", "Paquillao ES", "Paradise ES", "Paraiso ES", "Samberga ES", "San Carlos ES", "San Francisco ES", "San Isidro ES", "San Jose De Urquico ES", "San Jose ES", "San Juan Bautista ES", "San Juan De Mata ES", "San Juan De Mata HS", "San Manuel ES", "San Manuel HS", "San Miguel CES", "San Nicolas ES", "San Pablo ES", "San Pascual ES", "San Rafael ES", "San Sebastian ES", "San Vicente ES Annex", "San Vicente ES Main", "Sapang Maragul IS", "Sapang Tagalog ES", "Sepung Calzada Panampunan ES", "Sinait IS", "Sitio Dam ES", "Sta. Cruz ES", "Sta. Maria ES", "Sto. Cristo IS", "Sto. Domingo ES", "Sto. Niño ES", "Suizo Bliss ES", "Suizo Resettlement ES", "Tariji ES", "Tarlac West CES", "Tibag ES", "Tibag HS", "Trinidad ES", "Ungot IS", "Villa Bacolor ES", "Yabutan ES", "Division Office" ]
    print("Seeding database...")
    for dept_name in DEPARTMENTS:
        if not Department.query.filter_by(name=dept_name).first():
            db.session.add(Department(name=dept_name))
    db.session.commit()
    print("Departments seeded.")
    for dept_name, service_list in SERVICES.items():
        dept = Department.query.filter_by(name=dept_name).first()
        if dept:
            for service_name in service_list:
                if not Service.query.filter_by(name=service_name, department_id=dept.id).first():
                    db.session.add(Service(name=service_name, department_id=dept.id))
    db.session.commit()
    print("Services seeded.")
    for school_name in SCHOOLS:
        if not School.query.filter_by(name=school_name).first():
            db.session.add(School(name=school_name))
    db.session.commit()
    print("Schools seeded.")
    print("Database seeding complete!")

@app.cli.command("create-admin")
def create_admin():
    """Creates a default admin user."""
    if User.query.filter_by(username='admin').first():
        print('Admin user already exists.')
        return
    user = User(username='admin', role='Admin')
    user.set_password('password123')
    db.session.add(user)
    db.session.commit()
    print('Admin user created successfully! (Username: admin, Password: password123)')

# =================================================================
# === MAIN ROUTES SECTION =========================================
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

# app.py

@app.route('/create-ticket/select-department', methods=['GET', 'POST'])
def select_department():
    """
    STEP 1: User selects a Department.
    (UPDATED to serve departments in a custom order)
    """
    # Ito ang specific order na gusto natin
    DEPARTMENT_ORDER = [
        "ICT", 
        "Personnel", 
        "Legal Services", 
        "Office of the SDS", 
        "Accounting Unit", 
        "Supply Office"
    ]
    
    # Kukunin natin lahat ng departments
    all_departments = Department.query.all()
    
    # I-oorganize natin sila sa isang dictionary para madaling hanapin
    departments_dict = {dept.name: dept for dept in all_departments}
    
    # Gagawa tayo ng bagong listahan na sumusunod sa ating custom order
    ordered_departments = []
    for name in DEPARTMENT_ORDER:
        if name in departments_dict:
            ordered_departments.append(departments_dict[name])

    # Hindi na natin kailangan ng form dito dahil clickable na ang cards
    # Ang ipapasa na lang natin sa template ay ang listahan ng departments
    return render_template('select_department.html', 
                           departments=ordered_departments, 
                           title='Select a Department')

# app.py

@app.route('/create-ticket/select-service/<int:department_id>', methods=['GET'])
def select_service(department_id):
    """
    STEP 2: User selects a Service from the chosen Department.
    (UPDATED to display services as cards instead of a form)
    """
    department = db.session.get(Department, department_id)
    if not department:
        flash('Invalid department selected.', 'error')
        return redirect(url_for('select_department'))
    
    # Kukunin lang natin ang listahan ng services para sa department na ito
    services_for_department = department.services

    # At ipapasa natin ang listahan direkta sa template
    return render_template('select_service.html', 
                           department=department,
                           services=services_for_department, 
                           title=f'Select a Service for {department.name}')

# Replace the old create_ticket_form function with this new one
@app.route('/create-ticket/form/<int:service_id>', methods=['GET', 'POST'])
def create_ticket_form(service_id):
    """STEP 3: User fills out the final form for the selected service."""
    service = db.session.get(Service, service_id)
    if not service:
        flash('Invalid service selected.', 'error')
        return redirect(url_for('select_department'))

    # === Form Router: Selects the correct form based on service name ===
    form_map = {
        'Issuances and Online Materials': IssuanceForm,
        'Repair, Maintenance and Troubleshoot of IT Equipment': RepairForm,
        'DepEd Email Account': EmailAccountForm,
        'DPDS - DepEd Partnership Database System': DpdsForm,
        'DCP - DepEd Computerization Program: After-sales': DcpForm,
        'other ICT - Technical Assistance Needed': OtherIctForm,
    }
    # Get the correct form class from the map, or use the general one as a fallback
    FormClass = form_map.get(service.name, GeneralTicketForm)
    form = FormClass()

    if form.validate_on_submit():
        # === Data Processor: Collects data from the specific form ===
        details_data = {}
        # Get all fields that are NOT part of the GeneralTicketForm
        general_fields = [field for field in GeneralTicketForm()]
        for field in form:
            if field.name not in general_fields:
                if field.type == 'DateField': # Format date correctly
                    details_data[field.name] = field.data.strftime('%Y-%m-%d') if field.data else None
                else:
                    details_data[field.name] = field.data

        # === File Handler: Saves uploaded files ===
        saved_filenames = []
        if 'attachment' in form and form.attachment.data:
            file = form.attachment.data
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            saved_filenames.append(filename)

        # === Ticket Creator: Builds and saves the ticket to the database ===
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
        db.session.commit() # Commit here to get a ticket.id for the attachment

        # Link attachments to the new ticket
        for fname in saved_filenames:
            attachment_record = Attachment(filename=fname, ticket_id=new_ticket.id)
            db.session.add(attachment_record)
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