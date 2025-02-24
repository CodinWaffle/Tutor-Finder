import os
from . import db
from flask_login import UserMixin
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
import jwt
from time import time
from datetime import datetime

class User(UserMixin, db.Model):
  id = db.Column(db.Integer, primary_key=True)
  email = db.Column(db.String(100), unique=True)
  password = db.Column(db.String(255))
  username = db.Column(db.String(150))
  
  # Additional fields for user profile
  is_tutor = db.Column(db.Boolean, default=False)
  phone = db.Column(db.String(20))
  address = db.Column(db.String(200))
  bio = db.Column(db.Text)
  profile_pic = db.Column(db.String(200))
  is_verified = db.Column(db.Boolean, default=False)
  created_at = db.Column(db.DateTime, default=datetime.utcnow)
  
  # Tutor specific fields
  subjects = db.Column(db.String(500))  # Comma separated list of subjects
  hourly_rate = db.Column(db.Float)
  availability = db.Column(db.String(500))  # JSON string of availability
  
  # Relationships
  tutees = db.relationship('TutorStudent', foreign_keys='TutorStudent.tutor_id', backref='tutor', lazy=True)
  tutors = db.relationship('TutorStudent', foreign_keys='TutorStudent.student_id', backref='student', lazy=True)
  ratings_received = db.relationship('Rating', foreign_keys='Rating.tutor_id', backref='tutor', lazy=True)
  ratings_given = db.relationship('Rating', foreign_keys='Rating.student_id', backref='student', lazy=True)

  # New fields for admin and tutor approval status
  tutor_status = db.Column(db.String(20), default='pending')  # pending, approved, rejected

  def __repr__(self):
      return 'User {}'.format(self.username)

  def get_reset_token(self, expires=500):
    return jwt.encode(
      {'reset_password': self.email, 'exp': time() + expires},
      os.getenv('SECRET_KEY', 'key-goes-here'),
      algorithm='HS256'
    )

  @staticmethod
  def verify_reset_token(token):
    try:
      email = jwt.decode(
        token,
        os.getenv('SECRET_KEY', 'key-goes-here'),
        algorithms=['HS256']
      )['reset_password']
      return User.query.filter_by(email=email).first()
    except:
      return None

  @staticmethod
  def verify_email(email):
    return User.query.filter_by(email=email).first()

  @property
  def average_rating(self):
    ratings = [r.rating for r in self.ratings_received]
    return sum(ratings) / len(ratings) if ratings else 0

class OAuth(OAuthConsumerMixin, db.Model):
  __table_args__ = (db.UniqueConstraint("provider", "provider_user_id"),)
  provider_user_id = db.Column(db.String(255), nullable=False)
  provider_user_login = db.Column(db.String(255))
  user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
  user = db.relationship(User)

class TutorStudent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer)  # 1-5 stars
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='messages_sent')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='messages_received')

# Add new model for study materials
class StudyMaterial(db.Model):
    __tablename__ = 'study_materials'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(200), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    tutor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100))
    
    tutor = db.relationship('User', backref='study_materials')


