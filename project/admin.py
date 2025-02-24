from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, login_required, current_user
from werkzeug.security import check_password_hash
from .models import User, db
from functools import wraps

admin = Blueprint('admin', __name__)

@admin.route('/admin/login')
def login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin.tutor_applications'))
    return render_template('admin/login.html')

@admin.route('/admin/login', methods=['POST'])
def login_post():
    email = request.form.get('email')
    password = request.form.get('password')

    user = User.query.filter_by(email=email).first()

    # Add debug logging
    print(f"Login attempt - Email: {email}")
    print(f"User found: {user}")
    if user:
        print(f"Is admin: {user.is_admin}")
        print(f"Password check: {check_password_hash(user.password, password)}")

    # Check if user exists, is admin, and password is correct
    if not user or not user.is_admin or not check_password_hash(user.password, password):
        flash('Invalid admin credentials.', 'danger')
        return redirect(url_for('admin.login'))

    login_user(user)
    return redirect(url_for('admin.tutor_applications'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need to be an admin to access this page.', 'danger')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/admin/tutor-applications')
@login_required
@admin_required
def tutor_applications():
    pending_tutors = User.query.filter_by(
        is_tutor=True,
        tutor_status='pending'
    ).all()
    return render_template('admin/tutor_applications.html', pending_tutors=pending_tutors)

@admin.route('/admin/process-application/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def process_tutor_application(user_id):
    user = User.query.get_or_404(user_id)
    action = request.form.get('action')
    
    if action == 'approve':
        user.tutor_status = 'approved'
        flash(f'Tutor application for {user.username} has been approved.', 'success')
    elif action == 'reject':
        user.tutor_status = 'rejected'
        user.is_tutor = False
        flash(f'Tutor application for {user.username} has been rejected.', 'warning')
    
    db.session.commit()
    return redirect(url_for('admin.tutor_applications')) 