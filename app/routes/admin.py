"""
File: app/routes/admin.py

Routes for the administration panel and system configuration.

Author: Laura Sanz Lobo
"""
import os
import uuid
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app as app
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from app.extensions import db, bcrypt
from app.models import (
    User, Holiday, Site, Record, EmailConfig, OfficeConfig, SiteConfig, PartTimeConfig
)
from app.decorators import admin_required
from app.utils import allowed_file

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/admin")
@admin_required 
def admin_panel():
    return render_template("admin/admin_dashboard.html")

"""***************************************************************************"""
"""  User Management """

@admin_bp.route("/admin/users/create", methods=["GET", "POST"])
@admin_required 
def create_user():
    admin_exists = User.query.filter_by(is_admin=True).first()

    if admin_exists and "user_id" not in session:
        flash("Debes ser administrador para crear nuevos usuarios.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        national_id = request.form.get("national_id", "").strip()
        is_admin = "is_admin" in request.form if admin_exists else True
        worker_type = request.form.get("worker_type")
        start_date_str = request.form.get("start_date")
        end_date_str = request.form.get("end_date")

        if not username or not password or not full_name or not national_id or not start_date_str:
            flash("Todos los campos son obligatorios excepto la firma.", "error")
            return redirect(url_for("admin.create_user"))
        
        if worker_type not in ["office", "site", "part_time"]:
            flash("Tipo de trabajador inválido.", "error")
            return redirect(url_for("admin.create_user"))
            
        start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date() if start_date_str else date.today()
        end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date() if end_date_str else None

        signature_file = request.files.get("signature")
        signature_path = None
        
        if signature_file and signature_file.filename:
            if allowed_file(signature_file.filename):
                filename = f"{uuid.uuid4().hex}_{secure_filename(signature_file.filename)}"
                signature_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                signature_file.save(signature_path)
            else:
                flash("Formato de firma no permitido (solo PNG/JPG/JPEG/GIF).", "error")
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
            
            flash("Usuario creado con éxito.", "success")

            if not admin_exists:
                session["user_id"] = new_user.id
                return redirect(url_for("admin.admin_panel"))

            return redirect(url_for("admin.create_user"))

        except IntegrityError:
            db.session.rollback()
            flash("El nombre de usuario ya existe. Por favor, verifica los datos.", "error")
            return redirect(url_for("admin.create_user"))

        except Exception as e:
            flash(f"Error inesperado al crear usuario: {e}", "error")
            return redirect(url_for("admin.create_user"))
        
    return render_template("admin/create_user.html")


@admin_bp.route("/admin/users/edit/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
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
                flash("Formato de fecha inválido. Usa DD-MM-YYYY.", "error")
                return redirect(request.url)
        
        end_date_str = request.form.get("end_date", "").strip()
        if not end_date_str:
            user.end_date = None
        else:
            try:
                new_end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()
                user.end_date = new_end_date
                
                records_to_delete = Record.query.filter(
                    Record.user_id == user.id,
                    Record.date > new_end_date
                )
                records_to_delete.delete(synchronize_session=False)
                    
            except ValueError:
                flash("Formato de fecha de baja inválido. Usa DD-MM-YYYY.", "error")
                return redirect(request.url)

        signature_file = request.files.get("signature")
        if signature_file and signature_file.filename:
            if allowed_file(signature_file.filename):
                filename = f"{uuid.uuid4().hex}_{secure_filename(signature_file.filename)}"
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                signature_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                signature_file.save(signature_path)
                user.signature = signature_path
            else:
                flash("Formato de firma no permitido.", "error")
                return redirect(request.url)

        try:
            db.session.commit()
            flash("Usuario actualizado correctamente.", "success")
            return redirect(back_url)
        except IntegrityError:
            db.session.rollback()
            flash("Nombre de usuario duplicado.", "error")
            return redirect(request.url)

    return render_template("admin/edit_user.html", user=user, back_url=back_url)


@admin_bp.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == session["user_id"]:
        flash("No puedes eliminar tu propia cuenta.", "error")
    else:
        db.session.delete(user)
        db.session.commit()
        flash("Usuario eliminado correctamente.", "success")
        
    return redirect(request.referrer or url_for("admin.user_list"))


@admin_bp.route("/admin/users", methods=["GET"])
@admin_required
def user_list():
    search_query = request.args.get('q')
    query = User.query

    if search_query:
        query = query.filter(
            or_(
                User.full_name.ilike(f"%{search_query}%"),
                User.national_id.ilike(f"%{search_query}%"),
                User.username.ilike(f"%{search_query}%")
            )
        )
    
    users = query.order_by(User.full_name.asc()).all()
    return render_template("admin/user_list.html", users=users, current_filter=None)

@admin_bp.route("/admin/users/filter/<string:worker_type>")
@admin_required
def user_list_filter(worker_type):
    if worker_type not in ['office', 'site', 'part_time']: 
        return redirect(url_for("admin.user_list"))
    
    users = User.query.filter_by(worker_type=worker_type).order_by(User.full_name).all()
    return render_template("admin/user_list.html", users=users, current_filter=worker_type)


"""***************************************************************************"""
""" Manage Schedule Config """

@admin_bp.route('/admin/manage_hours', methods=['GET', 'POST'])
@admin_required
def manage_hours():
    config_office = OfficeConfig.query.first()
    config_site = SiteConfig.query.first()
    config_part_time = PartTimeConfig.query.first()

    if not config_office:
        config_office = OfficeConfig()
        db.session.add(config_office)
        db.session.commit()

    if not config_site:
        config_site = SiteConfig()
        db.session.add(config_site)
        db.session.commit()
        
    if not config_part_time:
        config_part_time = PartTimeConfig()
        db.session.add(config_part_time)
        db.session.commit()

    if request.method == 'POST':

        def parse_time(value):
            return datetime.strptime(value, "%H:%M").time() if value else None
        
        # Office Schedule
        config_office.morning_in_mon_wed_winter = parse_time(request.form.get("morning_in_mon_wed_winter"))
        config_office.morning_out_mon_wed_winter  = parse_time(request.form.get("morning_out_mon_wed_winter"))
        config_office.afternoon_in_mon_wed_winter  = parse_time(request.form.get("afternoon_in_mon_wed_winter"))
        config_office.afternoon_out_mon_wed_winter   = parse_time(request.form.get("afternoon_out_mon_wed_winter"))
        
        config_office.morning_in_tue_thu_winter = parse_time(request.form.get("morning_in_tue_thu_winter"))
        config_office.morning_out_tue_thu_winter  = parse_time(request.form.get("morning_out_tue_thu_winter"))
        
        config_office.in_friday_winter   = parse_time(request.form.get("in_friday_winter"))
        config_office.out_friday_winter    = parse_time(request.form.get("out_friday_winter"))

        config_office.summer_start = datetime.strptime(request.form.get("summer_start"), "%d-%m-%Y").date() if request.form.get("summer_start") else None
        config_office.summer_end = datetime.strptime(request.form.get("summer_end"), "%d-%m-%Y").date() if request.form.get("summer_end") else None
        config_office.morning_in_summer = parse_time(request.form.get("morning_in_summer"))
        config_office.morning_out_summer = parse_time(request.form.get("morning_out_summer"))
        config_office.in_friday_summer = parse_time(request.form.get("in_friday_summer"))
        config_office.out_friday_summer = parse_time(request.form.get("out_friday_summer"))

        # Part-Time Schedule
        config_part_time.in_winter = parse_time(request.form.get("in_winter_pt"))
        config_part_time.out_winter  = parse_time(request.form.get("out_winter_pt"))
        config_part_time.in_friday_winter = parse_time(request.form.get("in_friday_winter_pt"))
        config_part_time.out_friday_winter  = parse_time(request.form.get("out_friday_winter_pt"))
        
        config_part_time.in_summer = parse_time(request.form.get("in_summer_pt"))
        config_part_time.out_summer  = parse_time(request.form.get("out_summer_pt"))
        config_part_time.in_friday_summer = parse_time(request.form.get("in_friday_summer_pt"))
        config_part_time.out_friday_summer  = parse_time(request.form.get("out_friday_summer_pt"))

        # Site Schedule
        config_site.in_winter = parse_time(request.form.get("in_winter_site"))
        config_site.out_winter = parse_time(request.form.get("out_winter_site"))
        config_site.in_friday_winter = parse_time(request.form.get("in_friday_winter_site"))
        config_site.out_friday_winter = parse_time(request.form.get("out_friday_winter_site"))

        config_site.july_start = datetime.strptime(request.form.get("july_start_site"), "%d-%m-%Y").date() if request.form.get("july_start_site") else None
        config_site.july_end = datetime.strptime(request.form.get("july_end_site"), "%d-%m-%Y").date() if request.form.get("july_end_site") else None
        config_site.in_july = parse_time(request.form.get("in_july_site"))
        config_site.out_july = parse_time(request.form.get("out_july_site"))
        config_site.in_friday_july = parse_time(request.form.get("in_friday_july_site"))
        config_site.out_friday_july = parse_time(request.form.get("out_friday_july_site"))

        config_site.august_start = datetime.strptime(request.form.get("august_start_site"), "%d-%m-%Y").date() if request.form.get("august_start_site") else None
        config_site.august_end = datetime.strptime(request.form.get("august_end_site"), "%d-%m-%Y").date() if request.form.get("august_end_site") else None
        config_site.in_august = parse_time(request.form.get("in_august_site"))
        config_site.out_august = parse_time(request.form.get("out_august_site"))
        config_site.in_friday_august = parse_time(request.form.get("in_friday_august_site"))
        config_site.out_friday_august = parse_time(request.form.get("out_friday_august_site"))

        db.session.commit()
        flash("Horarios actualizados correctamente", "success")
        return redirect(url_for("admin.manage_hours"))
    
    summer_start_fmt = config_office.summer_start.strftime("%d-%m-%Y") if config_office.summer_start else ""
    summer_end_fmt = config_office.summer_end.strftime("%d-%m-%Y") if config_office.summer_end else ""
    
    if config_site.july_start:
        config_site.july_start = config_site.july_start.strftime("%d-%m-%Y")
    if config_site.july_end:
        config_site.july_end = config_site.july_end.strftime("%d-%m-%Y")
    if config_site.august_start:
        config_site.august_start = config_site.august_start.strftime("%d-%m-%Y")
    if config_site.august_end:
        config_site.august_end = config_site.august_end.strftime("%d-%m-%Y")

    return render_template(
        "admin/manage_hours.html", 
        config_office=config_office, 
        config_site=config_site, 
        config_part_time=config_part_time,
        summer_start_fmt=summer_start_fmt,
        summer_end_fmt=summer_end_fmt
    )


"""***************************************************************************"""
""" Manage Holidays """

@admin_bp.route("/admin/holidays", methods=["GET", "POST"])
@admin_required
def admin_holidays():
    if request.method == "POST":
        date_str = request.form.get("date")
        description = request.form.get("description")
        try:
            date_obj = datetime.strptime(date_str, "%d-%m-%Y").date()
            if Holiday.query.filter_by(date=date_obj).first():
                flash("Ya existe un festivo registrado para esa fecha.", "error")
            else:
                Record.query.filter_by(date=date_obj).delete()
                db.session.add(Holiday(date=date_obj, description=description))
                db.session.commit()
                flash("Festivo agregado correctamente.", "success")
        except ValueError:
            flash("Formato de fecha inválido.", "error")
        except IntegrityError:
            db.session.rollback()
            flash("Error de integridad al guardar el festivo.", "error")
        return redirect(url_for("admin.admin_holidays"))

    holidays = Holiday.query.order_by(Holiday.date).all()
    return render_template("admin/admin_holidays.html", holidays=holidays)


@admin_bp.route("/admin/holidays/delete/<int:holiday_id>", methods=["POST"])
@admin_required
def delete_holiday(holiday_id):
    holiday = Holiday.query.get_or_404(holiday_id)
    db.session.delete(holiday)
    db.session.commit()
    flash("Festivo eliminado correctamente.", "success")
    return redirect(url_for("admin.admin_holidays"))


"""***************************************************************************"""
""" Manage Sites """

@admin_bp.route("/admin/sites", methods=["GET", "POST"])
@admin_required
def admin_sites():
    if request.method == "POST":
        site_name = request.form.get("site_name", "").strip()
        if not site_name:
            flash("El nombre de la obra no puede estar vacío.", "error")
        else:
            try:
                db.session.add(Site(name=site_name))
                db.session.commit()
                flash("Obra agregada correctamente.", "success")
            except IntegrityError:
                db.session.rollback()
                flash("Ya existe una obra con ese nombre.", "error")
        return redirect(url_for("admin.admin_sites"))
    
    sites = Site.query.order_by(Site.is_active.desc(), Site.name.asc()).all()
    return render_template("admin/admin_sites.html", sites=sites)


@admin_bp.route("/admin/sites/delete/<int:site_id>", methods=["POST"])
@admin_required
def delete_site(site_id):
    site = Site.query.get_or_404(site_id)
    db.session.delete(site)
    db.session.commit()
    flash("Obra eliminada correctamente.", "success")
    return redirect(url_for("admin.admin_sites"))


@admin_bp.route("/admin/sites/archive/<int:site_id>", methods=["POST"])
@admin_required
def archive_site(site_id):
    site = Site.query.get_or_404(site_id)
    site.is_active = False
    db.session.commit()
    flash(f"La obra '{site.name}' ha sido archivada.", "success")
    return redirect(url_for("admin.admin_sites"))


@admin_bp.route("/admin/sites/reactivate/<int:site_id>", methods=["POST"])
@admin_required
def reactivate_site(site_id):
    site = Site.query.get_or_404(site_id)
    site.is_active = True
    db.session.commit()
    flash(f"La obra '{site.name}' ha sido reactivada.", "success")
    return redirect(url_for("admin.admin_sites"))


@admin_bp.route("/admin/sites/edit/<int:site_id>", methods=["POST"])
@admin_required
def edit_site(site_id):
    new_name = request.form.get("new_name", "").strip()
    if not new_name:
        flash("El nuevo nombre no puede estar vacío.", "error")
        return redirect(url_for("admin.admin_sites"))

    site = Site.query.get_or_404(site_id)
    site.name = new_name
    try:
        db.session.commit()
        flash("Nombre actualizado correctamente.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Ya existe una obra con ese nombre.", "error")
    return redirect(url_for("admin.admin_sites"))


"""***************************************************************************"""
""" Manage Email """

@admin_bp.route("/admin/email", methods=["GET", "POST"])
@admin_required
def admin_email():
    config = EmailConfig.query.first()
    if not config:
        config = EmailConfig(sender_email="", sender_password="", destination_email="")
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        sender_email = request.form.get("sender_email", "").strip()
        sender_password = request.form.get("sender_password", "").strip()
        destination_email = request.form.get("destination_email", "").strip()
        if sender_email and sender_password and destination_email:
            config.sender_email = sender_email
            config.sender_password = sender_password
            config.destination_email = destination_email
            db.session.commit()
            flash("Configuración de correo actualizada correctamente.", "success")
        else:
            flash("Debes introducir todos los campos.", "error")
        return redirect(url_for("admin.admin_email"))
    
    return render_template("admin/admin_email.html", config=config)