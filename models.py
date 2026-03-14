"""
Database Models for Face Recognition Attendance System
MySQL database with students, faculty, and attendance tables
"""

import mysql.connector
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# MySQL connection configuration (override via environment variables)
MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', 'makesh14'),
    'database': os.environ.get('MYSQL_DATABASE', 'face_recognition_db'),
}


def get_db_connection():
    """Create and return a MySQL database connection."""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    return conn


def init_db():
    """Initialize the database and required tables."""
    # First connect without specifying database to create it if needed
    init_config = {k: v for k, v in MYSQL_CONFIG.items() if k != 'database'}
    conn = mysql.connector.connect(**init_config)
    cursor = conn.cursor()
    
    db_name = MYSQL_CONFIG['database']
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
    cursor.execute(f"USE `{db_name}`")
    
    # Create students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            roll_no VARCHAR(100) UNIQUE NOT NULL,
            section VARCHAR(50) NOT NULL,
            image_path VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create faculty table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faculty (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(500) NOT NULL,
            department VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create attendance table
    # Unique constraint prevents duplicate attendance for same student/subject/section/period/date
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            subject VARCHAR(255) NOT NULL,
            section VARCHAR(50) NOT NULL,
            period VARCHAR(50) NOT NULL,
            date VARCHAR(20) NOT NULL,
            time VARCHAR(20) NOT NULL,
            status ENUM('PRESENT', 'ABSENT') NOT NULL,
            confidence FLOAT DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE KEY unique_attendance (student_id, subject, section, period, date)
        )
    ''')
    
    conn.commit()
    cursor.close()
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
    
    # Handle case where config is a list (take last entry)
    if isinstance(config, list):
        config = config[-1] if config else {}
    
    # Mapping of names to specific roll numbers as per user request
    # Using lowercase keys for case-insensitive matching
    ROLL_NO_MAP = {
        'makeshkumar': '693',
        'kavin': '647',
        'rohanbala': '648',
        'ratchagan': '655',
        'parkavan': '685',
        'boopathi': '686',
        'hasvandh': '696'
    }
    
    enrolled_names = config.get('students', [])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    synced = []
    for i, name in enumerate(enrolled_names, start=1):
        # Use specific roll number from mapping, or fall back to uppercase name
        roll_no = ROLL_NO_MAP.get(name.lower(), name.upper())
        student_name = name
        section = 'A'  # Default section
        image_path = f'dataset/{name}'
        
        try:
            # Check if student already exists by name (case-insensitive in MySQL usually)
            cursor.execute('SELECT id, roll_no FROM students WHERE name = %s', (student_name,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing student with new roll_no and image_path
                cursor.execute(
                    'UPDATE students SET roll_no = %s, image_path = %s WHERE id = %s',
                    (roll_no, image_path, existing[0])
                )
                synced.append({'name': name, 'roll_no': roll_no, 'status': 'updated'})
            else:
                # Insert new student
                cursor.execute(
                    'INSERT INTO students (name, roll_no, section, image_path) VALUES (%s, %s, %s, %s)',
                    (student_name, roll_no, section, image_path)
                )
                synced.append({'name': name, 'roll_no': roll_no, 'status': 'added'})
        except mysql.connector.IntegrityError as e:
            synced.append({'name': name, 'roll_no': roll_no, 'status': f'error: {str(e)}'})
    
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Synced {len(synced)} enrolled students to database")
    return synced


def clear_sample_students():
    """Remove sample students that are not in the enrolled list."""
    import json
    from pathlib import Path
    
    embeddings_path = Path(os.path.dirname(os.path.abspath(__file__))) / 'dataset' / 'embeddings'
    config_path = embeddings_path / 'config.json'
    
    enrolled_names_upper = []
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Handle case where config is a list (take last entry)
        if isinstance(config, list):
            config = config[-1] if config else {}
            
        enrolled_names = config.get('students', [])
        enrolled_names_upper = [n.upper() for n in enrolled_names]
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all students
    cursor.execute('SELECT roll_no FROM students')
    all_students = cursor.fetchall()
    
    removed = 0
    for student in all_students:
        roll_no = student['roll_no']
        # Remove if not in enrolled list
        if roll_no.upper() not in enrolled_names_upper:
            cursor.execute('DELETE FROM students WHERE roll_no = %s', (roll_no,))
            removed += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Removed {removed} sample students not in enrolled list")
    return removed


def add_student(name, roll_no, section='A', image_path=None):
    """Add a single student to database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO students (name, roll_no, section, image_path) VALUES (%s, %s, %s, %s)',
            (name, roll_no, section, image_path or f'dataset/{name}')
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.IntegrityError:
        cursor.close()
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
        ('Prof. Reddy', 'reddy@college.edu', 'password123', 'Electronics'),
        ('Prof. Iyer', 'iyer@college.edu', 'password123', 'Mathematics'),
        ('Prof. Patel', 'patel@college.edu', 'password123', 'Mechanical'),
        ('Admin', 'admin@college.edu', 'admin123', 'Administration'),
    ]
    
    for name, email, password, department in faculty_data:
        try:
            password_hash = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO faculty (name, email, password_hash, department) VALUES (%s, %s, %s, %s)',
                (name, email, password_hash, department)
            )
        except mysql.connector.IntegrityError:
            pass
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Database seeded with enrolled students and faculty!")


# ========================================
# Student Database Operations
# ========================================

def get_all_students(section=None):
    """Get all students, optionally filtered by section."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if section:
        cursor.execute(
            'SELECT * FROM students WHERE section = %s ORDER BY roll_no',
            (section,)
        )
    else:
        cursor.execute('SELECT * FROM students ORDER BY roll_no')
    students = cursor.fetchall()
    cursor.close()
    conn.close()
    return students


def get_student_by_roll_no(roll_no):
    """Get a student by roll number."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM students WHERE roll_no = %s',
        (roll_no,)
    )
    student = cursor.fetchone()
    cursor.close()
    conn.close()
    return student


def get_student_by_id(student_id):
    """Get a student by ID."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM students WHERE id = %s',
        (student_id,)
    )
    student = cursor.fetchone()
def get_student_by_name(name):
    """Get a student by name."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM students WHERE name = %s',
        (name,)
    )
    student = cursor.fetchone()
    cursor.close()
    conn.close()
    return student


# ========================================
# Faculty Database Operations
# ========================================

def get_faculty_by_email(email):
    """Get a faculty member by email."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM faculty WHERE email = %s',
        (email,)
    )
    faculty = cursor.fetchone()
    cursor.close()
    conn.close()
    return faculty


def verify_faculty_password(email, password):
    """Verify faculty credentials."""
    faculty = get_faculty_by_email(email)
    if faculty and check_password_hash(faculty['password_hash'], password):
        return faculty
    return None


def add_faculty(name, email, password, department='Computer Science'):
    """Add a new faculty member to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        password_hash = generate_password_hash(password)
        cursor.execute(
            'INSERT INTO faculty (name, email, password_hash, department) VALUES (%s, %s, %s, %s)',
            (name, email, password_hash, department)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.IntegrityError:
        cursor.close()
        conn.close()
        return False


# ========================================
# Attendance Database Operations
# ========================================

def mark_attendance(student_id, subject, section, period, date, time, status, confidence=0.0):
    """
    Mark attendance for a student.
    Returns True if successful, False if duplicate (already marked).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''INSERT INTO attendance 
               (student_id, subject, section, period, date, time, status, confidence)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
            (student_id, subject, section, period, date, time, status, confidence)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.IntegrityError:
        # Duplicate entry - student already marked for this session
        cursor.close()
        conn.close()
        return False


def update_attendance_status(student_id, subject, section, period, date, new_status, time=None):
    """Update an existing attendance record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if time:
        cursor.execute(
            '''UPDATE attendance 
               SET status = %s, time = %s
               WHERE student_id = %s AND subject = %s AND section = %s AND period = %s AND date = %s''',
            (new_status, time, student_id, subject, section, period, date)
        )
    else:
        cursor.execute(
            '''UPDATE attendance 
               SET status = %s
               WHERE student_id = %s AND subject = %s AND section = %s AND period = %s AND date = %s''',
            (new_status, student_id, subject, section, period, date)
        )
    conn.commit()
    cursor.close()
    conn.close()


def get_attendance(subject=None, section=None, period=None, date=None, student_id=None):
    """Get attendance records with optional filters."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = '''
        SELECT a.*, s.name as student_name, s.roll_no
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE 1=1
    '''
    params = []
    
    if subject:
        query += ' AND a.subject = %s'
        params.append(subject)
    if section:
        query += ' AND a.section = %s'
        params.append(section)
    if period:
        query += ' AND a.period = %s'
        params.append(period)
    if date:
        query += ' AND a.date = %s'
        params.append(date)
    if student_id:
        query += ' AND a.student_id = %s'
        params.append(student_id)
    
    query += ' ORDER BY a.time DESC'
    
    cursor.execute(query, params)
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    return records


def get_student_attendance_history(roll_no, limit=50):
    """Get attendance history for a specific student."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT a.*, s.name as student_name, s.roll_no
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE s.roll_no = %s
        ORDER BY a.date DESC, a.time DESC
        LIMIT %s
    ''', (roll_no, limit))
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    return records


def check_attendance_exists(student_id, subject, section, period, date):
    """Check if attendance already exists for a student in this session."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        '''SELECT * FROM attendance 
           WHERE student_id = %s AND subject = %s AND section = %s AND period = %s AND date = %s''',
        (student_id, subject, section, period, date)
    )
    record = cursor.fetchone()
    cursor.close()
    conn.close()
    return record


def delete_attendance(subject, section, period, date):
    """Delete all attendance records for a specific session."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''DELETE FROM attendance 
           WHERE subject = %s AND section = %s AND period = %s AND date = %s''',
        (subject, section, period, date)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return True


# Initialize database when module is imported
if __name__ == '__main__':
    init_db()
    seed_sample_data()
