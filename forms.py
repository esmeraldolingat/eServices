from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, PasswordField, TextAreaField, DateField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError, EqualTo
from flask_wtf.file import FileField, FileRequired, FileAllowed
from sqlalchemy import case
from flask_login import current_user # <-- ITO ANG IDINAGDAG NA IMPORT

# Import all necessary models
from models import School, AuthorizedEmail, User, Department

# ======================================================
# === CUSTOM VALIDATOR =================================
# ======================================================

def is_authorized_email(form, field):
    """Checks if the submitted email exists in the AuthorizedEmail table."""
    email_exists = AuthorizedEmail.query.filter_by(email=field.data).first()
    if not email_exists:
        raise ValidationError('This email address is not authorized to submit requests.')

# ======================================================
# === BASE, LOGIN & ADMIN FORMS ========================
# ======================================================

class DepartmentSelectionForm(FlaskForm):
    department = SelectField('Select a Department', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Next')

class ServiceSelectionForm(FlaskForm):
    service = SelectField('Select a Service', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Next')

class LoginForm(FlaskForm):
    username = StringField('DepEd Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class EditUserForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[('User', 'User'), ('Staff', 'Staff'), ('Admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Update User')

class AddAuthorizedEmailForm(FlaskForm):
    email = StringField('DepEd Email Address', validators=[DataRequired(), Email()])
    submit = SubmitField('Add Email')

    def validate_email(self, email):
        """Checks if the email is already authorized."""
        existing_email = AuthorizedEmail.query.filter_by(email=email.data).first()
        if existing_email:
            raise ValidationError('That email address is already authorized.')

class BulkUploadForm(FlaskForm):
    csv_file = FileField('Upload CSV', validators=[FileRequired(), FileAllowed(['csv'], 'Only CSV files are allowed!')])
    submit_bulk = SubmitField('Upload Bulk')

class DepartmentForm(FlaskForm):
    name = StringField('Department Name', validators=[DataRequired()])
    submit = SubmitField('Save Department')

    def validate_name(self, name):
        """Checks if the department name already exists."""
        existing_dept = Department.query.filter_by(name=name.data).first()
        if existing_dept:
            raise ValidationError('That department name already exists.')

class CannedResponseForm(FlaskForm):
    title = StringField('Response Title (e.g., "Password Reset Steps")', validators=[DataRequired()])
    body = TextAreaField('Response Body (This is the text that will be inserted)', validators=[DataRequired()])
    department_id = SelectField('Department', coerce=int, validators=[DataRequired()])
    service_id = SelectField('Specific Service (Optional)', coerce=int, validators=[Optional()]) # Added service_id
    submit = SubmitField('Save Response')


# ======================================================
# === TICKET & RESPONSE FORMS ==========================
# ======================================================

class GeneralTicketForm(FlaskForm):
    requester_name = StringField('Full Name', validators=[DataRequired()])
    requester_email = StringField('Email Address', validators=[DataRequired(), Email()], render_kw={'readonly': True})
    requester_contact = StringField('Contact Number')
    school = SelectField('School/Office', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Submit Ticket')

    def __init__(self, *args, **kwargs):
        super(GeneralTicketForm, self).__init__(*args, **kwargs)
        custom_order = case((School.name == "Division Office", 0), else_=1)
        all_schools = School.query.order_by(custom_order, School.name).all()
        self.school.choices = [(0, "-- Select your School/Office --")] + [(s.id, s.name) for s in all_schools]

class ResponseForm(FlaskForm):
    body = TextAreaField('Your Response', validators=[DataRequired()])
    attachment = FileField('Add Attachment (Optional)', validators=[Optional(), FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'], 'Allowed file types are: pdf, images, word docs')])
    submit = SubmitField('Submit Response')

class UpdateTicketForm(FlaskForm):
    body = TextAreaField('Response / Resolution Details', validators=[DataRequired()])
    status = SelectField('Update Status', choices=[('Open', 'Open'), ('In Progress', 'In Progress'), ('Resolved', 'Resolved')], validators=[DataRequired()])
    attachment = FileField('Add Attachment (Optional)', validators=[Optional(), FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'], 'Allowed file types are: pdf, images, word docs')])
    submit = SubmitField('Submit Update')

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
    position = StringField('Position / Designation', validators=[DataRequired()])
    purpose = TextAreaField('Purpose of Request', validators=[DataRequired()])
    attachment = FileField('Please attach a scanned copy of the appointment or a DepEd ID (PDF Only)', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])

# ======================================================
# === OFFICE OF THE SDS FORMS ==========================
# ======================================================

class LocatorSlipForm(GeneralTicketForm):
    position = StringField('Position / Designation', validators=[DataRequired()])
    attachment = FileField('Please attach a copy of your request for a Locator Slip (PDF Only)', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])

class AuthorityToTravelForm(GeneralTicketForm):
    position = StringField('Position / Designation', validators=[DataRequired()])
    attachment = FileField('Please attach a copy of your request for Authority to Travel (PDF Only)', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])

class OicDesignationForm(GeneralTicketForm):
    position = StringField('Position / Designation', validators=[DataRequired()])
    attachment = FileField('Please attach a copy of your request for OIC Designation (PDF Only)', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])

class SubstituteTeacherForm(GeneralTicketForm):
    position = StringField('Position / Designation', validators=[DataRequired()])
    attachment = FileField('Please attach a copy of your request for a Substitute Teacher (PDF Only)', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])

class AdmForm(GeneralTicketForm):
    position = StringField('Position / Designation', validators=[DataRequired()])
    attachment = FileField('Please attach a copy of your request for Alternative Delivery Mode (PDF Only)', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])

# ======================================================
# === ACCOUNTING UNIT FORMS ============================
# ======================================================

class ProvidentFundForm(GeneralTicketForm):
    position = StringField('Position / Designation', validators=[DataRequired()])
    employee_number = StringField('Employee Number', validators=[DataRequired()])
    station_no = StringField('Station No.', validators=[DataRequired()])
    query = SelectField('Query', choices=[('', '-- Select your Query --'), ('Application for a Provident Loan (1st time Borrower)', 'Application for a Provident Loan (1st time Borrower)'), ('Application for a Provident Loan (10K-100K) - old applicant', 'Application for a Provident Loan (10K-100K) - old applicant'), ('Application for a Provident Loan (Additional 100K)', 'Application for a Provident Loan (Additional 100K)'), ('Status of Application', 'Status of Application'), ('Statement of Account', 'Statement of Account'), ('Request for Provident Loan Accountability Clearance', 'Request for Provident Loan Accountability Clearance')], validators=[DataRequired()])
    LABEL_FIRST_TIME = """For employment verification, please attach scanned copies of the following documents (1 file only):
1. Provident Fund Form (front and back)
2. Deduction Authorization Letter
3. Your LATEST payslip and your co-maker's LATEST payslip
4. Your valid ID and your co-maker's valid ID, both with facsimile signatures
5. Approved Appointment"""
    LABEL_OLD_APPLICANT = """For employment verification, please attach scanned copies of the following documents (1 file only):
1. Provident Fund Form (front and back)
2. Deduction Authorization Letter
3. Your LATEST payslip and your co-maker's LATEST payslip
4. Your valid ID and your co-maker's valid ID, both with facsimile signatures"""
    LABEL_ADDITIONAL = """For employment verification, please attach scanned copies of the following documents (1 file only):
1. Provident Fund Form (front and back)
2. Deduction Authorization Letter
3. Your LATEST payslip and your co-maker's LATEST payslip
4. Your valid ID and your co-maker's valid ID, both with facsimile signatures
5. Request Letter
6. Hospital Bill/ Death Certificate etc."""
    LABEL_STATUS = "For employment verification, please attach scanned copy of your PRC ID/ Appointment or any valid documents in PDF format."
    LABEL_STATEMENT = "For employment verification, please attach scanned copy of your Intent to Resign Letter/ Retirement Notification Letter/ Letter of Intent to Travel Abroad etc."
    LABEL_CLEARANCE = "For employment verification, please attach scanned copy of your PRC ID/ Appointment or any valid documents in PDF format."
    attachment_first_time = FileField(LABEL_FIRST_TIME, validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])
    attachment_old_applicant = FileField(LABEL_OLD_APPLICANT, validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])
    attachment_additional = FileField(LABEL_ADDITIONAL, validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])
    attachment_status = FileField(LABEL_STATUS, validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])
    attachment_statement = FileField(LABEL_STATEMENT, validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])
    attachment_clearance = FileField(LABEL_CLEARANCE, validators=[Optional(), FileAllowed(['pdf'], 'PDF documents only!')])

# ======================================================
# === SUPPLY OFFICE FORMS ==============================
# ======================================================

class IcsForm(GeneralTicketForm):
    position = StringField('Position / Designation', validators=[DataRequired()])
    attachment = FileField('Please attach a copy of your Inventory Custodian Sheet - ICS in PDF format', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF documents only!')])

# ======================================================
# === REGISTRATION & PASSWORD RESET FORMS ==============
# ======================================================

class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('DepEd Email Address', validators=[DataRequired(), Email(), is_authorized_email])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    def validate_email(self, email):
        """Checks if the email is already registered."""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already registered. Please log in.')

class RequestResetForm(FlaskForm):
    email = StringField('DepEd Email Address', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('There is no account with that email. You must register first.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


# ======================================================
# === PERSONAL RESPONSE FORM ===========================
# ======================================================
class PersonalCannedResponseForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(message="Please provide a short title for this response.")])
    body = TextAreaField('Response Text', validators=[DataRequired(message="Response body cannot be empty.")], render_kw={'rows': 5})
    submit = SubmitField('Save Response')


# ======================================================
# === PROFILE FORMS ====================================
# ======================================================

class UpdateProfileForm(FlaskForm):
    """Form para i-update ang pangalan ng user."""
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email (Cannot be changed)', render_kw={'readonly': True})
    submit_profile = SubmitField('Update Name')

class ChangePasswordForm(FlaskForm):
    """Form para palitan ang password ng user."""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit_password = SubmitField('Change Password')

    # Custom validator para i-check kung tama ang current password
    def validate_current_password(self, current_password):
        if not current_user.check_password(current_password.data):
            raise ValidationError('Incorrect current password.')

