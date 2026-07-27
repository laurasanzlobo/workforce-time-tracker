"""
File: app/routes/api.py

Endpoints that return JSON for the calendar (FullCalendar) and AJAX logic.

Author: Laura Sanz Lobo
"""

from flask import Blueprint, jsonify, session, request
from app.models import Record, Holiday, User, OfficeConfig
from app.utils import get_default_hours
from datetime import datetime

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Calendar color configuration
COLOR_BG = {
    "vacation":      "rgba(40,167,69,.8)",    # green
    "sick_leave":    "rgba(111,66,193,.8)",   # purple
    "other_reasons": "rgba(108,117,125,.8)",  # gray
    "holiday":       "rgba(220,53,69,.8)",    # red
    "normal":        "rgba(0,123,255,.7)",    # soft blue
}

COLOR_TXT = {
    "vacation":      "#28a745",
    "sick_leave":    "#6f42c1",
    "other_reasons": "#6c757d",
    "holiday":       "#dc3545",
}

@api_bp.route("/records")
def api_records():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    events = []
    colored_dates = set()
    records = Record.query.filter_by(user_id=session["user_id"]).all()

    for reg in records:
        iso_day = reg.date.isoformat()
        day_type = reg.day_type or "normal"

        # 1. Time events (blue blocks)
        if reg.clock_in and reg.clock_out:
             events.append({
                "id": f"morning-{reg.id}",
                "title": f"{reg.clock_in.strftime('%H:%M')} - {reg.clock_out.strftime('%H:%M')}",
                "start": iso_day,
                "color": "#007bff", # Blue
                "day_type": day_type
            })
        
        if reg.clock_in_afternoon and reg.clock_out_afternoon:
             events.append({
                "id": f"afternoon-{reg.id}",
                "title": f"{reg.clock_in_afternoon.strftime('%H:%M')} - {reg.clock_out_afternoon.strftime('%H:%M')}",
                "start": iso_day,
                "color": "#007bff",
                "day_type": day_type
            })

        # 2. Cell background
        if iso_day not in colored_dates:
            events.append({
                "id": f"bg-{day_type}-{reg.id}",
                "start": iso_day,
                "display": "background",
                "backgroundColor": COLOR_BG.get(day_type, COLOR_BG["normal"]),
                "borderColor": "transparent"
            })
            colored_dates.add(iso_day)

        # 3. Text labels (Vac, Sick...)
        if day_type in ["vacation", "sick_leave", "other_reasons"]:
            label = {"vacation": "Vac", "sick_leave": "Sick", "other_reasons": "Other"}[day_type]
            events.append({
                "id": f"lbl-{day_type}-{reg.id}",
                "title": label,
                "start": iso_day,
                "color": "transparent",
                "textColor": COLOR_TXT[day_type],
                "className": "fc-label-clickthru"
            })

    # 4. Global Holidays
    holidays = Holiday.query.all()
    for h in holidays:
        iso_day = h.date.isoformat()
        events.append({
            "id": f"bg-holiday-{h.id}",
            "start": iso_day,
            "display": "background",
            "backgroundColor": COLOR_BG["holiday"],
            "borderColor": "transparent"
        })
        events.append({
            "id": f"lbl-holiday-{h.id}",
            "title": "Hol",
            "start": iso_day,
            "color": "transparent",
            "textColor": COLOR_TXT["holiday"],
            "className": "fc-label-clickthru"
        })

    return jsonify(events)

@api_bp.route("/record/<date_str>")
def api_record_detail(date_str):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date"}), 400

    user = User.query.get(session["user_id"])
    is_holiday = Holiday.query.filter_by(date=date_obj).first()

    if is_holiday:
        return jsonify({
            "day_type": "holiday", "clock_in": "", "clock_out": "",
            "clock_in_afternoon": "", "clock_out_afternoon": "",
            "site_id": None, "has_afternoon": False
        })

    # Check if the worker has an afternoon shift (Office logic)
    has_afternoon = False
    if user.worker_type == "office":
        config = OfficeConfig.query.first()
        if config:
            in_summer = config.summer_start and config.summer_end and \
                        (config.summer_start <= date_obj <= config.summer_end)
            weekday = date_obj.weekday()
            if not in_summer and weekday in [0, 2]: # Monday/Wednesday
                has_afternoon = True

    record = Record.query.filter_by(user_id=user.id, date=date_obj).first()
    
    if record:
        def fmt(h): return h.strftime("%H:%M") if h else ""
        return jsonify({
            "day_type": record.day_type,
            "clock_in": fmt(record.clock_in),
            "clock_out": fmt(record.clock_out),
            "clock_in_afternoon": fmt(record.clock_in_afternoon),
            "clock_out_afternoon": fmt(record.clock_out_afternoon),
            "site_id": record.site_id,
            "has_afternoon": has_afternoon
        })
    
    return jsonify({"day_type": "normal", "has_afternoon": has_afternoon})

@api_bp.route('/default_hours')
def default_hours_route():
    date_str = request.args.get('date')
    worker_type = request.args.get('type')
    if not date_str or not worker_type: return jsonify({"error": "Missing data"}), 400
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError: return jsonify({"error": "Invalid date"}), 400

    res = get_default_hours(date_obj, worker_type, session.get("user_id"))
    if not res: return jsonify({"error": "No hours"}), 400

    def fmt(h): return h.strftime("%H:%M") if h else ""
    res["clock_in"] = fmt(res["clock_in"])
    res["clock_out"] = fmt(res["clock_out"])
    res["clock_in_afternoon"] = fmt(res["clock_in_afternoon"])
    res["clock_out_afternoon"] = fmt(res["clock_out_afternoon"])
    
    return jsonify(res)