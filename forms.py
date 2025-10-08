from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TextAreaField, SubmitField, BooleanField, DateField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Email, Optional, ValidationError

# --- CANNED RESPONSES and DEPARTMENTS_AND_SERVICES dictionaries remain the same ---
CANNED_RESPONSES = {
    'ICT': [
        "Your transaction was already processed and completed. We will now close this ticket. Thank you.",
        "The files you uploaded have already been posted on the Division Website. Thank you.",
        "Use your temporary password to sign in to your DepEd Google account at Gmail.com",
        "Use your temporary password to sign in to your DepEd Microsoft account on Office.com",
        "Use your temporary password to sign in to your official school email address at partnershipsdatabase.deped.gov.ph",
        "The two-factor authentication has been successfully disabled. You can now access the provided email account using the same password that was previously set.",
        "Please provide the email address for which you wish to remove two-factor authentication. Thank you.",
        "Kindly provide the DepEd email address you wish to have reset by the ICTU. Thank you.",
        "Your request has been forwarded to the DepEd Central Office. We will email you the information as soon as the Microsoft account has been successfully created.",
        "Your request has been sent to the DepEd Central Office. Please wait for further instructions. Thank you.",
        "You sent more than one request with same Technical Services Needed to ICTU. We will disregard this request. Thank you.",
        "A DepEd Google account is required to create a Microsoft account. Kindly provide the DepEd Google account. Thank you.",
        "The form is incomplete. Kindly provide us the needed information. Choose the right Technical Services Needed.",
        "Please use valid attachment as proof for the newly hired teacher. Thank you.",
        "The activation of the DepEd email account is pending and that the recipient should wait for the Central Office to handle the activation process. Thank you",
        "Please ensure that your Google Drive storage does not exceed the maximum allocation of 100GB per person. Exceeding this limit will result in the suspension of Google Apps usage, so please free up space accordingly.",
        "Your account has been disabled by admin. To reactivate: 1. Visit Division Office (ICTU) for assistance or call Esmeraldo Lingat: (045) 982 4514. Thank you.",
        "The DepEd email account you provided is already activated. We cannot make any changes to this account. Thank you.",
        "If you want to use Canva, you need to link your Microsoft account to it. However, if your Microsoft account is not working, you may have used the wrong account, or if the account is correct, you might have forgotten the password. To resolve this issue, please ask your school ICT Coordinator to request a password reset from the Division ICT Unit (ICTU). Thank you."
    ],
    'Personnel': [], 'Legal Services': [], 'Office of the SDS': [], 'Accounting': [], 'Supply Office': []
}

DEPARTMENTS_AND_SERVICES = {
    'ICT': ['Issuances and Online Materials', 'Repair, Maintenance and Troubleshoot of IT Equipment', 'DepEd Email Account', 'DPDS - DepEd Partnership Database System', 'DCP - DepEd Computerization Program: After-sales', 'other ICT - Technical Assistance Needed'],
    'Personnel': ['Application for Leave of Absence', 'Certificate of Employment', 'Service Record', 'GSIS BP Number'],
    'Legal Services': ['Certificate of NO-Pending Case'],
    'Office of the SDS': ['Request for Approval of Locator Slip', 'Request for Approval of Authority to Travel', 'Request for Designation of Officer-in-Charge at the School', 'Request for Substitute Teacher', 'Alternative Delivery Mode'],
    'Accounting': ['DepEd TCSD Provident Fund'],
    'Supply Office': ['Submission of Inventory Custodian Slip – ICS']
}
SCHOOLS = [("", "-- Select Your School --"), ("Tarlac West A District", "Tarlac West A District"),("Tarlac West B District", "Tarlac West B District"),("Tarlac Central District", "Tarlac Central District"),("Tarlac South District", "Tarlac South District"),("Tarlac East District", "Tarlac East District"),("Tarlac North District", "Tarlac North District"),]
DOCUMENT_TYPES = [("", "-- Select Document Type --"),("Division Memorandum", "Division Memorandum"),("Division Advisory", "Division Advisory"),("Office Memo", "Office Memo"),("Other", "Other")]
POSITIONS = [("", "-- Select Position --"),("Teacher I", "Teacher I"),("Teacher II", "Teacher II"),("Teacher III", "Teacher III"),("Master Teacher I", "Master Teacher I"),("Master Teacher II", "Master Teacher II"),("Other", "Other")]
REMARKS_OPTIONS = [("", "-- Select Remarks --"),("For Creation", "For Creation"),("Password Reset", "Password Reset"),("Update/Correction of Name", "Update/Correction of Name"),("Other", "Other")]


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class TicketForm(FlaskForm):
    client_name = StringField('Your Full Name', validators=[DataRequired()])
    client_email = StringField('Your DepEd Email', validators=[DataRequired(), Email(message="Please enter a valid DepEd email.")])
    department = SelectField('Select Department', choices=[("", "-- Select Department --")] + [(d, d) for d in DEPARTMENTS_AND_SERVICES.keys()], validators=[DataRequired()])
    service_type = SelectField('Select Service Needed', choices=[("", "-- Select a Service --")], validators=[DataRequired()])
    description = TextAreaField('Please provide a brief description of your request/concern.', validators=[Optional()])
    school_name_text = StringField('Name of School', validators=[Optional()])
    contact_number = StringField('Contact Number', validators=[Optional()])
    document_title = StringField('Title of Document/Material', validators=[Optional()])
    document_type = SelectField('Type of Document', choices=DOCUMENT_TYPES, validators=[Optional()])
    document_type_other = StringField('If Other, please specify', validators=[Optional()])
    issuance_attachment = FileField('Attach File (PDF Only, Max 25MB)', validators=[Optional(), FileAllowed(['pdf'], 'PDF files only!')])
    device_type = SelectField('Device Type', choices=[("", "-- Select Device --"), ("Laptop", "Laptop"), ("Desktop", "Desktop"), ("Printer", "Printer"), ("Projector", "Projector"), ("Other", "Other")], validators=[Optional()])
    device_type_other = StringField('If Other, please specify device', validators=[Optional()])
    school_id = StringField('School ID', validators=[Optional()])
    school_name_select = SelectField('Name of School', choices=SCHOOLS, validators=[Optional()])
    personnel_first_name = StringField('FIRST NAME (CAPSLOCK)', validators=[Optional()])
    personnel_middle_name = StringField('MIDDLE NAME (CAPSLOCK)', validators=[Optional()])
    personnel_last_name = StringField('LAST NAME (CAPSLOCK)', validators=[Optional()])
    ext_name = StringField('Extension Name (e.g., Jr., III)', validators=[Optional()])
    sex = SelectField('Sex', choices=[("", "-- Select Sex --"), ("Male", "Male"), ("Female", "Female")], validators=[Optional()])
    date_of_birth = DateField('Date of Birth (e.g., January 1, 1980)', format='%Y-%m-%d', validators=[Optional()])
    position = SelectField('Position/Designation', choices=POSITIONS, validators=[Optional()])
    position_other = StringField('If Other, please specify position', validators=[Optional()])
    existing_email_or_na = StringField('Type DepEd Email if for RESET, else N/A', validators=[Optional()])
    remarks = SelectField('Remarks', choices=REMARKS_OPTIONS, validators=[Optional()])
    remarks_other = StringField('If Other, please specify remarks', validators=[Optional()])
    certification_attachment = FileField('Upload Certification (PDF Only, Max 25MB)', validators=[Optional(), FileAllowed(['pdf'], 'PDF files only!')])
    dpds_remarks = SelectField('Remarks', choices=[("", "-- Select Remarks --"), ('Password Reset', 'Password Reset'), ('Forget Account', 'Forget Account')], validators=[Optional()])
    
    # --- PERSONNEL FIELDS ---
    employee_number = StringField('Employee Number', validators=[Optional()])
    date_of_last_appointment = DateField('Date of Last Appointment', format='%Y-%m-%d', validators=[Optional()])

    # Final Fields
    privacy_agreement = BooleanField('I agree to the Data Privacy terms.', validators=[DataRequired()])
    submit = SubmitField('Submit Ticket')

    def validate_client_email(self, field):
        if not field.data.endswith('@deped.gov.ph'):
            raise ValidationError('Only @deped.gov.ph emails are allowed.')

class UpdateTicketForm(FlaskForm):
    status = SelectField('Update Status', choices=[('New', 'New'), ('In Progress', 'In Progress'), ('Resolved', 'Resolved')], validators=[DataRequired()])
    canned_response = SelectField('Canned Response (Optional)', choices=[("", "-- Select a response --")], validators=[Optional()])
    resolution_details = TextAreaField('Resolution Details / Remarks', validators=[Optional()])
    submit = SubmitField('Update Ticket')
