import os
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import or_, case
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from collections import defaultdict
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from forms import TicketForm, UpdateTicketForm, DEPARTMENTS_AND_SERVICES, CANNED_RESPONSES, LoginForm

app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = 'a-really-long-and-secret-string-nobody-can-guess'
basedir = os.path.abspath(os.path.dirname(__file__))
# Database Config
instance_path = os.path.join(basedir, 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'tickets.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# File Upload Config
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB limit
# EMAIL CONFIGURATION
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'tarlac.city@deped.gov.ph'  # PALITAN ITO
app.config['MAIL_PASSWORD'] = 'awutrwsieameobrc'      # PALITAN ITO

db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

# --- LOGIN MANAGER SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Database Models ---
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False)
    client_name = db.Column(db.String(100), nullable=False)
    client_email = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='New')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    resolution_details = db.Column(db.Text, nullable=True)
    document_title = db.Column(db.String(255), nullable=True)
    document_type = db.Column(db.String(100), nullable=True)
    attachment_filename = db.Column(db.String(255), nullable=True)
    device_type = db.Column(db.String(100), nullable=True)
    device_type_other = db.Column(db.String(255), nullable=True)
    school_id = db.Column(db.String(50), nullable=True)
    school_name = db.Column(db.String(255), nullable=True)
    personnel_first_name = db.Column(db.String(100), nullable=True)
    personnel_middle_name = db.Column(db.String(100), nullable=True)
    personnel_last_name = db.Column(db.String(100), nullable=True)
    ext_name = db.Column(db.String(10), nullable=True)
    sex = db.Column(db.String(10), nullable=True)
    date_of_birth = db.Column(db.String(50), nullable=True)
    position = db.Column(db.String(100), nullable=True)
    existing_email_or_na = db.Column(db.String(120), nullable=True)
    remarks = db.Column(db.String(255), nullable=True)
    contact_number = db.Column(db.String(50), nullable=True)
    document_type_other = db.Column(db.String(255), nullable=True)
    position_other = db.Column(db.String(255), nullable=True)
    remarks_other = db.Column(db.String(255), nullable=True)
    employee_number = db.Column(db.String(50), nullable=True)
    date_of_last_appointment = db.Column(db.String(50), nullable=True)
    # >>>>> ITO ANG IDINAGDAG <<<<<
    dpds_remarks = db.Column(db.String(100), nullable=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(100), nullable=False) 
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    # Inayos ang warning para sa legacy SQLAlchemy
    return db.session.get(User, int(user_id))

def generate_details_html(ticket):
    details = []
    if ticket.department == 'ICT':
        if ticket.service_type == 'Issuances and Online Materials':
            details.append(f"<b>Document Title:</b> {ticket.document_title or 'N/A'}")
            doc_type_display = ticket.document_type
            if ticket.document_type == 'Other' and ticket.document_type_other:
                doc_type_display += f" ({ticket.document_type_other})"
            details.append(f"<b>Document Type:</b> {doc_type_display or 'N/A'}")
        elif ticket.service_type == 'Repair, Maintenance and Troubleshoot of IT Equipment':
            device = ticket.device_type
            if device == 'Other' and ticket.device_type_other:
                device = ticket.device_type_other
            details.append(f"<b>Device Type:</b> {device or 'N/A'}")
            details.append(f"<b>Problem Description:</b> {ticket.description or 'N/A'}")
        elif ticket.service_type == 'DepEd Email Account':
            details.append(f"<b>School ID:</b> {ticket.school_id or 'N/A'}")
            details.append(f"<b>School Name:</b> {ticket.school_name or 'N/A'}")
            details.append(f"<b>Full Name:</b> {ticket.personnel_first_name} {ticket.personnel_middle_name} {ticket.personnel_last_name}")
            position_display = ticket.position
            if ticket.position == 'Other' and ticket.position_other:
                position_display += f" ({ticket.position_other})"
            details.append(f"<b>Position:</b> {position_display or 'N/A'}")
            remarks_display = ticket.remarks
            if ticket.remarks == 'Other' and ticket.remarks_other:
                remarks_display += f" ({ticket.remarks_other})"
            details.append(f"<b>Request Remarks:</b> {remarks_display or 'N/A'}")
        elif ticket.service_type == 'DPDS - DepEd Partnership Database System':
            details.append(f"<b>School Name:</b> {ticket.school_name or 'N/A'}")
            details.append(f"<b>Contact Number:</b> {ticket.contact_number or 'N/A'}")
            details.append(f"<b>School ID:</b> {ticket.school_id or 'N/A'}")
            details.append(f"<b>Remarks:</b> {ticket.dpds_remarks or 'N/A'}")
        elif ticket.service_type in ['DCP - DepEd Computerization Program: After-sales', 'other ICT - Technical Assistance Needed']:
            details.append(f"<b>School Name:</b> {ticket.school_name or 'N/A'}")
            details.append(f"<b>Contact Number:</b> {ticket.contact_number or 'N/A'}")
            details.append(f"<b>Description:</b> {ticket.description or 'N/A'}")
    return "<br>".join(details) if details else "No specific details were provided for this request."


# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
        login_user(user)
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('home')
        return redirect(next_page)
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/create-admin')
def create_admin():
    if User.query.filter_by(username='admin').first():
        return 'Admin user already exists. Use /reset-admin-password if needed.'
    user = User(username='admin', role='ICT')
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return 'Admin user created successfully! Username: admin, Password: password'

@app.route('/reset-admin-password')
def reset_admin():
    user = User.query.filter_by(username='admin').first()
    if not user:
        return 'Admin user not found. Please visit /create-admin first.'
    user.set_password('password')
    db.session.commit()
    return 'Admin password has been reset to "password". You can now log in.'

@app.route('/')
@login_required
def home():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    status_filter = request.args.get('status', 'Active')
    query = Ticket.query
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(or_(Ticket.ticket_number.ilike(search_term), Ticket.client_name.ilike(search_term), Ticket.service_type.ilike(search_term)))
    if status_filter == 'Active':
        query = query.filter(Ticket.status.in_(['New', 'In Progress']))
    elif status_filter:
        query = query.filter(Ticket.status == status_filter)
    status_order = case((Ticket.status == 'New', 1), (Ticket.status == 'In Progress', 2), (Ticket.status == 'Resolved', 3), else_=4)
    pagination = query.order_by(status_order, Ticket.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    tickets = pagination.items
    return render_template('dashboard.html', all_tickets=tickets, pagination=pagination, search_query=search_query, status_filter=status_filter)

@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def ticket_detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    form = UpdateTicketForm()
    if form.validate_on_submit():
        previous_status = ticket.status
        ticket.status = form.status.data
        ticket.resolution_details = form.resolution_details.data
        db.session.commit()
        if ticket.status == 'Resolved' and previous_status != 'Resolved':
            try:
                subject = f"Your Service Request has been resolved - Ticket # {ticket.ticket_number}"
                resolution_text = ticket.resolution_details
                details_html = generate_details_html(ticket)
                email_html = f"""<p>Dear {ticket.client_name},</p><p>This is to inform you that your service request has been marked as resolved.</p><hr>
                               <p><b>Ticket #:</b> {ticket.ticket_number}</p>
                               <p><b>Department:</b> {ticket.department}</p>
                               <p><b>Service Requested:</b> {ticket.service_type}</p>
                               <p><b>Original Request Details:</b><br>{details_html}</p><hr>
                               <h3>Resolution:</h3>
                               <p>{resolution_text.replace('\n', '<br>') if resolution_text else 'N/A'}</p><hr>
                               <p>For feedback on the services provided, please click the link: <a href="https://bit.ly/2025TCSDCSM">Client Satisfaction Survey</a></p>
                               <p>Thank you!</p>"""
                msg = Message(subject, sender=('TCSD e-Services', app.config['MAIL_USERNAME']), recipients=[ticket.client_email])
                msg.html = email_html
                mail.send(msg)
                flash('Ticket has been resolved and a notification email has been sent to the client.', 'success')
            except Exception as e:
                print("!!! RESOLUTION EMAIL FAILED. ERROR: ", e)
                flash('Ticket was updated, but the resolution email could not be sent. Please check server logs.', 'warning')
        else:
            flash('Ticket has been updated successfully!', 'success')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    form.status.data = ticket.status
    form.resolution_details.data = ticket.resolution_details
    return render_template('ticket_detail.html', ticket=ticket, form=form, CANNED_RESPONSES=CANNED_RESPONSES)

@app.route('/create', methods=['GET', 'POST'])
def create_ticket():
    form = TicketForm()
    if request.method == 'POST':
        form.service_type.choices = [(service, service) for service in DEPARTMENTS_AND_SERVICES.get(form.department.data, [])]
    if form.validate_on_submit():
        current_year = datetime.now(timezone.utc).year
        last_ticket = Ticket.query.order_by(Ticket.id.desc()).first()
        new_sequence = 1
        if last_ticket:
            try:
                last_ticket_year = int(last_ticket.ticket_number.split('-')[1])
                if last_ticket_year == current_year:
                    last_sequence = int(last_ticket.ticket_number.split('-')[-1])
                    new_sequence = last_sequence + 1
            except (ValueError, IndexError):
                new_sequence = (Ticket.query.filter(Ticket.ticket_number.like(f'%-{current_year}-%')).count() or 0) + 1
        new_ticket_number = f'TCSD-{current_year}-{new_sequence:04d}'
        saved_filename = None
        file_to_save = form.issuance_attachment.data or form.certification_attachment.data
        if file_to_save:
            filename = secure_filename(file_to_save.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file_to_save.save(file_path)
            saved_filename = filename
        new_ticket = Ticket(
            ticket_number=new_ticket_number, client_name=form.client_name.data, client_email=form.client_email.data, department=form.department.data,
            service_type=form.service_type.data, description=form.description.data, attachment_filename=saved_filename,
            document_title=form.document_title.data, document_type=form.document_type.data, device_type=form.device_type.data,
            device_type_other=form.device_type_other.data, school_id=form.school_id.data, school_name=form.school_name_select.data or form.school_name_text.data,
            personnel_first_name=form.personnel_first_name.data, personnel_middle_name=form.personnel_middle_name.data,
            personnel_last_name=form.personnel_last_name.data, ext_name=form.ext_name.data, sex=form.sex.data,
            date_of_birth=form.date_of_birth.data.strftime('%Y-%m-%d') if form.date_of_birth.data else None,
            position=form.position.data, existing_email_or_na=form.existing_email_or_na.data, remarks=form.remarks.data,
            contact_number=form.contact_number.data, document_type_other=form.document_type_other.data,
            position_other=form.position_other.data, remarks_other=form.remarks_other.data, employee_number=form.employee_number.data,
            date_of_last_appointment=form.date_of_last_appointment.data,
            dpds_remarks=form.dpds_remarks.data
        )
        db.session.add(new_ticket)
        db.session.commit()
        try:
            subject = f"Service Request Received - Ticket # {new_ticket.ticket_number}"
            details_html = generate_details_html(new_ticket)
            email_html = f"""<p>Dear {new_ticket.client_name},</p><p>This is to confirm that we have received your service request with the following details:</p><hr>
                           <p><b>Open Ticket No.:</b> {new_ticket.ticket_number}</p>
                           <p><b>Date and Time:</b> {new_ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                           <p><b>Department:</b> {new_ticket.department}</p>
                           <p><b>Service Requested:</b> {new_ticket.service_type}</p>
                           <p><b>Details Submitted:</b><br>{details_html}</p><hr>
                           <p>We are currently assessing your transaction and will get back to you as soon as possible. Thank you.</p>
                           <p><b>Sincerely,<br>Tarlac City Schools Division e-Services</b></p>"""
            msg = Message(subject, sender=('TCSD e-Services', app.config['MAIL_USERNAME']), recipients=[new_ticket.client_email])
            msg.html = email_html
            mail.send(msg)
        except Exception as e:
            print("!!! EMAIL SENDING FAILED. ERROR: ", e)
        return redirect(url_for('success_page'))
    return render_template('create_ticket.html', form=form, DEPARTMENTS_AND_SERVICES=DEPARTMENTS_AND_SERVICES)

@app.route('/success')
def success_page():
    return render_template('success.html')

@app.route('/summary')
@login_required
def summary():
    current_year = datetime.now().year
    year = request.args.get('year', current_year, type=int)
    tickets_in_year = Ticket.query.filter(db.func.strftime('%Y', Ticket.created_at) == str(year)).all()
    temp_form = TicketForm()
    service_types = sorted([choice[0] for choice in temp_form.service_type.choices if choice[0]])
    months = [datetime(year, m, 1).strftime('%B') for m in range(1, 13)]
    monthly_summary = {month: {cat: 0 for cat in service_types + ['total']} for month in months}
    for ticket in tickets_in_year:
        if isinstance(ticket.created_at, datetime):
            month_name = ticket.created_at.strftime('%B')
            if ticket.service_type in monthly_summary[month_name]:
                monthly_summary[month_name][ticket.service_type] += 1
            monthly_summary[month_name]['total'] += 1
    quarterly_summary = {'Q1': {cat: 0 for cat in service_types + ['total']}, 'Q2': {cat: 0 for cat in service_types + ['total']}, 'Q3': {cat: 0 for cat in service_types + ['total']}, 'Q4': {cat: 0 for cat in service_types + ['total']}}
    for month_index, month_name in enumerate(months):
        quarter = f'Q{(month_index // 3) + 1}'
        for cat in service_types + ['total']:
            quarterly_summary[quarter][cat] += monthly_summary[month_name][cat]
    grand_total = {cat: 0 for cat in service_types + ['total']}
    for month_name in months:
        for cat in service_types + ['total']:
            grand_total[cat] += monthly_summary[month_name][cat]
    chart_labels = service_types
    chart_data = [grand_total[st] for st in service_types]
    all_ticket_years = db.session.query(db.func.strftime('%Y', Ticket.created_at)).distinct().all()
    available_years = sorted([int(y[0]) for y in all_ticket_years], reverse=True)
    if not available_years:
        available_years.append(current_year)
    return render_template('summary.html',
                           monthly_summary=monthly_summary,
                           quarterly_summary=quarterly_summary,
                           grand_total=grand_total,
                           service_types=service_types,
                           months=months,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           selected_year=year,
                           available_years=available_years)

if __name__ == '__main__':
    app.run(debug=True)

    

