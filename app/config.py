"""
File: app/config.py

General application configuration, environment variables, and paths.

Author: Laura Sanz Lobo
"""

import os

# Project root directory
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    """Shared base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'default_secret_key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mail configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    
    # File upload configuration
    # Will be saved in: app/static/uploads/signatures
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads", "signatures")
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

class DevelopmentConfig(Config):
    """Configuration for local development."""
    # Path to the database in the upper instance folder
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'database.db')}"

class ProductionConfig(Config):
    """Configuration for production (Render)."""
    # Using the environment variable provided by the server
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")