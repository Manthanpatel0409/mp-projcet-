import os
import json
import re
from datetime import datetime
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    session, flash, jsonify, current_app
)
from sqlalchemy import func
from werkzeug.utils import secure_filename
from . import db, bcrypt
from . import db
from .models import User, Expense, ContactMessage

# 1. Create a Blueprint
main = Blueprint('main', __name__)

# 2. Set Tesseract path
# @main.before_app_first_request
# def configure_tesseract():
#     pytesseract.pytesseract.tesseract_cmd = current_app.config['TESSERACT_CMD']


# 3. All your routes, changed to use '@main.route'
@main.route('/')
def index():
    return render_template('index.html')


# ---------- LOGIN ----------
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('username') # This is the email field
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('main.home'))
        else:
            flash('Invalid email or password.', 'error')
    return render_template('login.html')


# ---------- REGISTER ----------
@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists. Please choose another.', 'error')
        else:
            # Hash the password
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            
            new_user = User(first_name=first_name, last_name=last_name,
                            email=email, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('main.login'))
    return render_template('signup.html')

# ---------- AJAX EMAIL CHECKER ----------
@main.route('/check_email', methods=['POST'])
def check_email():
    email = request.form.get('email')
    if not email:
        return jsonify(exists=False, message="Email is required."), 400
        
    existing_user = User.query.filter_by(email=email).first()
    
    if existing_user:
        return jsonify(exists=True)
    else:
        return jsonify(exists=False)


# ---------- LOGOUT ----------
@main.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.login'))


# ---------- HOME ----------
@main.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user = User.query.get(session['user_id'])
    user_id = session['user_id']
    
    user_expenses = Expense.query.filter_by(user_id=user_id)
    total_spent = db.session.query(func.sum(Expense.amount)).filter_by(user_id=user_id).scalar() or 0
    
    this_month = datetime.utcnow().month
    this_year = datetime.utcnow().year
    this_month_spent = db.session.query(func.sum(Expense.amount)).filter_by(user_id=user_id).filter(
        func.extract('month', Expense.date) == this_month,
        func.extract('year', Expense.date) == this_year
    ).scalar() or 0

    category_count = user_expenses.with_entities(Expense.category).distinct().count()
    receipt_count = user_expenses.count()
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
    return render_template('home.html', 
                           user=user, 
                           today=today,
                           total_spent=total_spent,
                           this_month_spent=this_month_spent,
                           category_count=category_count,
                           receipt_count=receipt_count)

# ---------- AJAX STATS FETCHER ----------
@main.route('/get_dashboard_stats')
def get_dashboard_stats():
    if 'user_id' not in session:
        return jsonify(error="Not logged in"), 401

    user_id = session['user_id']
    user_expenses = Expense.query.filter_by(user_id=user_id)

    total_spent = db.session.query(func.sum(Expense.amount)).filter_by(user_id=user_id).scalar() or 0
    
    this_month = datetime.utcnow().month
    this_year = datetime.utcnow().year
    this_month_spent = db.session.query(func.sum(Expense.amount)).filter_by(user_id=user_id).filter(
        func.extract('month', Expense.date) == this_month,
        func.extract('year', Expense.date) == this_year
    ).scalar() or 0

    category_count = user_expenses.with_entities(Expense.category).distinct().count()
    receipt_count = user_expenses.count()

    return jsonify(
        total_spent=total_spent,
        this_month_spent=this_month_spent,
        category_count=category_count,
        receipt_count=receipt_count
    )

# ---------- VIEW EXPENSES ----------
@main.route('/expenses', methods=['GET'])
def view_expenses():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    query = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc())

    search_name = request.args.get('name')
    search_date = request.args.get('date')

    if search_name:
        query = query.filter(Expense.name.like(f'%{search_name}%'))
    if search_date:
        query = query.filter(Expense.date == datetime.strptime(search_date, '%Y-%m-%d').date())

    expenses = query.all()
    return render_template('expenses.html', expenses=expenses,
                           search_name=search_name, search_date=search_date)


# ---------- ADD EXPENSE (AJAX) ----------
@main.route('/add_expense', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return jsonify(success=False, message="Not logged in"), 401

    try:
        name = request.form['name']
        amount = float(request.form['amount'])
        category = request.form['category']
        date = request.form.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
        text = request.form.get('text')

        new_expense = Expense(
            name=name,
            amount=amount,
            category=category,
            date=datetime.strptime(date, '%Y-%m-%d').date(),
            text=text,
            user_id=session['user_id']
        )
        db.session.add(new_expense)
        db.session.commit()
        return jsonify(success=True, message="Expense added successfully!")
    except Exception as e:
        db.session.rollback() # Important: undo changes if an error occurs
        return jsonify(success=False, message=str(e)), 500


# ---------- EDIT EXPENSE ----------
@main.route('/edit_expense/<int:expense_id>', methods=['POST'])
def edit_expense(expense_id):
    if 'user_id' not in session:
        return jsonify(success=False, message="Not logged in"), 401
    
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != session['user_id']:
        return jsonify(success=False, message="Unauthorized"), 403

    try:
        expense.name = request.form.get('name')
        expense.amount = float(request.form.get('amount', 0))
        expense.category = request.form.get('category')
        db.session.commit()
        return ('', 204)  # success but no HTML reload
    except Exception as e:
        db.session.rollback()
        return ('Error while updating expense', 500)


# # ---------- DELETE EXPENSE ----------
# @main.route('/delete_expense/<int:expense_id>', methods=['POST'])
# def delete_expense(expense_id):
#     if 'user_id' not in session:
#         return redirect(url_for('main.login'))

#     expense = Expense.query.get_or_404(expense_id)
#     if expense.user_id != session['user_id']:
#         flash('You are not authorized to delete this expense.', 'error')
#         return redirect(url_for('main.view_expenses'))

#     db.session.delete(expense)
#     db.session.commit()
#     flash('Expense deleted successfully!', 'success')
#     return redirect(url_for('main.view_expenses'))



# ---------- DELETE EXPENSE ----------
@main.route('/delete_expense/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    if 'user_id' not in session:
        return jsonify(success=False, message="Not logged in"), 401

    expense = Expense.query.get_or_404(expense_id)
    
    if expense.user_id != session['user_id']:
        return jsonify(success=False, message="Unauthorized"), 403

    try:
        db.session.delete(expense)
        db.session.commit()
        # This is the new reply that JavaScript is expecting
        return jsonify(success=True, message="Expense deleted successfully!")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


# # ---------- UPLOAD RECEIPT (OCR + SAVE) ----------
# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# @main.route('/upload_receipt', methods=['POST'])
# def upload_receipt():
#     pytesseract.pytesseract.tesseract_cmd = current_app.config['TESSERACT_CMD']
#     if 'user_id' not in session:
#         return redirect(url_for('main.login'))

#     if 'receipt' not in request.files:
#         flash('No file uploaded.', 'error')
#         return redirect(url_for('main.home'))

#     file = request.files['receipt']
#     if file and allowed_file(file.filename):
#         filename = secure_filename(file.filename)
#         file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
#         file.save(file_path)

#         text_data = ""
#         try:
#             if filename.lower().endswith('.pdf'):
#                 pages = convert_from_path(file_path, 300)
#                 for page in pages:
#                     text_data += pytesseract.image_to_string(page)
#             else:
#                 img = Image.open(file_path)
#                 text_data = pytesseract.image_to_string(img)
#         except Exception as e:
#             flash(f"OCR failed: {e}", 'error')
#             return redirect(url_for('main.home'))

#         name = "Scanned Receipt"
#         amount = 0.0
#         category = "Uncategorized"

#         for line in text_data.splitlines():
#             line = line.strip().lower()
#             if "total" in line:
#                 for word in line.split():
#                     if word.replace('.', '', 1).isdigit():
#                         amount = float(word)
#                         break

#         new_expense = Expense(
#             name=name,
#             amount=amount,
#             category=category,
#             date=datetime.utcnow().date(),
#             text=text_data,
#             file_path=file_path,
#             user_id=session['user_id']
#         )
#         db.session.add(new_expense)
#         db.session.commit()

#         flash('Receipt uploaded and expense added successfully!', 'success')
#         return redirect(url_for('main.view_expenses'))

#     flash('Invalid file format. Please upload an image or PDF.', 'error')
#     return redirect(url_for('main.home'))


# ---------- UPLOAD RECEIPT (AJAX OCR) ----------
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# This is a simple regex to find dollar/rupee amounts
# It looks for patterns like: 123.45, 123,45, 123
MONEY_REGEX = r'[\$₹€]?\s*(\d+([.,]\d{2})?)'

@main.route('/upload_receipt', methods=['POST'])
def upload_receipt():
    pytesseract.pytesseract.tesseract_cmd = current_app.config['TESSERACT_CMD']

    if 'user_id' not in session:
        return jsonify(success=False, message="Not logged in"), 401
    
    if 'receipt' not in request.files:
        return jsonify(success=False, message="No file uploaded"), 400

    file = request.files['receipt']
    if not (file and allowed_file(file.filename)):
        return jsonify(success=False, message="Invalid file type"), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    text_data = ""
    try:
        if filename.lower().endswith('.pdf'):
            pages = convert_from_path(file_path, 300)
            for page in pages:
                text_data += pytesseract.image_to_string(page)
        else:
            img = Image.open(file_path)
            text_data = pytesseract.image_to_string(img)
    except Exception as e:
        return jsonify(success=False, message=f"OCR failed: {e}"), 500

    # --- NEW OCR Guessing Logic ---
    lines = text_data.splitlines()
    
    # Guess 1: The Expense Name (default to first non-empty line)
    expense_name = "Scanned Receipt"
    for line in lines:
        if line.strip():
            expense_name = line.strip()
            break
            
    # Guess 2: The Amount
    amount = 0.0
    for line in reversed(lines): # Check from the bottom up
        line_lower = line.lower()
        if 'total' in line_lower or 'amount' in line_lower:
            matches = re.findall(MONEY_REGEX, line)
            if matches:
                # Find the largest number on that line, it's probably the total
                possible_amounts = [float(m[0].replace(',', '.')) for m in matches]
                amount = max(possible_amounts)
                break
    
    # If no "total" line found, just find the largest number on the receipt
    if amount == 0.0:
        all_matches = re.findall(MONEY_REGEX, text_data)
        if all_matches:
            all_amounts = [float(m[0].replace(',', '.')) for m in all_matches]
            amount = max(all_amounts)

    # We are done! Return the guesses as JSON
    return jsonify(
        success=True,
        expense_name=expense_name,
        amount=amount,
        raw_text=text_data
    )


#-----------ANALYTICS PAGE----------
@main.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    user_expenses = Expense.query.filter_by(user_id=user_id)
    total_spent = db.session.query(func.sum(Expense.amount)).filter_by(user_id=user_id).scalar() or 0
    total_expenses = user_expenses.count()
    
    this_month = datetime.utcnow().month
    this_year = datetime.utcnow().year
    monthly_count = user_expenses.filter(
        func.extract('month', Expense.date) == this_month,
        func.extract('year', Expense.date) == this_year
    ).count()

    category_count = user_expenses.with_entities(Expense.category).distinct().count()
    top_expenses = user_expenses.order_by(Expense.amount.desc()).limit(5).all()

    monthly_data_query = db.session.query(
        func.strftime('%Y-%m', Expense.date).label('month'),
        func.sum(Expense.amount).label('total')
    ).filter_by(user_id=user_id).group_by('month').order_by('month').all()
    monthly_labels = [row.month for row in monthly_data_query]
    monthly_values = [row.total for row in monthly_data_query]

    category_data_query = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total')
    ).filter_by(user_id=user_id).group_by(Expense.category).all()
    category_labels = [row.category if row.category else 'Uncategorized' for row in category_data_query]
    category_values = [row.total for row in category_data_query]

    return render_template('analytics.html',
                           total_spent=total_spent,
                           total_expenses=total_expenses,
                           monthly_count=monthly_count,
                           category_count=category_count,
                           top_expenses=top_expenses,
                           monthly_labels=json.dumps(monthly_labels),
                           monthly_values=json.dumps(monthly_values),
                           category_labels=json.dumps(category_labels),
                           category_values=json.dumps(category_values)
                           )


# ---------- REPORT ----------
@main.route('/report')
def report():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    expenses = Expense.query.filter_by(user_id=user_id).all()

    total_spent = sum(exp.amount for exp in expenses)
    total_expenses = len(expenses)
    monthly_count = len([exp for exp in expenses if exp.date.month == datetime.now().month])
    category_count = len(set(exp.category for exp in expenses if exp.category))

    monthly_data = {}
    for exp in expenses:
        month = exp.date.strftime('%Y-%m')
        monthly_data[month] = monthly_data.get(month, 0) + exp.amount

    category_data = {}
    for exp in expenses:
        if exp.category:
            category_data[exp.category] = category_data.get(exp.category, 0) + exp.amount

    top_expenses = sorted([(exp.name, exp.amount) for exp in expenses],
                          key=lambda x: x[1], reverse=True)[:5]

    return render_template('report.html',
                           total_spent=total_spent,
                           total_expenses=total_expenses,
                           monthly_count=monthly_count,
                           category_count=category_count,
                           monthly_labels=list(monthly_data.keys()),
                           monthly_values=list(monthly_data.values()),
                           category_labels=list(category_data.keys()),
                           category_values=list(category_data.values()),
                           top_expenses=top_expenses)


# ---------- FEATURES ----------
@main.route('/features')
def features():
    return render_template('features.html')


# ---------- SIGNUP PAGE ----------
@main.route('/signup')
def signup_page():
    return render_template('signup.html')


# --------------CONTACT US (NOW USES SQLALCHEMY)----------
@main.route('/contact', methods=['POST'])
def contact():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        newsletter = True if request.form.get('newsletter') else False

        new_message = ContactMessage(
            name=name,
            email=email,
            subject=subject,
            message=message,
            newsletter=newsletter
        )
        db.session.add(new_message)
        db.session.commit()
        
        flash('✅ Thank you for contacting us! We’ll get back to you soon.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error submitting form: {e}', 'error')
        
    return redirect(url_for('main.index'))



# ---------- PROFILE PAGE ----------
@main.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_details':
            # Handle updating name
            user.first_name = request.form.get('first_name')
            user.last_name = request.form.get('last_name')
            db.session.commit()
            flash('Your details have been updated!', 'success')
            return redirect(url_for('main.profile'))

        elif action == 'change_password':
            # Handle changing password
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not bcrypt.check_password_hash(user.password, current_password):
                flash('Your current password was incorrect. Please try again.', 'error')
                return redirect(url_for('main.profile'))
            
            if new_password != confirm_password:
                flash('Your new passwords do not match.', 'error')
                return redirect(url_for('main.profile'))
            
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            user.password = hashed_password
            db.session.commit()
            flash('Your password has been changed successfully!', 'success')
            return redirect(url_for('main.profile'))

        elif action == 'change_photo':
            # Handle profile photo upload
            if 'profile_pic' not in request.files:
                flash('No file part', 'error')
                return redirect(url_for('main.profile'))
            
            file = request.files['profile_pic']
            if file.filename == '':
                flash('No selected file', 'error')
                return redirect(url_for('main.profile'))
            
            if file and allowed_file(file.filename):
                # Create a secure, unique filename: user_1.png, user_2.jpg
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"user_{user.id}.{ext}"
                
                # Use the NEW profile pic folder
                file_path = os.path.join(current_app.config['PROFILE_PIC_FOLDER'], filename)
                
                # Save the new file
                file.save(file_path)
                
                # Update the user's profile image in the database
                user.profile_image = filename
                db.session.commit()
                
                flash('Profile picture updated!', 'success')
                return redirect(url_for('main.profile'))
            else:
                flash('Invalid file type. Please upload an image.', 'error')
                return redirect(url_for('main.profile'))

    # For a GET request, just show the page
    return render_template('profile.html', user=user)

