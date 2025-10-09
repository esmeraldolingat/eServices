import os
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# --- BAGONG IMPORTS ---
# Import natin ang db object at LAHAT ng models mula sa models.py
from models import db, User, Department, Service, School, Ticket, Attachment, Response, CannedResponse
# Import natin ang mga forms mula sa forms.py
from forms import ServiceSelectionForm, GeneralTicketForm, LoginForm

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
    # Ang data ay inilipat dito para mas madaling i-manage
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
# === ROUTES SECTION ==============================================
# =================================================================

@app.route('/')
@login_required
def home():
    """Main dashboard view."""
    # TODO: I-filter ang tickets base sa role ng current_user
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

# --- BAGONG TICKET CREATION FLOW ---
@app.route('/create-ticket/select-service', methods=['GET', 'POST'])
def select_service():
    """STEP 1: User selects a service from a grouped dropdown."""
    form = ServiceSelectionForm()
    departments_with_services = Department.query.options(db.joinedload(Department.services)).order_by(Department.name).all()
    choices = []
    for dept in departments_with_services:
        dept_services = [(service.id, service.name) for service in dept.services]
        choices.append((dept.name, dept_services))
    form.service.choices = choices
    if form.validate_on_submit():
        service_id = form.service.data
        return redirect(url_for('create_ticket_form', service_id=service_id))
    return render_template('select_service.html', form=form, title='Pumili ng Serbisyo')

@app.route('/create-ticket/form/<int:service_id>', methods=['GET', 'POST'])
def create_ticket_form(service_id):
    """STEP 2: User fills out the form for the selected service."""
    service = db.session.get(Service, service_id)
    if not service:
        flash('Invalid service selected.', 'error')
        return redirect(url_for('select_service'))
    form = GeneralTicketForm()
    if form.validate_on_submit():
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
            status='Open'
        )
        db.session.add(new_ticket)
        db.session.commit()
        flash(f'Your ticket has been created! Your ticket number is {new_ticket_number}.', 'success')
        return redirect(url_for('home'))
    return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')

# --- USER AUTHENTICATION ROUTES ---
# app.py

# --- USER AUTHENTICATION ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    # Gagamitin natin ang LoginForm mula sa forms.py
    form = LoginForm()
    
    # Ang validate_on_submit() ay che-check kung POST request at kung valid ang data
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        # Che-check kung may user at kung tama ang password
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            # I-redirect sa home kung walang next page, para mas ligtas
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            # Magpapakita ng error message kung mali ang credentials
            flash('Login Unsuccessful. Please check username and password', 'danger')
            
    return render_template('login.html', form=form, title='Login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)