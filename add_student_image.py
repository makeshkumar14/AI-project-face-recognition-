"""
Script to save the student image to the dataset folder.
Run this once to add the image, then restart the Flask server.
"""

import os
import urllib.request
import shutil

# The image needs to be placed in the dataset folder
dataset_path = os.path.join(os.path.dirname(__file__), 'dataset', 'Makesh_Kumar_CSE001')

print(f"Dataset folder: {dataset_path}")
print(f"Folder exists: {os.path.exists(dataset_path)}")

# List current contents
if os.path.exists(dataset_path):
    files = os.listdir(dataset_path)
    print(f"Current files: {files}")
    
print("\n--- Instructions ---")
print("To add a student face image:")
print("1. Copy your photo to the folder above")
print("2. Rename it to 'photo.jpg' or any .jpg/.png file")
print("3. Restart the Flask server")
print("4. The face recognition system will load the new face automatically")
