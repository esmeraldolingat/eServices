# models.py
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize the database object here, without the app
db = SQLAlchemy()

# --- Model Classes ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), nullable=False, default='User')
    responses = db.relationship('Response', backref='author', lazy=True)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    @staticmethod
    def verify_reset_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
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
    canned_responses = db.relationship('CannedResponse', backref='response_department', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Department('{self.name}')"


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    tickets = db.relationship('Ticket', backref='service_type', lazy=True)

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

    def __repr__(self):
        return f"CannedResponse('{self.title}')"


class AuthorizedEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f"AuthorizedEmail('{self.email}')"