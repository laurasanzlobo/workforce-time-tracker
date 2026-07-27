"""
File: app/routes/main.py

Main application routes: timesheet management, calendar, and reports.

Author: Laura Sanz Lobo
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response, current_app
from datetime import datetime, timedelta, date
from app.models import User, Record, Holiday, Site, OfficeConfig
from app.utils import (
    get_default_hours, adjust_clock_in, adjust_clock_out, 
    generate_pdf, send_async_email
)
from flask_mail import Message
import threading

# Define the 'main' Blueprint
main_bp = Blueprint('main', __name__)

@main_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Main view for the calendar and manual timesheet form.
    Manages the display and saving of daily records.
    """
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = User.query.get(session["user_id"])
    if not user:
        flash("User not found", "error")
        return redirect(url_for("auth.login"))

    is_admin = user.is_admin
    worker_type = user.worker_type or "unknown"

    # --- POST FORM PROCESSING (SAVE RECORD) ---
    if request.method == "POST":
        date_str = request.form.get("date")
        day_type = request.form.get("day_type", "normal")
        clock_in = request.form.get("clock_in")
        clock_out = request.form.get("clock_out")
        
        # Afternoon hours (office only)
        clock_in_afternoon = request.form.get("clock_in_afternoon") if worker_type == "office" else None
        clock_out_afternoon = request.form.get("clock_out_afternoon") if worker_type == "office" else None
        
        # Site (site workers only)
        site_id_raw = request.form.get("site_id")
        site_id = int(site_id_raw) if worker_type == "site" and site_id_raw else None

        # Data validation and conversion
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for("main.register"))

        if Holiday.query.filter_by(date=target_date).first():
            flash("Cannot save records on public holidays.", "error")
            return redirect(url_for("main.register", date=date_str))

        # Basic required hours validation
        if day_type == "normal":
             if not any([clock_in, clock_out, clock_in_afternoon, clock_out_afternoon]):
                 return redirect(url_for("main.register", date=date_str))
                 
             if (clock_in and not clock_out) or (not clock_in and clock_out):
                  flash("You must provide both clock-in and clock-out times.", "error")
                  return redirect(url_for("main.register", date=date_str))

        # Database save
        from app.extensions import db
        
        existing_record = Record.query.filter_by(user_id=user.id, date=target_date).first()
        if not existing_record:
            existing_record = Record(user_id=user.id, date=target_date)

        existing_record.day_type = day_type
        existing_record.clock_in = datetime.strptime(clock_in, "%H:%M").time() if clock_in else None
        existing_record.clock_out = datetime.strptime(clock_out, "%H:%M").time() if clock_out else None
        existing_record.clock_in_afternoon = datetime.strptime(clock_in_afternoon, "%H:%M").time() if clock_in_afternoon else None
        existing_record.clock_out_afternoon = datetime.strptime(clock_out_afternoon, "%H:%M").time() if clock_out_afternoon else None
        existing_record.site_id = site_id

        db.session.add(existing_record)
        db.session.commit()
        flash("Record saved successfully.", "success")
        return redirect(url_for("main.register", date=date_str))

    # --- GET LOGIC (INITIAL LOAD & AUTO-FILL) ---
    from app.extensions import db 
    
    now = datetime.now()
    original_date = request.args.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
    date_obj = datetime.strptime(original_date, "%Y-%m-%d").date()
    formatted_date = date_obj.strftime("%d-%m-%Y")
    
    # Auto-fill logic for past days
    today_date = now.date()
    cursor_date = user.start_date or date.today()
    changes_made = False

    while cursor_date <= today_date:
        if user.end_date and cursor_date > user.end_date:
            break
            
        # Ignore weekends and holidays for auto-fill
        if cursor_date.weekday() >= 5 or Holiday.query.filter_by(date=cursor_date).first():
            cursor_date += timedelta(days=1)
            continue
            
        hours = get_default_hours(cursor_date, worker_type, user.id)
        if not hours:
            cursor_date += timedelta(days=1)
            continue
            
        # Random adjustment of theoretical hours
        c_in = adjust_clock_in(hours["clock_in"])
        c_out  = adjust_clock_out(hours["clock_out"])
        c_in_afternoon = adjust_clock_in(hours["clock_in_afternoon"])
        c_out_afternoon  = adjust_clock_out(hours["clock_out_afternoon"])
        auto_site_id = hours.get("site_id")

        reg = Record.query.filter_by(user_id=user.id, date=cursor_date).first()
        
        # Case 1: Past day without record -> Create new
        if cursor_date < today_date:
            if not reg:
                new_reg = Record(
                    user_id=user.id, date=cursor_date, day_type="normal",
                    clock_in=c_in, clock_out=c_out,
                    clock_in_afternoon=c_in_afternoon, clock_out_afternoon=c_out_afternoon,
                    site_id=auto_site_id
                )
                db.session.add(new_reg)
                changes_made = True
            else:
                # Complete partial records in the past
                if reg.clock_in and not reg.clock_out:
                    reg.clock_out = c_out; changes_made = True
                if c_in_afternoon and c_out_afternoon:
                     if not reg.clock_in_afternoon and not reg.clock_out_afternoon:
                         reg.clock_in_afternoon = c_in_afternoon; reg.clock_out_afternoon = c_out_afternoon; changes_made = True
                     elif reg.clock_in_afternoon and not reg.clock_out_afternoon:
                         reg.clock_out_afternoon = c_out_afternoon; changes_made = True
        
        # Case 2: Current day -> Fill as time passes
        elif cursor_date == today_date:
            if not reg:
                reg = Record(user_id=user.id, date=cursor_date, day_type="normal", site_id=auto_site_id)
                db.session.add(reg)
            
            # Only fill if the current time has passed the theoretical time
            if c_in and now.time() >= c_in and reg.clock_in is None:
                reg.clock_in = c_in; changes_made = True
            if c_out and now.time() >= c_out and reg.clock_out is None:
                reg.clock_out = c_out; changes_made = True
            if c_in_afternoon and now.time() >= c_in_afternoon and reg.clock_in_afternoon is None:
                reg.clock_in_afternoon = c_in_afternoon; changes_made = True
            if c_out_afternoon and now.time() >= c_out_afternoon and reg.clock_out_afternoon is None:
                reg.clock_out_afternoon = c_out_afternoon; changes_made = True

        cursor_date += timedelta(days=1)

    if changes_made:
        db.session.commit()

    # Data preparation for the view
    current_record = Record.query.filter_by(user_id=user.id, date=date_obj).first()
    records = Record.query.filter_by(user_id=user.id).order_by(Record.date.desc()).all()
    sites = Site.query.filter_by(is_active=True).order_by(Site.name).all() if worker_type == "site" else []
    
    day_label = ""
    if date_obj.weekday() in [5, 6]: day_label = " - Weekend"
    if Holiday.query.filter_by(date=date_obj).first(): day_label = " - Holiday"

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
        config_office=OfficeConfig.query.first()
    )

# --- PDF MANAGEMENT ROUTES ---

@main_bp.route("/select_month", methods=["GET", "POST"])
def select_month():
    """View to select month and year before generating reports."""
    if "user_id" not in session: return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        month = request.form["month"]
        year = request.form["year"]
        return redirect(url_for("main.generate_pdf", month=month, year=year))
    
    return render_template("main/select_month.html")

@main_bp.route('/generate_pdf', methods=['GET'])
def generate_pdf():
    """Generates and downloads the attendance PDF."""
    if "user_id" not in session: return redirect(url_for("auth.login"))

    user = User.query.get(session["user_id"])
    if not user: return redirect(url_for("main.register"))

    month_param = request.args.get('month')
    year_param = request.args.get('year')
    
    if not month_param:
        flash("You must select a month", "error")
        return redirect(url_for("main.select_month"))
    
    try:
        if year_param:
            month, year = int(month_param), int(year_param)
        else:
            month, year = map(int, month_param.split('/'))
            
        pdf_bytes = generate_pdf(user, month, year)
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Report_{month:02d}_{year}.pdf'
        return response

    except Exception as e:
        flash(f"Error generating PDF: {e}", "error")
        return redirect(url_for("main.select_month"))

@main_bp.route('/send_pdf', methods=['GET'])
def send_pdf():
    """Sends the generated PDF via email."""
    if "user_id" not in session: return redirect(url_for("auth.login"))
    
    user = User.query.get(session["user_id"])
    month = int(request.args["month"])
    year  = int(request.args["year"])
    
    from app.models import EmailConfig
    from app.extensions import mail
    
    cfg = EmailConfig.query.first()
    if not cfg or not (cfg.sender_email and cfg.sender_password and cfg.destination_email):
        flash("Email configuration is incomplete.", "error")
        return redirect(url_for("admin.admin_email"))

    # Dynamic reconfiguration of Flask-Mail
    current_app.config.update(
        MAIL_USERNAME=cfg.sender_email,
        MAIL_PASSWORD=cfg.sender_password
    )
    mail.init_app(current_app)

    try:
        pdf_bytes = generate_pdf(user, month, year)
        msg = Message(
            subject=f"Timesheet - {user.full_name} - {user.national_id} – {month:02d}/{year}",
            sender=cfg.sender_email,
            recipients=[cfg.destination_email]
        )
        msg.attach(f"{user.full_name}_{month:02d}-{year}.pdf", "application/pdf", pdf_bytes)
        
        # Async sending passing the real app instance
        threading.Thread(
            target=send_async_email, 
            args=(current_app._get_current_object(), msg)
        ).start()
        
        flash("Report sent successfully.", "success")
    except Exception as e:
        flash(f"Error sending email: {e}", "error")

    return redirect(url_for("main.select_month"))

@main_bp.route('/process_pdf', methods=['GET'])
def process_pdf():
    """Intermediate router to decide whether to view or send the PDF."""
    action = request.args.get('action')
    month_param = request.args.get('month')
    
    if not month_param: return redirect(url_for('main.select_month'))
    
    # Date format normalization
    try:
        if '/' in month_param: month, year = month_param.split('/')
        elif '-' in month_param: month, year = month_param.split('-')
        else: raise ValueError
    except:
        flash("Incorrect format", "error")
        return redirect(url_for('main.select_month'))

    if action == 'view':
        return redirect(url_for('main.view_pdf', month=month, year=year))
    elif action == 'send':
        return redirect(url_for('main.send_pdf', month=month, year=year))
    
    return redirect(url_for('main.select_month'))

@main_bp.route('/view_pdf', methods=['GET'])
def view_pdf():
    """Preview of the PDF embedded in an iframe."""
    if "user_id" not in session: return redirect(url_for("auth.login"))
    
    month = request.args.get('month')
    year = request.args.get('year')
    
    # Timestamp to prevent browser caching
    t = int(datetime.now().timestamp())
    pdf_url = url_for('main.generate_pdf', month=month, year=year, t=t)
    
    return render_template('main/view_pdf.html', pdf_base=pdf_url)