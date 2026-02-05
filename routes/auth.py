"""
Authentication Routes
Handles faculty and student login/logout
"""

from flask import Blueprint, request, jsonify, session
from models import verify_faculty_password, get_student_by_roll_no, get_faculty_by_email

auth_bp = Blueprint('auth', __name__, url_prefix='/api')


@auth_bp.route('/login/faculty', methods=['POST'])
def faculty_login():
    """
    Faculty login endpoint.
    
    Request JSON:
    {
        "email": "faculty@college.edu",
        "password": "password123"
    }
    
    Response:
    {
        "success": true/false,
        "message": "...",
        "faculty": { id, name, email, department }
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'message': 'No data provided'
        }), 400
    
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({
            'success': False,
            'message': 'Email and password are required'
        }), 400
    
    # Verify credentials
    faculty = verify_faculty_password(email, password)
    
    if faculty:
        # Store in session
        session['user_type'] = 'faculty'
        session['user_id'] = faculty['id']
        session['user_email'] = faculty['email']
        session['user_name'] = faculty['name']
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'faculty': {
                'id': faculty['id'],
                'name': faculty['name'],
                'email': faculty['email'],
                'department': faculty.get('department', '')
            }
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Invalid email or password'
        }), 401


@auth_bp.route('/login/student', methods=['POST'])
def student_login():
    """
    Student login endpoint.
    
    Request JSON:
    {
        "roll_no": "CSE001",
        "password": "optional_password"  
    }
    
    Note: For demo purposes, any password works if roll_no exists.
    
    Response:
    {
        "success": true/false,
        "message": "...",
        "student": { id, name, roll_no, section }
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'message': 'No data provided'
        }), 400
    
    roll_no = data.get('roll_no', '').strip().upper()
    password = data.get('password', '')  # Optional for now
    
    if not roll_no:
        return jsonify({
            'success': False,
            'message': 'Roll number is required'
        }), 400
    
    # Find student
    student = get_student_by_roll_no(roll_no)
    
    if student:
        # Store in session
        session['user_type'] = 'student'
        session['user_id'] = student['id']
        session['user_roll_no'] = student['roll_no']
        session['user_name'] = student['name']
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'student': {
                'id': student['id'],
                'name': student['name'],
                'roll_no': student['roll_no'],
                'section': student['section']
            }
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Student not found'
        }), 404


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Logout endpoint - clears the session.
    """
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    })


@auth_bp.route('/session', methods=['GET'])
def get_session():
    """
    Get current session information.
    """
    if 'user_type' in session:
        return jsonify({
            'logged_in': True,
            'user_type': session.get('user_type'),
            'user_id': session.get('user_id'),
            'user_name': session.get('user_name')
        })
    else:
        return jsonify({
            'logged_in': False
        })
