import os
import shutil

src_dir = r"C:\Users\MAKESH\OneDrive\Desktop\MAX\dataset images"
dst_dir = r"c:\Users\MAKESH\OneDrive\Desktop\MAX(project)\Final AI project folder face recog\AI-project-face-recognition-\dataset\Makeshkumar"

files = [f for f in os.listdir(src_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
# Sorting chronologically if possible, or alphabetically by name
files.sort()

start_idx = 8
for i, file_name in enumerate(files):
    src_path = os.path.join(src_dir, file_name)
    # Using the original extension for compatibility (it's .jpeg)
    ext = os.path.splitext(file_name)[1]
    dst_name = f"Makeshkumar_{start_idx + i}{ext}"
    dst_path = os.path.join(dst_dir, dst_name)
    shutil.copy2(src_path, dst_path)
    print(f"Copied {file_name} to {dst_name}")

print("All files successfully copied and renamed.")
