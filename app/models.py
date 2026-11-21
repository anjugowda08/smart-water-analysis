from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Reading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    zone = db.Column(db.String(60), nullable=False, index=True)
    meter_id = db.Column(db.String(60), nullable=False)
    consumer_type = db.Column(db.String(40), nullable=False, default="Household")
    consumption_l = db.Column(db.Float, nullable=False)
    flow_rate = db.Column(db.Float, nullable=False)
    is_synthetic_leak = db.Column(db.Boolean, default=False)

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reading_id = db.Column(db.Integer, db.ForeignKey("reading.id"), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    zone = db.Column(db.String(60), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="Medium")
    message = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Open")
    reading = db.relationship("Reading", backref="alerts")
