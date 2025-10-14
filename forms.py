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
    document_type = SelectField('Type of Document', choices=[('', '-- Select Type of Document --'), ('Division Memorandum', 'Division Memorandum'), ('Division Advisory', 'Division Advisory'), ('Office Memorandum', 'Office Memorandum'), ('Other', 'Other')], validators=[DataRequired()])
    document_type_other = StringField('If Other, please specify', validators=[Optional()])
    attachment = FileField('Issuance Attachment (PDF Only, max 25MB)', validators=[FileRequired(), FileAllowed(['pdf'], 'Invalid file type. Only PDF files are allowed.')])

class RepairForm(GeneralTicketForm):
    device_type = SelectField('Device Type', choices=[('', '-- Select Device Type --'), ('Laptop', 'Laptop'), ('Desktop', 'Desktop'), ('Printer', 'Printer'), ('Other', 'Other')], validators=[DataRequired()])
    device_type_other = StringField('If Other, please specify', validators=[Optional()])
    description = TextAreaField('Please provide a brief description of your request/concern.', validators=[DataRequired()])

class EmailAccountForm(GeneralTicketForm):
    school_id = StringField('School ID', validators=[DataRequired()])
    teacher_name = StringField('Complete Name of Teacher or Personnel', validators=[DataRequired()])
    sex = SelectField('Sex', choices=[('', '-- Select Sex --'), ('Male', 'Male'), ('Female', 'Female')], validators=[DataRequired()])
    birth_date = DateField('Date of Birth', format='%Y-%m-%d', validators=[DataRequired()])
    position = StringField('Position / Designation', validators=[DataRequired()])
    existing_email = StringField('Type DepEd Email for RESET, or N/A for NEW', validators=[DataRequired()])
    remarks = SelectField('Remarks', choices=[('', '-- Select Remarks --'), ('NEW ACCOUNT - DepEd Email (Gmail)', 'NEW ACCOUNT - DepEd Email (Gmail)'), ('NEW ACCOUNT - Microsoft Account', 'NEW ACCOUNT - Microsoft Account'), ('PASSWORD RESET - DepEd Email (Gmail)', 'PASSWORD RESET - DepEd Email (Gmail)'), ('PASSWORD RESET - Microsoft Email (juan.delacruz@deped.gov.ph)', 'PASSWORD RESET - Microsoft Email (juan.delacruz@deped.gov.ph)'), ('PASSWORD RESET - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)', 'PASSWORD RESET - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)'), ('REACTIVATE - DepEd Email (Gmail)', 'REACTIVATE - DepEd Email (Gmail)'), ('Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)', 'Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)'), ('Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@deped.gov.ph)', 'Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@deped.gov.ph)'), ('Remove Two-factor Authentication (2FA) - DepEd - Gmail (Google)', 'Remove Two-factor Authentication (2FA) - DepEd - Gmail (Google)'), ('Other', 'Other')], validators=[DataRequired()])
    remarks_other = StringField('If Other, please specify', validators=[Optional()])
    attachment = FileField('Certification (DepEd ID or Appointment Paper, PDF Only, max 25MB)', validators=[FileRequired(), FileAllowed(['pdf'], 'Invalid file type. Only PDF files are allowed.')])

class DpdsForm(GeneralTicketForm):
    school_id = StringField('School ID', validators=[DataRequired()])
    remarks = SelectField('Remarks', choices=[('', '-- Select Remarks --'), ('Password Reset', 'Password Reset'), ('Forgot Account', 'Forgot Account')], validators=[DataRequired()])

class DcpForm(GeneralTicketForm):
    school_id = StringField('School ID', validators=[DataRequired()])
    description = TextAreaField('Please provide a brief description of your request/concern.', validators=[DataRequired()])

class OtherIctForm(GeneralTicketForm):
    school_id = StringField('School ID', validators=[DataRequired()])
    description = TextAreaField('Please provide a brief description of your request/concern.', validators=[DataRequired()])

# ======================================================
# === PERSONNEL DEPARTMENT FORMS =======================
# ======================================================

class LeaveApplicationForm(GeneralTicketForm):
    type_of_leave = SelectField('Type of Leave', choices=[('', '-- Select Type of Leave --'), ('Vacation Leave', 'Vacation Leave'), ('Mandatory/Forced Leave', 'Mandatory/Forced Leave'), ('Sick Leave', 'Sick Leave'), ('Maternity Leave', 'Maternity Leave'), ('Paternity Leave', 'Paternity Leave'), ('Special Privilege Leave', 'Special Privilege Leave'), ('Solo Parent Leave', 'Solo Parent Leave'), ('Study Leave', 'Study Leave'), ('10-Day VAWC Leave', '10-Day VAWC Leave'), ('Rehabilitation Privilege', 'Rehabilitation Privilege'), ('Special Leave Benefits for Women', 'Special Leave Benefits for Women'), ('Special Emergency (Calamity) Leave', 'Special Emergency (Calamity) Leave'), ('Adoption Leave', 'Adoption Leave'), ('Monetization of Leave Credits', 'Monetization of Leave Credits'), ('Compensatory time off (CTO)', 'Compensatory time off (CTO)'), ('Other', 'Other')], validators=[DataRequired()])
    type_of_leave_other = StringField('If Other, please specify', validators=[Optional()])
    classification = SelectField('Classification', choices=[('', '-- Select Classification --'), ('Teaching Personnel', 'Teaching Personnel'), ('Non-Teaching Personnel', 'Non-Teaching Personnel')], validators=[DataRequired()])
    position = StringField('Position / Designation', validators=[DataRequired()])
    form6_attachment = FileField('Please attach a copy of your Form 6 (PDF Only, max 25MB)', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])
    supporting_docs_attachment = FileField('Please upload any supporting documents, if any (PDF Only, max 25MB)', validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])

class CoeForm(GeneralTicketForm):
    """Certificate of Employment"""
    first_day_of_service = DateField('1st Day of Service', format='%Y-%m-%d', validators=[DataRequired()])
    basic_salary = StringField('Basic Salary', validators=[DataRequired()])
    position = StringField('Position / Designation', validators=[DataRequired()])
    specific_purpose = TextAreaField('Specific Purpose of Request', validators=[DataRequired()])
    remarks = SelectField('Remarks', choices=[('', '-- Select Remarks --'), ('With Compensation', 'With Compensation'), ('Without Compensation', 'Without Compensation')], validators=[DataRequired()])
    first_day_cert_attachment = FileField('Please upload a scanned copy of your 1st Day of Service Certificate (PDF Only)', validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])
    coe_wo_comp_attachment = FileField('Please upload a copy of your COE without compensation, prepared by your School AO II (PDF Only)', validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])
    payslip_attachment = FileField('Please upload a scanned copy of your PAYSLIP (PDF Only)', validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])
    coe_w_comp_attachment = FileField('Please upload a copy of your COE with compensation, prepared by your School AO II (PDF Only)', validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])

class ServiceRecordForm(GeneralTicketForm):
    position = StringField('Position / Designation', validators=[DataRequired()])
    birth_date = DateField('Birthdate', format='%Y-%m-%d', validators=[DataRequired()])
    place_of_birth = StringField('Place of Birth', validators=[DataRequired()])
    specific_purpose = TextAreaField('Specific Purpose of Request', validators=[DataRequired()])
    delivery_method = SelectField('How would you like to receive your service record?', choices=[('', '-- Select a method --'), ('Hard copy (printed)', 'Hard copy (printed)'), ('Soft copy (digital/PDF)', 'Soft copy (digital/PDF)')], validators=[DataRequired()])

class GsisForm(GeneralTicketForm):
    """GSIS BP Number"""
    address_street = StringField('Street/ Barangay/ Village (CAPSLOCK)', validators=[DataRequired()])
    address_city = StringField('Municipality/ City/ Province (CAPSLOCK)', validators=[DataRequired()])
    postal_code = StringField('Postal Code', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('', '-- Select Gender --'), ('Male', 'Male'), ('Female', 'Female')], validators=[DataRequired()])
    civil_status = SelectField('Civil Status', choices=[('', '-- Select Civil Status --'), ('SINGLE', 'SINGLE'), ('MARRIED', 'MARRIED'), ('DIVORCED', 'DIVORCED'), ('SEPARATED', 'SEPARATED'), ('WIDOWED', 'WIDOWED'), ('Other', 'Other')], validators=[DataRequired()])
    civil_status_other = StringField('If Other, please specify', validators=[Optional()])
    birth_date = DateField('Date of Birth', format='%Y-%m-%d', validators=[DataRequired()])
    place_of_birth = StringField('Place of Birth', validators=[DataRequired()])
    basic_salary = StringField('Basic monthly salary', validators=[DataRequired()])
    effective_date_from = DateField('Effective date From', format='%Y-%m-%d', validators=[DataRequired()])
    effective_date_to = StringField('Effective date To (N/A if not required)', default='N/A', validators=[DataRequired()])
    employment_status = SelectField('Status of Employment', choices=[('', '-- Select Status --'), ('PERMANENT', 'PERMANENT'), ('CASUAL', 'CASUAL'), ('CONTRACTUAL', 'CONTRACTUAL'), ('PROVISIONAL', 'PROVISIONAL'), ('SUBSTITUTE', 'SUBSTITUTE')], validators=[DataRequired()])
    position = StringField('Position/ Designation', validators=[DataRequired()])
    previous_gsis_bp = StringField('For reemployed personnel, provide previous GSIS BP Number if any', validators=[Optional()])
    previous_appointment = SelectField('Did you have any previous government appointment?', choices=[('', '-- Select --'), ('No', 'No'), ('Yes', 'Yes')], validators=[DataRequired()])
    previous_agency = StringField('If Yes, indicate the name of the agency', validators=[Optional()])
    attachment = FileField('Please upload a scanned copy of the advice (PDF Only)', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])

# ======================================================
# === LEGAL SERVICES DEPARTMENT FORMS ==================
# ======================================================

class NoPendingCaseForm(GeneralTicketForm):
    """Certificate of No Pending Case"""
    position = StringField('Position / Designation', validators=[DataRequired()])
    purpose = TextAreaField('Purpose of Request', validators=[DataRequired()])
    attachment = FileField('Please attach a scanned copy of the appointment or a DepEd ID (PDF Only)', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])