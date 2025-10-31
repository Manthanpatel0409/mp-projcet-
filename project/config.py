import os

# Get the absolute path of the directory where this file is
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or '4fb6a3d56aacbdc28fa545785879d90a' # Use an env variable in production
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, '..', 'instance', 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    
    # This is for RECEIPTS (unchanged)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', 'uploads') 
    
    # ADD THIS: This is for PROFILE PICS
    PROFILE_PIC_FOLDER = os.path.join(BASE_DIR, 'static', 'profile_pics')

    # Tesseract config
    TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"