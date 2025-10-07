from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, TextAreaField, SubmitField, BooleanField, DateField
from wtforms.validators import DataRequired, Email, Optional, ValidationError

# --- CANNED RESPONSES ---
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
    'Personnel': [
        "Your application for leave of absence has been duly approved. You may either retrieve the document in person or coordinate with the Administrative Officer at your school to facilitate its release from the Records Office of the Division. Additionally, I am providing a link for your reference, which will enable convenient access to the document.",
        "There appears to be a discrepancy in the data you have encoded. Kindly review the information thoroughly and resubmit your request once the necessary corrections have been made.",
        'Multiple requests with the same "eServices Needed" have been submitted to the Personnel Unit. Consequently, this request will be disregarded. Thank you for your attention to this matter.',
        "Kindly request the school head to affix their signature to your Form 6 for official validation.",
        "Your requested Certificate of Employment has been duly prepared and signed. You may either retrieve it in person or liaise with the Administrative Officer at your school to facilitate its release from the Records Office of the Division. Furthermore, a link will be provided to allow you to view the Certificate of Employment in advance.",
        "Please upload a copy of your Certificate of Employment, with or without compensation, to be prepared by your School Administrative Officer II",
        "Please upload a copy of your Certificate of Employment — not your Service Record — with or without compensation, to be prepared by your School Administrative Officer II.",
        "Your requested Service Record has been duly prepared and signed. You may either retrieve it in person or coordinate with the Administrative Officer at your school to facilitate its release from the Records Office of the Division.",
        "Your requested Service Record has been duly prepared and signed. You may now access and download it using the link provided."
    ],
    'Legal Services': [
        "This serves to formally notify you that your request for a No Pending Case Certification has been duly approved. You may collect the document in person or, alternatively, coordinate with the Administrative Officer of your school to facilitate its release from the Division Records Office. Furthermore, for your convenience, a reference link is provided herein to enable secure and expedient access to the document.",
        "There appears to be a discrepancy in the data you have encoded. Kindly review the information thoroughly and resubmit your request once the necessary corrections have been made."
    ],
    'Office of the SDS': [
        "Your Locator Slip has been duly approved. Kindly refer to the provided link to facilitate convenient access to the document.",
        "Your request for Authority to Travel has been duly approved. You may retrieve the document in person or coordinate with the Administrative Officer at your school to facilitate its release from the Division Records Office. Additionally, a link is provided for your reference to enable convenient access to the document.",
        "Your request for the Designation of an Officer-in-Charge at your School has been forwarded to the Personnel Unit for processing. Thank you.",
        "Your request for the Alternative Delivery Mode at your School has been forwarded to the Personnel Unit for processing. Thank you.",
        "Your request for a Substitute Teacher at your school has been forwarded to the Personnel Unit for processing. Thank you."
    ],
    'Accounting': [
        "Your DepEd TCSD Provident Fund application is currently being processed. The application will proceed upon the availability of funds.",
        "Your DepEd TCSD Provident Fund Statement of Account has been duly prepared and signed. You may retrieve it in person or coordinate with your school's Administrative Officer for its release. Additionally, a link will be provided for advance viewing.",
        "Your request for a Provident Loan Accountability Clearance has been duly prepared and signed. You may retrieve it in person or coordinate with your school's Administrative Officer for its release. Additionally, a link will be provided for advance viewing.",
        "Incomplete Requirements: Please attach the Provident Form, DepEd ID, and payslip as valid requirements, along with the same documents for the co-maker.",
        "Please attach your latest payslip to your application to proceed with your request."
    ],
    'Supply Office': [
        "Your submission of the Inventory Custodian Slip (ICS) has been reviewed, approved, and duly signed. Kindly refer to the link above to download the document, which shall serve as your official copy for school inventory records.",
        'Multiple requests with the same "eServices Needed" have been submitted to the Supply Unit. Consequently, this request will be disregarded. Thank you for your attention to this matter.'
    ]
}


# --- DEPARTMENTS AND SERVICES ---
DEPARTMENTS_AND_SERVICES = {
    'ICT': ['Issuances and Online Materials', 'Repair, Maintenance and Troubleshoot of IT Equipment', 'DepEd Email Account', 'DPDS - DepEd Partnership Database System', 'DCP - DepEd Computerization Program: After-sales', 'other ICT - Technical Assistance Needed'],
    'Personnel': ['Application for Leave of Absence', 'Certificate of Employment', 'Service Record', 'GSIS BP Number'],
    'Legal Services': ['Certificate of NO-Pending Case'],
    'Office of the SDS': ['Request for Approval of Locator Slip', 'Request for Approval of Authority to Travel', 'Request for Designation of Officer-in-Charge at the School', 'Request for Substitute Teacher', 'Alternative Delivery Mode'],
    'Accounting': ['DepEd TCSD Provident Fund'],
    'Supply Office': ['Submission of Inventory Custodian Slip – ICS']
}

# --- CHOICES FOR DROPDOWNS ---
SCHOOLS = [
    'Alvindia Aguso Central ES', 'Alvindia Aguso HS', 'Alvindia ES', 'Amucao ES', 'Amucao HS', 'Apalang ES',
    'Armenia IS', 'Asturias ES', 'Atioc Dela Paz ES', 'Bacuit ES', 'Bagong Barrio ES', 'Balanti ES', 'Balanti HS',
    'Balete ES', 'Balibago Primero IS', 'Balingcanaway Centro ES', 'Balingcanaway Corba ES', 'Banaba ES',
    'Bantog ES', 'Baras-Baras ES', 'Baras-Baras HS', 'Batang-Batang IS', 'Binauganan ES', 'Buenavista ES',
    'Buhilit ES', 'Burot IS', 'Camp Aquino ES', 'Capehan ES', 'Capulong ES', 'Carangian ES', 'Care ES', 'CAT ES',
    'CAT HS Annex', 'CAT HS Main', 'Cut Cut ES', 'Dalayap ES', 'Damaso Briones ES', 'Dolores ES',
    'Don Florencio P. Buan ES', 'Don Pepe Cojuangco ES', 'Doña Arsenia ES', 'Felicidad Magday ES', 'Laoang ES',
    'Lourdes ES', 'Maligaya ES', 'Maliwalo CES', 'Maliwalo National HS', 'Mapalacsiao ES', 'Mapalad ES',
    'Margarita Briones Soliman ES', 'Matatalaib Bato ES', 'Matatalaib Buno ES', 'Matatalaib HS',
    'Natividad De Leon ES', 'Northern Hill ES Annex', 'Northern Hill ES Main', 'Pag-asa ES', 'Paquillao ES',
    'Paradise ES', 'Paraiso ES', 'Samberga ES', 'San Carlos ES', 'San Francisco ES', 'San Isidro ES',
    'San Jose De Urquico ES', 'San Jose ES', 'San Juan Bautista ES', 'San Juan De Mata ES',
    'San Juan De Mata HS', 'San Manuel ES', 'San Manuel HS', 'San Miguel CES', 'San Nicolas ES',
    'San Pablo ES', 'San Pascual ES', 'San Rafael ES', 'San Sebastian ES', 'San Vicente ES Annex',
    'San Vicente ES Main', 'Sapang Maragul IS', 'Sapang Tagalog ES', 'Sepung Calzada Panampunan ES',
    'Sinait IS', 'Sitio Dam ES', 'Sta. Cruz ES', 'Sta. Maria ES', 'Sto. Cristo IS', 'Sto. Domingo ES',
    'Sto. Niño ES', 'Suizo Bliss ES', 'Suizo Resettlement ES', 'Tariji ES', 'Tarlac West CES', 'Tibag ES',
    'Tibag HS', 'Trinidad ES', 'Ungot IS', 'Villa Bacolor ES', 'Yabutan ES', 'Division Office'
]

POSITIONS = [
    'Teacher I', 'Teacher II', 'Teacher III', 'Teacher IV', 'Teacher V', 'Teacher VI', 
    'Master Teacher I', 'Master Teacher II', 'Master Teacher III', 'Master Teacher IV', 
    'Head Teacher I', 'Head Teacher II', 'Head Teacher III', 'Head Teacher IV', 'Head Teacher V', 'Head Teacher VI', 
    'Principal I', 'Principal II', 'Principal III', 'Principal IV', 
    'Administrative Aide I', 'Administrative Aide IV', 'Administrative Aide VI', 
    'Administrative Assistant I', 'Administrative Assistant II', 'Administrative Assistant III', 
    'Administrative Officer I', 'Administrative Officer II', 'PDO I', 'PDO II', 'Other'
]

REMARKS_OPTIONS = [
    'NEW ACCOUNT - DepEd Email (Gmail)', 'NEW ACCOUNT - Microsoft Account', 
    'PASSWORD RESET - DepEd Email (Gmail)', 'PASSWORD RESET - Microsoft Email (juan.delacruz@deped.gov.ph)', 
    'PASSWORD RESET - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)', 
    'REACTIVATE - DepEd Email (Gmail)', 
    'Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@r3-2.deped.gov.ph)', 
    'Remove Two-factor Authentication (2FA) - Microsoft Email (juan.delacruz@deped.gov.ph)', 
    'Remove Two-factor Authentication (2FA) - DepEd - Gmail (Google)', 'Other'
]

# --- LOGIN FORM ---
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


# --- MAIN TICKET FORM ---
class TicketForm(FlaskForm):
    # Core Fields
    client_name = StringField('Your Full Name', validators=[DataRequired()])
    client_email = StringField('Your DepEd Email', validators=[DataRequired(), Email(message="Please enter a valid DepEd email.")])
    department = SelectField('Select Department', choices=[("", "-- Select Department --")] + [(d, d) for d in DEPARTMENTS_AND_SERVICES.keys()], validators=[DataRequired()])
    service_type = SelectField('Select Service Needed', choices=[("", "-- Select a Service --")], validators=[DataRequired()])
    
    # Generic/Shared Fields
    description = TextAreaField('Please provide a brief description of your request/concern.', validators=[Optional()])
    school_name_text = StringField('Name of School', validators=[Optional()])
    contact_number = StringField('Contact Number', validators=[Optional()])

    # ICT: Issuances
    document_title = StringField('Title of Document/Material', validators=[DataRequired()])
    issuance_attachment = FileField('Attach File (PDF Only, Max 25MB)', validators=[DataRequired(), FileAllowed(['pdf'], 'PDF files only!')])

    # ICT: Repair
    device_type = SelectField('Device Type', choices=[("", "-- Select Device --"), ("Laptop", "Laptop"), ("Desktop", "Desktop"), ("Printer", "Printer"), ("Projector", "Projector"), ("Other", "Other")], validators=[Optional()])
    device_type_other = StringField('If Other, please specify device', validators=[Optional()])

    # ICT: DepEd Email
    school_id = StringField('School ID', validators=[DataRequired()])
    school_name_select = SelectField('Name of School', choices=[("", "-- Select a School --")] + [(s,s) for s in SCHOOLS], validators=[DataRequired()])
    personnel_first_name = StringField('FIRST NAME (CAPSLOCK)', validators=[DataRequired()])
    personnel_middle_name = StringField('MIDDLE NAME (CAPSLOCK)', validators=[DataRequired()])
    personnel_last_name = StringField('LAST NAME (CAPSLOCK)', validators=[DataRequired()])
    ext_name = StringField('Extension Name (e.g., Jr., III)', validators=[Optional()])
    sex = SelectField('Sex', choices=[("", "-- Select Sex --"), ("Male", "Male"), ("Female", "Female")], validators=[DataRequired()])
    date_of_birth = DateField('Date of Birth (e.g., January 1, 1980)', format='%Y-%m-%d', validators=[DataRequired()])
    position = SelectField('Position/Designation', choices=[("", "-- Select Position --")] + [(p,p) for p in POSITIONS], validators=[DataRequired()])
    position_other = StringField('If Other, please specify position', validators=[Optional()])
    existing_email_or_na = StringField('Type DepEd Email if for RESET, else N/A', validators=[DataRequired()])
    remarks = SelectField('Remarks', choices=[("", "-- Select Remarks --")] + [(r,r) for r in REMARKS_OPTIONS], validators=[DataRequired()])
    remarks_other = StringField('If Other, please specify remarks', validators=[Optional()])
    certification_attachment = FileField('Upload Certification (PDF Only, Max 25MB)', validators=[DataRequired(), FileAllowed(['pdf'], 'PDF files only!')])
    
    # ICT: DPDS
    dpds_remarks = SelectField('Remarks', choices=[("", "-- Select Remarks --"), ('Password Reset', 'Password Reset'), ('Forget Account', 'Forget Account')], validators=[DataRequired()])
    
    # Final Fields
    privacy_agreement = BooleanField('I agree to the Data Privacy terms.', validators=[DataRequired()])
    submit = SubmitField('Submit Ticket')

    def validate_client_email(self, field):
        # This is a placeholder for your actual authorized email validation
        pass


# --- UPDATE FORM ---
class UpdateTicketForm(FlaskForm):
    status = SelectField('Update Status', choices=[('New', 'New'), ('In Progress', 'In Progress'), ('Resolved', 'Resolved')], validators=[DataRequired()])
    canned_response = SelectField('Canned Response (Optional)', choices=[("", "-- Select a response --")], validators=[Optional()])
    resolution_details = TextAreaField('Resolution Details / Remarks', validators=[Optional()])
    submit = SubmitField('Update Ticket')

