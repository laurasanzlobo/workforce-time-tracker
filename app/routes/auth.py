"""
File: app/routes/auth.py

Authentication routes (Login and Logout).

Author: Laura Sanz Lobo
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.extensions import bcrypt
from app.models import User

# Define the authentication Blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/", methods=["GET", "POST"])
def login():
    # If the user is already logged in, redirect them directly to the register view
    if "user_id" in session:
        return redirect(url_for("main.register"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session["user_id"] = user.id
            # Redirect to the 'main' blueprint, 'register' function
            return redirect(url_for("main.register"))

        flash("Nombre de usuario o contraseña incorrectos.", "error")
        return redirect(url_for("auth.login"))

    return render_template("auth/login.html")

@auth_bp.route('/logout')
def logout():
    session.pop("user_id", None)
    return redirect(url_for("auth.login"))