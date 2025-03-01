from flask import Blueprint, render_template, redirect, url_for, request, flash 
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from flask_mail import Mail, Message
from flask_jwt_extended import jwt_required, create_access_token
from .models import User, OAuth
from . import db, mail
import os

auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
  return render_template('login.html') 

@auth.route('/login', methods=['POST']) 
def login_post():
  email = request.form.get('email')
  password = request.form.get('password')
  remember = True if request.form.get('remember') else False

  user = User.query.filter_by(email=email).first()

  if not user or not check_password_hash(user.password, password):
    flash('Please check your login details and try again.', 'danger')
    return redirect(url_for('auth.login'))

  login_user(user, remember=remember)

  return redirect(url_for('main.profile')) 

def send_email(user):
  token = user.get_reset_token()

  msg = Message()
  msg.subject = "Login System: Password Reset Request"
  msg.sender = 'dnxncpcx@gmail.com'
  msg.recipients = [user.email]
  msg.html = render_template('reset_pwd.html', user = user, token = token)

  mail.send(msg)

@auth.route('/reset', methods=['GET', 'POST'])
def reset():
    if request.method == "POST":
        email = request.form.get('email')
        user = User.verify_email(email)

        if user:
            send_email(user)
            flash('Password reset instructions have been sent to your email.', 'success')
        else:
            flash('No account found with that email address.', 'danger')
        return redirect(url_for('auth.login'))

    return render_template('reset.html')

@auth.route('/reset/<token>', methods=['GET', 'POST'])
def reset_verified(token):
    user = User.verify_reset_token(token)

    if not user:
        flash('Invalid or expired reset link. Please try again.', 'danger')
        return redirect(url_for('auth.reset'))

    if request.method == 'POST':
        password = request.form.get('password')
        if not password:
            flash('Password is required.', 'danger')
            return render_template('reset_password.html')
            
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('reset_password.html')

        user.password = generate_password_hash(password, method='sha256')
        db.session.commit()
        flash('Your password has been updated! You can now login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')

@auth.route('/signup')
def signup():
  return render_template('signup.html')
  
@auth.route('/signup', methods=['POST'])
def signup_post():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    phone = request.form.get('phone')
    address = request.form.get('address')
    is_tutor = True if request.form.get('is_tutor') else False
    
    # Get tutor-specific fields if registering as tutor
    subjects = None
    hourly_rate = None
    bio = None
    if is_tutor:
        subjects = request.form.get('subjects')
        try:
            hourly_rate = float(request.form.get('hourly_rate', 0))
        except ValueError:
            flash('Invalid hourly rate')
            return redirect(url_for('auth.signup'))
        bio = request.form.get('bio')
        tutor_status = 'pending'  # Set initial status as pending
    else:
        tutor_status = None

    # Check if user already exists
    user = User.query.filter_by(email=email).first()
    if user:
        flash('Email address already exists')
        return redirect(url_for('auth.signup'))
    
    # Create new user
    new_user = User(
        username=username,
        email=email,
        password=generate_password_hash(password, method='sha256'),
        phone=phone,
        address=address,
        is_tutor=is_tutor,
        subjects=subjects,
        hourly_rate=hourly_rate,
        bio=bio,
        tutor_status=tutor_status
    )

    db.session.add(new_user)
    db.session.commit()

    if is_tutor:
        flash('Your tutor application has been submitted and is pending approval.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('main.index'))  