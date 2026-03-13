"""
Face Recognition Module for Attendance System
Uses OpenCV's Haar Cascade for face detection
Falls back to basic detection when face_recognition is not available
"""

import os
import cv2
import numpy as np
from datetime import datetime

# Base directory for dataset
DATASET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dataset')

# Try to import face_recognition (optional, may not be installed)
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
    print("face_recognition library loaded successfully")
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("face_recognition library not available, using OpenCV fallback")

# Face detection cascade (built into OpenCV)
CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'

# Face recognition tolerance (lower = more strict, recommended: 0.4-0.6)
TOLERANCE = 0.5

# LBPH confidence threshold (lower = stricter matching)
# Typical LBPH distance: 0-50 = good match, 50-90 = possible match, >120 = poor match
# Higher threshold needed when: glasses, lighting variations, different angles
LBPH_THRESHOLD = 120


class FaceRecognitionManager:
    """
    Manages face recognition operations including:
    - Loading known faces from dataset
    - Recognizing faces in camera frames
    - Tracking recognized students
    """
    
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []  # Format: "Name_RollNo"
        self.known_roll_numbers = []
        self.is_loaded = False
        self.face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
        self.recognized_this_session = set()  # Track who's been recognized
        
        # OpenCV LBPH Face Recognizer for fallback mode
        self.lbph_recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.lbph_trained = False
        self.label_to_index = {}  # Maps LBPH labels to student indices
    
    def load_known_faces(self):
        """
        Load face encodings from the dataset folder.
        Expected structure: dataset/StudentName_RollNo/image.jpg
        """
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_roll_numbers = []
        self.recognized_this_session = set()
        
        if not os.path.exists(DATASET_PATH):
            os.makedirs(DATASET_PATH)
            print(f"Created dataset folder at: {DATASET_PATH}")
            return False
        
        # Iterate through student folders
        for student_folder in os.listdir(DATASET_PATH):
            folder_path = os.path.join(DATASET_PATH, student_folder)
            
            # Skip files (like README.md)
            if not os.path.isdir(folder_path):
                continue
            
            # Parse folder name: Name_RollNo (e.g., Rahul_Kumar_CSE001)
            parts = student_folder.rsplit('_', 1)
            if len(parts) == 2:
                student_name = parts[0].replace('_', ' ')
                roll_no = parts[1]
            else:
                student_name = student_folder.replace('_', ' ')
                roll_no = student_folder
            
            # Find ALL image files in the folder and load them
            images_loaded = 0
            for filename in os.listdir(folder_path):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    image_path = os.path.join(folder_path, filename)
                    
                    try:
                        if FACE_RECOGNITION_AVAILABLE:
                            # Use face_recognition library if available
                            image = face_recognition.load_image_file(image_path)
                            face_encodings = face_recognition.face_encodings(image)
                            
                            if len(face_encodings) > 0:
                                self.known_face_encodings.append(face_encodings[0])
                                self.known_face_names.append(student_name)
                                self.known_roll_numbers.append(roll_no)
                                images_loaded += 1
                                print(f"Loaded face (face_recognition): {student_name} ({roll_no}) - {filename}")
                                # Continue loading more images for this person
                        else:
                            # OpenCV fallback - use LBPH face recognizer
                            image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                            if image is not None:
                                # Detect face in the image
                                faces = self.face_cascade.detectMultiScale(image, 1.3, 5)
                                if len(faces) > 0:
                                    x, y, w, h = faces[0]
                                    face_roi = image[y:y+h, x:x+w]
                                    face_roi = cv2.resize(face_roi, (150, 150))
                                    self.known_face_encodings.append(face_roi)
                                    self.known_face_names.append(student_name)
                                    self.known_roll_numbers.append(roll_no)
                                    images_loaded += 1
                                    print(f"Loaded face (OpenCV LBPH): {student_name} ({roll_no}) - {filename}")
                                    # Continue loading more images for this person
                    except Exception as e:
                        print(f"Error loading {image_path}: {e}")
            
            if images_loaded == 0 and os.path.isdir(folder_path):
                print(f"Warning: No valid face image for {student_folder}")
            elif images_loaded > 0:
                print(f"Loaded {images_loaded} image(s) for {student_name}")
        
        self.is_loaded = len(self.known_face_encodings) > 0
        
        # Train LBPH recognizer if we have faces and face_recognition is not available
        if self.is_loaded and not FACE_RECOGNITION_AVAILABLE:
            try:
                # Create labels (0, 1, 2, ...) for each person
                labels = []
                faces_for_training = []
                for i, face_img in enumerate(self.known_face_encodings):
                    labels.append(i)
                    faces_for_training.append(face_img)
                    self.label_to_index[i] = i
                
                # Train the LBPH recognizer
                self.lbph_recognizer.train(faces_for_training, np.array(labels))
                self.lbph_trained = True
                print(f"LBPH recognizer trained with {len(faces_for_training)} faces")
            except Exception as e:
                print(f"Error training LBPH recognizer: {e}")
                self.lbph_trained = False
        
        print(f"Loaded {len(self.known_face_encodings)} known faces")
        return self.is_loaded
    
    def recognize_faces(self, frame):
        """
        Recognize faces in a video frame.
        
        Args:
            frame: BGR image from OpenCV (numpy array)
        
        Returns:
            List of dicts with recognized face info:
            [{'name': str, 'roll_no': str, 'location': tuple, 'confidence': float}]
        """
        recognized = []
        
        # Safety check for None frame
        if frame is None:
            return recognized
        
        try:
            # Resize frame to 640x480 to avoid memory issues
            frame = cv2.resize(frame, (640, 480))
        except Exception as e:
            print(f"Error resizing frame: {e}")
            return recognized
        
        if FACE_RECOGNITION_AVAILABLE and self.is_loaded:
            try:
                # Convert BGR to RGB for face_recognition library
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Scale down for faster processing
                small_frame = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
                
                # Detect face locations first
                face_locations = face_recognition.face_locations(small_frame)
                
                # Only run face_encodings if faces are found (prevents crash)
                if len(face_locations) == 0:
                    return recognized
                
                face_encodings = face_recognition.face_encodings(small_frame, face_locations)
                
                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    matches = face_recognition.compare_faces(
                        self.known_face_encodings, 
                        face_encoding, 
                        tolerance=TOLERANCE
                    )
                    
                    face_distances = face_recognition.face_distance(
                        self.known_face_encodings, 
                        face_encoding
                    )
                    
                    if len(face_distances) > 0 and True in matches:
                        best_match_index = np.argmin(face_distances)
                        
                        if matches[best_match_index]:
                            name = self.known_face_names[best_match_index]
                            roll_no = self.known_roll_numbers[best_match_index]
                            distance = face_distances[best_match_index]
                            confidence = round((1 - distance) * 100, 1)
                            location = (top * 4, right * 4, bottom * 4, left * 4)
                            
                            recognized.append({
                                'name': name,
                                'roll_no': roll_no,
                                'location': location,
                                'confidence': confidence
                            })
            except Exception as e:
                print(f"Face recognition error: {e}")
        else:
            # OpenCV fallback - use LBPH face recognizer
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(50, 50))
            
            for (x, y, w, h) in faces:
                # Extract and resize face region for recognition
                face_roi = gray[y:y+h, x:x+w]
                face_roi_resized = cv2.resize(face_roi, (150, 150))
                
                name = "Unknown"
                roll_no = "UNKNOWN"
                confidence = 0.0
                
                # Use LBPH recognizer if trained
                if self.lbph_trained and self.is_loaded:
                    try:
                        # Predict the label and confidence
                        label, lbph_confidence = self.lbph_recognizer.predict(face_roi_resized)
                        
                        # LBPH confidence is distance (lower = better match)
                        # Typical LBPH distance: 0-40 = good, 40-70 = possible, >70 = poor
                        # Only accept matches with low enough distance
                        if lbph_confidence < LBPH_THRESHOLD:
                            if label in self.label_to_index:
                                idx = self.label_to_index[label]
                                if idx < len(self.known_face_names):
                                    name = self.known_face_names[idx]
                                    roll_no = self.known_roll_numbers[idx]
                                    # Convert distance to confidence percentage
                                    # Lower distance = higher confidence
                                    confidence = round(max(0, min(100, (LBPH_THRESHOLD - lbph_confidence) * 100 / LBPH_THRESHOLD)), 1)
                        else:
                            # Distance too high - this is not a match
                            print(f"Face detected but no match (distance: {lbph_confidence:.1f})")
                    except Exception as e:
                        print(f"LBPH prediction error: {e}")
                
                # Location format: (top, right, bottom, left)
                location = (y, x + w, y + h, x)
                
                recognized.append({
                    'name': name,
                    'roll_no': roll_no,
                    'location': location,
                    'confidence': confidence
                })
        
        return recognized
    
    def get_loaded_students(self):
        """Return list of loaded student info."""
        return [
            {'name': name, 'roll_no': roll}
            for name, roll in zip(self.known_face_names, self.known_roll_numbers)
        ]


class WebcamCapture:
    """
    Manages webcam capture for face recognition.
    """
    
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.is_running = False
    
    def start(self):
        """Start the webcam capture."""
        if self.cap is None or not self.cap.isOpened():
            # Try multiple camera indices for compatibility across different laptops
            camera_indices = [self.camera_index, 0, 1, 2]
            # Remove duplicates while preserving order
            camera_indices = list(dict.fromkeys(camera_indices))
            
            # Try DirectShow backend first (more reliable on Windows)
            backends = [
                (cv2.CAP_DSHOW, "DirectShow"),
                (cv2.CAP_MSMF, "MSMF"),
                (cv2.CAP_ANY, "Default")
            ]
            
            camera_found = False
            for idx in camera_indices:
                if camera_found:
                    break
                for backend, name in backends:
                    print(f"Trying camera index {idx} with {name} backend...")
                    self.cap = cv2.VideoCapture(idx, backend)
                    
                    if self.cap.isOpened():
                        # Set MJPG codec first (more reliable on Windows, avoids corruption)
                        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                        self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
                        
                        # Set resolution and FPS before grabbing frames
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        self.cap.set(cv2.CAP_PROP_FPS, 30)
                        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        
                        # Flush a few frames to clear the buffer
                        for _ in range(5):
                            self.cap.read()
                        
                        # Test if we can actually grab a valid frame
                        ret, test_frame = self.cap.read()
                        if ret and test_frame is not None and test_frame.size > 0:
                            print(f"Camera {idx} opened successfully with {name} backend")
                            print(f"Frame size: {test_frame.shape}")
                            self.camera_index = idx
                            camera_found = True
                            break
                        else:
                            self.cap.release()
                            print(f"Camera {idx} with {name} backend opened but couldn't grab valid frame")
                    else:
                        print(f"Camera {idx} with {name} backend failed to open")
            
            if not camera_found:
                print("\n" + "="*60)
                print("ERROR: Could not open camera!")
                print("="*60)
                print("Troubleshooting tips for your team:")
                print("  1. Close other apps using camera (Zoom, Teams, Skype, etc.)")
                print("  2. Windows: Settings > Privacy > Camera > Allow apps to access")
                print("  3. Check if the laptop has a physical camera switch")
                print("  4. Try restarting the laptop")
                print("  5. Update camera drivers from Device Manager")
                print("="*60 + "\n")
                return False
        
        self.is_running = self.cap is not None and self.cap.isOpened()
        return self.is_running
    
    def read_frame(self):
        """Read a frame from the webcam with safety checks."""
        if self.cap is None or not self.cap.isOpened():
            return None
        
        try:
            ret, frame = self.cap.read()
            # Always check ret before processing frame
            if not ret or frame is None:
                return None
            
            # Resize frame to 640x480 to avoid memory crash
            frame = cv2.resize(frame, (640, 480))
            # Flip frame horizontally to fix mirror effect
            frame = cv2.flip(frame, 1)
            return frame
        except Exception as e:
            print(f"Error reading frame: {e}")
            return None
    
    def stop(self):
        """Stop the webcam capture."""
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
    
    def __del__(self):
        """Cleanup on destruction."""
        self.stop()


def draw_face_boxes(frame, recognized_faces):
    """
    Draw bounding boxes and labels on frame for recognized faces.
    
    Args:
        frame: OpenCV image (BGR)
        recognized_faces: List from recognize_faces()
    
    Returns:
        Frame with annotations
    """
    for face in recognized_faces:
        top, right, bottom, left = face['location']
        name = face['name']
        confidence = face['confidence']
        
        # Color based on confidence
        # LBPH typically gives lower confidence values, so use lower thresholds
        if confidence >= 50:
            color = (0, 255, 0)  # Green - good confidence
        elif confidence >= 30:
            color = (0, 255, 255)  # Yellow - medium confidence
        else:
            color = (0, 0, 255)  # Red - low/unknown
        
        # Draw rectangle
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        
        # Draw label background
        label = f"{name} ({confidence}%)"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        cv2.rectangle(
            frame, 
            (left, bottom), 
            (left + label_size[0] + 10, bottom + label_size[1] + 10),
            color, 
            cv2.FILLED
        )
        
        # Draw text
        cv2.putText(
            frame, 
            label, 
            (left + 5, bottom + label_size[1] + 5),
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.5, 
            (0, 0, 0), 
            1
        )
    
    return frame


# Global instance for use across the application
face_manager = FaceRecognitionManager()


# Testing function (standalone mode only - uses cv2.imshow)
if __name__ == '__main__':
    print("Testing Face Recognition Module...")
    print(f"face_recognition available: {FACE_RECOGNITION_AVAILABLE}")
    
    # Load known faces
    if face_manager.load_known_faces():
        print(f"\nLoaded students: {face_manager.get_loaded_students()}")
    else:
        print("No known faces loaded. Testing with detection only.")
    
    # Test with webcam
    cam = WebcamCapture()
    try:
        if cam.start():
            print("\nWebcam started. Press 'q' to quit.")
            
            while cam.is_running:
                frame = cam.read_frame()
                
                # Check if frame is valid
                if frame is None:
                    cv2.waitKey(10)  # Small delay to reduce CPU usage
                    continue
                
                # Recognize faces
                recognized = face_manager.recognize_faces(frame)
                
                # Draw boxes
                frame = draw_face_boxes(frame, recognized)
                
                # Display (only in standalone test mode)
                cv2.imshow('Face Recognition Test', frame)
                
                # Add small waitKey delay to reduce CPU usage and check for 'q' key
                key = cv2.waitKey(30) & 0xFF
                if key == ord('q'):
                    print("'q' pressed - exiting...")
                    break
        else:
            print("Failed to start webcam")
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        # Always release camera and destroy windows
        cam.stop()
        cv2.destroyAllWindows()
        print("Camera released and windows closed")
