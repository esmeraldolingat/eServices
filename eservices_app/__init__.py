# eservices_app/__init__.py

import os
from flask import Flask, render_template, request # Idinagdag ang request para sa error handlers
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import traceback
from werkzeug.exceptions import HTTPException
from datetime import datetime

# Load environment variables dito sa taas
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path)

# --- Initialize Extensions (without app) ---
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")

# --- Define Smarter Key Function ---
def smarter_key_func():
    if current_user and current_user.is_authenticated:
        return f"user-{current_user.id}"
    else:
        remote_addr = get_remote_address() or 'cli'
        return remote_addr

# --- Application Factory Function ---
def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True,
                static_folder='static',
                template_folder='templates')

    # --- Load Configuration ---
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-fallback-secret-key')

    # Database Config
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_DB = os.getenv('MYSQL_DB', 'eservices_db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}?charset=utf8mb4'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Upload Config
    UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
    app.config['MAX_FILE_SIZE_MB'] = 25

    # Other Config
    app.config['TICKETS_PER_PAGE'] = 10
    app.config['EMAILS_PER_PAGE'] = 50

    # Email Config
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    
    # Allowed Extensions for upload (ilagay natin sa config)
    app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}


    # --- Initialize Extensions (with app) ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' # 'blueprint_name.function_name'
    login_manager.login_message_category = 'info' # Optional: para maganda ang flash message
    mail.init_app(app)
    limiter.init_app(app)
    limiter.key_func = smarter_key_func
    limiter.default_limits = ["500 per 5 minutes", "2000 per hour"]

    # --- Setup Logging ---
    if not app.debug and not app.testing:
        log_dir = os.path.join(app.root_path, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(os.path.join(log_dir, 'eservices.log'),
                                           maxBytes=10240000, backupCount=5)
        log_format = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        file_handler.setFormatter(log_format)
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('eServices startup')

    # --- Import Models ---
    # Kailangan ito bago mag-register ng blueprints kung
    # ang blueprints ay gumagamit ng models (which they do)
    with app.app_context():
        from . import models

    # --- Register Blueprints ---
    # Dapat tamang indentation (Level 1, kapantay ng db.init_app)
    from .main.routes import main_bp
    app.register_blueprint(main_bp)

    from .auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .admin.routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from .tickets.routes import tickets_bp
    app.register_blueprint(tickets_bp) # Walang prefix


    # --- Context Processor ---
    # Dapat tamang indentation (Level 1 din)
    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.utcnow().year}

    # --- Login Manager User Loader ---
    # Dapat tamang indentation (Level 1 din)
    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    # --- Register Error Handlers ---
    # Dapat tamang indentation (Level 1 din)
    @app.errorhandler(429)
    def ratelimit_handler(e):
        app.logger.warning(f"Rate limit exceeded: {e.description} for {limiter.key_func()} on route {request.endpoint}")
        try:
            return render_template("429.html"), 429
        except Exception as render_error:
            app.logger.error(f"!!! Error rendering 429.html: {render_error} !!!", exc_info=True)
            return f"Too Many Requests ({e.description}).", 429

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            if e.code == 404:
                app.logger.warning(f"404 Not Found: {request.url}")
                try:
                    return render_template("404.html"), 404
                except Exception as render_error:
                     app.logger.error(f"!!! Error rendering 404.html: {render_error} !!!", exc_info=True)
                     return "Not Found", 404 # Simple fallback
            
            # Para sa ibang HTTP errors, i-log natin pero hayaan si Flask mag-handle
            app.logger.warning(f"{e.code} Error: {e.name} - {e.description} for URL {request.url}")
            return e

        # Para sa mga non-HTTP exceptions (Python errors)
        app.logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        try:
            return render_template("500.html"), 500
        except Exception as render_error:
             app.logger.error(f"!!! Error rendering 500.html: {render_error} !!!", exc_info=True)
             return "Internal Server Error", 500 # Simple fallback

    
    app.logger.info('eServices application created and configured.')
    return app