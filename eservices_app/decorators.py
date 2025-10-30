# eservices_app/decorators.py

from functools import wraps
from flask import flash, redirect, url_for, current_app
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Admin':
            flash('You do not have permission to access this page.', 'danger')
            # Gamitin ang logger ng app
            current_app.logger.warning(f"Unauthorized access attempt to admin page by user {current_user.email if current_user.is_authenticated else 'Guest'}")
            # Redirect sa main.home
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function

# Pwede ka ring gumawa ng @staff_or_admin_required dito kung kailangan mo sa ibang lugar
def staff_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['Admin', 'Staff']:
            flash('You do not have permission to access this page.', 'danger')
            current_app.logger.warning(f"Unauthorized access attempt to staff/admin page by user {current_user.email if current_user.is_authenticated else 'Guest'}")
            return redirect(url_for('main.home'))
        # Pwede pang magdagdag ng check dito kung specific service manager ba, etc.
        return f(*args, **kwargs)
    return decorated_function