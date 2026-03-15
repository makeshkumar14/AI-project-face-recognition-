"""
Attendance Routes
Handles attendance session control and data retrieval
"""

import csv
import io
from datetime import datetime
from flask import Blueprint, request, jsonify, session, Response

from models import get_all_students, get_attendance, get_student_attendance_history
from attendance_logic import (
    get_faculty_session,
    start_attendance_session,
    stop_attendance_session,
    mark_present,
    mark_absent,
    get_session_summary
)

attendance_bp = Blueprint('attendance', __name__, url_prefix='/api')


@attendance_bp.route('/start_attendance', methods=['POST'])
def start_attendance():
    """
    Start an attendance session.
    
    Request JSON:
    {
        "subject": "Artificial Intelligence",
        "section": "A",
        "period": "1",
        "date": "2026-02-05"  (optional, defaults to today)
    }
    
    Response:
    {
        "success": true/false,
        "message": "...",
        "session": { subject, section, period, date }
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'message': 'No data provided'
        }), 400
    
    subject = data.get('subject', '').strip()
    section = data.get('section', '').strip()
    department = data.get('department', '').strip()
    period = str(data.get('period', '1')).strip()
    date = data.get('date')  # Optional
    
    # Validation
    if not subject:
        return jsonify({
            'success': False,
            'message': 'Subject is required'
        }), 400
    
    if not section:
        return jsonify({
            'success': False,
            'message': 'Section is required'
        }), 400
    
    if not period:
        return jsonify({
            'success': False,
            'message': 'Period is required'
        }), 400
    
    # Start the session
    faculty_id = session.get('user_id')
    success, message = start_attendance_session(subject, section, department, period, date, faculty_id=faculty_id)
    
    if success:
        session_obj = get_faculty_session(faculty_id)
        return jsonify({
            'success': True,
            'message': message,
            'session': session_obj.get_status()
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


@attendance_bp.route('/stop_attendance', methods=['POST'])
def stop_attendance():
    """
    Stop the current attendance session.
    This will mark all remaining students as ABSENT.
    
    Response:
    {
        "success": true/false,
        "message": "...",
        "result": { subject, section, period, date, duration, students_marked }
    }
    """
    faculty_id = session.get('user_id')
    success, result = stop_attendance_session(faculty_id)
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Attendance session stopped',
            'result': result
        })
    else:
        return jsonify({
            'success': False,
            'message': result
        }), 400


@attendance_bp.route('/session_status', methods=['GET'])
def session_status():
    """
    Get the current session status.
    """
    faculty_id = session.get('user_id')
    session_obj = get_faculty_session(faculty_id)
    return jsonify(session_obj.get_status())


@attendance_bp.route('/mark_present', methods=['POST'])
def mark_student_present():
    """
    Manually mark a student as present.
    
    Request JSON:
    {
        "roll_no": "CSE001",
        "confidence": 98.5  (optional)
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'message': 'No data provided'
        }), 400
    
    roll_no = data.get('roll_no', '').strip().upper()
    confidence = data.get('confidence', 0.0)
    
    if not roll_no:
        return jsonify({
            'success': False,
            'message': 'Roll number is required'
        }), 400
    
    faculty_id = session.get('user_id')
    success, message = mark_present(faculty_id, roll_no, confidence)
    
    return jsonify({
        'success': success,
        'message': message
    }), 200 if success else 400


@attendance_bp.route('/mark_absent', methods=['POST'])
def mark_student_absent():
    """
    Manually mark a student as absent.
    
    Request JSON:
    {
        "roll_no": "CSE001"
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'message': 'No data provided'
        }), 400
    
    roll_no = data.get('roll_no', '').strip().upper()
    
    if not roll_no:
        return jsonify({
            'success': False,
            'message': 'Roll number is required'
        }), 400
    
    faculty_id = session.get('user_id')
    success, message = mark_absent(faculty_id, roll_no)
    
    return jsonify({
        'success': success,
        'message': message
    }), 200 if success else 400


@attendance_bp.route('/get_attendance', methods=['GET'])
def get_attendance_data():
    """
    Get attendance data with filters.
    
    Query parameters:
    - subject: Filter by subject
    - section: Filter by section
    - period: Filter by period
    - date: Filter by date (YYYY-MM-DD)
    
    Response:
    {
        "success": true,
        "session": { ... },
        "present": [ { id, name, roll_no, time, confidence } ],
        "absent": [ { id, name, roll_no } ],
        "counts": { total, present, absent, percentage }
    }
    """
    # Check if we have an active session and no filters provided
    faculty_id = session.get('user_id')
    session_obj = get_faculty_session(faculty_id)
    
    subject = request.args.get('subject')
    section = request.args.get('section')
    period = request.args.get('period')
    date = request.args.get('date')
    
    # If session is active and no filters, use session data
    if session_obj.is_active and not any([subject, section]):
        summary = get_session_summary(faculty_id)
        if summary:
            return jsonify({
                'success': True,
                **summary
            })
    
    # Otherwise, query database
    if not section:
        section = session_obj.section or 'A'
    
    all_students = get_all_students(section=section)
    
    # Build attendance records
    attendance_records = get_attendance(
        subject=subject or session_obj.subject,
        section=section,
        period=period or session_obj.period,
        date=date or session_obj.date or datetime.now().strftime('%Y-%m-%d')
    )
    
    # Map by roll number
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
                'confidence': record.get('confidence', 0)
            })
        else:
            absent.append({
                'id': student['id'],
                'name': student['name'],
                'roll_no': roll
            })
    
    total = len(all_students)
    present_count = len(present)
    absent_count = len(absent)
    
    return jsonify({
        'success': True,
        'session': {
            'subject': subject or session_obj.subject,
            'section': section,
            'period': period or session_obj.period,
            'date': date or session_obj.date or datetime.now().strftime('%Y-%m-%d'),
            'is_active': session_obj.is_active
        },
        'present': present,
        'absent': absent,
        'counts': {
            'total': total,
            'present': present_count,
            'absent': absent_count,
            'percentage': round((present_count / total * 100), 1) if total > 0 else 0
        }
    })


@attendance_bp.route('/export_csv', methods=['GET'])
def export_csv():
    """
    ... (omitted docstring)
    """
    faculty_id = session.get('user_id')
    session_obj = get_faculty_session(faculty_id)
    
    subject = request.args.get('subject') or session_obj.subject or 'All'
    section = request.args.get('section') or session_obj.section or 'A'
    period = request.args.get('period') or session_obj.period or '1'
    date = request.args.get('date') or session_obj.date or datetime.now().strftime('%Y-%m-%d')
    
    # Get all students and attendance
    all_students = get_all_students(section=section)
    attendance_records = get_attendance(
        subject=subject if subject != 'All' else None,
        section=section,
        period=period,
        date=date
    )
    
    # Map by roll number
    attendance_map = {r['roll_no']: r for r in attendance_records}
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Roll No',
        'Name',
        'Section',
        'Subject',
        'Period',
        'Date',
        'Time',
        'Status',
        'Confidence'
    ])
    
    # Data rows
    for student in all_students:
        roll = student['roll_no']
        record = attendance_map.get(roll)
        
        if record:
            writer.writerow([
                roll,
                student['name'],
                section,
                subject,
                period,
                date,
                record['time'],
                record['status'],
                f"{record.get('confidence', 0)}%"
            ])
        else:
            writer.writerow([
                roll,
                student['name'],
                section,
                subject,
                period,
                date,
                '--',
                'ABSENT',
                '--'
            ])
    
    # Prepare response
    output.seek(0)
    filename = f"attendance_{subject}_{section}_{date}.csv"
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )


@attendance_bp.route('/students', methods=['GET'])
def get_students():
    """
    Get list of all students.
    
    Query parameters:
    - section: Filter by section (optional)
    """
    section = request.args.get('section')
    students = get_all_students(section=section)
    
    return jsonify({
        'success': True,
        'students': students,
        'count': len(students)
    })


@attendance_bp.route('/student_history/<roll_no>', methods=['GET'])
def student_history(roll_no):
    """
    Get attendance history for a specific student.
    """
    history = get_student_attendance_history(roll_no.upper())
    
    if history:
        return jsonify({
            'success': True,
            'roll_no': roll_no.upper(),
            'history': history,
            'count': len(history)
        })
    else:
        return jsonify({
            'success': True,
            'roll_no': roll_no.upper(),
            'history': [],
            'count': 0
        })
