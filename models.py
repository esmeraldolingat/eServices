# Heto ang buong laman ng models.py mo

from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize the database object here, without the app
db = SQLAlchemy()

# Association Table for User <-> Service many-to-many relationship
user_service_association = db.Table('user_service',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('service.id'), primary_key=True)
)

# --- Model Classes ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), nullable=False, default='User') # e.g., 'User', 'Staff', 'Admin'
    
    # Ito ay para sa mga "comments" o "replies" sa isang ticket
    responses = db.relationship('Response', backref='author', lazy=True) 

    managed_services = db.relationship('Service', secondary=user_service_association,
                                       backref=db.backref('managers', lazy='dynamic'),
                                       lazy='dynamic')
    
    # --- IDINAGDAG PARA SA PERSONAL RESPONSES ---
    personal_canned_responses = db.relationship('PersonalCannedResponse', backref='owner', lazy=True, cascade="all, delete-orphan")
    # --- HANGGANG DITO ---

    # Ito ang "shortcut" para makuha lahat ng tickets na naka-assign sa user na ito
    assigned_tickets = db.relationship(
        'Ticket', 
        foreign_keys='Ticket.assigned_staff_id',  # Sinasabi kung aling column ang gagamitin
        backref='assigned_staff',                 # Gagawa ito ng 'ticket.assigned_staff'
        lazy=True
    )


    def get_reset_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps(self.id, salt='password-reset-salt')

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(
                token,
                salt='password-reset-salt',
                max_age=expires_sec
            )
        except:
            return None
        return db.session.get(User, user_id)

    def __repr__(self):
        return f"User('{self.name}', '{self.email}', '{self.role}')"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    services = db.relationship('Service', backref='department', lazy=True, cascade="all, delete-orphan")
    tickets = db.relationship('Ticket', backref='ticket_department', lazy=True)
    
    canned_responses = db.relationship('CannedResponse', backref='department', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Department('{self.name}')"

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    tickets = db.relationship('Ticket', backref='service_type', lazy=True)
    
    canned_responses = db.relationship('CannedResponse', backref='service', lazy=True)

    def __repr__(self):
        return f"Service('{self.name}')"

class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    school_id_code = db.Column(db.String(20), unique=True, nullable=True)
    tickets = db.relationship('Ticket', backref='school', lazy=True)

    def __repr__(self):
        return f"School('{self.name}')"

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Open')
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    requester_name = db.Column(db.String(100), nullable=False)
    requester_email = db.Column(db.String(120), nullable=False)
    requester_contact = db.Column(db.String(50), nullable=True)
    details = db.Column(db.JSON, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=True)
    
    attachments = db.relationship('Attachment', backref='ticket', lazy=True, cascade="all, delete-orphan")
    responses = db.relationship('Response', backref='ticket', lazy=True, cascade="all, delete-orphan")


    # Ito ang column sa database na maglalaman ng ID ng naka-assign na staff
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)




    def __repr__(self):
        return f"Ticket('{self.ticket_number}', Status: '{self.status}')"

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)

    def __repr__(self):
        return f"Attachment('{self.filename}')"



class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, nullable=False, default=False)    
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)

    def __repr__(self):
        return f"Response on Ticket {self.ticket_id}"


class CannedResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False) 
    body = db.Column(db.Text, nullable=False) 
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False) 
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)

    def __repr__(self):
        return f"CannedResponse('{self.title}')"

class AuthorizedEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f"AuthorizedEmail('{self.email}')"

# --- BAGONG MODEL PARA SA PERSONAL RESPONSES ---
class PersonalCannedResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False) # Isang maikling title, e.g., "My Follow-up"
    body = db.Column(db.Text, nullable=False) # Ang buong text ng response
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Sino ang may-ari nito

    def __repr__(self):
        return f"PersonalCannedResponse('{self.title}' by User {self.user_id})"

