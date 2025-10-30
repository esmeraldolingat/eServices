# eservices_app/auth/routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
# Import galing sa parent package (eservices_app)
from .. import db, limiter # Import db at limiter
from ..models import User # Import User model
from ..forms import RegistrationForm, LoginForm, RequestResetForm, ResetPasswordForm # Import Auth forms
# Import email sending function
from ..helpers import send_reset_email 

# Gumawa ng Blueprint instance
auth_bp = Blueprint('auth', __name__)

# --- Login Route ---
@auth_bp.route('/login', methods=['GET', 'POST'])
# --- SIMULA NG PAG-AYOS ---
# 1. Idinagdag ang 'methods=["POST"]' para ang pag-submit lang ang bilangin, hindi ang pag-refresh.
# 2. Idinagdag ang 'exempt_when' para hindi ma-limit ang mga naka-login na user.
# 3. Inayos ang redirect logic para sa Admin/Staff.
@limiter.limit("10 per minute; 30 per 2 hours", 
               methods=["POST"], 
               exempt_when=lambda: current_user.is_authenticated,
               error_message="Too many login attempts. Please wait 2 hours before trying again.")
def login():
    if current_user.is_authenticated:
        # Kung naka-login na, 'exempt_when' ang gumagana
        # at i-redirect sila sa tamang dashboard
        if current_user.role in ['Admin', 'Staff']:
            return redirect(url_for('admin.staff_dashboard'))
        return redirect(url_for('main.home'))

    form = LoginForm()
    
    # Ang code dito ay tatakbo lang sa 'POST' request (kapag nag-submit)
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user)
            current_app.logger.info(f"User {user.email} logged in successfully.")
            next_page = request.args.get('next')
            
            # Inayos na redirect: papuntang staff dashboard kung staff/admin
            if user.role in ['Admin', 'Staff']:
                 return redirect(next_page or url_for('admin.staff_dashboard'))
            
            # Papuntang main home kung regular user
            return redirect(next_page or url_for('main.home'))
        else:
            # Ito ay 'POST' request, kaya bibilangin ito ng limiter
            current_app.logger.warning(f"Failed login attempt for email: {form.username.data}")
            flash('Login Unsuccessful. Please check email and password', 'danger')
            
    # Ito ang 'GET' request (pag-load ng page), HINDI ito bibilangin ng limiter
    return render_template('login.html', form=form, title='Login')
# --- TAPOS NG PAG-AYOS ---


# --- Logout Route ---
@auth_bp.route('/logout')
@login_required
def logout():
    user_email = current_user.email
    logout_user()
    current_app.logger.info(f"User {user_email} logged out.")
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login')) # Redirect sa auth.login

# --- Registration Route ---
@auth_bp.route('/register', methods=['GET', 'POST'])
# Opsyonal: Lagyan din ng limit ang registration para iwas bots
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user_email = form.email.data
        user = User(name=form.name.data, email=user_email, role='User')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        current_app.logger.info(f"New user registered: {user_email}")
        flash('Your account has been created! You are now able to log in.', 'success')
        return redirect(url_for('auth.login')) # Redirect sa auth.login
    return render_template('register.html', form=form, title='Register')

# --- Password Reset Request Route ---
@auth_bp.route("/reset_password", methods=['GET', 'POST'])


# --- PASSWORD RESET LIMIT ---
# Idinagdag din ang methods=["POST"] at exempt_when dito
@limiter.limit("5 per day; 2 per hour", 
               methods=["POST"], 
               exempt_when=lambda: current_user.is_authenticated,
               error_message="Too many password reset requests. Please try again later.")
def reset_request():
# --- TAPOS NG PAG-AYOS ---
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
            current_app.logger.info(f"Password reset requested for user: {form.email.data}")
        else:
            current_app.logger.warning(f"Password reset requested for non-existent email: {form.email.data}")
        flash('An email has been sent with instructions to reset your password (if the email exists in our system).', 'info')
        return redirect(url_for('auth.login'))
    return render_template('request_reset.html', title='Reset Password', form=form)

# --- Password Reset Token Handling Route ---
@auth_bp.route("/reset_password/<token>", methods=['GET', 'POST'])
# --- SIMULA NG PAG-AYOS ---
# Nagdagdag ng limit sa POST para iwas brute-force sa token page
@limiter.limit("10 per minute", 
               methods=["POST"], 
               exempt_when=lambda: current_user.is_authenticated)
def reset_token(token):
# --- TAPOS NG PAG-AYOS ---
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        current_app.logger.warning(f"Invalid or expired password reset token used.")
        return redirect(url_for('auth.reset_request')) # Redirect sa auth.reset_request
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        current_app.logger.info(f"Password reset successfully for user: {user.email}")
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('auth.login')) # Redirect sa auth.login
    return render_template('reset_token.html', title='Reset Password', form=form)
