"""
Advanced Face Recognition Module for Attendance System
=======================================================

Uses industry best practices for maximum accuracy:
- MTCNN for accurate face detection with alignment
- FaceNet (InceptionResnetV1) for 512D embeddings
- Cosine similarity for robust matching
- Multi-frame voting for reliable recognition
- Automatic threshold optimization

Optimized for HIGH PRECISION (no wrong attendance) over recall.

Author: AI-Powered Face Recognition Attendance System
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from collections import Counter
from typing import List, Dict, Tuple, Optional
import cv2
import numpy as np
from PIL import Image

# Add temp torch installation to path
TORCH_PATH = os.path.join(os.environ.get('TEMP', '/tmp'), 'torch_temp')
if TORCH_PATH not in sys.path:
    sys.path.insert(0, TORCH_PATH)

import torch
from facenet_pytorch import MTCNN, InceptionResnetV1
from sklearn.metrics.pairwise import cosine_similarity

# ============================================================
# CONFIGURATION
# ============================================================

# Base paths
BASE_DIR = Path(__file__).parent
DATASET_PATH = BASE_DIR / 'dataset'
EMBEDDINGS_PATH = DATASET_PATH / 'embeddings'
LOGS_PATH = BASE_DIR / 'logs' / 'retraining'

# Model settings
DEVICE = torch.device('cpu')  # CPU mode as requested
IMAGE_SIZE = 160  # FaceNet input size
EMBEDDING_DIM = 512

# Recognition settings
# THRESHOLD CALCULATION STRATEGY:
# We use a conservative threshold to maximize precision (minimize false positives)
# A false positive (marking wrong student present) is worse than
# a false negative (missing a student, who can retry)
# Typical optimal range: 0.5 - 0.7 cosine similarity
DEFAULT_THRESHOLD = 0.55  # Conservative default

# MULTI-FRAME VOTING STRATEGY:
# Capture multiple frames and use majority voting to reduce single-frame errors
# Student must be recognized in >= MIN_VOTES frames out of VOTING_FRAMES total
VOTING_FRAMES = 5  # Number of frames to capture
MIN_VOTES = 3  # Minimum votes needed for positive ID
CONFIDENCE_AVERAGING = True  # Average confidence across successful frames

# Detection settings
MTCNN_THRESHOLDS = [0.6, 0.7, 0.7]  # Detection confidence thresholds
MIN_FACE_SIZE = 50  # Minimum face size in pixels

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# MTCNN FACE DETECTOR WITH ALIGNMENT
# ============================================================

class MTCNNDetector:
    """
    Face detector using MTCNN with eye-level alignment.
    
    MTCNN provides:
    - Multi-task cascaded detection (3 stages)
    - Facial landmark detection (5 points)
    - Robust to pose variation up to ±45°
    """
    
    def __init__(self):
        """Initialize MTCNN detector."""
        self.detector = MTCNN(
            image_size=IMAGE_SIZE,
            margin=20,
            min_face_size=MIN_FACE_SIZE,
            thresholds=MTCNN_THRESHOLDS,
            factor=0.709,
            post_process=True,  # Normalize to [-1, 1] for FaceNet
            device=DEVICE,
            keep_all=True  # Return all faces
        )
        logger.info("MTCNN detector initialized")
    
    def detect_faces(self, frame: np.ndarray) -> Tuple[Optional[torch.Tensor], Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Detect and align faces in a frame.
        
        Args:
            frame: BGR image from OpenCV
            
        Returns:
            Tuple of (aligned_faces, boxes, probs)
            - aligned_faces: Tensor of shape (N, 3, 160, 160)
            - boxes: numpy array of bounding boxes (N, 4)
            - probs: numpy array of detection probabilities (N,)
        """
        try:
            # Convert BGR to RGB for MTCNN
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image (MTCNN expects PIL)
            pil_image = Image.fromarray(rgb_frame)
            
            # Detect faces - returns aligned face tensors
            aligned_faces, probs = self.detector(pil_image, return_prob=True)
            
            # Get bounding boxes separately
            boxes, _ = self.detector.detect(pil_image)
            
            if aligned_faces is None:
                return None, None, None
            
            # Handle single face case
            if aligned_faces.dim() == 3:
                aligned_faces = aligned_faces.unsqueeze(0)
            
            return aligned_faces, boxes, probs
            
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return None, None, None
    
    def detect_single_face(self, image_path: str) -> Optional[torch.Tensor]:
        """
        Detect and align a single face from an image file.
        Used for enrollment.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Aligned face tensor of shape (3, 160, 160) or None
        """
        try:
            img = Image.open(image_path).convert('RGB')
            face = self.detector(img)
            
            if face is None:
                return None
            
            # Handle case where multiple faces are detected
            # MTCNN with keep_all=True returns (N, 3, 160, 160) for N faces
            if face.dim() == 4:
                # Multiple faces detected - take the first one (usually largest/most prominent)
                face = face[0]
            
            # Ensure correct shape (3, 160, 160)
            if face.dim() != 3 or face.shape != (3, 160, 160):
                logger.warning(f"Unexpected face tensor shape {face.shape} in {image_path}")
                return None
            
            return face
        except Exception as e:
            logger.error(f"Error processing {image_path}: {e}")
            return None


# ============================================================
# FACENET EMBEDDING GENERATOR
# ============================================================

class FaceNetEmbedder:
    """
    Generate 512D face embeddings using FaceNet (InceptionResnetV1).
    
    Uses pretrained model on VGGFace2 dataset for best accuracy.
    Embeddings are L2 normalized for cosine similarity.
    """
    
    def __init__(self):
        """Initialize FaceNet model."""
        self.model = InceptionResnetV1(
            pretrained='vggface2',
            device=DEVICE
        ).eval()
        logger.info("FaceNet embedder initialized (VGGFace2 pretrained)")
    
    def generate_embedding(self, aligned_face: torch.Tensor) -> np.ndarray:
        """
        Generate embedding for a single aligned face.
        
        Args:
            aligned_face: Tensor of shape (3, 160, 160) or (1, 3, 160, 160)
            
        Returns:
            512D embedding as numpy array
        """
        with torch.no_grad():
            if aligned_face.dim() == 3:
                aligned_face = aligned_face.unsqueeze(0)
            
            aligned_face = aligned_face.to(DEVICE)
            embedding = self.model(aligned_face)
            
            # L2 normalize
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
            
            return embedding.cpu().numpy().flatten()
    
    def generate_embeddings_batch(self, aligned_faces: torch.Tensor) -> np.ndarray:
        """
        Generate embeddings for multiple faces.
        
        Args:
            aligned_faces: Tensor of shape (N, 3, 160, 160)
            
        Returns:
            Embeddings as numpy array of shape (N, 512)
        """
        with torch.no_grad():
            aligned_faces = aligned_faces.to(DEVICE)
            embeddings = self.model(aligned_faces)
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            return embeddings.cpu().numpy()


# ============================================================
# EMBEDDING STORAGE AND MANAGEMENT
# ============================================================

class EmbeddingStore:
    """
    Manages storage and retrieval of face embeddings.
    
    Stores average embedding per student, computed from multiple enrollment images.
    Supports incremental updates without full retraining.
    """
    
    def __init__(self):
        """Initialize embedding store."""
        self.embeddings: Dict[str, np.ndarray] = {}  # name -> embedding
        self.metadata: Dict[str, dict] = {}  # name -> metadata
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories."""
        EMBEDDINGS_PATH.mkdir(parents=True, exist_ok=True)
        LOGS_PATH.mkdir(parents=True, exist_ok=True)
        (LOGS_PATH / 'false_positives').mkdir(exist_ok=True)
        (LOGS_PATH / 'false_negatives').mkdir(exist_ok=True)
    
    def save_embedding(self, name: str, embedding: np.ndarray, metadata: dict = None):
        """
        Save a student's embedding to disk.
        
        Args:
            name: Student name/ID
            embedding: 512D embedding
            metadata: Optional metadata dict
        """
        self.embeddings[name] = embedding
        self.metadata[name] = metadata or {}
        
        # Save to disk
        np.save(EMBEDDINGS_PATH / f"{name}.npy", embedding)
        
        if metadata:
            with open(EMBEDDINGS_PATH / f"{name}_meta.json", 'w') as f:
                json.dump(metadata, f)
        
        logger.info(f"Saved embedding for {name}")
    
    def load_all_embeddings(self) -> bool:
        """
        Load all embeddings from disk.
        
        Returns:
            True if any embeddings were loaded
        """
        self.embeddings = {}
        self.metadata = {}
        
        if not EMBEDDINGS_PATH.exists():
            logger.warning("Embeddings directory does not exist")
            return False
        
        for npy_file in EMBEDDINGS_PATH.glob("*.npy"):
            name = npy_file.stem
            self.embeddings[name] = np.load(npy_file)
            
            meta_file = EMBEDDINGS_PATH / f"{name}_meta.json"
            if meta_file.exists():
                with open(meta_file, 'r') as f:
                    self.metadata[name] = json.load(f)
        
        logger.info(f"Loaded {len(self.embeddings)} embeddings")
        return len(self.embeddings) > 0
    
    def get_all_embeddings(self) -> Tuple[List[str], np.ndarray]:
        """
        Get all stored embeddings as arrays.
        
        Returns:
            Tuple of (names list, embeddings matrix)
        """
        if not self.embeddings:
            return [], np.array([])
        
        names = list(self.embeddings.keys())
        embeddings_matrix = np.stack([self.embeddings[n] for n in names])
        return names, embeddings_matrix
    
    def get_student_names(self) -> List[str]:
        """Get list of enrolled student names."""
        return list(self.embeddings.keys())


# ============================================================
# DATA AUGMENTATION
# ============================================================

class DataAugmentor:
    """
    Apply data augmentation to face images for robust enrollment.
    
    Augmentations are subtle to avoid distorting facial identity:
    - Brightness adjustment (±20%)
    - Slight rotation (±10°)
    - Zoom (±10%)
    - Horizontal flip
    """
    
    @staticmethod
    def augment_image(image: np.ndarray) -> List[np.ndarray]:
        """
        Generate augmented versions of an image.
        
        Args:
            image: BGR image
            
        Returns:
            List of augmented images including original
        """
        augmented = [image]
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        
        # Brightness adjustments
        for factor in [0.8, 1.2]:
            bright = cv2.convertScaleAbs(image, alpha=factor, beta=0)
            augmented.append(bright)
        
        # Slight rotations
        for angle in [-10, 10]:
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(image, M, (w, h))
            augmented.append(rotated)
        
        # Zoom
        for scale in [0.9, 1.1]:
            M = cv2.getRotationMatrix2D(center, 0, scale)
            zoomed = cv2.warpAffine(image, M, (w, h))
            augmented.append(zoomed)
        
        # Horizontal flip
        flipped = cv2.flip(image, 1)
        augmented.append(flipped)
        
        return augmented


# ============================================================
# FALSE RESULT LOGGER
# ============================================================

class FalseResultLogger:
    """
    Log false positives and false negatives for future retraining.
    
    Stores:
    - Timestamp
    - Frame image
    - Predicted vs actual identity
    - Confidence score
    """
    
    @staticmethod
    def log_false_positive(frame: np.ndarray, predicted: str, confidence: float):
        """Log a false positive detection."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fp_{timestamp}_{predicted}_{confidence:.2f}.jpg"
        filepath = LOGS_PATH / 'false_positives' / filename
        cv2.imwrite(str(filepath), frame)
        logger.warning(f"False positive logged: {filename}")
    
    @staticmethod
    def log_false_negative(frame: np.ndarray, actual: str):
        """Log a false negative (missed detection)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fn_{timestamp}_{actual}.jpg"
        filepath = LOGS_PATH / 'false_negatives' / filename
        cv2.imwrite(str(filepath), frame)
        logger.warning(f"False negative logged: {filename}")


# ============================================================
# THRESHOLD OPTIMIZER
# ============================================================

class ThresholdOptimizer:
    """
    Calculate optimal similarity threshold using same-person vs different-person distances.
    
    STRATEGY:
    1. Compute all same-person similarities (intra-class)
    2. Compute all different-person similarities (inter-class)
    3. Find threshold that maximizes precision
    4. Prioritize precision over recall (reject uncertain matches)
    """
    
    @staticmethod
    def calculate_optimal_threshold(embeddings: Dict[str, List[np.ndarray]], 
                                     target_precision: float = 0.99) -> float:
        """
        Calculate optimal threshold from enrollment embeddings.
        
        Args:
            embeddings: Dict mapping name to list of embeddings
            target_precision: Target precision (default 99%)
            
        Returns:
            Optimal threshold value
        """
        if len(embeddings) < 2:
            logger.warning("Not enough students for threshold optimization")
            return DEFAULT_THRESHOLD
        
        # Collect same-person and different-person similarities
        same_person_sims = []
        diff_person_sims = []
        
        names = list(embeddings.keys())
        
        # Same-person comparisons
        for name in names:
            person_embeds = embeddings[name]
            if len(person_embeds) > 1:
                for i in range(len(person_embeds)):
                    for j in range(i + 1, len(person_embeds)):
                        sim = cosine_similarity(
                            person_embeds[i].reshape(1, -1),
                            person_embeds[j].reshape(1, -1)
                        )[0, 0]
                        same_person_sims.append(sim)
        
        # Different-person comparisons
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                for embed_i in embeddings[names[i]]:
                    for embed_j in embeddings[names[j]]:
                        sim = cosine_similarity(
                            embed_i.reshape(1, -1),
                            embed_j.reshape(1, -1)
                        )[0, 0]
                        diff_person_sims.append(sim)
        
        if not same_person_sims or not diff_person_sims:
            logger.warning("Insufficient data for threshold optimization")
            return DEFAULT_THRESHOLD
        
        # Find threshold for target precision
        # Precision = TP / (TP + FP)
        # We want to minimize FP (false positives = wrong identity matches)
        
        thresholds = np.linspace(0.3, 0.9, 100)
        best_threshold = DEFAULT_THRESHOLD
        best_precision = 0
        
        for thresh in thresholds:
            tp = sum(1 for s in same_person_sims if s >= thresh)
            fp = sum(1 for s in diff_person_sims if s >= thresh)
            
            if tp + fp > 0:
                precision = tp / (tp + fp)
                recall = tp / len(same_person_sims) if same_person_sims else 0
                
                # Prioritize high precision
                if precision >= target_precision and precision > best_precision:
                    best_precision = precision
                    best_threshold = thresh
        
        logger.info(f"Optimal threshold: {best_threshold:.3f} (precision: {best_precision:.3f})")
        return best_threshold


# ============================================================
# MAIN FACE RECOGNIZER
# ============================================================

class AdvancedFaceRecognizer:
    """
    Main face recognition class integrating all components.
    
    Features:
    - MTCNN detection with alignment
    - FaceNet 512D embeddings
    - Cosine similarity matching
    - Multi-frame voting for reliability
    - High precision mode (reject uncertain matches)
    """
    
    def __init__(self):
        """Initialize the face recognizer."""
        logger.info("Initializing Advanced Face Recognizer...")
        
        self.detector = MTCNNDetector()
        self.embedder = FaceNetEmbedder()
        self.store = EmbeddingStore()
        self.threshold = DEFAULT_THRESHOLD
        
        # Load existing embeddings
        if self.store.load_all_embeddings():
            logger.info(f"Loaded {len(self.store.embeddings)} enrolled students")
        else:
            logger.info("No enrolled students found. Run enrollment first.")
        
        # Multi-frame voting buffer
        self._voting_buffer: List[Dict] = []
        
        logger.info("Advanced Face Recognizer ready")
    
    def set_threshold(self, threshold: float):
        """Set recognition threshold."""
        self.threshold = threshold
        logger.info(f"Recognition threshold set to {threshold:.3f}")
    
    def recognize_frame(self, frame: np.ndarray) -> List[Dict]:
        """
        Recognize faces in a single frame.
        
        Args:
            frame: BGR image from OpenCV
            
        Returns:
            List of dicts with recognition results:
            [{'name': str, 'confidence': float, 'box': tuple, 'status': str}]
        """
        results = []
        names, known_embeddings = self.store.get_all_embeddings()
        
        if len(names) == 0:
            return results
        
        # Detect faces
        aligned_faces, boxes, probs = self.detector.detect_faces(frame)
        
        if aligned_faces is None:
            return results
        
        # Generate embeddings for detected faces
        embeddings = self.embedder.generate_embeddings_batch(aligned_faces)
        
        # Match each face
        for i, embedding in enumerate(embeddings):
            box = boxes[i] if boxes is not None else None
            prob = probs[i] if probs is not None else 0
            
            # Compute similarities to all known faces
            similarities = cosine_similarity(
                embedding.reshape(1, -1),
                known_embeddings
            )[0]
            
            best_idx = np.argmax(similarities)
            best_similarity = similarities[best_idx]
            
            if best_similarity >= self.threshold:
                # Match found
                result = {
                    'name': names[best_idx],
                    'confidence': float(best_similarity),
                    'box': tuple(box) if box is not None else None,
                    'detection_prob': float(prob),
                    'status': 'recognized'
                }
            else:
                # No confident match - REJECT (high precision mode)
                result = {
                    'name': 'Unknown',
                    'confidence': float(best_similarity),
                    'box': tuple(box) if box is not None else None,
                    'detection_prob': float(prob),
                    'status': 'rejected'
                }
            
            results.append(result)
        
        return results
    
    def recognize_with_voting(self, frames: List[np.ndarray]) -> List[Dict]:
        """
        Recognize faces using multi-frame voting.
        
        VOTING STRATEGY:
        1. Process each frame independently
        2. Collect predictions for each detected face
        3. Majority vote: student needs >= MIN_VOTES recognitions
        4. Average confidence across successful frames
        5. Reject if not enough votes (high precision mode)
        
        Args:
            frames: List of BGR images
            
        Returns:
            List of final recognition results
        """
        if len(frames) < VOTING_FRAMES:
            logger.warning(f"Only {len(frames)} frames provided, need {VOTING_FRAMES}")
        
        # Collect all predictions
        all_predictions = []
        for frame in frames:
            predictions = self.recognize_frame(frame)
            all_predictions.append(predictions)
        
        # Aggregate by face position (approximate matching)
        # For now, assume single face per session for simplicity
        name_votes = Counter()
        confidence_scores = {}
        
        for frame_preds in all_predictions:
            for pred in frame_preds:
                name = pred['name']
                if name != 'Unknown':
                    name_votes[name] += 1
                    if name not in confidence_scores:
                        confidence_scores[name] = []
                    confidence_scores[name].append(pred['confidence'])
        
        # Apply voting threshold
        final_results = []
        for name, votes in name_votes.items():
            if votes >= MIN_VOTES:
                avg_confidence = np.mean(confidence_scores[name])
                final_results.append({
                    'name': name,
                    'votes': votes,
                    'confidence': float(avg_confidence),
                    'status': 'confirmed'
                })
                logger.info(f"Confirmed: {name} ({votes}/{len(frames)} votes, conf: {avg_confidence:.3f})")
            else:
                logger.info(f"Rejected: {name} ({votes}/{len(frames)} votes, insufficient)")
        
        return final_results
    
    def add_to_voting_buffer(self, frame_results: List[Dict]):
        """Add frame results to voting buffer."""
        self._voting_buffer.append(frame_results)
        if len(self._voting_buffer) > VOTING_FRAMES:
            self._voting_buffer.pop(0)
    
    def get_voting_result(self) -> Optional[Dict]:
        """Get result from voting buffer if enough frames collected."""
        if len(self._voting_buffer) < VOTING_FRAMES:
            return None
        
        # Aggregate votes
        name_votes = Counter()
        confidence_scores = {}
        
        for frame_preds in self._voting_buffer:
            for pred in frame_preds:
                name = pred.get('name', 'Unknown')
                if name != 'Unknown':
                    name_votes[name] += 1
                    if name not in confidence_scores:
                        confidence_scores[name] = []
                    confidence_scores[name].append(pred['confidence'])
        
        # Get best match with enough votes
        for name, votes in name_votes.most_common():
            if votes >= MIN_VOTES:
                avg_confidence = np.mean(confidence_scores[name])
                return {
                    'name': name,
                    'votes': votes,
                    'confidence': float(avg_confidence),
                    'status': 'confirmed'
                }
        
        return None
    
    def clear_voting_buffer(self):
        """Clear the voting buffer."""
        self._voting_buffer = []


# ============================================================
# ENROLLMENT MANAGER
# ============================================================

class EnrollmentManager:
    """
    Manage student enrollment process.
    
    Processes images from dataset folder:
    - Detects and aligns faces
    - Applies data augmentation
    - Generates and averages embeddings
    - Calculates optimal threshold
    """
    
    def __init__(self):
        """Initialize enrollment manager."""
        self.detector = MTCNNDetector()
        self.embedder = FaceNetEmbedder()
        self.store = EmbeddingStore()
        self.augmentor = DataAugmentor()
    
    def enroll_from_dataset(self) -> Dict[str, int]:
        """
        Enroll all students from dataset folder.
        
        Expected structure: dataset/StudentName/image1.jpg, image2.jpg, ...
        
        Returns:
            Dict mapping student name to number of images processed
        """
        results = {}
        all_embeddings = {}  # For threshold calculation
        
        if not DATASET_PATH.exists():
            logger.error(f"Dataset path does not exist: {DATASET_PATH}")
            return results
        
        # Process each student folder
        for student_dir in DATASET_PATH.iterdir():
            if not student_dir.is_dir() or student_dir.name == 'embeddings':
                continue
            
            student_name = student_dir.name
            embeddings_list = []
            images_processed = 0
            
            # Process each image
            for img_path in student_dir.glob("*"):
                if img_path.suffix.lower() not in ['.jpg', '.jpeg', '.png']:
                    continue
                
                # Detect and align face
                face = self.detector.detect_single_face(str(img_path))
                
                if face is not None:
                    # Generate embedding
                    embedding = self.embedder.generate_embedding(face)
                    embeddings_list.append(embedding)
                    images_processed += 1
                    logger.info(f"Processed: {student_name}/{img_path.name}")
            
            if embeddings_list:
                # Compute average embedding
                avg_embedding = np.mean(embeddings_list, axis=0)
                # L2 normalize the average
                avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)
                
                # Save
                self.store.save_embedding(student_name, avg_embedding, {
                    'images_count': images_processed,
                    'enrolled_at': datetime.now().isoformat()
                })
                
                all_embeddings[student_name] = embeddings_list
                results[student_name] = images_processed
                logger.info(f"Enrolled: {student_name} ({images_processed} images)")
            else:
                logger.warning(f"No valid faces found for {student_name}")
        
        # Calculate optimal threshold
        if len(all_embeddings) >= 2:
            threshold = ThresholdOptimizer.calculate_optimal_threshold(all_embeddings)
            
            # Save threshold to config
            config = {'threshold': threshold, 'students': list(results.keys())}
            with open(EMBEDDINGS_PATH / 'config.json', 'w') as f:
                json.dump(config, f)
            
            logger.info(f"Optimal threshold: {threshold:.3f}")
        
        return results


# ============================================================
# GLOBAL INSTANCE FOR APP INTEGRATION
# ============================================================

# Create global recognizer instance (lazy initialization)
_recognizer = None

def get_recognizer() -> AdvancedFaceRecognizer:
    """Get or create the global recognizer instance."""
    global _recognizer
    if _recognizer is None:
        _recognizer = AdvancedFaceRecognizer()
        
        # Load optimal threshold if available
        config_path = EMBEDDINGS_PATH / 'config.json'
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                _recognizer.set_threshold(config.get('threshold', DEFAULT_THRESHOLD))
    
    return _recognizer


# ============================================================
# UTILITY FUNCTIONS FOR APP.PY INTEGRATION
# ============================================================

def draw_recognition_boxes(frame: np.ndarray, results: List[Dict]) -> np.ndarray:
    """
    Draw bounding boxes and labels on frame.
    
    Color coding:
    - Green: Confirmed recognition (high confidence)
    - Yellow: Recognized but needs more votes
    - Red: Unknown/rejected
    """
    for result in results:
        box = result.get('box')
        if box is None:
            continue
        
        x1, y1, x2, y2 = [int(b) for b in box]
        name = result.get('name', 'Unknown')
        confidence = result.get('confidence', 0)
        status = result.get('status', 'unknown')
        
        # Color based on status and confidence
        if status == 'confirmed' or (status == 'recognized' and confidence > 0.7):
            color = (0, 255, 0)  # Green
        elif status == 'recognized':
            color = (0, 255, 255)  # Yellow
        else:
            color = (0, 0, 255)  # Red
        
        # Draw box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Draw label
        label = f"{name} ({confidence*100:.1f}%)"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        
        cv2.rectangle(frame, (x1, y2), (x1 + label_size[0] + 10, y2 + label_size[1] + 10), color, -1)
        cv2.putText(frame, label, (x1 + 5, y2 + label_size[1] + 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    
    return frame


# ============================================================
# MAIN - FOR TESTING
# ============================================================

if __name__ == '__main__':
    print("Advanced Face Recognition Module")
    print("=" * 50)
    print(f"Device: {DEVICE}")
    print(f"Threshold: {DEFAULT_THRESHOLD}")
    print(f"Voting frames: {VOTING_FRAMES}")
    print(f"Min votes: {MIN_VOTES}")
    print("=" * 50)
    
    # Test enrollment
    print("\nEnrolling students from dataset...")
    manager = EnrollmentManager()
    results = manager.enroll_from_dataset()
    
    print(f"\nEnrollment complete: {len(results)} students")
    for name, count in results.items():
        print(f"  - {name}: {count} images")
