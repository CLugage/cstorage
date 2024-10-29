from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    storage_plan_id = db.Column(db.Integer, db.ForeignKey('storage_plan.id'), nullable=False)
    storage_limit = db.Column(db.Float, default=0.0) 

    storage_plan = db.relationship('StoragePlan', backref='users')

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

class StoragePlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    storage_limit = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<StoragePlan {self.name}>'


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    file_name = db.Column(db.String(150), nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    user = db.relationship('User', backref='activities')

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(150), nullable=False)
    size = db.Column(db.Integer, nullable=False)  # Store the file size in bytes
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='files')



