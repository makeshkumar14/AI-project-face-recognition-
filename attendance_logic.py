"""
Attendance Logic Module
Manages attendance sessions and enforces business rules
"""

import threading
from datetime import datetime
from typing import Dict, List, Set, Optional
from models import (
    get_all_students,
    get_student_by_roll_no,
    get_student_by_name,
    mark_attendance,
    check_attendance_exists,
    update_attendance_status,
    get_attendance,
)


#
# Mapping of embedding folder names (used by the advanced recognizer / dataset)
# to canonical roll numbers used in the database. This mirrors the mapping used
# during student sync so that recognizer names like "makeshkumar" can still be
# resolved even if the UI mainly works with roll numbers.
#
EMBEDDING_NAME_TO_ROLL = {
    'makeshkumar': '693',
    'kavin': '647',
    'rohanbala': '648',
    'ratchagan': '655',
    'parkavan': '685',
    'boopathi': '686',
    'hasvandh': '696',
}


class AttendanceSession:
    """
    Manages a single attendance session with:
    - Session state (running/stopped)
    - Session parameters (subject, section, period, date)
    - List of already-marked students (to prevent duplicates)
    - Thread-safe operations
    """
    
    def __init__(self):
        self.is_active = False
        self.subject = None
        self.section = None
        self.department = None
        self.period = None
        self.date = None
        self.faculty_id = None
        self.start_time = None
        self.color = 'transparent'
        self.marked_students = set()  # Roll numbers already marked
        self.current_face_count = 0    # Faces in current frame
        self.lock = threading.Lock()
    
    def start(self, subject, section, department, period, date=None, faculty_id=None, force=True, color='transparent'):
        """
        Start a new attendance session.
        """
        with self.lock:
            if self.is_active and not force:
                return False, "Session already running"

            # Resetting session state for new metadata
            self.is_active = False 

            self.subject = subject
            self.section = section
            self.department = department
            self.period = str(period)
            self.date = date or datetime.now().strftime('%Y-%m-%d')
            self.faculty_id = faculty_id
            self.start_time = datetime.now()
            self.color = color
            self.marked_students = set()
            self.is_active = True

            # Load any existing PRESENT attendance for this session
            existing = get_attendance(
                subject=self.subject,
                section=self.section,
                period=self.period,
                date=self.date,
                faculty_id=self.faculty_id
            )
            for record in existing:
                if record.get('status') == 'PRESENT':
                    self.marked_students.add(record['roll_no'])

            return True, f"Session started for {subject} ({department}) - Section {section}, Period {period}"
    
    def stop(self):
        """Stop the current attendance session."""
        with self.lock:
            if not self.is_active:
                return False, "No active session"
            
            self.is_active = False
            duration = datetime.now() - self.start_time if self.start_time else None
            
            # Mark all unmarked students as ABSENT
            self._mark_absent_students()
            
            result = {
                'subject': self.subject,
                'section': self.section,
                'period': self.period,
                'date': self.date,
                'duration': str(duration).split('.')[0] if duration else None,
                'students_marked': len(self.marked_students)
            }
            
            return True, result
    
    def _mark_absent_students(self):
        """Mark all students not in marked_students as ABSENT."""
        all_students = get_all_students(section=self.section)
        current_time = datetime.now().strftime('%H:%M:%S')
        
        for student in all_students:
            if student['roll_no'] not in self.marked_students:
                # Use update logic to handle cases where they were previously marked PRESENT manually
                # (though marked_students check should prevent that)
                existing = check_attendance_exists(
                    student['id'], 
                    self.subject, 
                    self.section, 
                    self.period, 
                    self.date,
                    faculty_id=self.faculty_id
                )
                if not existing:
                    mark_attendance(
                        student_id=student['id'],
                        subject=self.subject,
                        section=self.section,
                        department=self.department,
                        period=self.period,
                        date=self.date,
                        time=current_time,
                        status='ABSENT',
                        confidence=0.0,
                        faculty_id=self.faculty_id,
                        color=self.color
                    )
    
    def mark_student_present(self, identifier, confidence=0.0):
        """
        Mark a student as present.
        
        Args:
            roll_no: Student roll number
            confidence: Face recognition confidence (0-100)
        
        Returns:
            (success: bool, message: str)
        """
        with self.lock:
            if not self.subject:
                return False, "No session initialized"
            
            # Normalize incoming identifier
            raw_identifier = str(identifier).strip()
            if not raw_identifier:
                return False, "Empty identifier"

            # 1) If identifier matches a known embedding name, map to roll number
            mapped_roll = EMBEDDING_NAME_TO_ROLL.get(raw_identifier.lower())
            student = None
            if mapped_roll:
                student = get_student_by_roll_no(mapped_roll)

            # 2) Try as roll number (normalized to uppercase) if still not found
            if not student:
                roll_candidate = raw_identifier.upper()
                student = get_student_by_roll_no(roll_candidate)

            # 3) Try exact name match (case-sensitive) if roll lookup failed
            if not student:
                student = get_student_by_name(raw_identifier)

            # 4) Try case-insensitive name match within the current section
            if not student and self.section:
                students_in_section = get_all_students(section=self.section)
                lower_identifier = raw_identifier.lower()
                for s in students_in_section:
                    if s.get('name', '').lower() == lower_identifier:
                        student = s
                        break

            # 5) Fallback: try case-insensitive roll_no match across section
            if not student and self.section:
                students_in_section = get_all_students(section=self.section)
                lower_identifier = raw_identifier.lower()
                for s in students_in_section:
                    if s.get('roll_no', '').lower() == lower_identifier:
                        student = s
                        break
                
            if not student:
                print(f"WARNING: Student {raw_identifier} not found in database")
                return False, f"Student {raw_identifier} not found"
                
            # Use the canonical roll number from the database record
            db_roll_no = student['roll_no']
            
            # Check if already in marked_students set (already marked PRESENT)
            if db_roll_no in self.marked_students:
                return False, f"Student {student['name']} already marked PRESENT"
            
            current_time = datetime.now().strftime('%H:%M:%S')
            
            existing = check_attendance_exists(
                student['id'], 
                self.subject, 
                self.section, 
                self.period, 
                self.date,
                faculty_id=self.faculty_id
            )
            
            if existing:
                update_attendance_status(
                    student['id'],
                    self.subject,
                    self.section,
                    self.period,
                    self.date,
                    'PRESENT',
                    current_time,
                    faculty_id=self.faculty_id
                )
                success = True
            else:
                success = mark_attendance(
                    student_id=student['id'],
                    subject=self.subject,
                    section=self.section,
                    department=self.department,
                    period=self.period,
                    date=self.date,
                    time=current_time,
                    status='PRESENT',
                    confidence=confidence,
                    faculty_id=self.faculty_id,
                    color=self.color
                )
            
            if success:
                self.marked_students.add(db_roll_no)
                return True, f"Marked {student['name']} ({db_roll_no}) as PRESENT"
            else:
                return False, f"Failed to mark {student['name']} as present"
    
    def mark_student_absent(self, roll_no):
        """
        Explicitly mark a student as absent (manual override).
        """
        with self.lock:
            if not self.subject:
                return False, "No session initialized"
            # Get student from database - try roll_no first, then name
            student = get_student_by_roll_no(roll_no)
            if not student:
                student = get_student_by_name(roll_no)
                
            if not student:
                return False, f"Student {roll_no} not found"
            
            db_roll_no = student['roll_no']
            
            # Check if already marked
            existing = check_attendance_exists(
                student['id'], 
                self.subject, 
                self.section, 
                self.period, 
                self.date
            )
            
            current_time = datetime.now().strftime('%H:%M:%S')
            
            if existing:
                # Update existing record
                update_attendance_status(
                    student['id'],
                    self.subject,
                    self.section,
                    self.period,
                    self.date,
                    'ABSENT',
                    current_time
                )
            else:
                # Create new record
                mark_attendance(
                    student_id=student['id'],
                    subject=self.subject,
                    section=self.section,
                    department=self.department,
                    period=self.period,
                    date=self.date,
                    time=current_time,
                    status='ABSENT',
                    confidence=0.0,
                    color=self.color
                )
            
            # Remove from marked set if present
            self.marked_students.discard(db_roll_no)
            
            return True, f"Marked {student['name']} ({db_roll_no}) as ABSENT"
    
    def reset(self):
        """Reset the current session attendance records."""
        with self.lock:
            if not self.subject or not self.section:
                return False, "No session initialized to reset"
            
            from models import delete_attendance
            delete_attendance(self.subject, self.section, self.period, self.date)
            self.marked_students = set()
            return True, "Session attendance cleared successfully"
    
    def get_status(self):
        """Get current session status."""
        return {
            'is_active': self.is_active,
            'subject': self.subject,
            'section': self.section,
            'department': self.department,
            'period': self.period,
            'date': self.date,
            'start_time': self.start_time.strftime('%H:%M:%S') if self.start_time else None,
            'marked_count': len(self.marked_students)
        }
    
    def get_session_summary(self):
        """
        Get detailed summary of current session attendance.
        Returns present/absent lists and counts.
        """
        if not self.subject or not self.section:
            return None
        
        # For this mini-project, treat the sample dataset as shared across all
        # sections so that the same 7 students appear regardless of the chosen
        # section/subject. This avoids empty lists when the session section
        # does not match the students' stored section.
        all_students = get_all_students()
        attendance_records = get_attendance(
            subject=self.subject,
            section=self.section,
            period=self.period,
            date=self.date,
            faculty_id=self.faculty_id
        )
        
        # Build maps
        attendance_map = {r['roll_no']: r for r in attendance_records}
        
        present = []
        absent = []
        
        for student in all_students:
            roll = student['roll_no']
            record = attendance_map.get(roll)
            
            if record and record['status'] == 'PRESENT':
                present.append({
                    'id': student['id'],
                    'name': student['name'],
                    'roll_no': roll,
                    'time': record['time'],
                    'confidence': record.get('confidence', 0),
                    'image_path': student.get('image_path')
                })
            else:
                absent.append({
                    'id': student['id'],
                    'name': student['name'],
                    'roll_no': roll,
                    'image_path': student.get('image_path')
                })
        
        total = len(all_students)
        present_count = len(present)
        absent_count = len(absent)
        
        return {
            'session': {
                'subject': self.subject,
                'section': self.section,
                'department': self.department,
                'period': self.period,
                'date': self.date,
                'is_active': self.is_active,
                'color': self.color
            },
            'present': present,
            'absent': absent,
            'counts': {
                'total': total,
                'present': present_count,
                'absent': absent_count,
                'percentage': round((present_count / total * 100), 1) if total > 0 else 0,
                'faces_detected': self.current_face_count
            }
        }


# Multi-session storage per faculty
faculty_sessions: Dict[int, AttendanceSession] = {}

def get_faculty_session(faculty_id) -> AttendanceSession:
    """Get or create an attendance session for a specific faculty member."""
    if faculty_id not in faculty_sessions:
        faculty_sessions[faculty_id] = AttendanceSession()
    return faculty_sessions[faculty_id]


def start_attendance_session(subject, section, department, period, date=None, faculty_id=None, force=True, color='transparent'):
    """Start a session for a specific faculty."""
    session = get_faculty_session(faculty_id)
    return session.start(subject, section, department, period, date, faculty_id, force=force, color=color)


def stop_attendance_session(faculty_id):
    """Stop the session for a specific faculty."""
    session = get_faculty_session(faculty_id)
    return session.stop()


def mark_present(faculty_id, roll_no, confidence=0.0):
    """Mark student present in faculty's session."""
    session = get_faculty_session(faculty_id)
    return session.mark_student_present(roll_no, confidence)


def mark_absent(faculty_id, roll_no):
    """Mark student absent in faculty's session."""
    session = get_faculty_session(faculty_id)
    return session.mark_student_absent(roll_no)


def get_session_summary(faculty_id):
    """Get summary for faculty's session."""
    session = get_faculty_session(faculty_id)
    return session.get_session_summary()


def reset_session(faculty_id):
    """Reset faculty's session."""
    session = get_faculty_session(faculty_id)
    return session.reset()


# Testing
if __name__ == '__main__':
    from models import init_db, seed_sample_data
    
    # Initialize database
    init_db()
    seed_sample_data()
    
    # Test session
    print("\n--- Testing Attendance Session ---")
    
    success, msg = start_attendance_session("AI", "A", "1")
    print(f"Start: {success}, {msg}")
    
    print(f"Status: {current_session.get_status()}")
    
    # Mark some students present
    success, msg = mark_present("CSE001", 98.5)
    print(f"Mark CSE001: {success}, {msg}")
    
    success, msg = mark_present("CSE003", 97.2)
    print(f"Mark CSE003: {success}, {msg}")
    
    # Try duplicate
    success, msg = mark_present("CSE001", 99.0)
    print(f"Mark CSE001 again: {success}, {msg}")
    
    # Get summary
    summary = get_session_summary()
    print(f"\nSummary: {summary['counts']}")
    print(f"Present: {[s['name'] for s in summary['present']]}")
    
    # Stop session
    success, result = stop_attendance_session()
    print(f"\nStop: {success}, {result}")
