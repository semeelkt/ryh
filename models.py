from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time

db = SQLAlchemy()

class User(db.Model):
    """User model for admin, teacher, and student accounts."""
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # admin, teacher, student
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    classrooms_as_class_teacher = db.relationship('Classroom', backref='class_teacher_user', lazy=True, foreign_keys='Classroom.class_teacher_id')
    teacher_classes = db.relationship('TeacherClass', backref='teacher', lazy=True, cascade='all, delete-orphan')
    student = db.relationship('Student', uselist=False, backref='user')

    def set_password(self, password):
        """Hash and set password."""
        self.password = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against hash."""
        return check_password_hash(self.password, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Classroom(db.Model):
    """Classroom model representing a class."""
    __tablename__ = 'classroom'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., '1-A', '2-B'
    class_teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)  # Optional class teacher
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    students = db.relationship('Student', backref='classroom', lazy=True, cascade='all, delete-orphan')
    timetables = db.relationship('Timetable', backref='classroom', lazy=True, cascade='all, delete-orphan')
    teacher_classes = db.relationship('TeacherClass', backref='classroom', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Classroom {self.name}>'

class TeacherClass(db.Model):
    """Junction model linking teachers to classes with roles."""
    __tablename__ = 'teacher_class'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default='subject_teacher')  # class_teacher, subject_teacher
    subject_name = db.Column(db.String(100), nullable=True)  # For subject teachers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('teacher_id', 'classroom_id', 'subject_name', name='unique_teacher_class_subject'),)

    def __repr__(self):
        return f'<TeacherClass {self.teacher.username} - {self.classroom.name}>'

class Student(db.Model):
    """Student model."""
    __tablename__ = 'student'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    roll_no = db.Column(db.String(20), nullable=False, index=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False, index=True)
    parent_email = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    attendance_records = db.relationship('Attendance', backref='student', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (db.UniqueConstraint('roll_no', 'classroom_id', name='unique_rollno_per_classroom'),)

    def __repr__(self):
        return f'<Student {self.name} ({self.roll_no})>'

class Attendance(db.Model):
    """Attendance record model."""
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False, default='Absent')  # Present, Absent
    period_name = db.Column(db.String(50), nullable=True)  # Optional: subject or period name
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('student_id', 'date', 'period_name', name='unique_attendance'),)

    def __repr__(self):
        return f'<Attendance {self.student_id} on {self.date} - {self.status}>'

class Timetable(db.Model):
    """Timetable model for classes."""
    __tablename__ = 'timetable'

    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False, index=True)
    day_of_week = db.Column(db.String(10), nullable=False)  # Monday, Tuesday, etc.
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('classroom_id', 'day_of_week', 'start_time', name='unique_timetable_slot'),)

    def __repr__(self):
        return f'<Timetable {self.subject_name} on {self.day_of_week}>'

class LeaveRequest(db.Model):
    """Leave request model for student leave applications."""
    __tablename__ = 'leave_request'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, index=True)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending')  # Pending, Approved, Rejected
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Teacher who approved/rejected
    approved_by = db.relationship('User', foreign_keys=[teacher_id], backref='leave_approvals')
    student = db.relationship('Student', backref='leave_requests')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<LeaveRequest {self.student.name} - {self.status}>'

