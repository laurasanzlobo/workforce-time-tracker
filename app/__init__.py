"""
File: app/__init__.py

Flask application initialization (Application Factory).
Configures extensions, database, and registers Blueprints.

Author: Laura Sanz Lobo
"""

import os
from flask import Flask
from app.config import DevelopmentConfig
from app.extensions import db, bcrypt, mail
from app.utils import create_base_admin, get_template_configuration

def create_app(config_class=DevelopmentConfig):
    """
    Creates and configures a Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 1. Initialize extensions
    # Bind empty instances from extensions.py
    db.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)

    # 2. Folder configuration
    # Ensure the signature upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # 3. Register Blueprints (Routes)
    # Imported here to avoid circular dependencies
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)   # No prefix (for /, /logout)
    app.register_blueprint(main_bp)   # No prefix (for /register, /pdf)
    app.register_blueprint(admin_bp)  # Automatic prefix
    app.register_blueprint(api_bp)    # /api prefix (defined in api.py)

    # 4. Create Database
    # Create tables if they do not exist on startup
    with app.app_context():
        db.create_all()
        create_base_admin()

    # 5. Global context for templates
    @app.context_processor
    def inject_global_context():
        return get_template_configuration(app.root_path)

    return app