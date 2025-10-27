from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from pdf2image import convert_from_path
import os

# ---------------------------
# App Configuration
# ---------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = '4fb6a3d56aacbdc28fa545785879d90a'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
db = SQLAlchemy(app)

# Create upload folder if missing
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# ---------------------------
# Database Models
# ---------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    expenses = db.relationship('Expense', backref='user', lazy=True)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    text = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(255), nullable=True)  # store receipt file path
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


# ---------------------------
# Routes
# ---------------------------

@app.route('/')
def index():
    return render_template('index.html')


# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
    return render_template('login.html')


# ---------- REGISTER ----------
@app.route('/register', methods=['GET', 'POST'])
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
            new_user = User(first_name=first_name, last_name=last_name,
                            email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('signup.html')


# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# ---------- HOME ----------
@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    today = datetime.utcnow().strftime('%Y-%m-%d')
    return render_template('home.html', user=user, today=today)


# ---------- VIEW EXPENSES ----------
@app.route('/expenses', methods=['GET'])
def view_expenses():
    if 'user_id' not in session:
        return redirect(url_for('login'))

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


# ---------- ADD EXPENSE ----------
@app.route('/add_expense', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))

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
        flash('Expense added successfully!', 'success')
    except Exception as e:
        flash(f'Error while adding expense: {e}', 'error')

    return redirect(url_for('view_expenses'))


# ---------- EDIT EXPENSE ----------
@app.route('/edit_expense/<int:expense_id>', methods=['POST'])
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    try:
        expense.name = request.form.get('name')
        expense.amount = float(request.form.get('amount', 0))
        expense.category = request.form.get('category')
        db.session.commit()
        return ('', 204)  # success but no HTML reload
    except Exception as e:
        print("Edit error:", e)
        return ('Error while updating expense', 500)


# ---------- DELETE EXPENSE ----------
@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted successfully!', 'success')
    return redirect(url_for('view_expenses'))


# ---------- UPLOAD RECEIPT (OCR + SAVE) ----------
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload_receipt', methods=['POST'])
def upload_receipt():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if 'receipt' not in request.files:
        flash('No file uploaded.', 'error')
        return redirect(url_for('home'))

    file = request.files['receipt']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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
            flash(f"OCR failed: {e}", 'error')
            return redirect(url_for('home'))

        name = "Scanned Receipt"
        amount = 0.0
        category = "Uncategorized"

        for line in text_data.splitlines():
            line = line.strip().lower()
            if "total" in line:
                for word in line.split():
                    if word.replace('.', '', 1).isdigit():
                        amount = float(word)
                        break

        new_expense = Expense(
            name=name,
            amount=amount,
            category=category,
            date=datetime.utcnow().date(),
            text=text_data,
            file_path=file_path,
            user_id=session['user_id']
        )
        db.session.add(new_expense)
        db.session.commit()

        flash('Receipt uploaded and expense added successfully!', 'success')
        return redirect(url_for('view_expenses'))

    flash('Invalid file format. Please upload an image or PDF.', 'error')
    return redirect(url_for('home'))

#-----------ANALYTICS PAGE----------
@app.route('/dashboard')
def dashboard():
    # Fetch whatever you want to show on home/dashboard
    return render_template('home.html')

@app.route('/analytics')
def analytics():
    # Example: show analytics or summary
    return render_template('analytics.html')



# ---------- REPORT ----------
@app.route('/report')
def report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

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
@app.route('/features')
def features():
    return render_template('features.html')


# ---------- SIGNUP PAGE ----------
@app.route('/signup')
def signup_page():
    return render_template('signup.html')


# --------------contact us----------
@app.route('/init_db')
def init_db():
    import sqlite3
    conn = sqlite3.connect('expenses.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            newsletter INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    return "✅ contact_messages table created successfully!"

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')
    email = request.form.get('email')
    subject = request.form.get('subject')
    message = request.form.get('message')
    newsletter = 1 if request.form.get('newsletter') else 0

    import sqlite3
    conn = sqlite3.connect('expenses.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO contact_messages (name, email, subject, message, newsletter)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, email, subject, message, newsletter))
    conn.commit()
    conn.close()

    flash('✅ Thank you for contacting us! We’ll get back to you soon.', 'success')
    return redirect(url_for('index'))



# ---------------------------
# Run Server
# ---------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
