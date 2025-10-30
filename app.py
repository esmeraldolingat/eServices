# app.py (nasa labas ng eservices_app)

import os
# Import create_app at db mula sa ating package
from eservices_app import create_app, db
# Import models *na kailangan lang* para sa CLI commands
from eservices_app.models import User, Department, Service, School, CannedResponse, AuthorizedEmail

# Gumawa ng app instance gamit ang factory
# Maaaring kailanganin ng Flask-Migrate na malaman ang app instance
app = create_app()

# --- CLI COMMANDS ---
# Ilalagay natin sila dito para madaling i-run sa terminal

@app.cli.command("seed-db")
def seed_db():
    """Populates the database with initial data and canned responses."""
    # Gamitin ang app.app_context() para sa database operations sa CLI
    with app.app_context():
        print("Clearing old canned responses...")
        db.session.query(CannedResponse).delete()
        db.session.commit()
        print("Old canned responses cleared.")

        print("Seeding Departments...")
        DEPARTMENTS = ["ICT", "Personnel", "Legal Services", "Office of the SDS", "Accounting Unit", "Supply Office"]
        for dept_name in DEPARTMENTS:
            if not Department.query.filter_by(name=dept_name).first():
                db.session.add(Department(name=dept_name))
        db.session.commit()
        print("Departments seeded.")

        print("Seeding Services...")
        SERVICES = { "ICT": ["Issuances and Online Materials", "Repair, Maintenance and Troubleshoot of IT Equipment", "DepEd Email Account", "DPDS - DepEd Partnership Database System", "DCP - DepEd Computerization Program: After-sales", "other ICT - Technical Assistance Needed"], "Personnel": ["Application for Leave of Absence", "Certificate of Employment", "Service Record", "GSIS BP Number"], "Legal Services": ["Certificate of NO-Pending Case"], "Office of the SDS": ["Request for Approval of Locator Slip", "Request for Approval of Authority to Travel", "Request for Designation of Officer-in-Charge at the School", "Request for Substitute Teacher", "Alternative Delivery Mode"], "Accounting Unit": ["DepEd TCSD Provident Fund"], "Supply Office": ["Submission of Inventory Custodian Slip – ICS"] }
        for dept_name, service_list in SERVICES.items():
            dept = Department.query.filter_by(name=dept_name).first()
            if dept:
                for service_name in service_list:
                    if not Service.query.filter_by(name=service_name, department_id=dept.id).first():
                        db.session.add(Service(name=service_name, department_id=dept.id))
        db.session.commit()
        print("Services seeded.")

        print("Seeding Schools...")
        # (Pinaikli ko lang 'yung listahan dito para hindi masyadong mahaba)
        SCHOOLS = [ "Alvindia Aguso Central ES", "Alvindia Aguso HS", # ... (yung buong list mo) ...
                   "Villa Bacolor ES", "Yabutan ES", "Division Office" ]
        for school_name in SCHOOLS:
            if not School.query.filter_by(name=school_name).first():
                db.session.add(School(name=school_name))
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
        # (Pinaikli ko lang ulit 'yung listahan)
        CANNED_RESPONSES_BY_DEPT = {
            "ICT": [ ("Transaction Completed", "...") ], # ... (yung buong data mo) ...
            "Supply Office": [ ("ICS Approved", "...") ]
        }
        for dept_name, responses_list in CANNED_RESPONSES_BY_DEPT.items():
            dept = Department.query.filter_by(name=dept_name).first()
            if dept:
                for title, body in responses_list:
                    if not CannedResponse.query.filter_by(title=title, department_id=dept.id).first():
                        db.session.add(CannedResponse(title=title, body=body, department_id=dept.id, service_id=None))
        db.session.commit()
        print("Department-level canned responses seeded.")

        CANNED_RESPONSES_BY_SERVICE = {
            "Application for Leave of Absence": [ ("Leave Approved (with Soft Copy)", "...") ], # ... (yung buong data mo) ...
            "GSIS BP Number": [ ("GSIS BP Updated", "...") ]
        }
        for service_name, responses_list in CANNED_RESPONSES_BY_SERVICE.items():
            service = Service.query.filter_by(name=service_name).first()
            if service:
                for title, body in responses_list:
                    if not CannedResponse.query.filter_by(title=title, service_id=service.id).first():
                        db.session.add(CannedResponse(
                            title=title, body=body, department_id=service.department_id, service_id=service.id
                        ))
        db.session.commit()
        print("Service-level canned responses seeded.")
        print("Database seeding complete!")


@app.cli.command("create-admin")
def create_admin():
    """Creates the default admin user."""
    with app.app_context(): # Kailangan pa rin ito
        if User.query.filter_by(email='admin@deped.gov.ph').first():
            print('Admin user already exists.')
            return
        user = User(name='Administrator', email='admin@deped.gov.ph', role='Admin')
        user.set_password('password123') # Gamitin ang method mula sa User model
        db.session.add(user)
        db.session.commit()
    print('Admin user created successfully! (Email: admin@deped.gov.ph, Password: password123)')

# Wala nang 'if __name__ == "__main__":' dito. Ang 'flask run' na ang bahala.