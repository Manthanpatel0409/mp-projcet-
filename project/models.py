from . import db  # Imports the 'db' object from __init__.py
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    profile_image = db.Column(db.String(100), nullable=False, default='default.png')
    
    # Relationship: Connects User to their expenses
    expenses = db.relationship('Expense', backref='user', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    text = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(255), nullable=True)  # store receipt file path
    
    # Foreign Key: Links this expense to a user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# NEW: A proper model for your contact form
class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    newsletter = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)