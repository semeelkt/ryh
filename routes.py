from flask import render_template, request, jsonify, session, redirect, url_for, send_file
from models import db, User, Classroom, Student, Attendance, Timetable, TeacherClass
from utils import (
    calculate_attendance_percentage,
    process_excel_upload,
    get_student_attendance_data,
    get_classroom_students
)
from datetime import datetime, date, time
from functools import wraps
import os
import csv
import io
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def get_teacher_classrooms(teacher_id):
    """Get all classrooms for a teacher (as class teacher or subject teacher)."""
    teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher_id).all()
    classrooms = list(set([tc.classroom for tc in teacher_classes]))

    # Also include classrooms where teacher is class_teacher_id
    classrooms_as_class_teacher = Classroom.query.filter_by(class_teacher_id=teacher_id).all()
    classrooms = list(set(classrooms + classrooms_as_class_teacher))

    return classrooms

def allowed_file(filename):
    """Check if uploaded file has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    """Decorator to check if user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    """Decorator to check if user has specific role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))

            user = User.query.get(session['user_id'])
            if not user or user.role != role:
                return jsonify({'error': 'Unauthorized'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def register_routes(app):
    """Register all Flask routes."""

    # Ensure upload folder exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    @app.route('/')
    def index():
        """Home page."""
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
            if user.role == 'admin':
                return redirect(url_for('school_dashboard'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student_dashboard'))
        return redirect(url_for('login'))

    # ==================== Authentication Routes ====================
    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        """School sign-up page."""
        if request.method == 'POST':
            school_name = request.form.get('school_name', '').strip()
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            # Validation
            if not school_name or not username or not password:
                return render_template('signup.html', error='All fields are required')

            if len(username) < 3:
                return render_template('signup.html', error='Username must be at least 3 characters')

            if len(password) < 6:
                return render_template('signup.html', error='Password must be at least 6 characters')

            if password != confirm_password:
                return render_template('signup.html', error='Passwords do not match')

            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return render_template('signup.html', error='Username already taken')

            # Create school admin user
            school_admin = User(username=username, role='admin')
            school_admin.set_password(password)
            db.session.add(school_admin)
            db.session.flush()

            # Log in the new school admin
            session['user_id'] = school_admin.id
            session['username'] = school_admin.username
            session['role'] = school_admin.role
            session['school_name'] = school_name

            db.session.commit()

            return redirect(url_for('school_dashboard'))

        return render_template('signup.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login page."""
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()

            user = User.query.filter_by(username=username).first()

            if user and user.check_password(password):
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                return redirect(url_for('index'))

            return render_template('login.html', error='Invalid username or password')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        """Logout user."""
        session.clear()
        return redirect(url_for('login'))

    # ==================== SCHOOL ADMIN Routes ====================
    @app.route('/school/dashboard')
    @login_required
    @role_required('admin')
    def school_dashboard():
        """School admin dashboard."""
        user = User.query.get(session['user_id'])
        teachers = User.query.filter_by(role='teacher').all()
        classrooms = Classroom.query.all()
        students = Student.query.all()

        return render_template(
            'school_dashboard.html',
            teachers=teachers,
            classrooms=classrooms,
            students=students,
            total_teachers=len(teachers),
            total_classes=len(classrooms),
            total_students=len(students)
        )

    @app.route('/school/add-teacher', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def add_teacher():
        """Add a new teacher."""
        classrooms = Classroom.query.all()

        if request.method == 'POST':
            teacher_name = request.form.get('teacher_name', '').strip()
            email = request.form.get('email', '').strip()
            class_teacher_id = request.form.get('class_teacher_id', type=int)

            if not teacher_name or not email:
                return render_template(
                    'add_teacher.html',
                    classrooms=classrooms,
                    error='All fields required'
                )

            # Generate username and password
            teacher_username = teacher_name.lower().replace(' ', '_')
            # Make username unique by adding number if needed
            base_username = teacher_username
            counter = 1
            while User.query.filter_by(username=teacher_username).first():
                teacher_username = f"{base_username}{counter}"
                counter += 1

            teacher_password = f"teacher_{teacher_username}_{counter if counter > 1 else ''}"

            # Create teacher user
            teacher = User(username=teacher_username, role='teacher')
            teacher.set_password(teacher_password)
            db.session.add(teacher)
            db.session.flush()

            # Assign as class teacher if selected
            if class_teacher_id:
                classroom = Classroom.query.get(class_teacher_id)
                if classroom:
                    classroom.class_teacher_id = teacher.id
                    # Create TeacherClass entry
                    teacher_class = TeacherClass(
                        teacher_id=teacher.id,
                        classroom_id=class_teacher_id,
                        role='class_teacher'
                    )
                    db.session.add(teacher_class)

            db.session.commit()

            return render_template(
                'add_teacher.html',
                classrooms=classrooms,
                success=True,
                teacher_name=teacher_name,
                username=teacher_username,
                password=teacher_password
            )

        return render_template('add_teacher.html', classrooms=classrooms)

    @app.route('/school/add-class', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def add_class():
        """Add a new class."""
        from models import TeacherClass

        teachers = User.query.filter_by(role='teacher').all()

        if request.method == 'POST':
            class_name = request.form.get('class_name', '').strip()
            class_teacher_id = request.form.get('class_teacher_id', type=int)
            subject_teachers = request.form.getlist('subject_teacher_ids')

            if not class_name:
                return render_template(
                    'add_class.html',
                    teachers=teachers,
                    error='Class name required'
                )

            # Create classroom
            classroom = Classroom(
                name=class_name,
                class_teacher_id=class_teacher_id if class_teacher_id else None
            )
            db.session.add(classroom)
            db.session.flush()

            # Add class teacher to TeacherClass
            if class_teacher_id:
                teacher_class = TeacherClass(
                    teacher_id=class_teacher_id,
                    classroom_id=classroom.id,
                    role='class_teacher'
                )
                db.session.add(teacher_class)

            # Add subject teachers
            for teacher_id in subject_teachers:
                if teacher_id:
                    subject_teacher_id = int(teacher_id)
                    if subject_teacher_id != class_teacher_id:  # Avoid duplicate
                        teacher_class = TeacherClass(
                            teacher_id=subject_teacher_id,
                            classroom_id=classroom.id,
                            role='subject_teacher',
                            subject_name=request.form.get(f'subject_{teacher_id}', '').strip()
                        )
                        db.session.add(teacher_class)

            db.session.commit()

            return render_template(
                'add_class.html',
                teachers=teachers,
                success=True,
                class_name=class_name
            )

        return render_template('add_class.html', teachers=teachers)

    @app.route('/school/upload-students', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def school_upload_students():
        """School admin uploads students and generates credentials."""
        classrooms = Classroom.query.all()

        if request.method == 'POST':
            classroom_id = request.form.get('classroom_id', type=int)

            if not classroom_id:
                return render_template(
                    'school_upload_students.html',
                    classrooms=classrooms,
                    error='Classroom required'
                )

            if 'file' not in request.files:
                return render_template(
                    'school_upload_students.html',
                    classrooms=classrooms,
                    error='No file provided'
                )

            file = request.files['file']

            if file.filename == '':
                return render_template(
                    'school_upload_students.html',
                    classrooms=classrooms,
                    error='No file selected'
                )

            if not allowed_file(file.filename):
                return render_template(
                    'school_upload_students.html',
                    classrooms=classrooms,
                    error='File must be .xlsx or .xls format'
                )

            # Save and process file
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            # Process Excel
            result = process_excel_upload(filepath, classroom_id)

            # Clean up file
            os.remove(filepath)

            return render_template(
                'school_upload_students.html',
                classrooms=classrooms,
                result=result
            )

        return render_template('school_upload_students.html', classrooms=classrooms)

    # ==================== Teacher Routes ====================
    @app.route('/dashboard/teacher')
    @login_required
    @role_required('teacher')
    def teacher_dashboard():
        """Teacher dashboard."""
        from models import TeacherClass
        user = User.query.get(session['user_id'])

        # Get classrooms where teacher is class teacher or subject teacher
        teacher_classes = TeacherClass.query.filter_by(teacher_id=user.id).all()
        classrooms = list(set([tc.classroom for tc in teacher_classes]))

        # Also include classrooms where teacher is class_teacher_id
        classrooms_as_class_teacher = Classroom.query.filter_by(class_teacher_id=user.id).all()
        classrooms = list(set(classrooms + classrooms_as_class_teacher))

        return render_template('teacher_dashboard.html', classrooms=classrooms, teacher=user)

    @app.route('/upload_students', methods=['GET', 'POST'])
    @login_required
    @role_required('teacher')
    def upload_students():
        """Upload students from Excel file."""
        user = User.query.get(session['user_id'])
        classrooms = get_teacher_classrooms(user.id)

        if request.method == 'POST':
            # Check if classroom_id is provided
            classroom_id = request.form.get('classroom_id', type=int)
            if not classroom_id:
                return render_template(
                    'upload_students.html',
                    classrooms=classrooms,
                    error='Classroom required'
                )

            # Verify teacher owns this classroom
            classroom = Classroom.query.get(classroom_id)
            if not classroom:
                return render_template(
                    'upload_students.html',
                    classrooms=classrooms,
                    error='Classroom not found or unauthorized'
                )

            # Check if user is class teacher or subject teacher
            is_authorized = classroom.class_teacher_id == user.id
            if not is_authorized:
                teacher_class = TeacherClass.query.filter_by(
                    teacher_id=user.id,
                    classroom_id=classroom_id
                ).first()
                is_authorized = teacher_class is not None

            if not is_authorized:
                return render_template(
                    'upload_students.html',
                    classrooms=classrooms,
                    error='Classroom not found or unauthorized'
                )

            # Check if file is in request
            if 'file' not in request.files:
                return render_template(
                    'upload_students.html',
                    classrooms=classrooms,
                    error='No file provided'
                )

            file = request.files['file']

            if file.filename == '':
                return render_template(
                    'upload_students.html',
                    classrooms=classrooms,
                    error='No file selected'
                )

            if not allowed_file(file.filename):
                return render_template(
                    'upload_students.html',
                    classrooms=classrooms,
                    error='File must be .xlsx or .xls format'
                )

            # Save and process file
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            # Process Excel
            result = process_excel_upload(filepath, classroom_id)

            # Clean up file
            os.remove(filepath)

            return render_template(
                'upload_students.html',
                classrooms=classrooms,
                result=result
            )

        return render_template('upload_students.html', classrooms=classrooms)

    @app.route('/api/teacher/timetable', methods=['GET'])
    @login_required
    @role_required('teacher')
    def get_teacher_timetable():
        """Get timetable for all classrooms of the teacher."""
        user = User.query.get(session['user_id'])
        classrooms = get_teacher_classrooms(user.id)
        classroom_ids = [c.id for c in classrooms]

        timetables = Timetable.query.filter(
            Timetable.classroom_id.in_(classroom_ids)
        ).all()

        timetable_data = [
            {
                'id': t.id,
                'classroom_id': t.classroom_id,
                'day_of_week': t.day_of_week,
                'start_time': str(t.start_time),
                'end_time': str(t.end_time),
                'subject_name': t.subject_name
            }
            for t in timetables
        ]

        return jsonify(timetable_data)

    @app.route('/api/classroom/<int:classroom_id>/students', methods=['GET'])
    @login_required
    @role_required('teacher')
    def get_classroom_students_api(classroom_id):
        """Get students in a classroom (for teacher)."""
        user = User.query.get(session['user_id'])

        # Verify teacher has access to this classroom
        classroom = Classroom.query.get(classroom_id)
        if not classroom:
            return jsonify({'error': 'Classroom not found'}), 404

        # Check if user is class teacher or subject teacher
        is_authorized = classroom.class_teacher_id == user.id
        if not is_authorized:
            teacher_class = TeacherClass.query.filter_by(
                teacher_id=user.id,
                classroom_id=classroom_id
            ).first()
            is_authorized = teacher_class is not None

        if not is_authorized:
            return jsonify({'error': 'Unauthorized'}), 403

        students = Student.query.filter_by(classroom_id=classroom_id).all()
        students_data = [
            {
                'id': s.id,
                'name': s.name,
                'roll_no': s.roll_no,
                'parent_email': s.parent_email
            }
            for s in students
        ]

        return jsonify(students_data)

    @app.route('/api/classroom/<int:classroom_id>/teacher-subjects', methods=['GET'])
    @login_required
    @role_required('teacher')
    def get_teacher_subjects(classroom_id):
        """Get subjects taught by the logged-in teacher for a specific classroom."""
        user = User.query.get(session['user_id'])

        # Verify teacher has access to this classroom
        classroom = Classroom.query.get(classroom_id)
        if not classroom:
            return jsonify([]), 404

        # Check if user is class teacher or subject teacher
        is_authorized = classroom.class_teacher_id == user.id
        if not is_authorized:
            teacher_class = TeacherClass.query.filter_by(
                teacher_id=user.id,
                classroom_id=classroom_id
            ).first()
            is_authorized = teacher_class is not None

        if not is_authorized:
            return jsonify([]), 403

        # Get all timetables for this classroom taught by this teacher
        # Since timetables don't have teacher info, we'll get unique subjects
        timetables = Timetable.query.filter_by(classroom_id=classroom_id).all()
        subjects = sorted(set([t.subject_name for t in timetables]))

        return jsonify(subjects)

    @app.route('/api/student/<int:student_id>/update-credentials', methods=['POST'])
    @login_required
    @role_required('teacher')
    def update_student_credentials(student_id):
        """Update student username and password."""
        user = User.query.get(session['user_id'])
        student = Student.query.get(student_id)

        if not student:
            return jsonify({'error': 'Student not found'}), 404

        # Verify teacher has access to this student's classroom
        classroom = student.classroom

        # Check if user is class teacher or subject teacher
        is_authorized = classroom.class_teacher_id == user.id
        if not is_authorized:
            teacher_class = TeacherClass.query.filter_by(
                teacher_id=user.id,
                classroom_id=classroom.id
            ).first()
            is_authorized = teacher_class is not None

        if not is_authorized:
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json()
        new_username = data.get('username', '').strip()
        new_password = data.get('password', '').strip()

        if not new_username or not new_password:
            return jsonify({'error': 'Username and password are required'}), 400

        # Check if new username already exists (and is not the current user)
        if student.user_id:
            current_user = User.query.get(student.user_id)
            if current_user.username != new_username:
                existing_user = User.query.filter_by(username=new_username).first()
                if existing_user:
                    return jsonify({'error': 'Username already exists'}), 400
        else:
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user:
                return jsonify({'error': 'Username already exists'}), 400

        # Update or create user account
        if student.user_id:
            user_account = User.query.get(student.user_id)
        else:
            user_account = User(role='student')
            db.session.add(user_account)
            db.session.flush()
            student.user_id = user_account.id

        user_account.username = new_username
        user_account.set_password(new_password)
        db.session.commit()

        return jsonify({'success': True})

    @app.route('/api/student/<int:student_id>/delete', methods=['POST'])
    @login_required
    @role_required('teacher')
    def delete_student(student_id):
        """Delete a student."""
        user = User.query.get(session['user_id'])
        student = Student.query.get(student_id)

        if not student:
            return jsonify({'error': 'Student not found'}), 404

        # Verify teacher has access to this student's classroom
        classroom = student.classroom

        # Check if user is class teacher or subject teacher
        is_authorized = classroom.class_teacher_id == user.id
        if not is_authorized:
            teacher_class = TeacherClass.query.filter_by(
                teacher_id=user.id,
                classroom_id=classroom.id
            ).first()
            is_authorized = teacher_class is not None

        if not is_authorized:
            return jsonify({'error': 'Unauthorized'}), 403

        # Delete associated user account if exists
        if student.user_id:
            user_account = User.query.get(student.user_id)
            if user_account:
                db.session.delete(user_account)

        # Delete student (cascade will delete attendance records)
        db.session.delete(student)
        db.session.commit()

        return jsonify({'success': True})

    @app.route('/api/classroom/<int:classroom_id>/student-credentials', methods=['GET'])
    @login_required
    @role_required('teacher')
    def get_student_credentials(classroom_id):
        """Get student credentials (username and password) for a classroom."""
        user = User.query.get(session['user_id'])

        # Verify teacher has access to this classroom
        classroom = Classroom.query.get(classroom_id)
        if not classroom:
            return jsonify({'error': 'Classroom not found'}), 404

        # Check if user is class teacher or subject teacher
        is_authorized = classroom.class_teacher_id == user.id
        if not is_authorized:
            teacher_class = TeacherClass.query.filter_by(
                teacher_id=user.id,
                classroom_id=classroom_id
            ).first()
            is_authorized = teacher_class is not None

        if not is_authorized:
            return jsonify({'error': 'Unauthorized'}), 403

        students = Student.query.filter_by(classroom_id=classroom_id).all()
        students_data = [
            {
                'id': s.id,
                'name': s.name,
                'roll_no': s.roll_no,
                'username': s.roll_no,
                'password': f'student_{s.roll_no}',
                'parent_email': s.parent_email
            }
            for s in students
        ]

        return jsonify(students_data)

    @app.route('/teacher/manage-timetable', methods=['GET', 'POST'])
    @login_required
    @role_required('teacher')
    def manage_timetable():
        """Teacher manages timetable."""
        user = User.query.get(session['user_id'])
        classrooms = get_teacher_classrooms(user.id)

        if request.method == 'POST':
            classroom_id = request.form.get('classroom_id', type=int)
            day_of_week = request.form.get('day_of_week', '').strip()
            start_time = request.form.get('start_time', '').strip()
            end_time = request.form.get('end_time', '').strip()
            subject_name = request.form.get('subject_name', '').strip()

            if not all([classroom_id, day_of_week, start_time, end_time, subject_name]):
                return render_template(
                    'manage_timetable.html',
                    classrooms=classrooms,
                    error='All fields required'
                )

            # Verify classroom belongs to teacher
            classroom = Classroom.query.get(classroom_id)
            if not classroom:
                return render_template(
                    'manage_timetable.html',
                    classrooms=classrooms,
                    error='Class not found'
                )

            # Check if user is class teacher or subject teacher
            is_authorized = classroom.class_teacher_id == user.id
            if not is_authorized:
                teacher_class = TeacherClass.query.filter_by(
                    teacher_id=user.id,
                    classroom_id=classroom_id
                ).first()
                is_authorized = teacher_class is not None

            if not is_authorized:
                return render_template(
                    'manage_timetable.html',
                    classrooms=classrooms,
                    error='Unauthorized access'
                )

            # Check if slot already exists
            existing = Timetable.query.filter_by(
                classroom_id=classroom_id,
                day_of_week=day_of_week,
                start_time=start_time
            ).first()

            if existing:
                return render_template(
                    'manage_timetable.html',
                    classrooms=classrooms,
                    error='Timetable slot already exists'
                )

            try:
                start_t = datetime.strptime(start_time, '%H:%M').time()
                end_t = datetime.strptime(end_time, '%H:%M').time()

                if start_t >= end_t:
                    return render_template(
                        'manage_timetable.html',
                        classrooms=classrooms,
                        error='End time must be after start time'
                    )

                timetable = Timetable(
                    classroom_id=classroom_id,
                    day_of_week=day_of_week,
                    start_time=start_t,
                    end_time=end_t,
                    subject_name=subject_name
                )
                db.session.add(timetable)
                db.session.commit()

                return render_template(
                    'manage_timetable.html',
                    classrooms=classrooms,
                    success=True,
                    subject_name=subject_name
                )
            except ValueError:
                return render_template(
                    'manage_timetable.html',
                    classrooms=classrooms,
                    error='Invalid time format'
                )

        return render_template('manage_timetable.html', classrooms=classrooms)

    @app.route('/teacher/delete-timetable/<int:timetable_id>', methods=['POST'])
    @login_required
    @role_required('teacher')
    def delete_timetable(timetable_id):
        """Delete a timetable session."""
        user = User.query.get(session['user_id'])
        timetable = Timetable.query.get(timetable_id)

        if not timetable:
            return jsonify({'error': 'Timetable not found'}), 404

        # Verify teacher has access to this classroom
        classroom = timetable.classroom

        # Check if user is class teacher or subject teacher
        is_authorized = classroom.class_teacher_id == user.id
        if not is_authorized:
            teacher_class = TeacherClass.query.filter_by(
                teacher_id=user.id,
                classroom_id=classroom.id
            ).first()
            is_authorized = teacher_class is not None

        if not is_authorized:
            return jsonify({'error': 'Unauthorized'}), 403

        db.session.delete(timetable)
        db.session.commit()

        return jsonify({'success': True})

    @app.route('/teacher/attendance-records', methods=['GET'])
    @login_required
    @role_required('teacher')
    def view_attendance_records():
        """View submitted attendance records."""
        user = User.query.get(session['user_id'])
        classrooms = get_teacher_classrooms(user.id)
        classroom_ids = [c.id for c in classrooms]

        # Get all students in teacher's classrooms
        students = Student.query.filter(
            Student.classroom_id.in_(classroom_ids)
        ).all()

        student_ids = [s.id for s in students]

        # Get attendance records
        records = Attendance.query.filter(
            Attendance.student_id.in_(student_ids)
        ).order_by(Attendance.date.desc()).all()

        # Group by student
        attendance_by_student = {}
        for record in records:
            student_id = record.student_id
            if student_id not in attendance_by_student:
                attendance_by_student[student_id] = []
            attendance_by_student[student_id].append(record)

        return render_template(
            'teacher_attendance_records.html',
            classrooms=classrooms,
            students=students,
            attendance_by_student=attendance_by_student
        )

    @app.route('/teacher/delete-attendance/<int:attendance_id>', methods=['POST'])
    @login_required
    @role_required('teacher')
    def delete_attendance(attendance_id):
        """Delete attendance record."""
        user = User.query.get(session['user_id'])
        attendance = Attendance.query.get(attendance_id)

        if not attendance:
            return jsonify({'error': 'Record not found'}), 404

        # Verify teacher owns this student
        student = attendance.student
        classroom = student.classroom

        # Check if user is class teacher or subject teacher
        is_authorized = classroom.class_teacher_id == user.id
        if not is_authorized:
            # Check if user is a subject teacher for this class
            teacher_class = TeacherClass.query.filter_by(
                teacher_id=user.id,
                classroom_id=classroom.id
            ).first()
            is_authorized = teacher_class is not None

        if not is_authorized:
            return jsonify({'error': 'Unauthorized'}), 403

        db.session.delete(attendance)
        db.session.commit()

        return jsonify({'success': True})

    @app.route('/api/classroom/<int:classroom_id>/attendance-report', methods=['GET'])
    @login_required
    @role_required('teacher')
    def download_attendance_report(classroom_id):
        """Download attendance report as CSV for a classroom."""
        user = User.query.get(session['user_id'])

        # Verify teacher has access to this classroom
        classroom = Classroom.query.get(classroom_id)
        if not classroom:
            return jsonify({'error': 'Classroom not found'}), 404

        # Check if user is class teacher or subject teacher
        is_authorized = classroom.class_teacher_id == user.id
        if not is_authorized:
            teacher_class = TeacherClass.query.filter_by(
                teacher_id=user.id,
                classroom_id=classroom_id
            ).first()
            is_authorized = teacher_class is not None

        if not is_authorized:
            return jsonify({'error': 'Unauthorized'}), 403

        # Get all students in classroom
        students = Student.query.filter_by(classroom_id=classroom_id).all()
        student_ids = [s.id for s in students]

        # Get all attendance records
        records = Attendance.query.filter(
            Attendance.student_id.in_(student_ids)
        ).order_by(Attendance.student_id, Attendance.date).all()

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Roll No',
            'Student Name',
            'Date',
            'Period/Subject',
            'Status',
            'Parent Email'
        ])

        # Write student records
        for student in students:
            student_records = [r for r in records if r.student_id == student.id]
            if student_records:
                for record in student_records:
                    writer.writerow([
                        student.roll_no,
                        student.name,
                        record.date,
                        record.period_name or 'General',
                        record.status,
                        student.parent_email
                    ])
            else:
                # Include students with no records
                writer.writerow([
                    student.roll_no,
                    student.name,
                    '',
                    '',
                    'No records',
                    student.parent_email
                ])

        # Convert to bytes and return as file download
        output.seek(0)
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)

        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'attendance_{classroom.name}_{datetime.now().strftime("%Y%m%d")}.csv'
        )

    @app.route('/mark_attendance', methods=['GET', 'POST'])
    @login_required
    @role_required('teacher')
    def mark_attendance():
        """Mark attendance for students."""
        user = User.query.get(session['user_id'])

        if request.method == 'POST':
            data = request.get_json()
            classroom_id = data.get('classroom_id')
            attendance_date = data.get('date')  # Format: YYYY-MM-DD
            period_name = data.get('period_name')
            attendance_list = data.get('attendance_list', [])  # List of {student_id, status}

            # Verify classroom belongs to teacher
            classroom = Classroom.query.get(classroom_id)
            if not classroom:
                return jsonify({'error': 'Classroom not found'}), 404

            # Check if user is class teacher or subject teacher
            is_authorized = classroom.class_teacher_id == user.id
            if not is_authorized:
                teacher_class = TeacherClass.query.filter_by(
                    teacher_id=user.id,
                    classroom_id=classroom_id
                ).first()
                is_authorized = teacher_class is not None

            if not is_authorized:
                return jsonify({'error': 'Unauthorized'}), 403

            try:
                attendance_date_obj = datetime.strptime(attendance_date, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400

            # Process attendance records
            for item in attendance_list:
                student_id = item.get('student_id')
                status = item.get('status', 'Absent')

                # Verify student belongs to classroom
                student = Student.query.filter_by(
                    id=student_id,
                    classroom_id=classroom_id
                ).first()

                if not student:
                    continue

                # Update or create attendance record
                attendance = Attendance.query.filter_by(
                    student_id=student_id,
                    date=attendance_date_obj,
                    period_name=period_name
                ).first()

                if attendance:
                    attendance.status = status
                else:
                    attendance = Attendance(
                        student_id=student_id,
                        date=attendance_date_obj,
                        status=status,
                        period_name=period_name
                    )
                    db.session.add(attendance)

            db.session.commit()
            return jsonify({'success': True, 'message': 'Attendance marked successfully'})

        # GET: Show form
        classrooms = get_teacher_classrooms(user.id)
        return render_template('mark_attendance.html', classrooms=classrooms)

    # ==================== Student Routes ====================
    @app.route('/dashboard/student')
    @login_required
    @role_required('student')
    def student_dashboard():
        """Student dashboard."""
        user = User.query.get(session['user_id'])
        student = Student.query.filter_by(user_id=user.id).first()

        if not student:
            return "Student record not found", 404

        attendance_data = get_student_attendance_data(student.id)

        # Ensure attendance_data has default values if None
        if not attendance_data:
            attendance_data = {
                'student_id': student.id,
                'name': student.name,
                'roll_no': student.roll_no,
                'classroom_id': student.classroom_id,
                'percentage': 0,
                'total_records': 0,
                'present_count': 0,
                'absent_count': 0,
                'subject_breakdown': [],
                'medical_percentage': 0,
                'official_percentage': 0
            }

        return render_template('student_dashboard.html', student=student, attendance_data=attendance_data)

    @app.route('/api/student/attendance', methods=['GET'])
    @login_required
    @role_required('student')
    def get_student_attendance():
        """Get attendance data for logged-in student."""
        user = User.query.get(session['user_id'])
        student = Student.query.filter_by(user_id=user.id).first()

        if not student:
            return jsonify({'error': 'Student record not found'}), 404

        attendance_data = get_student_attendance_data(student.id)
        return jsonify(attendance_data)

    # ==================== SCHOOL ADMIN Attendance Routes ====================
    @app.route('/school/attendance-overview', methods=['GET'])
    @login_required
    @role_required('admin')
    def school_attendance_overview():
        """School admin view all attendance records."""
        # Get all teachers in school
        teachers = User.query.filter_by(role='teacher').all()

        # Get attendance data for all
        all_classrooms = Classroom.query.all()
        all_students = Student.query.all()

        attendance_by_class = {}
        for classroom in all_classrooms:
            students_in_class = [s for s in all_students if s.classroom_id == classroom.id]
            attendance_by_class[classroom.id] = {
                'class': classroom,
                'teacher': classroom.class_teacher_user,
                'students': students_in_class,
                'total_students': len(students_in_class),
                'records': []
            }

            for student in students_in_class:
                records = Attendance.query.filter_by(student_id=student.id).order_by(
                    Attendance.date.desc()
                ).all()
                attendance_by_class[classroom.id]['records'].extend([
                    {'student': student, 'record': r} for r in records
                ])

        return render_template(
            'school_attendance_overview.html',
            attendance_by_class=attendance_by_class,
            teachers=teachers,
            total_classrooms=len(all_classrooms),
            total_students=len(all_students)
        )

    @app.route('/school/attendance-by-teacher/<int:teacher_id>', methods=['GET'])
    @login_required
    @role_required('admin')
    def school_attendance_by_teacher(teacher_id):
        """School admin view attendance by specific teacher."""
        teacher = User.query.get(teacher_id)
        if not teacher or teacher.role != 'teacher':
            return "Teacher not found", 404

        classrooms = get_teacher_classrooms(teacher_id)

        attendance_data = {}
        for classroom in classrooms:
            students = Student.query.filter_by(classroom_id=classroom.id).all()
            records = Attendance.query.filter(
                Attendance.student_id.in_([s.id for s in students])
            ).order_by(Attendance.date.desc()).all()

            attendance_data[classroom.id] = {
                'class': classroom,
                'students': students,
                'records': records
            }

        return render_template(
            'school_attendance_teacher.html',
            teacher=teacher,
            attendance_data=attendance_data,
            classrooms=classrooms
        )

    @app.route('/school/attendance-by-class/<int:class_id>', methods=['GET'])
    @login_required
    @role_required('admin')
    def school_attendance_by_class(class_id):
        """School admin view attendance for specific class."""
        classroom = Classroom.query.get(class_id)
        if not classroom:
            return "Class not found", 404

        students = Student.query.filter_by(classroom_id=class_id).all()

        student_attendance = {}
        for student in students:
            records = Attendance.query.filter_by(student_id=student.id).order_by(
                Attendance.date.desc()
            ).all()
            percentage = calculate_attendance_percentage(student.id)
            student_attendance[student.id] = {
                'student': student,
                'records': records,
                'percentage': percentage
            }

        return render_template(
            'school_attendance_class.html',
            classroom=classroom,
            student_attendance=student_attendance
        )

    @app.route('/school/view-all-teachers', methods=['GET'])
    @login_required
    @role_required('admin')
    def view_all_teachers():
        """View all teachers in the school."""
        teachers = User.query.filter_by(role='teacher').all()
        return render_template('view_all_teachers.html', teachers=teachers)

    @app.route('/school/view-all-classes', methods=['GET'])
    @login_required
    @role_required('admin')
    def view_all_classes():
        """View all classes in the school with their assigned teachers."""
        classrooms = Classroom.query.all()
        return render_template('view_all_classes.html', classrooms=classrooms)

    @app.route('/school/view-all-students', methods=['GET'])
    @login_required
    @role_required('admin')
    def view_all_students():
        """View all students organized by class."""
        classrooms = Classroom.query.all()
        class_students = {}
        for classroom in classrooms:
            students = Student.query.filter_by(classroom_id=classroom.id).all()
            class_students[classroom.id] = {
                'classroom': classroom,
                'students': students
            }
        return render_template('view_all_students.html', class_students=class_students, classrooms=classrooms)

    # ==================== Admin Routes (Optional) ====================
    @app.route('/admin/setup', methods=['GET', 'POST'])
    def admin_setup():
        """Admin setup - create initial admin user and classrooms."""
        # Check if any admin exists
        admin_exists = User.query.filter_by(role='admin').first()

        if admin_exists and request.method == 'GET':
            return jsonify({'error': 'Setup already completed'}), 403

        if request.method == 'POST':
            data = request.get_json()

            # Create admin user
            admin = User(
                username=data.get('admin_username', 'admin'),
                role='admin'
            )
            admin.set_password(data.get('admin_password', 'admin123'))
            db.session.add(admin)
            db.session.flush()

            # Create sample teacher
            teacher = User(
                username=data.get('teacher_username', 'teacher1'),
                role='teacher'
            )
            teacher.set_password(data.get('teacher_password', 'teacher123'))
            db.session.add(teacher)
            db.session.flush()

            # Create sample classroom
            classroom = Classroom(
                name='1-A',
                teacher_id=teacher.id
            )
            db.session.add(classroom)

            # Create sample timetable
            timetable = Timetable(
                classroom_id=classroom.id,
                day_of_week='Monday',
                start_time=time(9, 0),
                end_time=time(10, 0),
                subject_name='Mathematics'
            )
            db.session.add(timetable)

            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Initial setup completed',
                'admin_username': data.get('admin_username', 'admin'),
                'teacher_username': data.get('teacher_username', 'teacher1')
            })

        return jsonify({'ready': not admin_exists})

    # ==================== Error Handlers ====================
    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('500.html'), 500
