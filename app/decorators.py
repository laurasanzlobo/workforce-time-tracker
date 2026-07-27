"""
File: app/decorators.py

Custom decorators for permission management and access control.

Author: Laura Sanz Lobo
"""

from functools import wraps
from flask import session, redirect, url_for
from app.models import User

def admin_required(f):
    """
    Decorator to restrict access to views for administrators only.
    If the user is not an admin, it returns a 403 error.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            # Redirects to the login of the authentication blueprint
            return redirect(url_for("auth.login"))
        
        user = User.query.get(session["user_id"])
        
        if not user or not user.is_admin:
            return "You do not have permission to access this section.", 403
            
        return f(*args, **kwargs)
    
    return decorated_function