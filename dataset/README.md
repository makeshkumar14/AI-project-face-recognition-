# Dataset Folder

This folder contains student face images for recognition.

## Structure

Each student should have a folder named: `StudentName_RollNo`

Example:

```
dataset/
├── Rahul_Kumar_CSE001/
│   └── face.jpg
├── Priya_Sharma_CSE002/
│   └── face.jpg
├── Amit_Singh_CSE003/
│   └── face.jpg
```

## Requirements

- Each folder should contain at least one clear face image
- Supported formats: `.jpg`, `.jpeg`, `.png`
- Best results with frontal face photos
- Good lighting recommended
- One person per image

## Adding New Students

1. Create a folder: `FirstName_LastName_RollNo`
2. Add a clear face photo named `face.jpg`
3. Restart the server or reload faces via API

## Notes

- The system will automatically load all faces on startup
- Face encodings are generated from the first valid image found
- If no face is detected in an image, it will be skipped
