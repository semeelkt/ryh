#!/usr/bin/env python3
"""
Setup script for School Attendance System
Creates initial users for all roles, classroom, and sample timetable
"""

from app import create_app, db
from models import User, Classroom, Student, Timetable
from datetime import time

def setup():
    app = create_app()

    with app.app_context():
        # Clear existing data (optional - comment out to keep existing data)
        # db.drop_all()

        print("\n" + "="*70)
        print("SCHOOL ATTENDANCE SYSTEM - SETUP".center(70))
        print("="*70 + "\n")

        print("Setting up School Attendance System with test accounts...\n")

        # ==================== ADMIN ACCOUNT ====================
        admin = User(username='school', role='admin')
        admin.set_password('school123')
        db.session.add(admin)
        db.session.flush()
        print("✓ Created ADMIN account")
        print("   Username: school")
        print("   Password: school123\n")

        # ==================== TEACHER ACCOUNT ====================
        teacher = User(username='teacher', role='teacher')
        teacher.set_password('teacher123')
        db.session.add(teacher)
        db.session.flush()
        print("✓ Created TEACHER account")
        print("   Username: teacher")
        print("   Password: teacher123\n")

        # ==================== CLASSROOM ====================
        classroom = Classroom(
            name='1-A',
            class_teacher_id=teacher.id
        )
        db.session.add(classroom)
        db.session.flush()
        print("✓ Created classroom: Class 1-A\n")

        # ==================== SAMPLE STUDENTS ====================
        sample_students = [
            ('Aarav Kumar', '1001', 'aarav.parent@email.com'),
            ('Bhavna Singh', '1002', 'bhavna.parent@email.com'),
            ('Chirag Patel', '1003', 'chirag.parent@email.com'),
            ('Disha Sharma', '1004', 'disha.parent@email.com'),
            ('Esha Verma', '1005', 'esha.parent@email.com'),
        ]

        student_accounts = []
        for name, roll_no, parent_email in sample_students:
            # Create student user account
            student_user = User(username=roll_no, role='student')
            student_user.set_password(f'student_{roll_no}')
            db.session.add(student_user)
            db.session.flush()

            # Create student record
            student = Student(
                name=name,
                roll_no=roll_no,
                classroom_id=classroom.id,
                parent_email=parent_email,
                user_id=student_user.id
            )
            db.session.add(student)
            student_accounts.append((roll_no, f'student_{roll_no}'))

        print("✓ Created 5 STUDENT accounts:")
        for roll_no, password in student_accounts:
            print(f"   - Roll No: {roll_no}, Password: {password}")
        print()

        # ==================== TIMETABLE ====================
        timetable_entries = [
            ('Monday', time(9, 0), time(10, 0), 'Mathematics'),
            ('Monday', time(10, 0), time(11, 0), 'English'),
            ('Tuesday', time(9, 0), time(10, 0), 'Science'),
            ('Tuesday', time(10, 0), time(11, 0), 'Hindi'),
            ('Wednesday', time(9, 0), time(10, 0), 'History'),
            ('Wednesday', time(10, 0), time(11, 0), 'Geography'),
            ('Thursday', time(9, 0), time(10, 0), 'Mathematics'),
            ('Thursday', time(10, 0), time(11, 0), 'Computer Science'),
            ('Friday', time(9, 0), time(10, 0), 'Physical Education'),
            ('Friday', time(10, 0), time(11, 0), 'Art'),
        ]

        for day, start, end, subject in timetable_entries:
            timetable = Timetable(
                classroom_id=classroom.id,
                day_of_week=day,
                start_time=start,
                end_time=end,
                subject_name=subject
            )
            db.session.add(timetable)

        db.session.commit()
        print("✓ Created timetable with 10 class sessions\n")

        # ==================== DISPLAY SUMMARY ====================
        print("="*70)
        print("SETUP COMPLETE! LOGIN CREDENTIALS".center(70))
        print("="*70)

        print("\n┌─ SCHOOL/ADMIN ─────────────────────────────────────────────────────┐")
        print("│ Role:     Admin/School Administrator                               │")
        print("│ Username: school                                                   │")
        print("│ Password: school123                                                │")
        print("└────────────────────────────────────────────────────────────────────┘")

        print("\n┌─ TEACHER ──────────────────────────────────────────────────────────┐")
        print("│ Role:     Teacher                                                  │")
        print("│ Username: teacher                                                  │")
        print("│ Password: teacher123                                               │")
        print("│ Class:    1-A                                                      │")
        print("└────────────────────────────────────────────────────────────────────┘")

        print("\n┌─ STUDENTS ─────────────────────────────────────────────────────────┐")
        print("│ Role:     Students (Class 1-A)                                     │")
        print("│                                                                    │")
        for i, (roll_no, password) in enumerate(student_accounts, 1):
            print(f"│ Student {i}: Username: {roll_no:6} | Password: {password:15} │")
        print("└────────────────────────────────────────────────────────────────────┘")

        print("\n" + "="*70)
        print("START THE APPLICATION".center(70))
        print("="*70)
        print("\n  Command: python3 app.py")
        print("  URL:     http://localhost:5000")
        print("\n" + "="*70 + "\n")

if __name__ == '__main__':
    setup()
