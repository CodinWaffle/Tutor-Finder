from flask import Flask 
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_migrate import Migrate
import os 

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

db = SQLAlchemy()
jwt = JWTManager()
mail = Mail()
migrate = Migrate()

def create_app():
  app = Flask(__name__)

  app.config['SECRET_KEY'] = 'key-goes-here'
  app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost:3306/tutor_finder'
  app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
  app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
  app.config['MAIL_PORT'] = 587
  app.config['MAIL_USE_TLS'] = True
  app.config['MAIL_USERNAME'] = 'dnxncpcx@gmail.com'
  app.config['MAIL_PASSWORD'] = "cftc pflo tzdg kvmh"
  app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
  app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

  # Create uploads directory if it doesn't exist
  if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

  db.init_app(app)
  migrate.init_app(app, db)

  login_manager = LoginManager()
  login_manager.login_view = 'auth.login'
  login_manager.init_app(app)

  jwt.init_app(app)
  mail.init_app(app)

  from .models import User, OAuth

  @login_manager.user_loader
  def load_user(user_id):
    return User.query.get(int(user_id))

  #blueprints auth routes
  from .auth import auth as auth_blueprint
  app.register_blueprint(auth_blueprint)

  from .social_login import github_blueprint
  app.register_blueprint(github_blueprint, url_prefix = "/login")

  from .social_login import google_blueprint
  app.register_blueprint(google_blueprint, url_prefix = "/login")

  from .social_login import facebook_blueprint
  app.register_blueprint(facebook_blueprint, url_prefix = "/login")

  #non-auth parts
  from .main import main as main_blueprint
  app.register_blueprint(main_blueprint)

  from .admin import admin as admin_blueprint
  app.register_blueprint(admin_blueprint)

  return app