# from flask import Flask
# from flask_sqlalchemy import SQLAlchemy
# from .config import Config
# import os

# # Create database instance
# db = SQLAlchemy()

# def create_app():
#     app = Flask(__name__, instance_relative_config=True)
    
#     # 1. Load configuration
#     app.config.from_object(Config)
    
#     # 2. Ensure the instance folder exists
#     try:
#         os.makedirs(app.instance_path)
#     except OSError:
#         pass # Already exists

#     # 3. Initialize database
#     db.init_app(app)

#     with app.app_context():
#         # 4. Import models (so SQLAlchemy knows about them)
#         from . import models
        
#         # 5. Create database tables
#         db.create_all() 

#         # 6. Import and register routes
#         from . import routes
        
#         return app



from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from .config import Config
import os

# Create database instance
db = SQLAlchemy()

bcrypt = Bcrypt()

def create_app():
    app = Flask(__name__, 
                instance_relative_config=True,
                static_folder='static',  # Tell Flask where static is
                template_folder='templates') # Tell Flask where templates is
    
    # 1. Load configuration
    app.config.from_object(Config)
    
    # 2. Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass # Already exists

    # 3. Initialize database
    db.init_app(app)

    bcrypt.init_app(app)

    # 4. Import and register the routes Blueprint
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    with app.app_context():
        # 5. Import models (so SQLAlchemy knows about them)
        from . import models
        
        # 6. Create database tables (if they don't exist)
        db.create_all() 
        
        return app