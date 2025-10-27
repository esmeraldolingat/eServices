import os
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from functools import wraps
import csv
import io
from dotenv import load_dotenv
from sqlalchemy import func, case, extract, or_
from sqlalchemy.orm import joinedload
import logging
from logging.handlers import RotatingFileHandler
import traceback # Para sa mas detailed error logging
from werkzeug.exceptions import HTTPException 
from flask import jsonify 
from datetime import timezone

load_dotenv()

# --- IMPORTS FROM OUR PROJECT FILES ---
from models import (
    db, User, Department, Service, School, Ticket, Attachment, Response as TicketResponse,
    CannedResponse, AuthorizedEmail, PersonalCannedResponse
)
from forms import (
    DepartmentSelectionForm, ServiceSelectionForm, GeneralTicketForm, LoginForm,
    IssuanceForm, RepairForm, EmailAccountForm, DpdsForm, DcpForm, OtherIctForm,
    LeaveApplicationForm, CoeForm, ServiceRecordForm, GsisForm, NoPendingCaseForm,
    LocatorSlipForm, AuthorityToTravelForm, OicDesignationForm, SubstituteTeacherForm, AdmForm,
    ProvidentFundForm, IcsForm, RegistrationForm, RequestResetForm, ResetPasswordForm,
    ResponseForm, EditUserForm, AddAuthorizedEmailForm, BulkUploadForm, DepartmentForm,
    UpdateTicketForm, CannedResponseForm, PersonalCannedResponseForm,
    UpdateProfileForm, ChangePasswordForm, ServiceForm
)

# --- App Initialization and Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

app.secret_key = os.getenv('SECRET_KEY')


# --- App Initialization and Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

# --- SIMULA NG BAGONG CONFIGURATIONS ---
# Maximum file size per upload (in Megabytes)
app.config['MAX_FILE_SIZE_MB'] = 25 
# Calculate bytes (1MB = 1024 * 1024 bytes)
MAX_FILE_SIZE_BYTES = app.config['MAX_FILE_SIZE_MB'] * 1024 * 1024 
# Define allowed extensions here (or get from form validators if consistent)
# Mas maganda kung consistent ito sa FileAllowed validators mo sa forms.py
ALLOWED_EXTENSIONS = {'pdf'}
# --- TAPOS NG BAGONG CONFIGURATIONS ---

app.secret_key = os.getenv('SECRET_KEY')

# ... (Database Configuration, etc. - walang binago dito) ...



# --- Database Configuration ---
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_DB = os.getenv('MYSQL_DB', 'eservices_db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Other Configurations ---
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
app.config['TICKETS_PER_PAGE'] = 10
app.config['EMAILS_PER_PAGE'] = 50

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

# --- Logging Setup ---
if not app.debug: # I-enable lang ang file logging kapag HINDI naka-debug mode
    if not os.path.exists('logs'):
        os.mkdir('logs')
    # Mag-log sa file, 10MB per file, hanggang 5 backup files
    file_handler = RotatingFileHandler('logs/eservices.log', maxBytes=10240000, backupCount=5)
    # Format ng log message: [Timestamp] LEVEL in module: message [pathname:line number]
    log_format = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(log_format)
    # Itakda ang logging level (INFO, WARNING, ERROR, CRITICAL)
    file_handler.setLevel(logging.INFO)
    # Idagdag ang handler sa Flask app logger
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('eServices startup') # Mag-log kapag nagsimula ang app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Context Processor para sa Current Year ---
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.utcnow().year}

# =================================================================
# === ADMIN DECORATOR =============================================
# =================================================================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Admin':
            flash('You do not have permission to access this page.', 'danger')
            app.logger.warning(f"Unauthorized access attempt to admin page by user {current_user.email if current_user.is_authenticated else 'Guest'}")
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
    try:
        mail.send(msg)
        app.logger.info(f"New ticket email sent successfully to {ticket.requester_email} for ticket {ticket.ticket_number}")
    except Exception as e:
        app.logger.error(f"Error sending new ticket email to {ticket.requester_email} for ticket {ticket.ticket_number}: {e}\n{traceback.format_exc()}")

def send_staff_notification_email(ticket, response):
    recipients = {manager.email for manager in ticket.service_type.managers}
    admins = User.query.filter_by(role='Admin').all()
    for admin in admins:
        recipients.add(admin.email)
    
    if not recipients:
        app.logger.warning(f"No recipients found for staff notification for ticket {ticket.ticket_number}")
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
    try:
        mail.send(msg)
        app.logger.info(f"Staff notification email sent successfully for ticket {ticket.ticket_number}")
    except Exception as e:
        app.logger.error(f"Error sending staff notification email for ticket {ticket.ticket_number}: {e}\n{traceback.format_exc()}")

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request', sender=('TCSD e-Services', app.config['MAIL_USERNAME']), recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}
If you did not make this request then simply ignore this email and no changes will be made.
'''
    try:
        mail.send(msg)
        app.logger.info(f"Password reset email sent successfully to {user.email}")
    except Exception as e:
        app.logger.error(f"Error sending password reset email to {user.email}: {e}\n{traceback.format_exc()}")

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
    try:
        mail.send(msg)
        app.logger.info(f"Resolution email sent successfully to {ticket.requester_email} for ticket {ticket.ticket_number}")
    except Exception as e:
        app.logger.error(f"Error sending resolution email to {ticket.requester_email} for ticket {ticket.ticket_number}: {e}\n{traceback.format_exc()}")


# =================================================================
# === CLI COMMANDS ================================================
# =================================================================

@app.cli.command("seed-db")
def seed_db():
    """Populates the database with initial data and canned responses."""
    
    print("Clearing old canned responses...")
    db.session.query(CannedResponse).delete()
    db.session.commit()
    print("Old canned responses cleared.")

    print("Seeding Departments...")
    DEPARTMENTS = ["ICT", "Personnel", "Legal Services", "Office of the SDS", "Accounting Unit", "Supply Office"]
    for dept_name in DEPARTMENTS:
        if not Department.query.filter_by(name=dept_name).first(): db.session.add(Department(name=dept_name))
    db.session.commit()
    print("Departments seeded.")

    print("Seeding Services...")
    SERVICES = { "ICT": ["Issuances and Online Materials", "Repair, Maintenance and Troubleshoot of IT Equipment", "DepEd Email Account", "DPDS - DepEd Partnership Database System", "DCP - DepEd Computerization Program: After-sales", "other ICT - Technical Assistance Needed"], "Personnel": ["Application for Leave of Absence", "Certificate of Employment", "Service Record", "GSIS BP Number"], "Legal Services": ["Certificate of NO-Pending Case"], "Office of the SDS": ["Request for Approval of Locator Slip", "Request for Approval of Authority to Travel", "Request for Designation of Officer-in-Charge at the School", "Request for Substitute Teacher", "Alternative Delivery Mode"], "Accounting Unit": ["DepEd TCSD Provident Fund"], "Supply Office": ["Submission of Inventory Custodian Slip – ICS"] }
    for dept_name, service_list in SERVICES.items():
        dept = Department.query.filter_by(name=dept_name).first()
        if dept:
            for service_name in service_list:
                if not Service.query.filter_by(name=service_name, department_id=dept.id).first(): db.session.add(Service(name=service_name, department_id=dept.id))
    db.session.commit()
    print("Services seeded.")

    print("Seeding Schools...")
    SCHOOLS = [ "Alvindia Aguso Central ES", "Alvindia Aguso HS", "Alvindia ES", "Amucao ES", "Amucao HS", "Apalang ES", "Armenia IS", "Asturias ES", "Atioc Dela Paz ES", "Bacuit ES", "Bagong Barrio ES", "Balanti ES", "Balanti HS", "Balete ES", "Balibago Primero IS", "Balingcanaway Centro ES", "Balingcanaway Corba ES", "Banaba ES", "Bantog ES", "Baras-Baras ES", "Baras-Baras HS", "Batang-Batang IS", "Binauganan ES", "Buenavista ES", "Buhilit ES", "Burot IS", "Camp Aquino ES", "Capehan ES", "Capulong ES", "Carangian ES", "Care ES", "CAT ES", "CAT HS Annex", "CAT HS Main", "Cut Cut ES", "Dalayap ES", "Damaso Briones ES", "Dolores ES", "Don Florencio P. Buan ES", "Don Pepe Cojuangco ES", "Doña Arsenia ES", "Felicidad Magday ES", "Laoang ES", "Lourdes ES", "Maligaya ES", "Maliwalo CES", "Maliwalo National HS", "Mapalacsiao ES", "Mapalad ES", "Margarita Briones Soliman ES", "Matatalaib Bato ES", "Matatalaib Buno ES", "Matatalaib HS", "Natividad De Leon ES", "Northern Hill ES Annex", "Northern Hill ES Main", "Pag-asa ES", "Paquillao ES", "Paradise ES", "Paraiso ES", "Samberga ES", "San Carlos ES", "San Francisco ES", "San Isidro ES", "San Jose De Urquico ES", "San Jose ES", "San Juan Bautista ES", "San Juan De Mata ES", "San Juan De Mata HS", "San Manuel ES", "San Manuel HS", "San Miguel CES", "San Nicolas ES", "San Pablo ES", "San Pascual ES", "San Rafael ES", "San Sebastian ES", "San Vicente ES Annex", "San Vicente ES Main", "Sapang Maragul IS", "Sapang Tagalog ES", "Sepung Calzada Panampunan ES", "Sinait IS", "Sitio Dam ES", "Sta. Cruz ES", "Sta.Maria ES", "Sto. Cristo IS", "Sto. Domingo ES", "Sto. Niño ES", "Suizo Bliss ES", "Suizo Resettlement ES", "Tariji ES", "Tarlac West CES", "Tibag ES", "Tibag HS", "Trinidad ES", "Ungot IS", "Villa Bacolor ES", "Yabutan ES", "Division Office" ]
    for school_name in SCHOOLS:
        if not School.query.filter_by(name=school_name).first(): db.session.add(School(name=school_name))
    db.session.commit()
    print("Schools seeded.")

    print("Seeding Authorized Emails...")
    AUTHORIZED_EMAILS = ['icts.tarlaccity@deped.gov.ph', 'esmeraldo.lingat@deped.gov.ph', 'pedro.penduko@deped.gov.ph', 'admin@deped.gov.ph']
    for email_address in AUTHORIZED_EMAILS:
        if not AuthorizedEmail.query.filter_by(email=email_address).first():
            db.session.add(AuthorizedEmail(email=email_address))
    db.session.commit()
    print("Authorized emails seeded.")

    print("Seeding Canned Responses...")
    
    # Ito na ang KUMPLETONG listahan mo, ikakabit lahat sa Department
    # LAHAT NG ITO AY "GENERAL" (service_id=None)
    CANNED_RESPONSES_BY_DEPT = {
        "ICT": [
            ("Transaction Completed", "Your transaction was already processed and completed. We will now close this ticket. Thank you."),
            ("Files Posted Online", "The files you uploaded have already been posted on the Division Website. Thank you."),
            ("Temp Password - Google", "Use your temporary password to sign in to your DepEd Google account at Gmail.com"),
            ("Temp Password - Microsoft", "Use your temporary password to sign in to your DepEd Microsoft account on Office.com"),
            ("Temp Password - DPDS", "Use your temporary password to sign in to your official school email address at partnershipsdatabase.deped.gov.ph"),
            ("Sent to Central Office", "Your request has been sent to the DepEd Central Office. Please wait for further instructions. Thank you."),
            ("2FA Disabled", "The two-factor authentication has been successfully disabled. You can now access the provided email account using the same password that was previously set."),
            ("Missing Email - 2FA", "Please provide the email address for which you wish to remove two-factor authentication. Thank you."),
            ("Missing Email - Reset", "Kindly provide the DepEd email address you wish to have reset by the ICTU. Thank you."),
            ("Google Account Required", "A DepEd Google account is required to create a Microsoft account. Kindly provide the DepEd Google account. Thank you."),
            ("Invalid Attachment", "Please use valid attachment as proof for the newly hired teacher. Thank you."),
            ("Pending Activation", "The activation of the DepEd email account is pending and that the recipient should wait for the Central Office to handle the activation process. Thank you"),
            ("Storage Warning", "Please ensure that your Google Drive storage does not exceed the maximum allocation of 100GB per person. Exceeding this limit will result in the suspension of Google Apps usage, so please free up space accordingly."),
            ("Account Disabled", "Your account has been disabled by admin. To reactivate: 1. Visit Division Office (ICTU) for assistance or call Esmeraldo Lingat: (045) 982 4514. Thank you."),
            ("Account Already Active", "The DepEd email account you provided is already activated. We cannot make any changes to this account. Thank you."),
            ("Canva Account Info", "If you want to use Canva, you need to link your Microsoft account to it. However, if your Microsoft account is not working, you may have used the wrong account, or if the account is correct, you might have forgotten the password. To resolve this issue, please ask your school ICT Coordinator to request a password reset from the Division ICT Unit (ICTU). Thank you.")
        ],
        "Legal Services": [
            ("No Pending Case Approved", "This serves to formally notify you that your request for a No Pending Case Certification has been duly approved. You may collect the document in person or, alternatively, coordinate with the Administrative Officer of your school to facilitate its release from the Division Records Office. Additionally, a soft copy has been provided for your convenience. You may access it by signing in to your school account through TCSD e-Services.")
        ],
        "Office of the SDS": [
            ("Locator Slip Approved", "Your Locator Slip has been duly approved. You may access the document by signing in to your school account through TCSD e-Services."),
            ("Authority to Travel Approved", "Your request for Authority to Travel has been duly approved. You may retrieve the document in person or coordinate with the Administrative Officer at your school to facilitate its release from the Division Records Office. Additionally, a soft copy has been provided for your convenience. You may access it by signing in to your school account through TCSD e-Services."),
            ("OIC Request Forwarded", "Your request for the Designation of an Officer-in-Charge at your School has been forwarded to the Personnel Unit for processing. Thank you."),
            ("ADM Request Forwarded", "Your request for the Alternative Delivery Mode at your School has been forwarded to the Personnel Unit for processing. Thank you."),
            ("Substitute Teacher Fowarded", "Your request for a Substitute Teacher at your school has been forwarded to the Personnel Unit for processing. Thank you.")
        ],
        "Accounting Unit": [
            ("Provident Fund Processing", "Your DepEd TCSD Provident Fund application is currently being processed. The application will proceed upon the availability of funds."),
            ("Provident Fund SOA Ready", "Your DepEd TCSD Provident Fund Statement of Account has been duly prepared and signed. You may retrieve it in person or coordinate with your school's Administrative Officer for its release Additionally, a soft copy has been provided for your convenience. You may access it by signing in to your school account through TCSD e-Services."),
            ("Provident Fund Clearance Ready", "Your request for a Provident Loan Accountability Clearance has been duly prepared and signed. You may retrieve it in person or coordinate with your school's Administrative Officer for its release. Additionally, a soft copy has been provided for your convenience. You may access it by signing in to your school account through TCSD e-Services.")
        ],
        "Supply Office": [
            ("ICS Approved", "Your submission of the Inventory Custodian Slip (ICS) has been reviewed, approved, and duly signed. Kindly refer to the soft copy provided in TCSD e-Services by signing in to your school account. This shall serve as your official copy for school inventory records.")
        ]
    }

    for dept_name, responses_list in CANNED_RESPONSES_BY_DEPT.items():
        dept = Department.query.filter_by(name=dept_name).first()
        if dept:
            for title, body in responses_list:
                # Titingnan natin kung existing na ba bago idagdag
                if not CannedResponse.query.filter_by(title=title, department_id=dept.id).first():
                    # Idadagdag natin sila na may service_id=None (general)
                    db.session.add(CannedResponse(title=title, body=body, department_id=dept.id, service_id=None))
    db.session.commit()
    print("Department-level canned responses seeded.")

    # Ito yung para sa Personnel na specific per service
    CANNED_RESPONSES_BY_SERVICE = {
        "Application for Leave of Absence": [ ("Leave Approved (with Soft Copy)", "Your application for leave of absence has been duly approved. You may either retrieve the document in person or coordinate with the Administrative Officer at your school to facilitate its release from the Records Office of the Division. Additionally, a soft copy is provided for your convenience. You may access it by signing in to your school account through TCSD e-Services."), ("Form 6 - Needs Signature", "Kindly request the school head to affix their signature to your Form 6 for official validation.") ],
        "Certificate of Employment": [ ("COE Approved (with Soft Copy)", "Your requested Certificate of Employment has been duly prepared and signed. You may either retrieve it in person or coordinate with the Administrative Officer at your school to facilitate its release from the Records Office of the Division. Additionally, a soft copy has been provided for your convenience. You may access it by signing in to your school account through TCSD e-Services.") ],
        "Service Record": [ ("SR Approved (Hard Copy only)", "Your requested Service Record has been duly prepared and signed. You may either retrieve it in person or coordinate with the Administrative Officer at your school to facilitate its release from the Records Office of the Division."), ("SR Approved (Soft Copy only)", "Your requested Service Record has been duly prepared and signed. You may access the soft copy by signing in to your school account through TCSD e-Services.") ],
        "GSIS BP Number": [ ("GSIS BP Created", "Your BP number has been duly created. Please check."), ("GSIS BP Updated", "Your BP number has been duly updated. Please check.") ]
    }
    
    for service_name, responses_list in CANNED_RESPONSES_BY_SERVICE.items():
        service = Service.query.filter_by(name=service_name).first()
        if service:
            for title, body in responses_list:
                # Titingnan natin kung existing na ba bago idagdag
                if not CannedResponse.query.filter_by(title=title, service_id=service.id).first():
                    # Idadagdag natin sila na nakakabit sa department at service
                    db.session.add(CannedResponse(
                        title=title, 
                        body=body, 
                        department_id=service.department_id, 
                        service_id=service.id
                    ))
    db.session.commit()
    print("Service-level canned responses seeded.")
    print("Database seeding complete!")


@app.cli.command("create-admin")
def create_admin():
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


# =================================================================
# === SIMULA NG PAGBABAGO: Inayos na staff_dashboard function ======
# =================================================================
@app.route('/staff-dashboard')
@login_required
def staff_dashboard():
    if current_user.role not in ['Admin', 'Staff']:
        flash('Access denied.', 'danger')
        app.logger.warning(f"Unauthorized access attempt to staff dashboard by user {current_user.email}")
        return redirect(url_for('my_tickets'))
        
    page_active = request.args.get('page_active', 1, type=int)
    page_resolved = request.args.get('page_resolved', 1, type=int)
    search_query = request.args.get('search', '').strip()
    
    # --- Year/Quarter Filtering Logic (Walang binago dito) ---
    available_years_query = db.session.query(extract('year', Ticket.date_posted)).distinct().order_by(extract('year', Ticket.date_posted).desc())
    available_years = [y[0] for y in available_years_query.all()]
    current_year = datetime.utcnow().year
    selected_year = request.args.get('year', current_year, type=int)
    if not available_years: available_years.append(current_year)
    elif selected_year not in available_years: selected_year = available_years[0]
    
    selected_quarter = request.args.get('quarter', 0, type=int)
    quarters = {
        1: (datetime(selected_year, 1, 1, tzinfo=timezone.utc), datetime(selected_year, 3, 31, 23, 59, 59, tzinfo=timezone.utc)),
        2: (datetime(selected_year, 4, 1, tzinfo=timezone.utc), datetime(selected_year, 6, 30, 23, 59, 59, tzinfo=timezone.utc)),
        3: (datetime(selected_year, 7, 1, tzinfo=timezone.utc), datetime(selected_year, 9, 30, 23, 59, 59, tzinfo=timezone.utc)),
        4: (datetime(selected_year, 10, 1, tzinfo=timezone.utc), datetime(selected_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
    }
    
    # --- Base Query for Tickets & Staff Filtering (Walang binago) ---
    ticket_base_query = Ticket.query.options(db.joinedload(Ticket.school), db.joinedload(Ticket.service_type))
    managed_service_ids = None # Initialize para malaman kung Staff
    if current_user.role == 'Staff':
        managed_service_ids = [service.id for service in current_user.managed_services]
        if not managed_service_ids:
            flash("You are not assigned to any services. Please contact an administrator.", "warning")
            app.logger.warning(f"Staff user {current_user.email} has no assigned services.")
            # Important: Still need to return the template structure even if empty
            empty_paginate = db.paginate(db.select(Ticket).where(db.false()), page=1, per_page=app.config['TICKETS_PER_PAGE'], error_out=False)
            return render_template('staff_dashboard.html', 
                                   active_tickets=empty_paginate, 
                                   resolved_tickets=empty_paginate, 
                                   dashboard_summary={}, 
                                   school_summary={}, # Ipasa rin ang empty school summary
                                   title="My Managed Tickets", 
                                   available_years=available_years, 
                                   selected_year=selected_year, 
                                   selected_quarter=selected_quarter, 
                                   search_query=search_query)
        ticket_base_query = ticket_base_query.filter(Ticket.service_id.in_(managed_service_ids))

    # --- Apply Search or Date Filters to Ticket Query (Walang binago) ---
    if search_query:
        search_term = f"%{search_query}%"
        ticket_base_query = ticket_base_query.join(School, Ticket.school_id == School.id, isouter=True).filter(
            or_(
                Ticket.ticket_number.ilike(search_term),
                Ticket.requester_name.ilike(search_term),
                School.name.ilike(search_term)
            )
        )
    else:
        # Apply year filter always when not searching
        ticket_base_query = ticket_base_query.filter(extract('year', Ticket.date_posted) == selected_year)
        # Apply quarter filter if selected
        if selected_quarter in quarters:
            start_date, end_date = quarters[selected_quarter]
            # Ensure comparison is timezone-aware if date_posted is
            ticket_base_query = ticket_base_query.filter(Ticket.date_posted.between(start_date, end_date))

    # --- Paginate Active/Resolved Tickets (Walang binago) ---
    status_order = case((Ticket.status == 'Open', 1), (Ticket.status == 'In Progress', 2), else_=3)
    active_tickets = db.paginate(ticket_base_query.filter(Ticket.status.in_(['Open', 'In Progress'])).order_by(status_order, Ticket.date_posted.desc()), 
                                 page=page_active, per_page=app.config['TICKETS_PER_PAGE'], error_out=False)
    resolved_tickets = db.paginate(ticket_base_query.filter(Ticket.status == 'Resolved').order_by(Ticket.date_posted.desc()), 
                                   page=page_resolved, per_page=app.config['TICKETS_PER_PAGE'], error_out=False)
    
    # --- Generate Department Summary (Logic mostly the same, used for Dept Tab) ---
    dashboard_summary = {}
    if not search_query: # Summary only shown when not searching
        dept_summary_query = db.session.query(
            Department.name.label('dept_name'),
            Service.name.label('service_name'),
            Service.id.label('service_id'), # Added service_id
            func.count(Ticket.id).label('total'),
            func.sum(case((Ticket.status == 'Resolved', 1), else_=0)).label('resolved_count')
        ).select_from(Ticket).join(Service, Ticket.service_id == Service.id).join(Department, Service.department_id == Department.id)

        # Apply Year/Quarter filters
        dept_summary_query = dept_summary_query.filter(extract('year', Ticket.date_posted) == selected_year)
        if selected_quarter in quarters:
            start_date, end_date = quarters[selected_quarter]
            dept_summary_query = dept_summary_query.filter(Ticket.date_posted.between(start_date, end_date))

        # Apply Staff filter if applicable
        if managed_service_ids is not None:
             dept_summary_query = dept_summary_query.filter(Service.id.in_(managed_service_ids))
        
        dept_summary_data = dept_summary_query.group_by(Department.name, Service.name, Service.id).all()
        
        # Determine relevant departments for the user
        if current_user.role == 'Admin':
            all_departments = Department.query.options(db.joinedload(Department.services)).order_by(Department.name).all()
        else: # Staff
            all_departments = Department.query.join(Service).filter(Service.id.in_(managed_service_ids)).options(db.joinedload(Department.services.and_(Service.id.in_(managed_service_ids)))).order_by(Department.name).distinct().all()

        color_palette = ['#FE9321', '#6FE3CC', '#185D7A', '#C8DB2A', '#EF4687', '#5BC0DE', '#F0AD4E', '#D9534F'] # Added more colors

        for dept in all_departments:
            dept_services_data = []
            department_total_tickets = 0
            # Ensure we only iterate services relevant to staff
            services_in_dept = sorted([s for s in dept.services if managed_service_ids is None or s.id in managed_service_ids], key=lambda s: s.name)
            
            for i, service in enumerate(services_in_dept):
                found_data = next((row for row in dept_summary_data if row.dept_name == dept.name and row.service_id == service.id), None)
                
                if found_data:
                    resolved = found_data.resolved_count
                    total = found_data.total
                    active = total - resolved
                    dept_services_data.append({
                        'name': service.name, 
                        'active': active, 
                        'resolved': resolved, 
                        'total': total, 
                        'resolved_percent': int(resolved / total * 100) if total > 0 else 0,
                        'color': color_palette[i % len(color_palette)]
                    })
                    department_total_tickets += total
                else: # Service exists but has 0 tickets in the period
                     dept_services_data.append({
                        'name': service.name, 
                        'active': 0, 
                        'resolved': 0, 
                        'total': 0, 
                        'resolved_percent': 0,
                        'color': color_palette[i % len(color_palette)]
                    })

            if dept_services_data: # Only add department if it has relevant services
                dashboard_summary[dept.name] = {
                    'services': dept_services_data,
                    'department_total': department_total_tickets,
                    'service_count': len(dept_services_data) # Add service count here
                }

    # --- BAGONG LOGIC: Generate School Summary (For School Tab) ---
    school_summary = {}
    if not search_query: # Summary only shown when not searching
        school_summary_query = db.session.query(
            School.name.label('school_name'),
            Service.name.label('service_name'),
            Service.id.label('service_id'), # Added service_id
            func.count(Ticket.id).label('total'),
            func.sum(case((Ticket.status == 'Resolved', 1), else_=0)).label('resolved_count')
        ).select_from(Ticket).join(Service, Ticket.service_id == Service.id).join(School, Ticket.school_id == School.id) # Ensure School join is correct

        # Apply Year/Quarter filters
        school_summary_query = school_summary_query.filter(extract('year', Ticket.date_posted) == selected_year)
        if selected_quarter in quarters:
            start_date, end_date = quarters[selected_quarter]
            school_summary_query = school_summary_query.filter(Ticket.date_posted.between(start_date, end_date))

        # Apply Staff filter if applicable
        if managed_service_ids is not None:
             school_summary_query = school_summary_query.filter(Service.id.in_(managed_service_ids))

        # Group by School and Service
        school_summary_data_flat = school_summary_query.group_by(School.name, Service.name, Service.id).order_by(School.name, Service.name).all()

        # Transform flat data into nested dictionary
        for row in school_summary_data_flat:
            school_name = row.school_name
            if school_name not in school_summary:
                school_summary[school_name] = {'total_school_tickets': 0, 'services': []}
            
            resolved = row.resolved_count
            total = row.total
            active = total - resolved
            
            school_summary[school_name]['services'].append({
                'name': row.service_name,
                'active': active,
                'resolved': resolved,
                'total': total
            })
            school_summary[school_name]['total_school_tickets'] += total
            
    # --- Ipasa lahat sa template ---
    return render_template('staff_dashboard.html', 
                           active_tickets=active_tickets, 
                           resolved_tickets=resolved_tickets, 
                           dashboard_summary=dashboard_summary, 
                           school_summary=school_summary, # Ipasa ang bagong data
                           title="System Dashboard", 
                           available_years=available_years, 
                           selected_year=selected_year, 
                           selected_quarter=selected_quarter, 
                           search_query=search_query)
# =================================================================
# === TAPOS NG PAGBABAGO: Ang natitirang code ay pareho na ========
# =================================================================


@app.route('/export-tickets')
@login_required
@admin_required
def export_tickets():
    search_query = request.args.get('search', '').strip()
    selected_year = request.args.get('year', datetime.utcnow().year, type=int)
    selected_quarter = request.args.get('quarter', 0, type=int)

    export_query = Ticket.query.options(
        joinedload(Ticket.school),
        joinedload(Ticket.service_type).joinedload(Service.department)
    ).order_by(Ticket.date_posted.desc())

    if search_query:
        search_term = f"%{search_query}%"
        export_query = export_query.join(School, Ticket.school_id == School.id, isouter=True).filter(
            or_(
                Ticket.ticket_number.ilike(search_term),
                Ticket.requester_name.ilike(search_term),
                School.name.ilike(search_term)
            )
        )
    else:
        export_query = export_query.filter(extract('year', Ticket.date_posted) == selected_year)
        quarters = {
            1: (datetime(selected_year, 1, 1), datetime(selected_year, 3, 31, 23, 59, 59)),
            2: (datetime(selected_year, 4, 1), datetime(selected_year, 6, 30, 23, 59, 59)),
            3: (datetime(selected_year, 7, 1), datetime(selected_year, 9, 30, 23, 59, 59)),
            4: (datetime(selected_year, 10, 1), datetime(selected_year, 12, 31, 23, 59, 59)),
        }
        if selected_quarter in quarters:
            start_date, end_date = quarters[selected_quarter]
            export_query = export_query.filter(Ticket.date_posted.between(start_date, end_date))
    
    tickets_to_export = export_query.all()

    output = io.StringIO()
    writer = csv.writer(output)

    header = [
        'Ticket Number', 'Status', 'Requester Name', 'Requester Email', 
        'School/Office', 'Department', 'Service', 'Date Submitted'
    ]
    writer.writerow(header)

    for ticket in tickets_to_export:
        row = [
            ticket.ticket_number,
            ticket.status,
            ticket.requester_name,
            ticket.requester_email,
            ticket.school.name if ticket.school else 'N/A',
            ticket.service_type.department.name,
            ticket.service_type.name,
            ticket.date_posted.strftime('%Y-%m-%d %H:%M:%S')
        ]
        writer.writerow(row)

    output.seek(0)
    
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = "attachment;filename=tickets_export.csv"
    return response


@app.route('/my-tickets')
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

    active_tickets = base_query.filter(Ticket.status.in_(['Open', 'In Progress'])).order_by(status_order, Ticket.date_posted.desc()).paginate(page=page_active, per_page=app.config['TICKETS_PER_PAGE'], error_out=False)
    resolved_tickets = base_query.filter(Ticket.status == 'Resolved').order_by(Ticket.date_posted.desc()).paginate(page=page_resolved, per_page=app.config['TICKETS_PER_PAGE'], error_out=False)
    
    return render_template('my_tickets.html', active_tickets=active_tickets, resolved_tickets=resolved_tickets, title='My Tickets', search_query=search_query)


@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def ticket_detail(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        flash('Ticket not found!', 'error')
        app.logger.warning(f"Attempt to access non-existent ticket ID: {ticket_id}")
        return redirect(url_for('home'))
    
    is_staff_or_admin = current_user.role == 'Admin' or (current_user.role == 'Staff' and ticket.service_type in current_user.managed_services)
    
    if is_staff_or_admin:
        form = UpdateTicketForm()
    else:
        if ticket.requester_email != current_user.email:
             flash('You do not have permission to view this ticket.', 'danger')
             app.logger.warning(f"Unauthorized attempt by user {current_user.email} to view ticket {ticket_id}")
             return redirect(url_for('home'))
        form = ResponseForm()

    # --- Canned Response Query (Walang binago dito, gamit ang inayos na version) ---
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
            return redirect(url_for('ticket_detail', ticket_id=ticket.id))
        
        # --- SIMULA NG FILE VALIDATION & HANDLING ---
        file_to_save_object = None   # To hold the FileStorage object
        filename_to_save_in_db = None # To hold the final filename for DB and saving
        
        if form.attachment.data:
            file = form.attachment.data
            filename = secure_filename(file.filename)
            
            # 1. Size Check
            try:
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)

                if file_size == 0:
                    flash(f"Attachment '{filename}' appears to be empty. Please upload a valid file.", 'warning')
                    # Don't redirect yet, maybe they just want to add text
                
                elif file_size > MAX_FILE_SIZE_BYTES:
                    flash(f"Attachment '{filename}' exceeds the {app.config['MAX_FILE_SIZE_MB']}MB size limit. Response not submitted.", 'danger')
                    return redirect(url_for('ticket_detail', ticket_id=ticket.id)) # Redirect back

            except Exception as e:
                app.logger.error(f"Error checking attachment size for ticket {ticket_id}: {e}")
                flash(f"Could not check the size of attachment '{filename}'. Response not submitted.", 'danger')
                return redirect(url_for('ticket_detail', ticket_id=ticket.id)) # Redirect back

            # 2. Type Check (only if file has size)
            if file_size > 0 and filename and ('.' not in filename or \
               filename.rsplit('.', 1)[1].lower() not in ALLOWED_EXTENSIONS):
                 flash(f"Attachment file type for '{filename}' is not allowed. Allowed types are: {', '.join(sorted(ALLOWED_EXTENSIONS))}. Response not submitted.", 'danger')
                 return redirect(url_for('ticket_detail', ticket_id=ticket.id)) # Redirect back

            # If checks passed and file has content, prepare for saving
            if file_size > 0:
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
                filename_to_save_in_db = f"{timestamp}_{filename}"
                file_to_save_object = file # Keep the file object ready
        # --- TAPOS NG FILE VALIDATION & HANDLING ---

        # --- Proceed with saving response and file (if validated) ---
        try:
            # Save the file FIRST if it exists and was validated
            if file_to_save_object and filename_to_save_in_db:
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename_to_save_in_db)
                file_to_save_object.save(save_path)
                app.logger.info(f"Successfully saved attachment: {filename_to_save_in_db} for ticket {ticket_id}")
            
            # Add response to DB
            new_response = TicketResponse(body=form.body.data, user_id=current_user.id, ticket_id=ticket.id)
            db.session.add(new_response)
            
            # Add attachment record to DB if file was saved
            if filename_to_save_in_db:
                db.session.add(Attachment(filename=filename_to_save_in_db, ticket_id=ticket.id))
            
            # Update ticket status if applicable (staff/admin form)
            if hasattr(form, 'status'):
                old_status = ticket.status
                new_status = form.status.data
                if old_status != new_status:
                    ticket.status = new_status
                    app.logger.info(f"Ticket {ticket_id} status changed from '{old_status}' to '{new_status}' by user {current_user.email}")
                    if new_status == 'Resolved':
                        send_resolution_email(ticket, form.body.data)
                        flash('Your response has been added and a resolution email has been sent.', 'success')
                    else:
                        flash('Your response has been added and the ticket status has been updated.', 'success')
                else: # Status didn't change, just added response
                    flash('Your response has been added successfully!', 'success')
            else: # User added a response
                flash('Your response has been added successfully!', 'success')
                # Notify staff only if the user (not staff/admin) added the response
                if not is_staff_or_admin: 
                    send_staff_notification_email(ticket, new_response)
                    
            db.session.commit() # Commit all changes (response, attachment record, status)

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error saving response/attachment for ticket {ticket_id}: {e}\n{traceback.format_exc()}")
            flash('An error occurred while saving the response or attachment. Please try again.', 'danger')
            # Optional: Attempt to delete saved file if DB fails
        
        return redirect(url_for('ticket_detail', ticket_id=ticket.id)) # Redirect after successful POST or error handling
    
    # --- GET Request logic (Walang binago) ---
    if request.method == 'GET' and hasattr(form, 'status'):
        form.status.data = ticket.status
        
    details_pretty = json.dumps(ticket.details, indent=2) if ticket.details else "No additional details."
    
    return render_template('ticket_detail.html', ticket=ticket, details_pretty=details_pretty, form=form, is_staff_or_admin=is_staff_or_admin, system_canned_responses=system_canned_responses, personal_canned_responses=personal_canned_responses)

@app.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_ticket(ticket_id):
    ticket_to_delete = db.session.get(Ticket, ticket_id)
    if ticket_to_delete:
        ticket_number = ticket_to_delete.ticket_number
        
        # Ang 'cascade="all, delete-orphan"' sa models.py
        # ang bahala sa pag-delete ng related attachments at responses.
        db.session.delete(ticket_to_delete)
        db.session.commit()
        
        app.logger.info(f"Admin {current_user.email} deleted ticket {ticket_number}")
        flash(f'Ticket {ticket_number} and all its related responses/attachments have been deleted.', 'success')
        return redirect(url_for('staff_dashboard'))
    else:
        flash('Ticket not found.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to delete non-existent ticket ID: {ticket_id}")
        return redirect(url_for('staff_dashboard'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile_form = UpdateProfileForm()
    password_form = ChangePasswordForm()

    if 'submit_profile' in request.form and profile_form.validate_on_submit():
        old_name = current_user.name
        current_user.name = profile_form.name.data
        db.session.commit()
        app.logger.info(f"User {current_user.email} updated name from '{old_name}' to '{current_user.name}'")
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('profile'))
    elif 'submit_password' in request.form and password_form.validate_on_submit():
        current_user.set_password(password_form.new_password.data)
        db.session.commit()
        app.logger.info(f"User {current_user.email} changed their password successfully.")
        flash('Your password has been changed successfully.', 'success')
        return redirect(url_for('profile'))

    if request.method == 'GET' or ('submit_profile' in request.form and not profile_form.validate()):
        profile_form.name.data = current_user.name
        profile_form.email.data = current_user.email 

    return render_template('profile.html', title='My Profile', profile_form=profile_form, password_form=password_form)

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
        app.logger.warning(f"Admin {current_user.email} attempted to edit non-existent user ID: {user_id}")
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
        app.logger.info(f"Admin {current_user.email} updated user profile for {user.email}")
        flash(f'User {user.name} has been updated successfully!', 'success')
        return redirect(url_for('manage_users'))
    
    if request.method == 'GET':
        form.name.data = user.name
        form.email.data = user.email
        form.role.data = user.role

    departments = Department.query.options(joinedload(Department.services)).order_by(Department.name).all()
    managed_service_ids = {service.id for service in user.managed_services}
    
    return render_template('admin/edit_user.html', form=form, user=user, departments=departments, managed_service_ids=managed_service_ids, title='Edit User')


@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user and user.id != current_user.id:
        user_email = user.email # Kunin ang email bago i-delete
        db.session.delete(user)
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} deleted user {user_email}")
        flash(f'User {user.name} has been deleted.', 'success')
    elif user and user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to delete their own account.")
    else:
        flash('User not found.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to delete non-existent user ID: {user_id}")
    return redirect(url_for('manage_users'))

@app.route('/admin/authorized-emails', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_authorized_emails():
    add_form = AddAuthorizedEmailForm()
    bulk_form = BulkUploadForm()
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)

    if request.method == 'POST' and 'delete_selected' in request.form:
        email_ids_to_delete = request.form.getlist('email_ids')
        if email_ids_to_delete:
            emails_to_delete_objects = AuthorizedEmail.query.filter(AuthorizedEmail.id.in_(email_ids_to_delete)).all()
            deleted_count = len(emails_to_delete_objects)
            for email_obj in emails_to_delete_objects:
                db.session.delete(email_obj)
            db.session.commit()
            app.logger.info(f"Admin {current_user.email} deleted {deleted_count} authorized emails via bulk action.")
            flash(f'{deleted_count} email(s) have been deleted.', 'success')
        else:
            flash('No emails were selected for deletion.', 'warning')
        return redirect(url_for('manage_authorized_emails', search=search_query, page=page))

    if add_form.validate_on_submit() and add_form.submit.data:
        new_email_addr = add_form.email.data
        new_email = AuthorizedEmail(email=new_email_addr)
        db.session.add(new_email)
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} added authorized email: {new_email_addr}")
        flash(f'Email {new_email_addr} has been authorized.', 'success')
        return redirect(url_for('manage_authorized_emails'))
        
    if bulk_form.validate_on_submit() and bulk_form.submit_bulk.data:
        csv_file = bulk_form.csv_file.data
        added_count, duplicate_count = 0, 0
        try:
            stream = io.StringIO(csv_file.read().decode("UTF8"), newline=None)
            csv_reader = csv.reader(stream)
            for row in csv_reader:
                if row and row[0].strip():
                    email = row[0].strip()
                    if not AuthorizedEmail.query.filter_by(email=email).first():
                        db.session.add(AuthorizedEmail(email=email))
                        added_count += 1
                    else:
                        duplicate_count += 1
            if added_count > 0: db.session.commit()
            app.logger.info(f"Admin {current_user.email} performed bulk email upload. Added: {added_count}, Skipped: {duplicate_count}.")
            flash(f'Bulk upload complete. Added: {added_count} new emails. Duplicates skipped: {duplicate_count}.', 'info')
        except Exception as e:
            app.logger.error(f"Error processing bulk email upload by admin {current_user.email}: {e}\n{traceback.format_exc()}")
            flash(f'Error processing bulk upload: {e}', 'danger')
        return redirect(url_for('manage_authorized_emails'))
    
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
        email_addr = email_to_delete.email
        db.session.delete(email_to_delete)
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} deleted authorized email: {email_addr}")
        flash(f'Email {email_addr} has been removed from the authorized list.', 'success')
    else:
        flash('Email not found.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to delete non-existent authorized email ID: {email_id}")
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
        dept_name = form.name.data
        new_dept = Department(name=dept_name)
        db.session.add(new_dept)
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} added new department: {dept_name}")
        flash(f'Department "{dept_name}" has been created.', 'success')
        return redirect(url_for('manage_departments'))
    return render_template('admin/add_edit_department.html', form=form, title='Add Department')

@app.route('/admin/department/<int:dept_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_department(dept_id):
    dept = db.session.get(Department, dept_id)
    if not dept:
        flash('Department not found.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to edit non-existent department ID: {dept_id}")
        return redirect(url_for('manage_departments'))
    
    original_name = dept.name
    form = DepartmentForm(obj=dept)
    
    if form.validate_on_submit():
        new_name = form.name.data
        # Check for uniqueness only if the name has changed
        if new_name != original_name:
            existing_dept = Department.query.filter_by(name=new_name).first()
            if existing_dept:
                flash('That department name already exists.', 'danger')
                return render_template('admin/add_edit_department.html', form=form, title='Edit Department', department=dept)
        
        dept.name = new_name
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} updated department name from '{original_name}' to '{new_name}'")
        flash(f'Department has been updated to "{new_name}".', 'success')
        return redirect(url_for('manage_departments'))
        
    return render_template('admin/add_edit_department.html', form=form, title='Edit Department', department=dept)

@app.route('/admin/department/<int:dept_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_department(dept_id):
    dept_to_delete = db.session.get(Department, dept_id)
    if dept_to_delete:
        dept_name = dept_to_delete.name
        # Check for associated services first
        if dept_to_delete.services:
            flash(f'Cannot delete department "{dept_name}" because it has existing services. Please delete or re-assign services first.', 'danger')
            app.logger.warning(f"Admin {current_user.email} failed to delete department '{dept_name}' due to existing services.")
            return redirect(url_for('manage_departments'))
        # Check for associated tickets (though services should catch this first)
        if dept_to_delete.tickets:
            flash(f'Cannot delete department "{dept_name}" because it has existing tickets.', 'danger')
            app.logger.warning(f"Admin {current_user.email} failed to delete department '{dept_name}' due to existing tickets.")
            return redirect(url_for('manage_departments'))

        db.session.delete(dept_to_delete)
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} deleted department: {dept_name}")
        flash(f'Department "{dept_name}" has been deleted.', 'success')
    else:
        flash('Department not found.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to delete non-existent department ID: {dept_id}")
    return redirect(url_for('manage_departments'))

@app.route('/admin/services')
@login_required
@admin_required
def manage_services():
    services = Service.query.join(Department, Service.department_id == Department.id) \
                           .options(joinedload(Service.department)) \
                           .order_by(Department.name, Service.name).all()
    return render_template('admin/manage_services.html', services=services, title='Manage Services')

@app.route('/admin/service/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_service():
    form = ServiceForm()
    form.department_id.choices = [(0, '-- Select Department --')] + [(d.id, d.name) for d in Department.query.order_by('name')]
    
    if form.validate_on_submit():
        if form.department_id.data == 0:
            flash('Please select a valid department.', 'danger')
            return render_template('admin/add_edit_service.html', form=form, title='Add Service')
        
        existing_service = Service.query.filter_by(name=form.name.data, department_id=form.department_id.data).first()
        if existing_service:
            flash(f'The service "{form.name.data}" already exists in this department.', 'danger')
            return render_template('admin/add_edit_service.html', form=form, title='Add Service')

        new_service = Service(name=form.name.data, department_id=form.department_id.data)
        db.session.add(new_service)
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} added new service: '{new_service.name}' to department ID {new_service.department_id}")
        flash(f'Service "{new_service.name}" has been created.', 'success')
        return redirect(url_for('manage_services'))
    
    return render_template('admin/add_edit_service.html', form=form, title='Add Service')

@app.route('/admin/service/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_service(service_id):
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to edit non-existent service ID: {service_id}")
        return redirect(url_for('manage_services'))

    form = ServiceForm(obj=service)
    form.department_id.choices = [(d.id, d.name) for d in Department.query.order_by('name')]

    if form.validate_on_submit():
        if form.department_id.data == 0:
            flash('Please select a valid department.', 'danger')
            return render_template('admin/add_edit_service.html', form=form, title='Edit Service', service=service)

        if service.name != form.name.data or service.department_id != form.department_id.data:
            existing_service = Service.query.filter(
                Service.name == form.name.data,
                Service.department_id == form.department_id.data,
                Service.id != service_id
            ).first()
            if existing_service:
                flash(f'The service "{form.name.data}" already exists in this department.', 'danger')
                return render_template('admin/add_edit_service.html', form=form, title='Edit Service', service=service)

        service.name = form.name.data
        service.department_id = form.department_id.data
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} updated service ID {service_id} to name '{service.name}'")
        flash(f'Service "{service.name}" has been updated.', 'success')
        return redirect(url_for('manage_services'))

    if request.method == 'GET':
        form.name.data = service.name
        form.department_id.data = service.department_id

    return render_template('admin/add_edit_service.html', form=form, title='Edit Service', service=service)

@app.route('/admin/service/<int:service_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_service(service_id):
    service = db.session.get(Service, service_id)
    if service:
        service_name = service.name
        if service.tickets:
            flash(f'Cannot delete service "{service_name}" because it has existing tickets.', 'danger')
            app.logger.warning(f"Admin {current_user.email} failed to delete service '{service_name}' due to existing tickets.")
            return redirect(url_for('manage_services'))
        
        CannedResponse.query.filter_by(service_id=service_id).delete()
        
        db.session.delete(service)
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} deleted service: {service_name}")
        flash(f'Service "{service_name}" and its related canned responses have been deleted.', 'success')
    else:
        flash('Service not found.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to delete non-existent service ID: {service_id}")
    return redirect(url_for('manage_services'))


@app.route('/admin/canned-responses')
@login_required
@admin_required
def manage_canned_responses():
    responses = CannedResponse.query.join(Department, CannedResponse.department_id == Department.id) \
                                      .options(joinedload(CannedResponse.department), joinedload(CannedResponse.service)) \
                                      .order_by(Department.name, CannedResponse.title).all()
    return render_template('admin/canned_responses.html', responses=responses, title='Manage Canned Responses')

@app.route('/admin/canned-response/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_canned_response():
    form = CannedResponseForm()
    form.department_id.choices = [(0, '-- Select Department --')] + [(d.id, d.name) for d in Department.query.order_by('name')]
    form.service_id.choices = [(0, '-- General (All Services) --')]
    
    if request.method == 'POST':
        dept_id = request.form.get('department_id')
        if dept_id and dept_id != '0':
            services = Service.query.filter_by(department_id=int(dept_id)).order_by('name').all()
            form.service_id.choices.extend([(s.id, s.name) for s in services])
        
        if form.validate_on_submit():
            service_id_val = form.service_id.data if form.service_id.data != 0 else None
            new_response = CannedResponse(title=form.title.data, body=form.body.data, department_id=form.department_id.data, service_id=service_id_val)
            db.session.add(new_response)
            db.session.commit()
            app.logger.info(f"Admin {current_user.email} added new canned response: '{form.title.data}'")
            flash(f'Canned response "{form.title.data}" has been created.', 'success')
            return redirect(url_for('manage_canned_responses'))
    
    return render_template('admin/add_edit_canned_response.html', form=form, title='Add Canned Response')

@app.route('/admin/canned-response/<int:response_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_canned_response(response_id):
    response = db.session.get(CannedResponse, response_id)
    if not response:
        flash('Canned response not found.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to edit non-existent canned response ID: {response_id}")
        return redirect(url_for('manage_canned_responses'))
    
    form = CannedResponseForm(obj=response)
    form.department_id.choices = [(d.id, d.name) for d in Department.query.order_by('name')]
    
    services = Service.query.filter_by(department_id=response.department_id).order_by('name').all()
    form.service_id.choices = [(0, '-- General (All Services) --')] + [(s.id, s.name) for s in services]
    
    if request.method == 'POST':
        dept_id = request.form.get('department_id')
        if dept_id and dept_id != '0':
            services = Service.query.filter_by(department_id=int(dept_id)).order_by('name').all()
            form.service_id.choices = [(0, '-- General (All Services) --')] + [(s.id, s.name) for s in services]
        
        if form.validate_on_submit():
            response.title = form.title.data
            response.body = form.body.data
            response.department_id = form.department_id.data
            response.service_id = form.service_id.data if form.service_id.data != 0 else None
            db.session.commit()
            app.logger.info(f"Admin {current_user.email} updated canned response ID {response_id} (Title: '{response.title}')")
            flash(f'Canned response "{form.title.data}" has been updated.', 'success')
            return redirect(url_for('manage_canned_responses'))
            
    if request.method == 'GET':
        form.service_id.data = response.service_id if response.service_id else 0

    return render_template('admin/add_edit_canned_response.html', form=form, title='Edit Canned Response')

@app.route('/admin/_get_services_for_department/<int:dept_id>')
@login_required
@admin_required
def _get_services_for_department(dept_id):
    services = Service.query.filter_by(department_id=dept_id).order_by('name').all()
    service_array = [{"id": s.id, "name": s.name} for s in services]
    return json.dumps(service_array)

@app.route('/admin/canned-response/<int:response_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_canned_response(response_id):
    response = db.session.get(CannedResponse, response_id)
    if response:
        response_title = response.title
        db.session.delete(response)
        db.session.commit()
        app.logger.info(f"Admin {current_user.email} deleted canned response: '{response_title}'")
        flash(f'Canned response "{response_title}" has been deleted.', 'success')
    else:
        flash('Canned response not found.', 'danger')
        app.logger.warning(f"Admin {current_user.email} attempted to delete non-existent canned response ID: {response_id}")
    return redirect(url_for('manage_canned_responses'))

@app.route('/my-responses', methods=['GET', 'POST'])
@login_required
def manage_my_responses():
    if current_user.role not in ['Admin', 'Staff']:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    form = PersonalCannedResponseForm()
    ticket_id = request.args.get('ticket_id') # Para sa back button
    
    if form.validate_on_submit():
        new_response = PersonalCannedResponse(title=form.title.data, body=form.body.data, owner=current_user)
        db.session.add(new_response)
        db.session.commit()
        app.logger.info(f"User {current_user.email} added new personal response: '{form.title.data}'")
        flash('Your new personal response has been saved!', 'success')
        return redirect(url_for('manage_my_responses', ticket_id=ticket_id)) # Ipasa ulit ang ticket_id

    my_responses = PersonalCannedResponse.query.filter_by(user_id=current_user.id).order_by(PersonalCannedResponse.title).all()
    
    return render_template('manage_my_responses.html', title='My Personal Canned Responses', form=form, my_responses=my_responses, ticket_id=ticket_id)

@app.route('/my-responses/<int:response_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_my_response(response_id):
    response = db.session.get(PersonalCannedResponse, response_id)
    ticket_id = request.args.get('ticket_id') # Kunin para sa back button

    if not response or response.user_id != current_user.id or current_user.role not in ['Admin', 'Staff']:
        flash('Error: Response not found or you do not have permission to edit it.', 'danger')
        app.logger.warning(f"User {current_user.email} attempted to edit unauthorized/non-existent personal response ID: {response_id}")
        return redirect(url_for('manage_my_responses', ticket_id=ticket_id))

    form = PersonalCannedResponseForm(obj=response) 

    if form.validate_on_submit():
        response.title = form.title.data
        response.body = form.body.data
        db.session.commit()
        app.logger.info(f"User {current_user.email} updated personal response ID {response_id}")
        flash('Your personal response has been updated.', 'success')
        return redirect(url_for('manage_my_responses', ticket_id=ticket_id)) 

    return render_template('edit_my_response.html', title='Edit Personal Response', form=form, response_id=response_id, ticket_id=ticket_id)


@app.route('/my-responses/<int:response_id>/delete', methods=['POST'])
@login_required
def delete_my_response(response_id):
    response = db.session.get(PersonalCannedResponse, response_id)
    ticket_id = request.args.get('ticket_id') # Kunin para sa redirect
    
    if response and response.user_id == current_user.id:
        response_title = response.title
        db.session.delete(response)
        db.session.commit()
        app.logger.info(f"User {current_user.email} deleted personal response: '{response_title}'")
        flash('Your personal response has been deleted.', 'success')
    else:
        flash('Error: Response not found or you do not have permission to delete it.', 'danger')
        app.logger.warning(f"User {current_user.email} attempted to delete unauthorized/non-existent personal response ID: {response_id}")
        
    return redirect(url_for('manage_my_responses', ticket_id=ticket_id)) # Bumalik sa listahan

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
        
    # --- Form Mapping (Walang binago dito) ---
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
    
    # --- Pre-fill form (Walang binago) ---
    if request.method == 'GET' and current_user.is_authenticated:
        form.requester_email.data = current_user.email
        form.requester_name.data = current_user.name
        
    if form.validate_on_submit():
        
        # --- SIMULA NG FILE VALIDATION LOGIC ---
        files_to_save = {} # Store {field_name: FileStorage_object} for valid files
        validation_passed = True
        
        for field in form:
            # Check only FileFields that actually have data
            if field.type == 'FileField' and field.data:
                file = field.data
                filename = secure_filename(file.filename) # Get safe filename early
                field_label = field.label.text # Get the field label for error messages

                # 1. Size Check
                try:
                    file.seek(0, os.SEEK_END) # Go to the end of the file stream
                    file_size = file.tell()   # Get the position (which is the size in bytes)
                    file.seek(0)              # IMPORTANT: Go back to the start of the stream
                    
                    if file_size == 0:
                         flash(f"File '{filename}' for '{field_label}' appears to be empty. Please upload a valid file.", 'warning')
                         validation_passed = False
                         # Don't break here, let other checks proceed, but mark as failed

                    elif file_size > MAX_FILE_SIZE_BYTES:
                        flash(f"File '{filename}' ({field_label}) exceeds the {app.config['MAX_FILE_SIZE_MB']}MB size limit. Please upload a smaller file.", 'danger')
                        validation_passed = False
                        # Optional: break here if you want to stop checking immediately on first large file
                        # break 

                except Exception as e:
                    app.logger.error(f"Error checking size for file '{filename}' ({field_label}): {e}")
                    flash(f"Could not determine the size of file '{filename}'. Please try uploading again.", 'danger')
                    validation_passed = False
                    # Optional: break here

                # 2. Type Check (Double check, FileAllowed should catch most)
                # Check only if filename is not empty after securing
                if filename and ('.' not in filename or \
                   filename.rsplit('.', 1)[1].lower() not in ALLOWED_EXTENSIONS):
                     flash(f"File type for '{filename}' ({field_label}) is not allowed. Allowed types are: {', '.join(sorted(ALLOWED_EXTENSIONS))}.", 'danger')
                     validation_passed = False
                     # Optional: break here

                # If all checks for this file passed so far, add it to the list to be saved
                if validation_passed and file_size > 0: 
                    files_to_save[field.name] = file # Store the FileStorage object

        # If any validation failed, stop processing and re-render the form
        if not validation_passed:
             return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')
        # --- TAPOS NG FILE VALIDATION LOGIC ---

        # --- Proceed only if all validations passed ---
        details_data = {}
        general_fields = {f.name for f in GeneralTicketForm()}
        for field in form:
            if field.name not in general_fields and field.type not in ['FileField', 'CSRFTokenField', 'SubmitField']:
                if field.type == 'DateField':
                    details_data[field.name] = field.data.strftime('%Y-%m-%d') if field.data else None
                else:
                    details_data[field.name] = field.data

        # --- Save validated files ---
        saved_filenames_map = {} # Store {original_field_name: saved_filename}
        try:
            for field_name, file_to_save in files_to_save.items():
                original_filename = secure_filename(file_to_save.filename)
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f') # Added microseconds for more uniqueness
                # Create a more unique filename
                filename_to_save = f"{timestamp}_{field_name}_{original_filename}" 
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename_to_save)
                file_to_save.save(save_path)
                saved_filenames_map[field_name] = filename_to_save
                app.logger.info(f"Successfully saved file: {filename_to_save}")
        except Exception as e:
            app.logger.error(f"Error saving validated files for service {service_id}: {e}\n{traceback.format_exc()}")
            flash(f'An error occurred while saving attachments. Please try submitting again.', 'danger')
            # Consider deleting already saved files if needed, then re-render
            # For simplicity now, just re-render
            return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')
            
        # --- Ticket Number Generation (Walang binago) ---
        current_year = datetime.now(timezone.utc).year
        dept_code_map = {"ICT": "ICT", "Personnel": "PERS", "Legal Services": "LEGAL", "Office of the SDS": "SDS", "Accounting Unit": "ACCT", "Supply Office": "SUP"}
        dept_code = dept_code_map.get(service.department.name, "GEN")
        
        last_ticket = Ticket.query.filter(Ticket.ticket_number.like(f'{dept_code}-{current_year}-%')).order_by(Ticket.id.desc()).first()
        new_sequence = (int(last_ticket.ticket_number.split('-')[-1]) + 1) if last_ticket else 1
        new_ticket_number = f'{dept_code}-{current_year}-{new_sequence:04d}'
        
        # --- Create and Save Ticket (Walang binago) ---
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
            # Important: Commit here to get the new_ticket.id
            db.session.commit() 
            
            # --- Save Attachment Records to DB ---
            for saved_filename in saved_filenames_map.values():
                db.session.add(Attachment(filename=saved_filename, ticket_id=new_ticket.id))
            
            # Final commit for attachments
            db.session.commit() 
            
            app.logger.info(f"New ticket {new_ticket_number} created by {form.requester_email.data} for service '{service.name}' with {len(saved_filenames_map)} attachments.")
            send_new_ticket_email(new_ticket)
            flash(f'Your ticket has been created! A confirmation has been sent to your email. Your ticket number is {new_ticket_number}.', 'success')
            
            if current_user.is_authenticated:
                return redirect(url_for('my_tickets'))
            else:
                return redirect(url_for('select_department')) 
        except Exception as e:
            db.session.rollback() # Rollback changes if DB error occurs
            app.logger.error(f"Database error creating ticket {new_ticket_number} or attachments: {e}\n{traceback.format_exc()}")
            flash('A database error occurred while creating the ticket. Please try again.', 'danger')
            # Optional: Attempt to delete saved files here if DB fails
            return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')

    # --- Render form on GET or if validation fails (basic WTForms validation) ---
    return render_template('create_ticket_form.html', form=form, service=service, title=f'Request for {service.name}')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user_email = form.email.data
        user = User(name=form.name.data, email=user_email, role='User')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        app.logger.info(f"New user registered: {user_email}")
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
            app.logger.info(f"User {user.email} logged in successfully.")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            app.logger.warning(f"Failed login attempt for email: {form.username.data}")
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form, title='Login')


@app.route('/check-new-tickets')
@login_required
def check_new_tickets():
    """
    Checks for tickets posted after a given timestamp.
    Returns JSON: {'new_count': count, 'latest_timestamp': iso_timestamp_of_latest}
    """
    if current_user.role not in ['Admin', 'Staff']:
        return jsonify({'error': 'Unauthorized'}), 403

    since_iso = request.args.get('since', datetime.min.replace(tzinfo=timezone.utc).isoformat()) # Default with timezone
    try:
        # Use fromisoformat which handles timezone correctly ('Z' or '+00:00')
        since_dt = datetime.fromisoformat(since_iso.replace('Z', '+00:00'))
        # Ensure it's timezone-aware for comparison, default to UTC if naive
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        since_dt = datetime.min.replace(tzinfo=timezone.utc) # Default with timezone

    # Ensure date_posted is compared correctly (assuming date_posted is timezone-aware UTC in DB)
    base_query = Ticket.query.filter(Ticket.date_posted > since_dt)

    if current_user.role == 'Staff':
        managed_service_ids = [service.id for service in current_user.managed_services]
        if not managed_service_ids:
            return jsonify({'new_count': 0, 'latest_timestamp': since_iso})
        base_query = base_query.filter(Ticket.service_id.in_(managed_service_ids))
    
    new_count = base_query.count()

    latest_ticket = base_query.order_by(Ticket.date_posted.desc()).first()
    # Ensure the returned timestamp is also timezone-aware (ISO format includes offset)
    latest_timestamp_iso = latest_ticket.date_posted.isoformat() if latest_ticket else since_iso

    return jsonify({
        'new_count': new_count,
        'latest_timestamp': latest_timestamp_iso 
    })
# =================================================================
# === TAPOS NG ROUTE ==============================================
# =================================================================


@app.route('/logout')
@login_required
def logout():
    user_email = current_user.email
    logout_user()
    app.logger.info(f"User {user_email} logged out.")
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
            app.logger.info(f"Password reset requested for user: {form.email.data}")
        else:
            app.logger.warning(f"Password reset requested for non-existent email: {form.email.data}")
        flash('An email has been sent with instructions to reset your password (if the email exists in our system).', 'info')
        return redirect(url_for('login'))
    return render_template('request_reset.html', title='Reset Password', form=form)

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        app.logger.warning(f"Invalid or expired password reset token used.")
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        app.logger.info(f"Password reset successfully for user: {user.email}")
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        if e.code == 404:
            app.logger.warning(f"404 Not Found: {request.url}")
            return render_template("404.html"), 404 
        return e
    
    app.logger.error(f"An unexpected error occurred: {e}\n{traceback.format_exc()}")
    return render_template("500.html"), 500 

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')