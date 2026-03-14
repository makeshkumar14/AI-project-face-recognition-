"""
Attendance Logic Module
Manages attendance sessions and enforces business rules
"""

import threading
from datetime import datetime
from models import (
    get_all_students, 
    get_student_by_roll_no,
    mark_attendance, 
    check_attendance_exists,
    update_attendance_status,
    get_attendance
)


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
        self.period = None
        self.date = None
        self.start_time = None
        self.marked_students = set()  # Roll numbers already marked
        self.lock = threading.Lock()
    
    def start(self, subject, section, period, date=None):
        """
        Start a new attendance session.
        
        Args:
            subject: Subject name (e.g., "Artificial Intelligence")
            section: Class section (e.g., "A")
            period: Period number (e.g., "1")
            date: Optional date string (defaults to today)
        """
        with self.lock:
            if self.is_active:
                return False, "Session already running"
            
            self.subject = subject
            self.section = section
            self.period = str(period)
            self.date = date or datetime.now().strftime('%Y-%m-%d')
            self.start_time = datetime.now()
            self.marked_students = set()
            self.is_active = True
            
            # Load any existing attendance for this session (only PRESENT students)
            existing = get_attendance(
                subject=self.subject,
                section=self.section,
                period=self.period,
                date=self.date
            )
            for record in existing:
                if record.get('status') == 'PRESENT':
                    self.marked_students.add(record['roll_no'])
            
            return True, f"Session started for {subject} - Section {section}, Period {period}"
    
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
                    self.date
                )
                if not existing:
                    mark_attendance(
                        student_id=student['id'],
                        subject=self.subject,
                        section=self.section,
                        period=self.period,
                        date=self.date,
                        time=current_time,
                        status='ABSENT',
                        confidence=0.0
                    )
    
    def mark_student_present(self, roll_no, confidence=0.0):
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
            
            # Check if already in marked_students set (already marked PRESENT)
            if roll_no in self.marked_students:
                return False, f"Student {roll_no} already marked PRESENT"
            
            # Get student from database
            student = get_student_by_roll_no(roll_no)
            if not student:
                return False, f"Student {roll_no} not found"
            
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # Check if an ABSENT record already exists to UPDATE instead of INSERT
            existing = check_attendance_exists(
                student['id'], 
                self.subject, 
                self.section, 
                self.period, 
                self.date
            )
            
            if existing:
                update_attendance_status(
                    student['id'],
                    self.subject,
                    self.section,
                    self.period,
                    self.date,
                    'PRESENT',
                    current_time
                )
                success = True
            else:
                success = mark_attendance(
                    student_id=student['id'],
                    subject=self.subject,
                    section=self.section,
                    period=self.period,
                    date=self.date,
                    time=current_time,
                    status='PRESENT',
                    confidence=confidence
                )
            
            if success:
                self.marked_students.add(roll_no)
                return True, f"Marked {student['name']} ({roll_no}) as PRESENT"
            else:
                return False, f"Failed to mark {roll_no} as present"
    
    def mark_student_absent(self, roll_no):
        """
        Explicitly mark a student as absent (manual override).
        """
        with self.lock:
            if not self.subject:
                return False, "No session initialized"
            
            student = get_student_by_roll_no(roll_no)
            if not student:
                return False, f"Student {roll_no} not found"
            
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
                    period=self.period,
                    date=self.date,
                    time=current_time,
                    status='ABSENT',
                    confidence=0.0
                )
            
            # Remove from marked set if present
            self.marked_students.discard(roll_no)
            
            return True, f"Marked {student['name']} ({roll_no}) as ABSENT"
    
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
        
        all_students = get_all_students(section=self.section)
        attendance_records = get_attendance(
            subject=self.subject,
            section=self.section,
            period=self.period,
            date=self.date
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
                'period': self.period,
                'date': self.date,
                'is_active': self.is_active
            },
            'present': present,
            'absent': absent,
            'counts': {
                'total': total,
                'present': present_count,
                'absent': absent_count,
                'percentage': round((present_count / total * 100), 1) if total > 0 else 0
            }
        }


# Global session instance
current_session = AttendanceSession()


def get_current_session():
    """Get the global attendance session."""
    return current_session


def start_attendance_session(subject, section, period, date=None):
    """Convenience function to start a session."""
    return current_session.start(subject, section, period, date)


def stop_attendance_session():
    """Convenience function to stop the session."""
    return current_session.stop()


def mark_present(roll_no, confidence=0.0):
    """Convenience function to mark student present."""
    return current_session.mark_student_present(roll_no, confidence)


def mark_absent(roll_no):
    """Convenience function to mark student absent."""
    return current_session.mark_student_absent(roll_no)


def get_session_summary():
    """Convenience function to get session summary."""
    return current_session.get_session_summary()


def reset_session():
    """Convenience function to reset current session."""
    return current_session.reset()


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
