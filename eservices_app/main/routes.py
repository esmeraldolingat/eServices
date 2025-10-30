# eservices_app/main/routes.py

from flask import Blueprint, redirect, url_for, render_template # Import Blueprint at iba pa
from flask_login import login_required, current_user
# Mag-iimport tayo mula sa parent package gamit ang '..'
# O pwede ring specific path kung alam mo
# from .. import db # Halimbawa kung kailangan ng db
# from ..models import User # Halimbawa kung kailangan ng models

# Gumawa ng Blueprint instance
# 'main' ang pangalan ng blueprint, __name__ para malaman ang location
main_bp = Blueprint('main', __name__)

# --- Ilipat natin dito 'yung home() route ---
@main_bp.route('/') # Gamitin ang @main_bp.route imbes na @app.route
@login_required
def home():
    # Ang logic ay pareho pa rin
    if current_user.role in ['Admin', 'Staff']:
        # IMPORTANT: Palitan ang endpoint name sa url_for
        # Dapat 'blueprint_name.function_name'
        return redirect(url_for('admin.staff_dashboard')) # Gagamitin natin 'admin' blueprint mamaya
    else:
        # IMPORTANT: Palitan din ito
        return redirect(url_for('tickets.my_tickets')) # Gagamitin natin 'tickets' blueprint mamaya

# --- Ilipat din natin dito 'yung profile() route ---
# (Kailangan natin i-import ang forms at db dito)
from flask import request, flash # Import request at flash
from .. import db # '..' ibig sabihin ay "umakyat sa parent package" (eservices_app)
from ..forms import UpdateProfileForm, ChangePasswordForm # Import forms

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile_form = UpdateProfileForm()
    password_form = ChangePasswordForm()

    # Note: Kailangan i-access ang app.logger sa ibang paraan or mag-import ng logging
    # For now, tatanggalin ko muna ang logging dito para simple
    # import logging
    # logger = logging.getLogger(__name__)

    if 'submit_profile' in request.form and profile_form.validate_on_submit():
        current_user.name = profile_form.name.data
        db.session.commit()
        # logger.info(...)
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('main.profile')) # Gamitin ang 'main.profile'
    elif 'submit_password' in request.form and password_form.validate_on_submit():
        current_user.set_password(password_form.new_password.data)
        db.session.commit()
        # logger.info(...)
        flash('Your password has been changed successfully.', 'success')
        return redirect(url_for('main.profile')) # Gamitin ang 'main.profile'

    if request.method == 'GET' or ('submit_profile' in request.form and not profile_form.validate()):
        profile_form.name.data = current_user.name
        profile_form.email.data = current_user.email

    # Kailangan i-import ang render_template dito
    return render_template('profile.html', title='My Profile', profile_form=profile_form, password_form=password_form)