"""
File: app/extensions.py

Initialization of extensions (DB, Security, Mail) for the Application Factory pattern.

Author: Laura Sanz Lobo
"""

from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mail import Mail

# Instantiate empty objects.
db = SQLAlchemy()
bcrypt = Bcrypt()
mail = Mail()