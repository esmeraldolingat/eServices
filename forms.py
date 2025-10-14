# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, PasswordField, TextAreaField, DateField
from wtforms.validators import DataRequired, Email, Length, Optional
from flask_wtf.file import FileField, FileRequired, FileAllowed
from sqlalchemy import case

from models import School

# ======================================================
# === BASE & LOGIN FORMS ===============================
# ======================================================

class DepartmentSelectionForm(FlaskForm):
    department = SelectField('Select a Department', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Next')

class ServiceSelectionForm(FlaskForm):
    service = SelectField('Select a Service', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Next')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class GeneralTicketForm(FlaskForm):
    """Base form with common requester info."""
    requester_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    requester_email = StringField('DepEd Email Address', validators=[DataRequired(), Email()])
    requester_contact = StringField('Contact Number', validators=[DataRequired(), Length(min=7, max=15)])
    school = SelectField('School / Office', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Submit Ticket')

    def __init__(self, *args, **kwargs):
        super(GeneralTicketForm, self).__init__(*args, **kwargs)
        custom_order = case((School.name == "Division Office", 0), else_=1)
        all_schools = School.query.order_by(custom_order, School.name).all()
        self.school.choices = [(0, "-- Select your School/Office --")] + [(s.id, s.name) for s in all_schools]

# ======================================================
# === ICT DEPARTMENT FORMS =============================
# ======================================================

class IssuanceForm(GeneralTicketForm):
    document_title = StringField('Title of Document/Material', validators=[DataRequired()])
    document_type = SelectField('Type of Document', choices=[
        ('', '-- Select Type of Document --'), ('Division Memorandum', 'Division Memorandum'),
        ('Division Advisory', 'Division Advisory'), ('Office Memorandum', 'Office Memorandum'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    document_type_other = StringField('If Other, please specify', validators=[Optional()])
    attachment = FileField('Issuance Attachment (PDF Only, max 25MB)', validators=[
        FileRequired(), FileAllowed(['pdf'], 'Invalid file type. Only PDF files are allowed.')
    ])

class RepairForm(GeneralTicketForm):
    device_type = SelectField('Device Type', choices=[
        ('', '-- Select Device Type --'), ('Laptop', 'Laptop'), ('Desktop', 'Desktop'),
        ('Printer', 'Printer'), ('Other', 'Other')
    ], validators=[DataRequired()])
    device_type_other = StringField('If Other, please specify', validators=[Optional()])
    description = TextAreaField('Please provide a brief description of your request/concern.', validators=[DataRequired()])

class EmailAccountForm(GeneralTicketForm):
    school_id = StringField('School ID', validators=[DataRequired()])
    # The "Name of School" dropdown is already inherited from GeneralTicketForm
    teacher_name = StringField('Complete Name of Teacher or Personnel', validators=[DataRequired()])
    sex = SelectField('Sex', choices=[('', '-- Select Sex --'), ('Male', 'Male'), ('Female', 'Female')], validators=[DataRequired()])
    birth_date = DateField('Date of Birth', format='%Y-%m-%d', validators=[DataRequired()])
    position = StringField('Position / Designation', validators=[DataRequired()])
    existing_email = StringField('Type DepEd Email for RESET, or N/A for NEW', validators=[DataRequired()])
    remarks = SelectField('Remarks', choices=[
        ('', '-- Select Remarks --'),
        # CORRECTED: Now using (value, label) tuples
        ('NEW ACCOUNT - DepEd Email (Gmail)', 'NEW ACCOUNT - DepEd Email (Gmail)'),
        ('NEW ACCOUNT - Microsoft Account', 'NEW ACCOUNT - Microsoft Account'),
        ('PASSWORD RESET - DepEd Email (Gmail)', 'PASSWORD RESET - DepEd Email (Gmail)'),
        ('PASSWORD RESET - Microsoft Email (juan.delacruz@deped.gov.ph)', 'PASSWORD RESET - Microsoft Email (juan.delacruz@deped.gov.ph)'),
        ('PASSWORD RESET - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)', 'PASSWORD RESET - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)'),
        ('REACTIVATE - DepEd Email (Gmail)', 'REACTIVATE - DepEd Email (Gmail)'),
        ('Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)', 'Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)'),
        ('Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@deped.gov.ph)', 'Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@deped.gov.ph)'),
        ('Remove Two-factor Authentication (2FA) - DepEd - Gmail (Google)', 'Remove Two-factor Authentication (2FA) - DepEd - Gmail (Google)'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    remarks_other = StringField('If Other, please specify', validators=[Optional()])
    attachment = FileField('Certification (DepEd ID or Appointment Paper, PDF Only, max 25MB)', validators=[
        FileRequired(), FileAllowed(['pdf'], 'Invalid file type. Only PDF files are allowed.')
    ])

class DpdsForm(GeneralTicketForm):
    school_id = StringField('School ID', validators=[DataRequired()])
    # CORRECTED: Now using (value, label) tuples
    remarks = SelectField('Remarks', choices=[
        ('', '-- Select Remarks --'),
        ('Password Reset', 'Password Reset'),
        ('Forgot Account', 'Forgot Account')
    ], validators=[DataRequired()])

class DcpForm(GeneralTicketForm):
    school_id = StringField('School ID', validators=[DataRequired()])
    description = TextAreaField('Please provide a brief description of your request/concern.', validators=[DataRequired()])

class OtherIctForm(GeneralTicketForm):
    school_id = StringField('School ID', validators=[DataRequired()])
    description = TextAreaField('Please provide a brief description of your request/concern.', validators=[DataRequired()])