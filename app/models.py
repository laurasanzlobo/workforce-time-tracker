"""
File: app/models.py

Database models definition.

Author: Laura Sanz Lobo
"""

from app.extensions import db
from datetime import date, datetime
from sqlalchemy import event, extract
from sqlalchemy.engine import Engine
from sqlalchemy.types import Enum

"""***************************************************************************"""
"""  User Model """
class User(db.Model):
    __tablename__ = "user"
    __table_args__ = {'sqlite_autoincrement': True}  # prevents rowid reuse in SQLite
    id = db.Column(db.Integer, primary_key=True)
    records = db.relationship(
        "Record", backref="user",
        cascade="all, delete-orphan", passive_deletes=True
    )
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    full_name = db.Column(db.String(200), nullable=False)
    national_id = db.Column(db.String(20), unique=True, nullable=False)
    signature = db.Column(db.String(200), nullable=True)
    worker_type = db.Column(
        Enum("office", "site", "part_time", name="worker_type_enum"),
        nullable=False,
        default="office"
    )
    start_date = db.Column(db.Date, default=date.today)
    end_date = db.Column(db.Date, nullable=True)

"""***************************************************************************"""
"""  Record Model """
class Record(db.Model):
    __tablename__ = "record"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), index=True)
    date = db.Column(db.Date, nullable=False)
    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_record_user_date"),  # 1 record per day/user
    )
    clock_in = db.Column(db.Time, nullable=True)
    clock_out = db.Column(db.Time, nullable=True)
    clock_in_afternoon = db.Column(db.Time, nullable=True) # Only for office workers
    clock_out_afternoon = db.Column(db.Time, nullable=True)   # Only for office workers
    day_type = db.Column(db.Enum("normal", "vacation", "sick_leave", "other_reasons", name="day_type_enum"), 
                         default="normal", nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=True)  # Only for site workers
    site = db.relationship("Site", backref="records")

"""***************************************************************************"""
"""  Holiday Model  """
class Holiday(db.Model):
    __tablename__ = "holiday"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    description = db.Column(db.String(120), nullable=True)

"""***************************************************************************"""
"""  Site Model """
class Site(db.Model):
    __tablename__ = "site"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

"""***************************************************************************"""
"""  Office Hours Model """
class OfficeConfig(db.Model):
    __tablename__ = "office_config"
    id = db.Column(db.Integer, primary_key=True)

    # Winter Schedule
    morning_in_mon_wed_winter = db.Column(db.Time, nullable=True)
    morning_out_mon_wed_winter  = db.Column(db.Time, nullable=True)
    afternoon_in_mon_wed_winter  = db.Column(db.Time, nullable=True)
    afternoon_out_mon_wed_winter   = db.Column(db.Time, nullable=True)
    
    morning_in_tue_thu_winter = db.Column(db.Time, nullable=True)
    morning_out_tue_thu_winter  = db.Column(db.Time, nullable=True)
    
    in_friday_winter   = db.Column(db.Time, nullable=True)
    out_friday_winter    = db.Column(db.Time, nullable=True)

    # Summer Schedule
    summer_start = db.Column(db.Date, nullable=True)
    summer_end = db.Column(db.Date, nullable=True)
    morning_in_summer = db.Column(db.Time, nullable=True)
    morning_out_summer = db.Column(db.Time, nullable=True)
    in_friday_summer = db.Column(db.Time, nullable=True)
    out_friday_summer = db.Column(db.Time, nullable=True)

"""***************************************************************************"""
"""  Site Hours Model """
class SiteConfig(db.Model):
    __tablename__ = "site_config"
    id = db.Column(db.Integer, primary_key=True)

    # Winter Schedule
    in_winter = db.Column(db.Time, nullable=True)
    out_winter = db.Column(db.Time, nullable=True)
    in_friday_winter = db.Column(db.Time, nullable=True)
    out_friday_winter = db.Column(db.Time, nullable=True)

    # Summer Schedule - July
    july_start = db.Column(db.Date, nullable=True)
    july_end = db.Column(db.Date, nullable=True)
    in_july = db.Column(db.Time, nullable=True)
    out_july = db.Column(db.Time, nullable=True)
    in_friday_july = db.Column(db.Time, nullable=True)
    out_friday_july = db.Column(db.Time, nullable=True)

    # Summer Schedule - August
    august_start = db.Column(db.Date, nullable=True)
    august_end = db.Column(db.Date, nullable=True)
    in_august = db.Column(db.Time, nullable=True)
    out_august = db.Column(db.Time, nullable=True)
    in_friday_august = db.Column(db.Time, nullable=True)
    out_friday_august = db.Column(db.Time, nullable=True)
    
"""***************************************************************************"""
"""  Part-Time Hours Model """
class PartTimeConfig(db.Model):
    __tablename__ = "part_time_config"
    id = db.Column(db.Integer, primary_key=True)

    # Winter Schedule
    in_winter = db.Column(db.Time, nullable=True)
    out_winter  = db.Column(db.Time, nullable=True)
    in_friday_winter = db.Column(db.Time, nullable=True)
    out_friday_winter  = db.Column(db.Time, nullable=True)

    # Summer Schedule (shared with office)
    in_summer = db.Column(db.Time, nullable=True) 
    out_summer  = db.Column(db.Time, nullable=True)
    in_friday_summer = db.Column(db.Time, nullable=True)
    out_friday_summer  = db.Column(db.Time, nullable=True)


"""***************************************************************************"""
"""  Email Configuration Model """
class EmailConfig(db.Model):
    __tablename__ = "email_config"
    id = db.Column(db.Integer, primary_key=True)
    sender_email = db.Column(db.String(200), nullable=True)
    sender_password = db.Column(db.String(200), nullable=True)
    destination_email = db.Column(db.String(200), nullable=True)