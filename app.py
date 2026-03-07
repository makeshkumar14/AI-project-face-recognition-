"""
AI-Powered Face Recognition Attendance System
Flask Backend Application

Main entry point that integrates all modules:
- Database models (SQLite)
- Authentication routes
- Attendance control routes
- Face recognition module
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_cors import CORS
from datetime import datetime
import os

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Enable CORS for API endpoints
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ========================================
# Database Initialization
# ========================================
from models import init_db, seed_sample_data

# Initialize database on startup
with app.app_context():
    init_db()
    seed_sample_data()

# ========================================
# Register Blueprints
# ========================================
from routes.auth import auth_bp
from routes.attendance import attendance_bp

app.register_blueprint(auth_bp)
app.register_blueprint(attendance_bp)

# ========================================
# Template Routes (Frontend Pages)
# ========================================

@app.route('/')
def role_select():
    """Landing page - Role selection"""
    return render_template('role_select.html')


@app.route('/faculty_login', methods=['GET', 'POST'])
def faculty_login():
    """Faculty login page"""
    if request.method == 'POST':
        faculty_id = request.form.get('faculty_id')
        password = request.form.get('password')
        
        # Import here to avoid circular imports
        from models import verify_faculty_password, get_faculty_by_email
        
        # Try to verify with email/password
        faculty = verify_faculty_password(faculty_id, password)
        
        if not faculty:
            # Also try direct ID match for demo purposes
            faculty = get_faculty_by_email(faculty_id)
        
        if faculty_id and password:
            session['user_type'] = 'faculty'
            session['user_id'] = faculty_id
            session['user_name'] = faculty['name'] if faculty else 'Faculty'
            return redirect(url_for('select_subject'))
        
    return render_template('faculty_login.html')


@app.route('/select_subject', methods=['GET', 'POST'])
def select_subject():
    """Subject selection page - shown after faculty login"""
    if session.get('user_type') != 'faculty':
        return redirect(url_for('faculty_login'))
    
    if request.method == 'POST':
        subject = request.form.get('subject')
        if subject:
            session['current_subject'] = subject
            return redirect(url_for('select_class'))
    
    return render_template('subject_select.html')


@app.route('/select_class', methods=['GET', 'POST'])
def select_class():
    """Class (Department + Section) selection page"""
    if session.get('user_type') != 'faculty':
        return redirect(url_for('faculty_login'))
    
    if not session.get('current_subject'):
        return redirect(url_for('select_subject'))
    
    if request.method == 'POST':
        department = request.form.get('department')
        section = request.form.get('section')
        if department and section:
            session['current_department'] = department
            session['current_section'] = section
            return redirect(url_for('faculty_dashboard'))
    
    return render_template('class_select.html')


@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    """Student login page"""
    if request.method == 'POST':
        roll_number = request.form.get('roll_number')
        password = request.form.get('password')
        
        from models import get_student_by_roll_no
        student = get_student_by_roll_no(roll_number.upper()) if roll_number else None
        
        if roll_number and password:
            session['user_type'] = 'student'
            session['user_id'] = roll_number
            session['user_name'] = student['name'] if student else 'Student'
            return redirect(url_for('student_dashboard'))
        
    return render_template('student_login.html')


@app.route('/faculty_dashboard')
def faculty_dashboard():
    """Faculty dashboard - Main control panel"""
    if session.get('user_type') != 'faculty':
        return redirect(url_for('faculty_login'))
    return render_template('faculty_dashboard.html')


@app.route('/student_dashboard')
def student_dashboard():
    """Student dashboard - View attendance"""
    if session.get('user_type') != 'student':
        return redirect(url_for('student_login'))
    return render_template('student_dashboard.html')


# ========================================
# Legacy API Endpoints (for backward compatibility)
# ========================================

@app.route('/start', methods=['POST'])
def start_attendance():
    """Start the attendance recognition system (legacy endpoint)"""
    from attendance_logic import start_attendance_session
    
    # Get session info
    subject = session.get('current_subject', 'Unknown')
    section = session.get('current_section', 'A')
    period = request.json.get('period', '1') if request.is_json else '1'
    
    success, message = start_attendance_session(subject, section, period)
    
    return jsonify({
        'success': success,
        'message': message
    })


@app.route('/stop', methods=['POST'])
def stop_attendance():
    """Stop the attendance recognition system (legacy endpoint)"""
    from attendance_logic import stop_attendance_session
    
    success, result = stop_attendance_session()
    
    return jsonify({
        'success': success,
        'message': 'Attendance system stopped' if success else result,
        'result': result if success else None
    })


@app.route('/attendance', methods=['GET'])
def get_attendance():
    """Get attendance records (legacy endpoint)"""
    from attendance_logic import get_session_summary
    from models import get_all_students
    
    summary = get_session_summary()
    
    if summary:
        # Format for frontend compatibility
        attendance_data = []
        for student in summary['present']:
            attendance_data.append({
                'id': student['roll_no'],
                'name': student['name'],
                'date': summary['session']['date'],
                'time': student['time'],
                'status': 'present',
                'confidence': student.get('confidence', 0)
            })
        
        return jsonify(attendance_data)
    else:
        # Return sample data if no session
        return jsonify([])


@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('role_select'))


# ========================================
# Face Recognition Streaming (Optional)
# ========================================

@app.route('/video_feed')
def video_feed():
    """
    Video streaming route for face recognition.
    Returns MJPEG stream of webcam with face detection overlay.
    
    Note: This is optional and requires webcam access.
    """
    try:
        from face_recognition_module import WebcamCapture, face_manager, draw_face_boxes
        from attendance_logic import get_current_session, mark_present
        import cv2
        
        def generate_frames():
            cam = WebcamCapture()
            if not cam.start():
                yield b'--frame\r\nContent-Type: text/plain\r\n\r\nCamera not available\r\n'
                return
            
            # Load known faces
            face_manager.load_known_faces()
            
            while True:
                frame = cam.read_frame()
                if frame is None:
                    continue
                
                session_obj = get_current_session()
                
                if session_obj.is_active:
                    # Recognize faces
                    recognized = face_manager.recognize_faces(frame)
                    
                    # Mark attendance for recognized faces with confidence >= 40%
                    CONFIDENCE_THRESHOLD = 40.0
                    for face in recognized:
                        if face['confidence'] >= CONFIDENCE_THRESHOLD and face['name'] != 'Unknown':
                            # Use the student name (uppercase) as roll_no since that's how dataset folders are named
                            roll_no = face['roll_no'].upper()
                            mark_present(roll_no, face['confidence'])
                    
                    # Draw boxes
                    frame = draw_face_boxes(frame, recognized)
                
                # Encode frame
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    continue
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        return app.response_class(
            generate_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========================================
# Error Handlers
# ========================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ========================================
# Run Application
# ========================================

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Face Recognition Attendance System")
    print("="*50)
    print(f"Server starting at: http://localhost:5000")
    print(f"API endpoints available at: http://localhost:5000/api/")
    print("="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
