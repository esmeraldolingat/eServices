# forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, Email, Length
from flask_wtf.file import FileField, FileAllowed, FileRequired

# New forms.py import
from models import School

# =================================================================
# === BAGONG FORMS SECTION ========================================
# =================================================================

class LoginForm(FlaskForm):
    """Form para sa user login."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ServiceSelectionForm(FlaskForm):
    """Ito ang unang form na makikita ng user, para pumili ng serbisyo."""
    # Ang choices para dito ay ipo-populate natin mula sa app.py
    service = SelectField('Anong serbisyo ang kailangan mo?', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Next')

class GeneralTicketForm(FlaskForm):
    """Isang general form na may common fields. Gagamitin natin itong base."""
    requester_name = StringField('Buong Pangalan (Full Name)', validators=[DataRequired(), Length(min=2, max=100)])
    requester_email = StringField('DepEd Email Address', validators=[DataRequired(), Email()])
    requester_contact = StringField('Contact Number', validators=[DataRequired(), Length(min=7, max=15)])
    
    # Ito na ang dynamic na school dropdown!
    school = SelectField('Paaralan (School)', coerce=int, validators=[DataRequired()])
    
    submit = SubmitField('Submit Ticket')

    def __init__(self, *args, **kwargs):
        super(GeneralTicketForm, self).__init__(*args, **kwargs)
        # Kukunin natin ang listahan ng schools mula sa database at ilalagay bilang choices
        self.school.choices = [(s.id, s.name) for s in School.query.order_by('name').all()]

# TODO: Dito natin ilalagay sa susunod ang mga specific na forms tulad ng:
# class LeaveApplicationForm(GeneralTicketForm):
#     # ... mga fields para sa leave ...
#
# class RepairForm(GeneralTicketForm):
#     # ... mga fields para sa repair ...

# Pansamantala, ito muna ang laman ng forms.py natin.