"""
File: app/utils.py

Auxiliary functions for the application.

Author: Laura Sanz Lobo
"""

import os
import pytz
import random
import traceback
from datetime import datetime, timedelta, date, time
from flask import current_app, render_template
from werkzeug.utils import secure_filename
from weasyprint import HTML
from calendar import monthrange
from flask_mail import Message

from app.extensions import mail, db, bcrypt
from app.models import (
    User, Record, Holiday, Site, 
    OfficeConfig, SiteConfig, PartTimeConfig
)

TZ = pytz.timezone("Europe/Madrid")


def get_current_date():
    """
    Retrieves the current date and time localized to the application's default timezone.
    
    Returns:
        datetime: The current localized datetime object.
    """
    return datetime.now(TZ)


def allowed_file(filename):
    """
    Validates if an uploaded file has a permitted extension based on app configuration.
    
    Args:
        filename (str): The name of the uploaded file.
        
    Returns:
        bool: True if the file extension is allowed, False otherwise.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def create_base_admin():
    """
    Initializes a default administrator account if no admin exists in the database.
    This is triggered during the first deployment or after a database reset.
    """
    existing_admin = User.query.filter_by(username="admin").first()
    
    if not existing_admin:
        print(">> INITIALIZATION: Creating default admin user...")
        hashed_password = bcrypt.generate_password_hash("admin").decode("utf-8")
        
        new_admin = User(
            username="admin",
            password=hashed_password,
            full_name="Administrador",
            national_id="00000000X",
            worker_type="office",
            is_admin=True,
            start_date=get_current_date().date()
        )
        
        db.session.add(new_admin)
        db.session.commit()
        print(">> SUCCESS: 'admin' user created.")


def get_template_configuration(root_path):
    """
    Determines and manages which static assets (Favicon, Manifest, Mobile Icon) 
    to serve dynamically in the application templates.
    """
    import os
    config = {}

    # 1. FAVICON (Browser tab)
    if os.path.exists(os.path.join(root_path, "static", "icons", "real.ico")):
        config["favicon_file"] = "icons/real.ico"
    else:
        config["favicon_file"] = "icons/favicon.ico"

    # 2. MANIFEST (PWA Installation)
    if os.path.exists(os.path.join(root_path, "static", "manifest_real.json")):
        config["manifest_file"] = "manifest_real.json"
    else:
        config["manifest_file"] = "manifest.json"

    # 3. MOBILE ICON (iPhone/Android Icon)
    if os.path.exists(os.path.join(root_path, "static", "icons", "real_192x192.png")):
        config["mobile_icon_file"] = "icons/real_192x192.png"
    else:
        config["mobile_icon_file"] = "icons/icon_192.png" 

    return config


def adjust_clock_in(h: time) -> time:
    """
    Applies a weighted random logic to slightly vary the clock-in time, 
    simulating realistic human entry patterns.
    """
    if not h:
        return None
    
    options = [-5, -4, -3, -2, -1, 0, 1, 2, 3]
    weights = [5,   5,  10,  10,  20, 20, 20, 5, 5]

    delta = random.choices(options, weights=weights, k=1)[0]
    dt = datetime.combine(datetime.today(), h)
    dt += timedelta(minutes=delta)
    return dt.time()


def adjust_clock_out(h: time) -> time:
    """
    Applies a weighted random logic to slightly vary the clock-out time, 
    ensuring exit times look organic.
    """
    if not h:
        return None

    options = [0,   1,  2,  3, 4, 5]
    weights = [20, 20, 20, 20, 5, 5]

    delta = random.choices(options, weights=weights, k=1)[0]
    dt = datetime.combine(datetime.today(), h)
    dt += timedelta(minutes=delta)
    return dt.time()


def get_default_hours(date_obj, worker_type, user_id):
    """
    Calculates the theoretical work schedule for a specific employee on a given date.
    Considers the season (summer/winter), weekends, public holidays, and specific role configurations.
    """
    # 1. Check for holidays or weekends
    if date_obj.weekday() in [5, 6] or Holiday.query.filter_by(date=date_obj).first():
        return None

    # 2. Logic for OFFICE
    if worker_type == "office":
        config = OfficeConfig.query.first()
        if not config: return None

        in_summer = config.summer_start and config.summer_end and \
                    (config.summer_start <= date_obj <= config.summer_end)
        weekday = date_obj.weekday()
        
        morning_in, morning_out = None, None
        afternoon_in, afternoon_out = None, None
        has_afternoon = False

        if in_summer:
            if weekday == 4: # Friday
                morning_in = config.in_friday_summer
                morning_out  = config.out_friday_summer
            else:
                morning_in = config.morning_in_summer
                morning_out  = config.morning_out_summer
        else:
            if weekday in [0, 2]: # Monday/Wednesday
                morning_in = config.morning_in_mon_wed_winter
                morning_out  = config.morning_out_mon_wed_winter
                afternoon_in  = config.afternoon_in_mon_wed_winter
                afternoon_out   = config.afternoon_out_mon_wed_winter
                has_afternoon = True
            elif weekday in [1, 3]: # Tuesday/Thursday
                morning_in = config.morning_in_tue_thu_winter
                morning_out  = config.morning_out_tue_thu_winter
            elif weekday == 4: # Friday
                morning_in = config.in_friday_winter
                morning_out  = config.out_friday_winter

        return {
            "clock_in": morning_in, "clock_out": morning_out,
            "clock_in_afternoon": afternoon_in, "clock_out_afternoon": afternoon_out,
            "day_type": "normal", "site_id": None, "has_afternoon": has_afternoon
        }

    # 3. Logic for SITE
    elif worker_type == "site":
        config = SiteConfig.query.first()
        if not config: return None

        is_friday = date_obj.weekday() == 4
        in_july = config.july_start and config.july_end and \
                   (config.july_start <= date_obj <= config.july_end)
        in_august = config.august_start and config.august_end and \
                    (config.august_start <= date_obj <= config.august_end)

        clock_in, clock_out = None, None
        
        if is_friday:
            if in_july:
                clock_in, clock_out = config.in_friday_july, config.out_friday_july
            elif in_august:
                clock_in, clock_out = config.in_friday_august, config.out_friday_august
            else:
                clock_in, clock_out = config.in_friday_winter, config.out_friday_winter
        else:
            if in_july:
                clock_in, clock_out = config.in_july, config.out_july
            elif in_august:
                clock_in, clock_out = config.in_august, config.out_august
            else:
                clock_in, clock_out = config.in_winter, config.out_winter

        site_id = None
        previous = Record.query.filter(
            Record.user_id == user_id,
            Record.date < date_obj,
            Record.site_id.isnot(None)
        ).order_by(Record.date.desc()).first()

        if previous and previous.site_id:
            site_id = previous.site_id
        else:
            first_site = Site.query.order_by(Site.id).first()
            if first_site: site_id = first_site.id

        return {
            "clock_in": clock_in, "clock_out": clock_out,
            "clock_in_afternoon": None, "clock_out_afternoon": None,
            "day_type": "normal", "site_id": site_id, "has_afternoon": False
        }

    # 4. Logic for PART-TIME
    elif worker_type == "part_time":
        config = PartTimeConfig.query.first()
        if not config: return None

        is_friday = date_obj.weekday() == 4
        office_conf = OfficeConfig.query.first()
        in_summer = office_conf and office_conf.summer_start and office_conf.summer_end and \
                    (office_conf.summer_start <= date_obj <= office_conf.summer_end)

        if is_friday:
            clock_in = config.in_friday_summer if in_summer else config.in_friday_winter
            clock_out  = config.out_friday_summer  if in_summer else config.out_friday_winter
        else:
            clock_in = config.in_summer if in_summer else config.in_winter
            clock_out  = config.out_summer  if in_summer else config.out_winter

        return {
            "clock_in": clock_in, "clock_out": clock_out,
            "clock_in_afternoon": None, "clock_out_afternoon": None,
            "day_type": "normal", "site_id": None, "has_afternoon": False
        }

    return None


def generate_pdf(user, month, year):
    """
    Generates a formal monthly attendance PDF report for a given user.
    It calculates total hours worked, handles missing days, and incorporates user signatures.
    """
    start_date = date(year, month, 1)
    _, last_day = monthrange(year, month)
    end_date = date(year, month, last_day)

    records = Record.query.filter(
        Record.user_id == user.id,
        Record.date >= start_date,
        Record.date <= end_date
    ).order_by(Record.date).all()
    
    record_dates = set(r.date for r in records)
    holidays = Holiday.query.filter(Holiday.date.between(start_date, end_date)).all()
    
    for h in holidays:
        if h.date not in record_dates:
            records.append(Record(date=h.date, day_type="holiday", user_id=user.id))
    
    records.sort(key=lambda r: r.date)

    total_hours, total_minutes = 0, 0
    for reg in records:
        if reg.day_type not in ["vacation", "sick_leave", "other_reasons", "holiday"]:
            if reg.clock_in and reg.clock_out:
                d = datetime.combine(date.min, reg.clock_out) - datetime.combine(date.min, reg.clock_in)
                total_hours += d.seconds // 3600
                total_minutes += (d.seconds // 60) % 60
            if reg.clock_in_afternoon and reg.clock_out_afternoon:
                d = datetime.combine(date.min, reg.clock_out_afternoon) - datetime.combine(date.min, reg.clock_in_afternoon)
                total_hours += d.seconds // 3600
                total_minutes += (d.seconds // 60) % 60
    
    total_hours += total_minutes // 60
    total_minutes %= 60

    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo_real.jpg')
    if not os.path.exists(logo_path):
        logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo_placeholder.jpg')

    css_path = os.path.join(current_app.root_path, 'static', 'css', 'main/pdf_template.css')
    signature_url = f"file://{os.path.abspath(user.signature)}" if user.signature else None
    
    rendered_html = render_template(
        "main/pdf_template.html",
        records=records,
        month=f"{month:02d}/{year}",
        logo_path=logo_path,
        user=user,
        user_name=user.full_name,
        user_dni=user.national_id,
        is_site=(user.worker_type == 'site'),
        is_part_time=(user.worker_type == 'part_time'),
        signature_url=signature_url,
        total_hours=total_hours,
        total_minutes=total_minutes
    )
    
    return HTML(string=rendered_html).write_pdf(stylesheets=[css_path])


def send_async_email(app, msg):
    """
    Handles the asynchronous dispatch of emails using Flask-Mail.
    Configures context dynamically to avoid thread issues.
    """
    with app.app_context():
        try:
            app.extensions['mail'].username = app.config.get('MAIL_USERNAME')
            app.extensions['mail'].password = app.config.get('MAIL_PASSWORD')
            
            mail.send(msg)
            app.logger.info(f"Correo enviado con éxito a {msg.recipients}")
            
        except Exception as e:
            app.logger.error(f"Error crítico al enviar correo: {str(e)}")
            app.logger.error(traceback.format_exc())


def sync_record_range(user_id, start_date, end_date):
    """
    Fills and deeply repairs records for a user strictly within the given date range.
    Optimized for bulk checking using a dictionary map.
    """
    user = User.query.get(user_id)
    if not user:
        return

    worker_type = user.worker_type or "unknown"
    now = datetime.now()
    today = now.date()

    if user.end_date and user.end_date < end_date:
        end_date = user.end_date

    if start_date > end_date:
        return

    # Efficient bulk load O(1)
    existing_records = Record.query.filter(
        Record.user_id == user.id,
        Record.date >= start_date,
        Record.date <= end_date
    ).all()
    records_dict = {r.date: r for r in existing_records}

    holidays = Holiday.query.filter(
        Holiday.date >= start_date,
        Holiday.date <= end_date
    ).all()
    holiday_dates = {h.date for h in holidays}

    made_changes = False
    cursor_date = start_date

    while cursor_date <= end_date:
        if cursor_date.weekday() >= 5 or cursor_date in holiday_dates:
            cursor_date += timedelta(days=1)
            continue

        hours = get_default_hours(cursor_date, worker_type, user.id)
        if not hours:
            cursor_date += timedelta(days=1)
            continue
        
        clock_in = adjust_clock_in(hours.get("clock_in"))
        clock_out = adjust_clock_out(hours.get("clock_out"))
        clock_in_afternoon = adjust_clock_in(hours.get("clock_in_afternoon"))
        clock_out_afternoon = adjust_clock_out(hours.get("clock_out_afternoon"))
        site_id = hours.get("site_id")

        record = records_dict.get(cursor_date)

        # DEEP REPAIR LOGIC
        if cursor_date < today:
            if not record:
                new_record = Record(
                    user_id=user.id, date=cursor_date, day_type="normal",
                    clock_in=clock_in, clock_out=clock_out,
                    clock_in_afternoon=clock_in_afternoon, clock_out_afternoon=clock_out_afternoon,
                    site_id=site_id
                )
                db.session.add(new_record)
                made_changes = True
            elif not record.day_type or record.day_type == "normal":
                if clock_in and record.clock_in is None: record.clock_in = clock_in; made_changes = True
                if clock_out and record.clock_out is None: record.clock_out = clock_out; made_changes = True
                if clock_in_afternoon and clock_out_afternoon:
                    if record.clock_in_afternoon is None: record.clock_in_afternoon = clock_in_afternoon; made_changes = True
                    if record.clock_out_afternoon is None: record.clock_out_afternoon = clock_out_afternoon; made_changes = True

        elif cursor_date == today:
            if not record:
                record = Record(user_id=user.id, date=cursor_date, day_type="normal", site_id=site_id)
                db.session.add(record)

            if clock_in and now.time() >= clock_in and record.clock_in is None:
                record.clock_in = clock_in; made_changes = True
            if clock_out and now.time() >= clock_out and record.clock_out is None:
                record.clock_out = clock_out; made_changes = True
            if clock_in_afternoon and now.time() >= clock_in_afternoon and record.clock_in_afternoon is None:
                record.clock_in_afternoon = clock_in_afternoon; made_changes = True
            if clock_out_afternoon and now.time() >= clock_out_afternoon and record.clock_out_afternoon is None:
                record.clock_out_afternoon = clock_out_afternoon; made_changes = True

        cursor_date += timedelta(days=1)

    if made_changes:
        db.session.commit()