"""
AI-Powered Face Recognition Attendance System
Flask Backend Application

Main entry point that integrates all modules:
- Database models (MySQL)
- Authentication routes
- Attendance control routes
- Face recognition module
"""

from datetime import datetime
import os
import glob
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_from_directory
from flask_cors import CORS

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

# Pre-load face recognition models to prevent delay when opening camera
import threading
def preload_models():
    print("Pre-loading Face Recognition models in background...")
    try:
        from advanced_face_recognition import get_recognizer
        get_recognizer()
        print("Advanced Face Recognition models pre-loaded successfully!")
    except Exception as e:
        print(f"Could not pre-load advanced models: {e}")
        try:
            from face_recognition_module import face_manager
            face_manager.load_known_faces()
            print("Basic Face Recognition models pre-loaded!")
        except:
            pass

threading.Thread(target=preload_models, daemon=True).start()

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
    """Faculty login page - sign in only, no registration"""
    message = request.args.get('message')
    message_type = request.args.get('message_type', 'error')
    
    if request.method == 'POST':
        faculty_id = request.form.get('faculty_id', '').strip()
        password = request.form.get('password', '')
        
        if not faculty_id or not password:
            return render_template('faculty_login.html',
                                 message='Email and password are required.',
                                 message_type='error')
        
        # Import here to avoid circular imports
        from models import verify_faculty_password
        
        # Strictly verify credentials against the database
        faculty = verify_faculty_password(faculty_id, password)
        
        if faculty:
            session['user_type'] = 'faculty'
            session['user_id'] = faculty['id']
            session['user_name'] = faculty['name']
            return redirect(url_for('select_subject'))
        else:
            return render_template('faculty_login.html',
                                 message='Invalid credentials. Please register if you do not have an account.',
                                 message_type='error',
                                 show_register_option=True)
        
    return render_template('faculty_login.html', message=message, message_type=message_type)


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
    message = request.args.get('message')
    message_type = request.args.get('message_type', 'error')
    
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
        
    return render_template('student_login.html', message=message, message_type=message_type)


@app.route('/faculty_register', methods=['POST'])
def faculty_register():
    """Faculty registration endpoint"""
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not name or not email or not password:
        return render_template('faculty_login.html', 
                             message='All fields are required', 
                             message_type='error',
                             show_register=True)
    
    if password != confirm_password:
        return render_template('faculty_login.html', 
                             message='Passwords do not match', 
                             message_type='error',
                             show_register=True)
    
    if len(password) < 4:
        return render_template('faculty_login.html', 
                             message='Password must be at least 4 characters', 
                             message_type='error',
                             show_register=True)
    
    from models import add_faculty
    success = add_faculty(name, email, password)
    
    if success:
        return redirect(url_for('faculty_login', 
                               message='Registration successful! Please sign in.',
                               message_type='success'))
    else:
        return render_template('faculty_login.html', 
                             message='Email already registered', 
                             message_type='error',
                             show_register=True)


@app.route('/student_register', methods=['POST'])
def student_register():
    """Student registration endpoint"""
    name = request.form.get('name', '').strip()
    roll_number = request.form.get('roll_number', '').strip().upper()
    section = request.form.get('section', '').strip().upper()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not name or not roll_number or not section or not password:
        return render_template('student_login.html', 
                             message='All fields are required', 
                             message_type='error',
                             show_register=True)
    
    if password != confirm_password:
        return render_template('student_login.html', 
                             message='Passwords do not match', 
                             message_type='error',
                             show_register=True)
    
    if len(password) < 4:
        return render_template('student_login.html', 
                             message='Password must be at least 4 characters', 
                             message_type='error',
                             show_register=True)
    
    from models import add_student
    success = add_student(name, roll_number, section)
    
    if success:
        return redirect(url_for('student_login', 
                               message='Registration successful! Please sign in.',
                               message_type='success'))
    else:
        return render_template('student_login.html', 
                             message='Roll number already registered', 
                             message_type='error',
                             show_register=True)


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
# Student & Attendance Data API
# ========================================

@app.route('/api/sync_students', methods=['POST'])
def api_sync_students():
    """Sync enrolled students from embeddings to database."""
    from models import sync_enrolled_students, clear_sample_students
    
    # Clear old sample students
    removed = clear_sample_students()
    
    # Sync enrolled students
    synced = sync_enrolled_students()
    
    return jsonify({
        'success': True,
        'message': f'Synced {len(synced)} students, removed {removed} old entries',
        'synced': synced
    })


@app.route('/api/students', methods=['GET'])
def api_get_students():
    """Get all enrolled students from database."""
    from models import get_all_students
    
    students = get_all_students()
    return jsonify({
        'success': True,
        'students': students,
        'total': len(students)
    })


@app.route('/api/attendance_data', methods=['GET'])
def api_attendance_data():
    """Get current attendance data for the running session."""
    from attendance_logic import get_session_summary
    from models import get_all_students
    
    summary = get_session_summary()
    
    # Get all students, filtered by the current session's section if available
    current_section = summary['session'].get('section') if summary else None
    all_students = get_all_students(section=current_section)
    
    if not summary:
        # No active session - show students in the current section as absent
        return jsonify({
            'success': True,
            'session_active': False,
            'present': [],
            'absent': [{'id': s['roll_no'], 'name': s['name']} for s in all_students],
            'total': len(all_students),
            'present_count': 0,
            'absent_count': len(all_students)
        })
    
    # Format present students
    present = []
    present_roll_nos = set()
    for s in summary.get('present', []):
        present_roll_nos.add(s['roll_no'])
        present.append({
            'id': s['roll_no'],
            'name': s['name'],
            'time': s.get('time', '--:--'),
            'confidence': s.get('confidence', 0),
            'image_url': f"/api/student_image/{s.get('image_path', '').replace('dataset/', '')}" if s.get('image_path') else None
        })
    
    # Calculate absent (all students in THIS section not in present)
    absent = []
    for s in all_students:
        if s['roll_no'] not in present_roll_nos:
            absent.append({
                'id': s['roll_no'],
                'name': s['name'],
                'image_url': f"/api/student_image/{s.get('image_path', '').replace('dataset/', '')}" if s.get('image_path') else None
            })
    
    return jsonify({
        'success': True,
        'session_active': True,
        'session': summary['session'],
        'present': present,
        'absent': absent,
        'total': len(all_students),
        'present_count': len(present),
        'absent_count': len(absent)
    })


@app.route('/api/student_image/<path:student_dir>')
def get_student_image(student_dir):
    """Serve the first valid image found in the student's dataset directory."""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dataset')
    full_path = os.path.join(base_dir, student_dir)
    
    # Try case-insensitive folder match if path doesn't exist
    if not os.path.isdir(full_path):
        target = student_dir.lower()
        if os.path.exists(base_dir):
            for d in os.listdir(base_dir):
                if d.lower() == target:
                    full_path = os.path.join(base_dir, d)
                    break
    
    if os.path.isdir(full_path):
        # Look for image files with various extensions
        patterns = ["*.[jJ][pP][gG]", "*.[jJ][pP][eE][gG]", "*.[pP][nN][gG]", "*.[wW][eE][bB][pP]"]
        image_files = []
        for p in patterns:
            image_files.extend(glob.glob(os.path.join(full_path, p)))
        
        # Sort and return the first non-empty image
        image_files.sort()
        for img_path in image_files:
            try:
                if os.path.getsize(img_path) > 0:
                    filename = os.path.basename(img_path)
                    return send_from_directory(os.path.dirname(img_path), filename)
            except Exception as e:
                continue
            
    # Return 404 if no image found
    return "Image not found", 404


@app.route('/api/reset_session', methods=['POST'])
def api_reset_session():
    """Reset the current attendance session."""
    from attendance_logic import reset_session
    success, message = reset_session()
    return jsonify({
        'success': success,
        'message': message
    })


@app.route('/api/export_excel', methods=['GET'])
def api_export_excel():
    """Export attendance data to Excel file."""
    from attendance_logic import get_session_summary
    from models import get_all_students
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from datetime import datetime
    import io
    
    summary = get_session_summary()
    all_students = get_all_students()
    
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Report"
    
    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    present_fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
    absent_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Session info
    session_info = summary.get('session', {}) if summary else {}
    ws['A1'] = "Attendance Report"
    ws['A1'].font = Font(bold=True, size=16)
    ws['A2'] = f"Date: {session_info.get('date', datetime.now().strftime('%Y-%m-%d'))}"
    ws['A3'] = f"Subject: {session_info.get('subject', 'N/A')}"
    ws['A4'] = f"Section: {session_info.get('section', 'A')}"
    ws['A5'] = f"Period: {session_info.get('period', 'N/A')}"
    
    # Headers (row 7)
    headers = ['S.No', 'Roll No', 'Student Name', 'Status', 'Time', 'Confidence (%)']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=7, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border
    
    # Collect present roll numbers
    present_data = {}
    if summary:
        for s in summary.get('present', []):
            present_data[s['roll_no']] = {
                'time': s.get('time', '--:--'),
                'confidence': s.get('confidence', 0)
            }
    
    # Data rows
    row_num = 8
    for i, student in enumerate(all_students, 1):
        roll_no = student['roll_no']
        is_present = roll_no in present_data
        
        status = 'PRESENT' if is_present else 'ABSENT'
        time_str = present_data[roll_no]['time'] if is_present else '--'
        confidence = present_data[roll_no]['confidence'] if is_present else 0
        
        row_data = [i, roll_no, student['name'], status, time_str, f"{confidence:.1f}" if confidence else '--']
        
        for col, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')
            
            # Color status cell
            if col == 4:  # Status column
                cell.fill = present_fill if is_present else absent_fill
        
        row_num += 1
    
    # Summary row
    present_count = len(present_data)
    absent_count = len(all_students) - present_count
    ws.cell(row=row_num + 1, column=1, value="Summary:").font = Font(bold=True)
    ws.cell(row=row_num + 1, column=2, value=f"Present: {present_count}")
    ws.cell(row=row_num + 1, column=3, value=f"Absent: {absent_count}")
    ws.cell(row=row_num + 1, column=4, value=f"Total: {len(all_students)}")
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 15
    
    # Save to bytes buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    # Generate filename
    date_str = session_info.get('date', datetime.now().strftime('%Y-%m-%d'))
    subject = session_info.get('subject', 'Attendance')
    filename = f"Attendance_{subject}_{date_str}.xlsx"
    
    from flask import send_file
    return send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


# ========================================
# Face Recognition Streaming (Advanced)
# ========================================

@app.route('/video_feed')
def video_feed():
    """
    Video streaming route for face recognition.
    Uses Advanced Face Recognition with:
    - MTCNN detection
    - FaceNet embeddings
    - Multi-frame voting
    - High precision mode
    """
    try:
        import sys
        import os
        
        # Add torch path
        TORCH_PATH = os.path.join(os.environ.get('TEMP', '/tmp'), 'torch_temp')
        if TORCH_PATH not in sys.path:
            sys.path.insert(0, TORCH_PATH)
        
        from face_recognition_module import WebcamCapture
        from attendance_logic import get_current_session, mark_present
        import cv2
        import time
        
        # Try to use advanced recognizer, fall back to basic if not available
        try:
            from advanced_face_recognition import get_recognizer, draw_recognition_boxes
            recognizer = get_recognizer()
            use_advanced = True
            print("Using Advanced Face Recognition (MTCNN + FaceNet)")
        except Exception as e:
            print(f"Advanced recognition not available: {e}")
            print("Falling back to basic recognition")
            from face_recognition_module import face_manager, draw_face_boxes
            face_manager.load_known_faces()
            use_advanced = False
        
        def generate_frames():
            cam = WebcamCapture()
            try:
                if not cam.start():
                    yield b'--frame\r\nContent-Type: text/plain\r\n\r\nCamera not available\r\n'
                    return
                
                # Frame counter for voting system
                frame_count = 0
                last_advanced_results = []
                last_basic_results = []
                
                while True:
                    frame = cam.read_frame()
                    
                    if frame is None:
                        time.sleep(0.01)
                        continue
                    
                    session_obj = get_current_session()
                    display_frame = frame.copy()
                    
                    if session_obj.is_active:
                        try:
                            if use_advanced:
                                # Advanced recognition: Process every 5th frame to reduce lag
                                if frame_count % 5 == 0:
                                    results = recognizer.recognize_frame(frame)
                                    recognizer.add_to_voting_buffer(results)
                                    last_advanced_results = results
                                    
                                    # Check for confirmed recognition via voting
                                    voting_result = recognizer.get_voting_result()
                                    if voting_result and voting_result['status'] == 'confirmed':
                                        # Mark attendance for confirmed recognition
                                        name = voting_result['name']
                                        confidence = voting_result['confidence']
                                        
                                        # Use name as roll_no (can be customized)
                                        mark_present(name, confidence * 100)
                                        print(f"Attendance marked: {name} (conf: {confidence:.2f})")
                                        
                                        # Clear buffer after successful recognition
                                        recognizer.clear_voting_buffer()
                                
                                # Draw boxes on frame using cached results
                                display_frame = draw_recognition_boxes(display_frame, last_advanced_results)
                            else:
                                # Fallback to basic recognition: Process every 5th frame
                                if frame_count % 5 == 0:
                                    recognized = face_manager.recognize_faces(frame)
                                    for face in recognized:
                                        if face.get('roll_no') and face['roll_no'] != 'UNKNOWN':
                                            mark_present(face['roll_no'], face['confidence'])
                                    last_basic_results = recognized
                                display_frame = draw_face_boxes(display_frame, last_basic_results)
                                    
                        except Exception as e:
                            print(f"Recognition error: {e}")
                    
                    frame_count += 1
                    
                    # Encode and yield frame
                    try:
                        ret, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if ret:
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                    except Exception as e:
                        print(f"Frame encoding error: {e}")
                    
                    # Small delay only when not actively predicting on this frame,
                    # OpenCV cap.read() already blocks to match camera framerate
                    if frame_count % 5 != 0:
                        time.sleep(0.01)
                    
            finally:
                cam.stop()
                if use_advanced:
                    recognizer.clear_voting_buffer()
                print("Camera released")
        
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
