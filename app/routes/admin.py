"""
File: app/routes/admin.py

Routes for the administration panel and system configuration.

Author: Laura Sanz Lobo
"""

import os
import uuid
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError

from app.extensions import db, bcrypt
from app.models import (
    User, Holiday, Site, Record, 
    OfficeConfig, SiteConfig, PartTimeConfig, EmailConfig
)
from app.decorators import admin_required
from app.utils import allowed_file

admin_bp = Blueprint('admin', __name__)

# --- MAIN DASHBOARD ---

@admin_bp.route("/admin")
@admin_required 
def admin_panel():
    """Main view for the administration dashboard."""
    return render_template("admin/admin_dashboard.html")

# --- USER MANAGEMENT (CREATE & EDIT) ---

@admin_bp.route("/admin/users/create", methods=["GET", "POST"])
def create_user():
    """
    Allows the creation of new users.
    If no administrators exist in the DB, allows creating the first one without login.
    If they already exist, requires an active administrator session.
    """
    admin_exists = User.query.filter_by(is_admin=True).first()

    # Protection: If an admin already exists, the user must be logged in as admin
    if admin_exists and "user_id" not in session:
        flash("You must be an administrator to create new users.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        national_id = request.form.get("national_id", "").strip()
        # The first user will always be an admin, subsequent ones depend on the checkbox
        is_admin = "is_admin" in request.form if admin_exists else True 
        worker_type = request.form.get("worker_type")
        start_date_str = request.form.get("start_date")
        end_date_str = request.form.get("end_date")

        if not username or not password or not full_name or not national_id or not start_date_str:
            flash("All fields are required except signature and end date.", "error")
            return redirect(url_for("admin.create_user"))
        
        if worker_type not in ["office", "site", "part_time"]:
            flash("Invalid worker type.", "error")
            return redirect(url_for("admin.create_user"))
            
        start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date() if start_date_str else date.today()
        end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date() if end_date_str else None

        # Signature processing
        signature_file = request.files.get("signature")
        signature_path = None
        
        if signature_file and signature_file.filename:
            if allowed_file(signature_file.filename):
                filename = f"{uuid.uuid4().hex}_{secure_filename(signature_file.filename)}"
                signature_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                signature_file.save(signature_path)
            else:
                flash("Signature format not allowed.", "error")
                return redirect(url_for("admin.create_user"))
            
        try:
            hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
            new_user = User(
                username=username,
                password=hashed_password,
                full_name=full_name,
                national_id=national_id,
                worker_type=worker_type,
                start_date=start_date,
                end_date=end_date,
                is_admin=is_admin,
                signature=signature_path
            )

            db.session.add(new_user)
            db.session.commit()
            flash("User successfully created.", "success")

            # Auto-login if it's the first user in the system
            if not admin_exists:
                session["user_id"] = new_user.id
                return redirect(url_for("admin.admin_panel"))

            return redirect(url_for("admin.create_user"))

        except IntegrityError:
            db.session.rollback()
            flash("The username or National ID already exists.", "error")
            return redirect(url_for("admin.create_user"))
        except Exception as e:
            flash(f"Unexpected error: {e}", "error")
            return redirect(url_for("admin.create_user"))

    return render_template("admin/create_user.html")

@admin_bp.route("/admin/users/edit/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    """Edits an existing user's data."""
    user = User.query.get_or_404(user_id)
    back_url = request.args.get("back") or url_for("admin.user_list")

    if request.method == "POST":
        user.username = request.form.get("username", "").strip()
        user.full_name = request.form.get("full_name", "").strip()
        user.national_id = request.form.get("national_id", "").strip()
        user.worker_type = request.form.get("worker_type")
        user.is_admin = "is_admin" in request.form

        new_pass = request.form.get("password", "").strip()
        if new_pass:
            user.password = bcrypt.generate_password_hash(new_pass).decode("utf-8")
        
        start_date_str = request.form.get("start_date", "").strip()
        if start_date_str:
            try:
                user.start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
            except ValueError:
                flash("Invalid start date.", "error")
                return redirect(request.url)
        
        end_date_str = request.form.get("end_date", "").strip()
        if not end_date_str:
            user.end_date = None
        else:
            try:
                new_end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()
                user.end_date = new_end_date
                # Clear future records after the end date
                Record.query.filter(
                    Record.user_id == user.id,
                    Record.date > new_end_date
                ).delete(synchronize_session=False)
            except ValueError:
                flash("Invalid end date.", "error")
                return redirect(request.url)

        # Signature update
        signature_file = request.files.get("signature")
        if signature_file and signature_file.filename:
            if allowed_file(signature_file.filename):
                filename = f"{uuid.uuid4().hex}_{secure_filename(signature_file.filename)}"
                signature_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                signature_file.save(signature_path)
                user.signature = signature_path
            else:
                flash("Incorrect signature format.", "error")
                return redirect(request.url)

        try:
            db.session.commit()
            flash("User updated.", "success")
            return redirect(back_url)
        except IntegrityError:
            db.session.rollback()
            flash("Duplicate username or National ID.", "error")
            return redirect(request.url)

    return render_template("admin/edit_user.html", user=user, back_url=back_url)

@admin_bp.route("/admin/users/delete/<int:user_id>/<string:worker_type>", methods=["POST"])
@admin_required
def delete_user(user_id, worker_type):
    """Logical or physical deletion of a user."""
    user = User.query.get_or_404(user_id)
    if user.id == session["user_id"]:
        flash("You cannot delete your own account.", "error")
    else:
        db.session.delete(user)
        db.session.commit()
        flash("User deleted.", "success")
    
    # Dynamic redirection based on the origin list
    if worker_type == 'office': return redirect(url_for("admin.user_list_office"))
    elif worker_type == 'site': return redirect(url_for("admin.user_list_site"))
    elif worker_type == 'part_time': return redirect(url_for("admin.user_list_part_time"))
    return redirect(url_for("admin.user_list"))

# --- USER LISTS ---

@admin_bp.route("/admin/users")
@admin_required
def user_list():
    return render_template("admin/user_list.html")

@admin_bp.route("/admin/users/office")
@admin_required
def user_list_office():
    users = User.query.filter_by(worker_type='office').all()
    return render_template("admin/user_list_office.html", users=users)

@admin_bp.route("/admin/users/site")
@admin_required
def user_list_site():
    users = User.query.filter_by(worker_type='site').all()
    return render_template("admin/user_list_site.html", users=users)

@admin_bp.route("/admin/users/part_time")
@admin_required
def user_list_part_time():
    users = User.query.filter_by(worker_type='part_time').all()
    return render_template("admin/user_list_part_time.html", users=users)

# --- HOLIDAY MANAGEMENT ---

@admin_bp.route("/admin/holidays", methods=["GET", "POST"])
@admin_required
def admin_holidays():
    if request.method == "POST":
        date_str = request.form.get("date")
        description = request.form.get("description")
        try:
            date_obj = datetime.strptime(date_str, "%d-%m-%Y").date()
            if Holiday.query.filter_by(date=date_obj).first():
                flash("A holiday already exists on that date.", "error")
            else:
                db.session.add(Holiday(date=date_obj, description=description))
                db.session.commit()
                flash("Holiday added.", "success")
        except ValueError:
            flash("Invalid date format.", "error")
        except IntegrityError:
            db.session.rollback()
            flash("Database integrity error.", "error")
        
        return redirect(url_for("admin.admin_holidays"))

    holidays = Holiday.query.order_by(Holiday.date).all()
    return render_template("admin/admin_holidays.html", holidays=holidays)

@admin_bp.route("/admin/holidays/delete/<int:holiday_id>", methods=["POST"])
@admin_required
def delete_holiday(holiday_id):
    holiday = Holiday.query.get_or_404(holiday_id)
    db.session.delete(holiday)
    db.session.commit()
    flash("Holiday deleted.", "success")
    return redirect(url_for("admin.admin_holidays"))

# --- SITE MANAGEMENT ---

@admin_bp.route("/admin/sites", methods=["GET", "POST"])
@admin_required
def admin_sites():
    if request.method == "POST":
        name = request.form.get("site_name", "").strip()
        if not name:
            flash("Name cannot be empty.", "error")
        else:
            try:
                db.session.add(Site(name=name))
                db.session.commit()
                flash("Site added.", "success")
            except IntegrityError:
                db.session.rollback()
                flash("Duplicate site name.", "error")
        return redirect(url_for("admin.admin_sites"))

    sites = Site.query.order_by(Site.is_active.desc(), Site.name.asc()).all()
    return render_template("admin/admin_sites.html", sites=sites)

@admin_bp.route("/admin/sites/delete/<int:site_id>", methods=["POST"])
@admin_required
def delete_site(site_id):
    site = Site.query.get_or_404(site_id)
    db.session.delete(site)
    db.session.commit()
    flash("Site deleted.", "success")
    return redirect(url_for("admin.admin_sites"))

@admin_bp.route("/admin/sites/archive/<int:site_id>", methods=["POST"])
@admin_required
def archive_site(site_id):
    site = Site.query.get_or_404(site_id)
    site.is_active = False
    db.session.commit()
    flash(f"Site '{site.name}' archived.", "success")
    return redirect(url_for("admin.admin_sites"))

@admin_bp.route("/admin/sites/reactivate/<int:site_id>", methods=["POST"])
@admin_required
def reactivate_site(site_id):
    site = Site.query.get_or_404(site_id)
    site.is_active = True
    db.session.commit()
    flash(f"Site '{site.name}' reactivated.", "success")
    return redirect(url_for("admin.admin_sites"))

@admin_bp.route("/admin/sites/edit/<int:site_id>", methods=["POST"])
@admin_required
def edit_site(site_id):
    new_name = request.form.get("new_name", "").strip()
    if not new_name:
        flash("The name cannot be empty.", "error")
        return redirect(url_for("admin.admin_sites"))

    site = Site.query.get_or_404(site_id)
    site.name = new_name
    try:
        db.session.commit()
        flash("Name updated.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("A site with that name already exists.", "error")
    return redirect(url_for("admin.admin_sites"))

# --- EMAIL AND SCHEDULE CONFIGURATION ---

@admin_bp.route("/admin/email", methods=["GET", "POST"])
@admin_required
def admin_email():
    config = EmailConfig.query.first()
    if not config:
        config = EmailConfig(sender_email="", sender_password="", destination_email="")
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        config.sender_email = request.form.get("sender_email", "").strip()
        config.sender_password = request.form.get("sender_password", "").strip()
        config.destination_email = request.form.get("destination_email", "").strip()
        db.session.commit()
        flash("Configuration updated.", "success")
        return redirect(url_for("admin.admin_email"))
    
    return render_template("admin/admin_email.html", config=config)

@admin_bp.route('/admin/manage_hours', methods=['GET', 'POST'])
@admin_required
def manage_hours():
    # Lazy creation of configs if they do not exist
    if not OfficeConfig.query.first(): db.session.add(OfficeConfig()); db.session.commit()
    if not SiteConfig.query.first(): db.session.add(SiteConfig()); db.session.commit()
    if not PartTimeConfig.query.first(): db.session.add(PartTimeConfig()); db.session.commit()

    c_office = OfficeConfig.query.first()
    c_site = SiteConfig.query.first()
    c_part_time = PartTimeConfig.query.first()

    if request.method == 'POST':
        def pt(v): return datetime.strptime(v, "%H:%M").time() if v else None
        def pd(v): return datetime.strptime(v, "%d-%m-%Y").date() if v else None

        # Office schedule mass update
        c_office.morning_in_mon_wed_winter = pt(request.form.get("morning_in_mon_wed_winter"))
        c_office.morning_out_mon_wed_winter = pt(request.form.get("morning_out_mon_wed_winter"))
        c_office.afternoon_in_mon_wed_winter = pt(request.form.get("afternoon_in_mon_wed_winter"))
        c_office.afternoon_out_mon_wed_winter = pt(request.form.get("afternoon_out_mon_wed_winter"))
        c_office.morning_in_tue_thu_winter = pt(request.form.get("morning_in_tue_thu_winter"))
        c_office.morning_out_tue_thu_winter = pt(request.form.get("morning_out_tue_thu_winter"))
        c_office.in_friday_winter = pt(request.form.get("in_friday_winter"))
        c_office.out_friday_winter = pt(request.form.get("out_friday_winter"))
        
        c_office.summer_start = pd(request.form.get("summer_start"))
        c_office.summer_end = pd(request.form.get("summer_end"))
        c_office.morning_in_summer = pt(request.form.get("morning_in_summer"))
        c_office.morning_out_summer = pt(request.form.get("morning_out_summer"))
        c_office.in_friday_summer = pt(request.form.get("in_friday_summer"))
        c_office.out_friday_summer = pt(request.form.get("out_friday_summer"))

        # Part-Time schedule update
        c_part_time.in_winter = pt(request.form.get("in_winter_pt"))
        c_part_time.out_winter = pt(request.form.get("out_winter_pt"))
        c_part_time.in_friday_winter = pt(request.form.get("in_friday_winter_pt"))
        c_part_time.out_friday_winter = pt(request.form.get("out_friday_winter_pt"))
        c_part_time.in_summer = pt(request.form.get("in_summer_pt"))
        c_part_time.out_summer = pt(request.form.get("out_summer_pt"))
        c_part_time.in_friday_summer = pt(request.form.get("in_friday_summer_pt"))
        c_part_time.out_friday_summer = pt(request.form.get("out_friday_summer_pt"))

        # Site schedule update
        c_site.in_winter = pt(request.form.get("in_winter_site"))
        c_site.out_winter = pt(request.form.get("out_winter_site"))
        c_site.in_friday_winter = pt(request.form.get("in_friday_winter_site"))
        c_site.out_friday_winter = pt(request.form.get("out_friday_winter_site"))
        
        c_site.july_start = pd(request.form.get("july_start_site"))
        c_site.july_end = pd(request.form.get("july_end_site"))
        c_site.in_july = pt(request.form.get("in_july_site"))
        c_site.out_july = pt(request.form.get("out_july_site"))
        c_site.in_friday_july = pt(request.form.get("in_friday_july_site"))
        c_site.out_friday_july = pt(request.form.get("out_friday_july_site"))
        
        c_site.august_start = pd(request.form.get("august_start_site"))
        c_site.august_end = pd(request.form.get("august_end_site"))
        c_site.in_august = pt(request.form.get("in_august_site"))
        c_site.out_august = pt(request.form.get("out_august_site"))
        c_site.in_friday_august = pt(request.form.get("in_friday_august_site"))
        c_site.out_friday_august = pt(request.form.get("out_friday_august_site"))

        db.session.commit()
        flash("Schedules updated successfully.", "success")
        return redirect(url_for("admin.manage_hours"))

    fmt = "%d-%m-%Y"
    formatted_dates = {
        "summer_start": c_office.summer_start.strftime(fmt) if c_office.summer_start else "",
        "summer_end": c_office.summer_end.strftime(fmt) if c_office.summer_end else ""
    }
    
    return render_template(
        "admin/manage_hours.html", 
        config_office=c_office, config_site=c_site, config_part_time=c_part_time,
        summer_start_fmt=formatted_dates["summer_start"],
        summer_end_fmt=formatted_dates["summer_end"]
    )