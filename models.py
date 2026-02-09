"""
Database Models for Face Recognition Attendance System
SQLite database with students, faculty, and attendance tables
"""

import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Database file path
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')


def get_db_connection():
    """Create and return a database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            section TEXT NOT NULL,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create faculty table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            department TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create attendance table
    # Unique constraint prevents duplicate attendance for same student/subject/section/period/date
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            section TEXT NOT NULL,
            period TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT CHECK(status IN ('PRESENT', 'ABSENT')) NOT NULL,
            confidence REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, subject, section, period, date)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")


def sync_enrolled_students():
    """
    Sync enrolled students from embeddings folder to database.
    This replaces the sample data with real enrolled students.
    """
    import json
    from pathlib import Path
    
    # Path to embeddings config
    embeddings_path = Path(os.path.dirname(os.path.abspath(__file__))) / 'dataset' / 'embeddings'
    config_path = embeddings_path / 'config.json'
    
    if not config_path.exists():
        print("No enrolled students found. Run enroll_students.py first.")
        return []
    
    # Read enrolled students from config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    enrolled_names = config.get('students', [])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    synced = []
    for i, name in enumerate(enrolled_names, start=1):
        # Use name as roll_no (or generate one)
        roll_no = name  # Using name as roll_no for simplicity
        section = 'A'  # Default section
        image_path = f'dataset/{name}'
        
        try:
            cursor.execute(
                'INSERT INTO students (name, roll_no, section, image_path) VALUES (?, ?, ?, ?)',
                (name, roll_no, section, image_path)
            )
            synced.append({'name': name, 'roll_no': roll_no, 'status': 'added'})
        except sqlite3.IntegrityError:
            # Student already exists, update if needed
            cursor.execute(
                'UPDATE students SET name = ?, image_path = ? WHERE roll_no = ?',
                (name, image_path, roll_no)
            )
            synced.append({'name': name, 'roll_no': roll_no, 'status': 'updated'})
    
    conn.commit()
    conn.close()
    print(f"Synced {len(synced)} enrolled students to database")
    return synced


def clear_sample_students():
    """Remove sample students that are not in the enrolled list."""
    import json
    from pathlib import Path
    
    embeddings_path = Path(os.path.dirname(os.path.abspath(__file__))) / 'dataset' / 'embeddings'
    config_path = embeddings_path / 'config.json'
    
    enrolled_names = []
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
        enrolled_names = config.get('students', [])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all students
    all_students = cursor.execute('SELECT roll_no FROM students').fetchall()
    
    removed = 0
    for student in all_students:
        roll_no = student['roll_no']
        # Remove if not in enrolled list
        if roll_no not in enrolled_names:
            cursor.execute('DELETE FROM students WHERE roll_no = ?', (roll_no,))
            removed += 1
    
    conn.commit()
    conn.close()
    print(f"Removed {removed} sample students not in enrolled list")
    return removed


def add_student(name, roll_no, section='A', image_path=None):
    """Add a single student to database."""
    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO students (name, roll_no, section, image_path) VALUES (?, ?, ?, ?)',
            (name, roll_no, section, image_path or f'dataset/{name}')
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def seed_sample_data():
    """Seed database with enrolled students from embeddings (not sample data)."""
    # First sync enrolled students
    synced = sync_enrolled_students()
    
    # Seed faculty data
    conn = get_db_connection()
    cursor = conn.cursor()
    
    faculty_data = [
        ('Prof. Sharma', 'sharma@college.edu', 'password123', 'Computer Science'),
        ('Prof. Gupta', 'gupta@college.edu', 'password123', 'Computer Science'),
        ('Admin', 'admin@college.edu', 'admin123', 'Administration'),
    ]
    
    for name, email, password, department in faculty_data:
        try:
            password_hash = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO faculty (name, email, password_hash, department) VALUES (?, ?, ?, ?)',
                (name, email, password_hash, department)
            )
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()
    conn.close()
    print("Database seeded with enrolled students and faculty!")


# ========================================
# Student Database Operations
# ========================================

def get_all_students(section=None):
    """Get all students, optionally filtered by section."""
    conn = get_db_connection()
    if section:
        students = conn.execute(
            'SELECT * FROM students WHERE section = ? ORDER BY roll_no',
            (section,)
        ).fetchall()
    else:
        students = conn.execute('SELECT * FROM students ORDER BY roll_no').fetchall()
    conn.close()
    return [dict(s) for s in students]


def get_student_by_roll_no(roll_no):
    """Get a student by roll number."""
    conn = get_db_connection()
    student = conn.execute(
        'SELECT * FROM students WHERE roll_no = ?',
        (roll_no,)
    ).fetchone()
    conn.close()
    return dict(student) if student else None


def get_student_by_id(student_id):
    """Get a student by ID."""
    conn = get_db_connection()
    student = conn.execute(
        'SELECT * FROM students WHERE id = ?',
        (student_id,)
    ).fetchone()
    conn.close()
    return dict(student) if student else None


# ========================================
# Faculty Database Operations
# ========================================

def get_faculty_by_email(email):
    """Get a faculty member by email."""
    conn = get_db_connection()
    faculty = conn.execute(
        'SELECT * FROM faculty WHERE email = ?',
        (email,)
    ).fetchone()
    conn.close()
    return dict(faculty) if faculty else None


def verify_faculty_password(email, password):
    """Verify faculty credentials."""
    faculty = get_faculty_by_email(email)
    if faculty and check_password_hash(faculty['password_hash'], password):
        return faculty
    return None


# ========================================
# Attendance Database Operations
# ========================================

def mark_attendance(student_id, subject, section, period, date, time, status, confidence=0.0):
    """
    Mark attendance for a student.
    Returns True if successful, False if duplicate (already marked).
    """
    conn = get_db_connection()
    try:
        conn.execute(
            '''INSERT INTO attendance 
               (student_id, subject, section, period, date, time, status, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (student_id, subject, section, period, date, time, status, confidence)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Duplicate entry - student already marked for this session
        conn.close()
        return False


def update_attendance_status(student_id, subject, section, period, date, new_status, time=None):
    """Update an existing attendance record."""
    conn = get_db_connection()
    if time:
        conn.execute(
            '''UPDATE attendance 
               SET status = ?, time = ?
               WHERE student_id = ? AND subject = ? AND section = ? AND period = ? AND date = ?''',
            (new_status, time, student_id, subject, section, period, date)
        )
    else:
        conn.execute(
            '''UPDATE attendance 
               SET status = ?
               WHERE student_id = ? AND subject = ? AND section = ? AND period = ? AND date = ?''',
            (new_status, student_id, subject, section, period, date)
        )
    conn.commit()
    conn.close()


def get_attendance(subject=None, section=None, period=None, date=None, student_id=None):
    """Get attendance records with optional filters."""
    conn = get_db_connection()
    
    query = '''
        SELECT a.*, s.name as student_name, s.roll_no
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE 1=1
    '''
    params = []
    
    if subject:
        query += ' AND a.subject = ?'
        params.append(subject)
    if section:
        query += ' AND a.section = ?'
        params.append(section)
    if period:
        query += ' AND a.period = ?'
        params.append(period)
    if date:
        query += ' AND a.date = ?'
        params.append(date)
    if student_id:
        query += ' AND a.student_id = ?'
        params.append(student_id)
    
    query += ' ORDER BY a.time DESC'
    
    records = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in records]


def get_student_attendance_history(roll_no, limit=50):
    """Get attendance history for a specific student."""
    conn = get_db_connection()
    records = conn.execute('''
        SELECT a.*, s.name as student_name, s.roll_no
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE s.roll_no = ?
        ORDER BY a.date DESC, a.time DESC
        LIMIT ?
    ''', (roll_no, limit)).fetchall()
    conn.close()
    return [dict(r) for r in records]


def check_attendance_exists(student_id, subject, section, period, date):
    """Check if attendance already exists for a student in this session."""
    conn = get_db_connection()
    record = conn.execute(
        '''SELECT * FROM attendance 
           WHERE student_id = ? AND subject = ? AND section = ? AND period = ? AND date = ?''',
        (student_id, subject, section, period, date)
    ).fetchone()
    conn.close()
    return dict(record) if record else None


# Initialize database when module is imported
if __name__ == '__main__':
    init_db()
    seed_sample_data()
