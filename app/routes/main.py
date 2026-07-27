"""
File: app/routes/main.py

Main application routes: timesheet management, calendar, and reports.

Author: Laura Sanz Lobo
"""

import os
import threading
from datetime import datetime, date, timedelta
from calendar import monthrange
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response, current_app
from flask_mail import Message

from app.extensions import db
from app.models import User, Record, Holiday, Site, EmailConfig, OfficeConfig
from app.utils import (
    generate_pdf, send_async_email, get_current_date, sync_record_range
)

# Define the 'main' Blueprint
main_bp = Blueprint('main', __name__)

"""***************************************************************************"""
""" Calendar - MAIN PAGE """

@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = User.query.get(session["user_id"])  # Get current user
    if not user:
        flash("Usuario no encontrado", "error")
        return redirect(url_for("auth.login"))

    is_admin = user.is_admin  
    worker_type = user.worker_type if user.worker_type else "unknown"

    if request.method == "POST":
        date_str = request.form.get("date")
        day_type = request.form.get("day_type", "normal")
        clock_in = request.form.get("clock_in")
        clock_out = request.form.get("clock_out")
        clock_in_afternoon = request.form.get("clock_in_afternoon") if worker_type == "office" else None
        clock_out_afternoon = request.form.get("clock_out_afternoon") if worker_type == "office" else None
        site_id_raw = request.form.get("site_id")
        site_id = int(site_id_raw) if worker_type == "site" and site_id_raw else None

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Formato de fecha incorrecto.", "error")
            return redirect(url_for("main.register"))

        if Holiday.query.filter_by(date=target_date).first():
            flash("No se pueden guardar registros en días festivos.", "error")
            return redirect(url_for("main.register", date=date_str))

        if day_type == "normal":
                if not any([clock_in, clock_out, clock_in_afternoon, clock_out_afternoon]):
                    flash("Error: No se puede guardar un día laborable completamente vacío.", "error")
                    return redirect(url_for("main.register", date=date_str))
                
                if worker_type == "office":
                    if not clock_in and clock_out:
                        flash("Debe indicar tanto hora de entrada como de salida.", "error")
                        return redirect(url_for("main.register"))
                    if not clock_in_afternoon and clock_out_afternoon:
                        flash("Debe indicar tanto hora de entrada como de salida.", "error")
                        return redirect(url_for("main.register"))

                elif worker_type in ["site", "part_time"]:
                    if not clock_in and clock_out:
                        flash("Debe indicar tanto hora de entrada como de salida.", "error")
                        return redirect(url_for("main.register"))

        record = Record.query.filter_by(user_id=user.id, date=target_date).first()
        if not record:
            record = Record(user_id=user.id, date=target_date)

        record.day_type = day_type
        record.clock_in = datetime.strptime(clock_in, "%H:%M").time() if clock_in else None
        record.clock_out = datetime.strptime(clock_out, "%H:%M").time() if clock_out else None
        record.clock_in_afternoon = datetime.strptime(clock_in_afternoon, "%H:%M").time() if clock_in_afternoon else None
        record.clock_out_afternoon = datetime.strptime(clock_out_afternoon, "%H:%M").time() if clock_out_afternoon else None
        record.site_id = site_id if site_id else None

        db.session.add(record)
        db.session.commit()
        flash("Registro guardado con éxito.", "success")
        return redirect(url_for("main.register", date=date_str))

    # For GET
    now = get_current_date()

    last_record = Record.query.filter_by(user_id=user.id).order_by(Record.date.desc()).first()
    
    if last_record:
        sync_start_date = last_record.date + timedelta(days=1)
    else:
        sync_start_date = user.start_date or now.date().replace(day=1)

    sync_record_range(user.id, sync_start_date, now.date())

    original_date = request.args.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
    date_obj = datetime.strptime(original_date, "%Y-%m-%d").date()
    formatted_date = date_obj.strftime("%d-%m-%Y")
    
    selected_date = datetime.strptime(original_date, "%Y-%m-%d").date()
    current_record = Record.query.filter_by(user_id=user.id, date=selected_date).first()
    records = Record.query.filter_by(user_id=user.id).order_by(Record.date.desc()).all()
    sites = Site.query.filter_by(is_active=True).order_by(Site.name).all() if worker_type == "site" else []

    day_label = ""
    if date_obj.weekday() in [5, 6]:
        day_label = " - Fin de semana"
    if Holiday.query.filter_by(date=date_obj).first():
        day_label = " - Festivo"
        
    config_office = OfficeConfig.query.first()

    return render_template(
        "main/register.html",
        original_date=original_date,
        formatted_date=formatted_date,
        day_label=day_label,
        current_record=current_record,
        records=records,
        sites=sites,
        worker_type=worker_type,
        is_admin=is_admin,
        config_office=config_office
    )

"""***************************************************************************"""
""" PDF Management """

@main_bp.route("/select_month", methods=["GET", "POST"])
def select_month():
    if "user_id" not in session: 
        return redirect(url_for("auth.login"))

    logged_in_user = User.query.get(session["user_id"])
    origin = request.args.get('origin') 

    target_user_id = request.args.get('user_id')
    target_user = None

    if target_user_id and logged_in_user.is_admin:
        target_user = User.query.get(target_user_id)
    
    if not target_user:
        target_user = logged_in_user

    if request.method == "POST":
        month = request.form["month"]
        year = request.form["year"]
        form_user_id = request.form.get("user_id")
        
        return redirect(url_for("main.view_pdf", month=month, year=year, user_id=form_user_id))

    return render_template("main/select_month.html", target_user=target_user, origin=origin)


@main_bp.route('/generate_pdf', methods=['GET'])
def generate_pdf():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    logged_in_user = User.query.get(session["user_id"])
    if not logged_in_user:
        return redirect(url_for("auth.login"))

    target_user_id = request.args.get('user_id')

    if target_user_id and logged_in_user.is_admin:
        target_user = User.query.get(target_user_id)
        if not target_user:
            flash("Usuario no encontrado", "error")
            return redirect(url_for("main.select_month"))
    else:
        target_user = logged_in_user

    month_param = request.args.get('month')
    year_param = request.args.get('year')
    
    if not month_param:
        flash("Debes seleccionar un mes", "error")
        return redirect(request.referrer or url_for("main.select_month"))
    
    try:
        if year_param:
            month = int(month_param)
            year = int(year_param)
        else:
            month, year = map(int, month_param.split('/'))
    except Exception as e:
        flash(f"Error fecha: {e}", "error")
        return redirect(request.referrer)

    today = get_current_date().date()
    days_in_month = monthrange(year, month)[1]

    month_start_date = date(year, month, 1)
    month_end_date = date(year, month, days_in_month)
    
    limit_date = month_end_date if month_end_date < today else today

    previous_last_record = Record.query.filter(
        Record.user_id == target_user.id,
        Record.date < month_start_date
    ).order_by(Record.date.desc()).first()

    if previous_last_record:
        sync_start_date = previous_last_record.date + timedelta(days=1)
    else:
        sync_start_date = target_user.start_date or month_start_date

    sync_record_range(target_user.id, sync_start_date, limit_date)
    
    pdf_bytes = generate_pdf(target_user, month, year)
    fname = f"Informe_{target_user.national_id}_{month:02d}_{year}.pdf"

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={fname}'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@main_bp.route('/send_pdf', methods=['GET'])
def send_pdf():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    logged_in_user = User.query.get(session["user_id"])
    target_user_id = request.args.get('user_id')

    if target_user_id and logged_in_user.is_admin:
        target_user = User.query.get(target_user_id)
        if not target_user:
            flash("Usuario no encontrado", "error")
            return redirect(url_for("main.select_month"))
    else:
        target_user = logged_in_user

    try:
        month = int(request.args["month"])
        year  = int(request.args["year"])
    except (KeyError, ValueError):
        flash("Parámetros de fecha inválidos.", "error")
        return redirect(url_for("main.select_month"))

    today = get_current_date().date()
    days_in_month = monthrange(year, month)[1]
    month_start_date = date(year, month, 1)
    month_end_date = date(year, month, days_in_month)
    limit_date = month_end_date if month_end_date < today else today

    previous_last_record = Record.query.filter(
        Record.user_id == target_user.id,  
        Record.date < month_start_date
    ).order_by(Record.date.desc()).first()

    if previous_last_record:
        sync_start_date = previous_last_record.date + timedelta(days=1)
    else:
        sync_start_date = target_user.start_date or month_start_date

    sync_record_range(target_user.id, sync_start_date, limit_date)
    
    pdf_bytes = generate_pdf(target_user, month, year)

    cfg = EmailConfig.query.first()
    if not cfg or not (cfg.sender_email and cfg.sender_password and cfg.destination_email):
        flash("La configuración de correo no está completa.", "error")
        return redirect(url_for("admin.admin_email"))

    app = current_app._get_current_object()
    
    app.config.update(
        MAIL_USERNAME=cfg.sender_email,
        MAIL_PASSWORD=cfg.sender_password
    )

    msg = Message(
        subject=f"Informe - {target_user.full_name} - {target_user.national_id} – {month:02d}/{year}",
        sender=cfg.sender_email,
        recipients=[cfg.destination_email]
    )

    filename = f"{target_user.full_name.replace(' ', '_')}_{target_user.national_id}_{month:02d}-{year}.pdf"
    msg.attach(filename, "application/pdf", pdf_bytes)
    
    threading.Thread(target=send_async_email, args=(app, msg)).start()
    
    flash("Informe enviado correctamente.", "success")
    return redirect(url_for("main.select_month"))
        

@main_bp.route('/process_pdf', methods=['GET'])
def process_pdf():
    action = request.args.get('action')
    month_param = request.args.get('month')
    target_user_id = request.args.get('user_id')

    if not month_param:
        flash("Debes seleccionar un mes.", "error")
        return redirect(url_for('main.select_month'))
    
    month_param = month_param.strip()
    
    if '/' in month_param:
        month, year = month_param.split('/')
    elif '-' in month_param:
        month, year = month_param.split('-')
    else:
        flash("El formato del mes seleccionado es incorrecto.", "error")
        return redirect(url_for('main.select_month'))
    
    if action == 'view':
        return redirect(url_for('main.view_pdf', month=month, year=year, t=int(get_current_date().timestamp()), user_id=target_user_id))
    elif action == 'send':
        return redirect(url_for('main.send_pdf', month=month, year=year, user_id=target_user_id))
    else:
        flash("Acción no reconocida", "error")
        return redirect(url_for('main.select_month'))


@main_bp.route('/view_pdf', methods=['GET'])
def view_pdf():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    logged_in_user = User.query.get(session["user_id"])
    month = request.args.get('month')
    year = request.args.get('year')
    target_user_id = request.args.get('user_id')

    if not month or not year:
        flash("Faltan parámetros.", "error")
        return redirect(url_for("main.select_month"))

    t = int(datetime.now().timestamp())
    
    if target_user_id and logged_in_user.is_admin:
        pdf_base = url_for('main.generate_pdf', month=month, year=year, t=t, _external=True, user_id=target_user_id)
    else:
        pdf_base = url_for('main.generate_pdf', month=month, year=year, t=t, _external=True)

    return render_template('main/view_pdf.html', pdf_base=pdf_base)