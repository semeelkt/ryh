# ryh — School Attendance System

A Flask-based web application for managing school attendance, timetables, and leave requests.

## Features

- **Admin (School)**: Manage teachers, classrooms, and student uploads via Excel
- **Teacher**: Mark attendance, manage timetables, approve/reject leave requests
- **Student**: View attendance records and submit leave requests

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run setup to create sample data:
   ```bash
   python setup.py
   ```

3. Start the application:
   ```bash
   python app.py
   ```

4. Open [http://localhost:5000](http://localhost:5000) in your browser.

## Demo Credentials

| Role    | Username | Password      |
|---------|----------|---------------|
| Admin   | school   | school123     |
| Teacher | teacher  | teacher123    |
| Student | 1001     | student_1001  |
