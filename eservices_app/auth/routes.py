# eservices_app/auth/routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
# Import galing sa parent package (eservices_app)
from .. import db, limiter # Import db at limiter
from ..models import User # Import User model
from ..forms import RegistrationForm, LoginForm, RequestResetForm, ResetPasswordForm # Import Auth forms
# Import email sending function (assuming nasa parent pa rin)
# Kung ililipat din natin sa 'utils' later, babaguhin ito
# from ..utils import send_reset_email  # Example kung nasa utils.py
from ..helpers import send_reset_email # Gagamitin natin ang pangalang 'helpers.py' mamaya para sa email functions

# Gumawa ng Blueprint instance
# 'auth' ang pangalan ng blueprint
# url_prefix='/auth' ay idadagdag natin mamaya sa registration para maging /auth/login, /auth/register etc.
auth_bp = Blueprint('auth', __name__)

# --- Login Route ---
@auth_bp.route('/login', methods=['GET', 'POST'])
# Ilipat ang limiter dito mula sa luma mong app.py
@limiter.limit("40 per 2 hours; 10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home')) # Redirect sa main.home
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            # Gamitin ang logger ng app
            current_app.logger.info(f"User {user.email} logged in successfully.")
            next_page = request.args.get('next')
            # Mag-ingat sa open redirect vulnerability
            # Siguraduhing internal URL lang ang next_page or default sa home
            return redirect(next_page or url_for('main.home'))
        else:
            current_app.logger.warning(f"Failed login attempt for email: {form.username.data}")
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form, title='Login')

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
# Ilipat ang limiter dito mula sa luma mong app.py
@limiter.limit("10 per day; 5 per hour")
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Gagamitin natin ang na-import na send_reset_email
            send_reset_email(user)
            current_app.logger.info(f"Password reset requested for user: {form.email.data}")
        else:
            current_app.logger.warning(f"Password reset requested for non-existent email: {form.email.data}")
        # Laging ipakita itong message para hindi malaman kung existing ang email
        flash('An email has been sent with instructions to reset your password (if the email exists in our system).', 'info')
        return redirect(url_for('auth.login'))
    return render_template('request_reset.html', title='Reset Password', form=form)

# --- Password Reset Token Handling Route ---
@auth_bp.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
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