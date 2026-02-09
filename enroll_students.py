"""
Student Enrollment Script
=========================

Processes existing images in the dataset folder to generate embeddings.
Run this before using the face recognition attendance system.

Usage:
    python enroll_students.py
"""

import sys
import os

# Add temp torch installation to path
TORCH_PATH = os.path.join(os.environ.get('TEMP', '/tmp'), 'torch_temp')
if TORCH_PATH not in sys.path:
    sys.path.insert(0, TORCH_PATH)

from advanced_face_recognition import EnrollmentManager, DATASET_PATH, EMBEDDINGS_PATH


def main():
    print("=" * 60)
    print("Student Enrollment for Face Recognition Attendance System")
    print("=" * 60)
    print()
    print(f"Dataset path: {DATASET_PATH}")
    print(f"Embeddings will be saved to: {EMBEDDINGS_PATH}")
    print()
    
    # List existing students
    print("Scanning for student folders...")
    student_folders = [d for d in DATASET_PATH.iterdir() 
                       if d.is_dir() and d.name != 'embeddings']
    
    if not student_folders:
        print("\nNo student folders found!")
        print(f"Please add student folders to: {DATASET_PATH}")
        print("Expected structure: dataset/StudentName/image1.jpg")
        return
    
    print(f"Found {len(student_folders)} student folders:")
    for folder in student_folders:
        images = list(folder.glob("*.jpg")) + list(folder.glob("*.jpeg")) + list(folder.glob("*.png"))
        print(f"  - {folder.name}: {len(images)} images")
    
    print()
    print("Starting enrollment...")
    print("-" * 40)
    
    # Run enrollment
    manager = EnrollmentManager()
    results = manager.enroll_from_dataset()
    
    # Summary
    print()
    print("=" * 60)
    print("ENROLLMENT COMPLETE")
    print("=" * 60)
    print(f"Students enrolled: {len(results)}")
    print()
    
    if results:
        print("Details:")
        for name, count in results.items():
            print(f"  [OK] {name}: {count} images processed")
    
    print()
    print(f"Embeddings saved to: {EMBEDDINGS_PATH}")
    print()
    print("You can now start the attendance system: python app.py")


if __name__ == '__main__':
    main()
