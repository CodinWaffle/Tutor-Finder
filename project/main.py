from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, send_file
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from . import db
from .models import User, TutorStudent, Message, Rating, StudyMaterial
from werkzeug.security import generate_password_hash
import os
from werkzeug.utils import secure_filename
from datetime import datetime

main = Blueprint('main', __name__)

# Add these constants at the top of the file
UPLOAD_FOLDER = 'project/static/profile_pics'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route('/')
@login_required
def index():
    return render_template('index.html')

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', name=current_user.username)

@main.route('/newsfeed')
@login_required
def newsfeed():
    # Get all unique subjects from tutors
    all_subjects = set()
    tutors_with_subjects = User.query.filter_by(is_tutor=True).filter(User.subjects.isnot(None))
    
    for tutor in tutors_with_subjects:
        if tutor.subjects:
            subjects = [s.strip() for s in tutor.subjects.split(',')]
            all_subjects.update(subjects)
    
    # Sort subjects alphabetically
    all_subjects = sorted(list(all_subjects))
    
    # Get filter parameters
    subject = request.args.get('subject', '').lower()
    max_rate = request.args.get('max_rate', type=float)
    
    # Base query
    query = User.query.filter_by(is_tutor=True)
    
    # Apply filters
    if subject:
        query = query.filter(User.subjects.ilike(f'%{subject}%'))
    if max_rate:
        query = query.filter(User.hourly_rate <= max_rate)
        
    tutors = query.all()
    return render_template('newsfeed.html', tutors=tutors, all_subjects=all_subjects)

@main.route('/tutor/<int:tutor_id>')
@login_required
def tutor_profile(tutor_id):
    tutor = User.query.get_or_404(tutor_id)
    if not tutor.is_tutor:
        flash('This user is not a tutor')
        return redirect(url_for('main.newsfeed'))
    return render_template('tutor_profile.html', tutor=tutor)

@main.route('/request_tutor/<int:tutor_id>')
@login_required
def request_tutor(tutor_id):
    if current_user.is_tutor:
        flash('Tutors cannot request other tutors', 'warning')
        return redirect(url_for('main.newsfeed'))
        
    tutor = User.query.get_or_404(tutor_id)
    if not tutor.is_tutor:
        flash('This user is not a tutor', 'warning')
        return redirect(url_for('main.newsfeed'))
        
    # Check if any request exists (including previous relationships)
    existing_request = TutorStudent.query.filter_by(
        student_id=current_user.id,
        tutor_id=tutor_id
    ).first()
    
    if existing_request:
        if existing_request.status == 'pending':
            flash('You have already requested this tutor', 'info')
        elif existing_request.status == 'accepted':
            flash('You are already a student of this tutor', 'info')
        else:  # For removed/rejected relationships
            flash('You cannot request this tutor again. Please contact them directly if you wish to resume tutoring.', 'warning')
        return redirect(url_for('main.tutor_profile', tutor_id=tutor_id))
    
    # Create new request
    new_request = TutorStudent(
        student_id=current_user.id,
        tutor_id=tutor_id,
        status='pending'
    )
    
    db.session.add(new_request)
    db.session.commit()
    
    flash('Request sent successfully! Waiting for tutor approval.', 'success')
    return redirect(url_for('main.tutor_profile', tutor_id=tutor_id))

@main.route('/accept_request/<int:request_id>')
@login_required
def accept_request(request_id):
    if not current_user.is_tutor:
        flash('Only tutors can accept requests', 'warning')
        return redirect(url_for('main.profile'))
        
    request = TutorStudent.query.get_or_404(request_id)
    
    # Security check
    if request.tutor_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('main.profile'))
    
    request.status = 'accepted'
    db.session.commit()
    
    flash(f'You are now tutoring {request.student.username}!', 'success')
    return redirect(url_for('main.profile'))

@main.route('/reject_request/<int:request_id>')
@login_required
def reject_request(request_id):
    if not current_user.is_tutor:
        flash('Only tutors can reject requests', 'warning')
        return redirect(url_for('main.profile'))
        
    request = TutorStudent.query.get_or_404(request_id)
    
    # Security check
    if request.tutor_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('main.profile'))
    
    db.session.delete(request)
    db.session.commit()
    
    flash('Request rejected', 'info')
    return redirect(url_for('main.profile'))

@main.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        # Get form data
        current_user.username = request.form.get('username', current_user.username)
        current_user.email = request.form.get('email', current_user.email)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.address = request.form.get('address', current_user.address)
        current_user.bio = request.form.get('bio', current_user.bio)

        # Handle tutor-specific fields
        if current_user.is_tutor:
            current_user.subjects = request.form.get('subjects', current_user.subjects)
            try:
                hourly_rate = float(request.form.get('hourly_rate', current_user.hourly_rate))
                current_user.hourly_rate = hourly_rate
            except ValueError:
                flash('Invalid hourly rate format')
                return redirect(url_for('main.edit_profile'))

        # Handle password change
        new_password = request.form.get('new_password')
        if new_password:
            current_user.password = generate_password_hash(new_password, method='sha256')

        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('main.profile'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating your profile.', 'error')
            return redirect(url_for('main.edit_profile'))

    return render_template('edit_profile.html')

@main.route('/update_profile_pic', methods=['POST'])
@login_required
def update_profile_pic():
    if 'profile_pic' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('main.profile'))
    
    file = request.files['profile_pic']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('main.profile'))
    
    if file and allowed_file(file.filename):
        # Create upload folder if it doesn't exist
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
            
        # Delete old profile picture if it exists
        if current_user.profile_pic:
            old_pic_path = os.path.join(current_app.root_path, 'static', current_user.profile_pic)
            if os.path.exists(old_pic_path):
                os.remove(old_pic_path)
        
        # Save new profile picture
        filename = secure_filename(f"user_{current_user.id}_{file.filename}")
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # Update database
        current_user.profile_pic = f'profile_pics/{filename}'
        db.session.commit()
        
        flash('Profile picture updated successfully!', 'success')
        return redirect(url_for('main.profile'))
    
    flash('Invalid file type. Please use PNG, JPG, JPEG or GIF', 'error')
    return redirect(url_for('main.profile'))

@main.route('/messages')
@login_required
def messages():
    # Get all conversations (unique users the current user has messaged with)
    sent_to = db.session.query(Message.recipient_id).filter(Message.sender_id == current_user.id).distinct()
    received_from = db.session.query(Message.sender_id).filter(Message.recipient_id == current_user.id).distinct()
    
    conversation_user_ids = [user_id for (user_id,) in sent_to.union(received_from)]
    conversation_users = User.query.filter(User.id.in_(conversation_user_ids)).all()
    
    # Get the last message and unread count for each conversation
    conversations = []
    for user in conversation_users:
        last_message = Message.query.filter(
            or_(
                and_(Message.sender_id == current_user.id, Message.recipient_id == user.id),
                and_(Message.sender_id == user.id, Message.recipient_id == current_user.id)
            )
        ).order_by(Message.created_at.desc()).first()
        
        # Count unread messages
        unread_count = Message.query.filter_by(
            sender_id=user.id,
            recipient_id=current_user.id,
            is_read=False
        ).count()
        
        conversations.append({
            'user': user,
            'last_message': last_message,
            'unread_count': unread_count
        })
    
    # Sort conversations by last message date
    conversations.sort(key=lambda x: x['last_message'].created_at if x['last_message'] else datetime.min, reverse=True)
    
    return render_template('messages.html', conversations=conversations)

@main.route('/conversation/<int:user_id>')
@login_required
def conversation(user_id):
    other_user = User.query.get_or_404(user_id)
    
    # Mark all messages from other user as read
    Message.query.filter_by(
        sender_id=user_id,
        recipient_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    # Get all messages between the two users
    messages = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
            and_(Message.sender_id == user_id, Message.recipient_id == current_user.id)
        )
    ).order_by(Message.created_at).all()
    
    return render_template('conversation.html', other_user=other_user, messages=messages)

@main.route('/send_message/<int:recipient_id>', methods=['POST'])
@login_required
def send_message(recipient_id):
    content = request.form.get('message')
    if not content:
        flash('Message cannot be empty', 'error')
        return redirect(request.referrer)
    
    message = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        content=content
    )
    db.session.add(message)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'status': 'success',
            'message': {
                'content': message.content,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M'),
                'sender_id': message.sender_id
            }
        })
    
    flash('Message sent successfully!', 'success')
    return redirect(request.referrer)

@main.route('/remove_tutor/<int:relation_id>', methods=['POST'])
@login_required
def remove_tutor(relation_id):
    relation = TutorStudent.query.get_or_404(relation_id)
    
    # Security check to ensure the student owns this relation
    if relation.student_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('main.profile'))
    
    # Store tutor name for the flash message
    tutor_name = relation.tutor.username
    
    # Remove the relation
    db.session.delete(relation)
    db.session.commit()
    
    flash(f'Successfully removed {tutor_name} from your tutors', 'success')
    return redirect(url_for('main.profile'))

@main.route('/my_tutors')
@login_required
def my_tutors():
    if current_user.is_tutor:
        return redirect(url_for('main.profile'))
    return render_template('my_tutors.html')

@main.route('/my_students')
@login_required
def my_students():
    if not current_user.is_tutor:
        return redirect(url_for('main.profile'))
    return render_template('my_students.html')

@main.route('/submit_rating/<int:tutor_id>', methods=['POST'])
@login_required
def submit_rating(tutor_id):
    if current_user.is_tutor:
        flash('Tutors cannot submit ratings', 'error')
        return redirect(url_for('main.tutor_profile', tutor_id=tutor_id))
        
    tutor = User.query.get_or_404(tutor_id)
    
    # Check if the student is accepted by this tutor
    tutor_relation = TutorStudent.query.filter_by(
        tutor_id=tutor_id,
        student_id=current_user.id,
        status='accepted'
    ).first()
    
    if not tutor_relation:
        flash('You can only rate tutors who have accepted you as a student', 'warning')
        return redirect(url_for('main.tutor_profile', tutor_id=tutor_id))
    
    # Check if user has already rated this tutor
    existing_rating = Rating.query.filter_by(
        tutor_id=tutor_id,
        student_id=current_user.id
    ).first()
    
    rating_value = int(request.form.get('rating'))
    comment = request.form.get('comment')
    
    if existing_rating:
        # Update existing rating
        existing_rating.rating = rating_value
        existing_rating.comment = comment
        existing_rating.created_at = datetime.utcnow()
        flash('Your review has been updated!', 'success')
    else:
        # Create new rating
        new_rating = Rating(
            tutor_id=tutor_id,
            student_id=current_user.id,
            rating=rating_value,
            comment=comment
        )
        db.session.add(new_rating)
        flash('Your review has been submitted!', 'success')
    
    db.session.commit()
    return redirect(url_for('main.tutor_profile', tutor_id=tutor_id))

@main.route('/study_materials')
@login_required
def study_materials():
    if current_user.is_tutor:
        # Tutors see their uploaded materials
        materials = StudyMaterial.query.filter_by(tutor_id=current_user.id).order_by(StudyMaterial.upload_date.desc()).all()
    else:
        # Students see materials from their tutors
        tutor_ids = [relation.tutor_id for relation in current_user.tutors if relation.status == 'accepted']
        materials = StudyMaterial.query.filter(StudyMaterial.tutor_id.in_(tutor_ids)).order_by(StudyMaterial.upload_date.desc()).all()
    
    return render_template('study_materials.html', materials=materials)

@main.route('/upload_material', methods=['POST'])
@login_required
def upload_material():
    if not current_user.is_tutor:
        flash('Only tutors can upload materials', 'error')
        return redirect(url_for('main.study_materials'))
        
    file = request.files.get('file')
    if not file or not allowed_file(file.filename):
        flash('Invalid file type', 'error')
        return redirect(url_for('main.study_materials'))
        
    filename = secure_filename(file.filename)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    new_material = StudyMaterial(
        title=request.form.get('title'),
        description=request.form.get('description'),
        filename=filename,
        file_path=file_path,
        tutor_id=current_user.id,
        subject=request.form.get('subject')
    )
    
    db.session.add(new_material)
    db.session.commit()
    
    flash('Material uploaded successfully', 'success')
    return redirect(url_for('main.study_materials'))

@main.route('/download_material/<int:material_id>')
@login_required
def download_material(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    
    # Check if student has access to this material
    if not current_user.is_tutor:
        tutor_ids = [relation.tutor_id for relation in current_user.tutors if relation.status == 'accepted']
        if material.tutor_id not in tutor_ids:
            flash('Access denied', 'error')
            return redirect(url_for('main.study_materials'))
            
    return send_file(material.file_path, as_attachment=True)

@main.route('/rate_tutor/<int:tutor_id>', methods=['POST'])
@login_required
def rate_tutor(tutor_id):
    if current_user.is_tutor:
        flash('Tutors cannot rate other tutors', 'warning')
        return redirect(url_for('main.tutor_profile', tutor_id=tutor_id))
        
    tutor = User.query.get_or_404(tutor_id)
    
    # Check if the student is accepted by this tutor
    tutor_relation = TutorStudent.query.filter_by(
        tutor_id=tutor_id,
        student_id=current_user.id,
        status='accepted'
    ).first()
    
    if not tutor_relation:
        flash('You can only rate tutors who have accepted you as a student', 'warning')
        return redirect(url_for('main.tutor_profile', tutor_id=tutor_id))
    
    # Check if user has already rated this tutor
    existing_rating = Rating.query.filter_by(
        tutor_id=tutor_id,
        student_id=current_user.id
    ).first()
    
    try:
        rating_value = int(request.form.get('rating'))
        if not 1 <= rating_value <= 5:
            raise ValueError('Invalid rating value')
    except (ValueError, TypeError):
        flash('Invalid rating value', 'danger')
        return redirect(url_for('main.tutor_profile', tutor_id=tutor_id))
        
    comment = request.form.get('comment')
    
    if existing_rating:
        # Update existing rating
        existing_rating.rating = rating_value
        existing_rating.comment = comment
        existing_rating.created_at = datetime.utcnow()
        flash('Your review has been updated!', 'success')
    else:
        # Create new rating
        new_rating = Rating(
            tutor_id=tutor_id,
            student_id=current_user.id,
            rating=rating_value,
            comment=comment
        )
        db.session.add(new_rating)
        flash('Your review has been submitted!', 'success')
    
    db.session.commit()
    return redirect(url_for('main.tutor_profile', tutor_id=tutor_id))