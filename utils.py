from models import db, Student, Attendance, Classroom, User
from werkzeug.security import generate_password_hash
import pandas as pd
from datetime import datetime

def calculate_attendance_percentage(student_id):
    """
    Calculate attendance percentage for a specific student.

    Args:
        student_id: The ID of the student

    Returns:
        A float representing the attendance percentage (0-100)
    """
    attendance_records = Attendance.query.filter_by(student_id=student_id).all()

    if not attendance_records:
        return 0.0

    total_count = len(attendance_records)
    present_count = sum(1 for record in attendance_records if record.status == 'Present')

    percentage = (present_count / total_count) * 100 if total_count > 0 else 0.0
    return round(percentage, 2)

def create_student_from_excel(row_data, classroom_id):
    """
    Create a student record and associated user account from Excel row data.

    Args:
        row_data: Dictionary with keys 'Name', 'Roll No', 'Parent Email'
        classroom_id: The ID of the classroom

    Returns:
        Tuple (success: bool, message: str, student: Student or None)
    """
    try:
        name = str(row_data.get('Name', '')).strip()
        roll_no = str(row_data.get('Roll No', '')).strip()
        parent_email = str(row_data.get('Parent Email', '')).strip()

        # Validation
        if not name or not roll_no or not parent_email:
            return False, "Missing required fields (Name, Roll No, Parent Email)", None

        # Check if roll number already exists in this classroom
        existing_student = Student.query.filter_by(
            classroom_id=classroom_id,
            roll_no=roll_no
        ).first()

        if existing_student:
            return False, f"Roll number {roll_no} already exists in this classroom", None

        # Create User account for student
        username = roll_no
        password = f"student_{roll_no}"

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return False, f"Username {username} already exists", None

        user = User(username=username, role='student')
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # Get the ID before committing

        # Create Student record
        student = Student(
            name=name,
            roll_no=roll_no,
            classroom_id=classroom_id,
            parent_email=parent_email,
            user_id=user.id
        )
        db.session.add(student)

        return True, f"Student {name} created successfully", student

    except Exception as e:
        return False, f"Error creating student: {str(e)}", None

def process_excel_upload(file_path, classroom_id):
    """
    Process an Excel file and create students.

    Args:
        file_path: Path to the Excel file
        classroom_id: The ID of the classroom

    Returns:
        Dictionary with 'success', 'total', 'created', 'errors'
    """
    result = {
        'success': True,
        'total': 0,
        'created': 0,
        'errors': []
    }

    try:
        # Read Excel file
        df = pd.read_excel(file_path)

        # Validate required columns
        required_columns = {'Name', 'Roll No', 'Parent Email'}
        if not required_columns.issubset(set(df.columns)):
            result['success'] = False
            result['errors'].append(f"Excel file must contain columns: {required_columns}")
            return result

        result['total'] = len(df)

        # Process each row
        for index, row in df.iterrows():
            success, message, student = create_student_from_excel(row.to_dict(), classroom_id)

            if success:
                result['created'] += 1
            else:
                result['errors'].append(f"Row {index + 2}: {message}")

        # Commit all changes
        if result['created'] > 0:
            db.session.commit()

        return result

    except pd.errors.EmptyDataError:
        result['success'] = False
        result['errors'].append("Excel file is empty")
        return result
    except Exception as e:
        result['success'] = False
        result['errors'].append(f"Error processing Excel file: {str(e)}")
        db.session.rollback()
        return result

def get_student_attendance_data(student_id):
    """
    Get attendance data for a student including percentage.

    Args:
        student_id: The ID of the student

    Returns:
        Dictionary with attendance info
    """
    student = Student.query.get(student_id)
    if not student:
        return None

    percentage = calculate_attendance_percentage(student_id)
    attendance_records = Attendance.query.filter_by(student_id=student_id).all()

    return {
        'student_id': student_id,
        'name': student.name,
        'roll_no': student.roll_no,
        'classroom_id': student.classroom_id,
        'percentage': percentage,
        'total_records': len(attendance_records),
        'present_count': sum(1 for r in attendance_records if r.status == 'Present'),
        'absent_count': sum(1 for r in attendance_records if r.status == 'Absent')
    }

def get_classroom_students(classroom_id):
    """
    Get all students in a classroom with attendance data.

    Args:
        classroom_id: The ID of the classroom

    Returns:
        List of student dictionaries with attendance data
    """
    students = Student.query.filter_by(classroom_id=classroom_id).all()

    return [
        {
            'id': student.id,
            'name': student.name,
            'roll_no': student.roll_no,
            'parent_email': student.parent_email,
            'attendance_percentage': calculate_attendance_percentage(student.id)
        }
        for student in students
    ]
