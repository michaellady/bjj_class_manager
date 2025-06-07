import cv2
import numpy as np
from typing import Tuple, Dict
import os

class FaceQualityAnalyzer:
    def __init__(self):
        """Initialize the face quality analyzer with OpenCV's face detection."""
        # Load face detection model
        model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models')
        os.makedirs(model_dir, exist_ok=True)
        
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    def get_face_angles(self, image: np.ndarray) -> Tuple[float, float, float]:
        """
        Estimate face angles using eye positions and face shape.
        
        Args:
            image: RGB image array
            
        Returns:
            Tuple of (pitch, yaw, roll) angles in degrees
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
            
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) == 0:
            return 0.0, 0.0, 0.0
            
        (x, y, w, h) = faces[0]
        face_roi_gray = gray[y:y+h, x:x+w]
        
        # Detect eyes in the face region
        eyes = self.eye_cascade.detectMultiScale(face_roi_gray)
        if len(eyes) < 2:
            return 0.0, 0.0, 0.0
            
        # Sort eyes by x-coordinate to get left and right eye
        eyes = sorted(eyes, key=lambda e: e[0])
        if len(eyes) >= 2:
            left_eye = eyes[0]
            right_eye = eyes[1]
            
            # Calculate roll angle from eye positions
            dx = right_eye[1] - left_eye[1]
            dy = right_eye[0] - left_eye[0]
            roll = np.degrees(np.arctan2(dx, dy))
            
            # Estimate yaw from relative eye sizes
            left_eye_width = left_eye[2]
            right_eye_width = right_eye[2]
            eye_width_ratio = left_eye_width / right_eye_width if right_eye_width > 0 else 1.0
            yaw = (eye_width_ratio - 1.0) * 45  # Rough estimation
            
            # Estimate pitch from vertical position of eyes relative to face height
            eye_y = (left_eye[1] + right_eye[1]) / 2
            relative_eye_pos = eye_y / h
            pitch = (relative_eye_pos - 0.4) * 90  # Rough estimation
            
            return pitch, yaw, roll
        
        return 0.0, 0.0, 0.0

    def analyze_face_quality(self, image: np.ndarray) -> Dict[str, float]:
        """
        Analyze various quality metrics for a face image.
        
        Args:
            image: BGR or RGB image array
            
        Returns:
            Dictionary containing quality metrics:
            - brightness_score: 0-1 score for image brightness
            - contrast_score: 0-1 score for image contrast
            - sharpness_score: 0-1 score for image sharpness
            - size_score: 0-1 score for face size relative to image
            - overall_quality: Combined quality score (0-1)
        """
        # Convert to grayscale for calculations
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
            
        # Calculate brightness score
        brightness_mean = np.mean(gray) / 255
        brightness_score = 1.0 - 2.0 * abs(0.5 - brightness_mean)
        
        # Calculate contrast score
        contrast = np.std(gray) / 128
        contrast_score = min(contrast, 1.0)
        
        # Calculate sharpness score using Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(laplacian_var / 500, 1.0)
        
        # Calculate face size score
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) > 0:
            x, y, w, h = faces[0]
            face_area = w * h
            image_area = gray.shape[0] * gray.shape[1]
            face_size_score = min((face_area / image_area) * 4, 1.0)  # Normalize to 0-1
        else:
            face_size_score = 0.0
        
        # Calculate overall quality score (weighted average)
        overall_quality = (
            0.3 * brightness_score +
            0.2 * contrast_score +
            0.3 * sharpness_score +
            0.2 * face_size_score
        )
        
        return {
            'brightness_score': brightness_score,
            'contrast_score': contrast_score,
            'sharpness_score': sharpness_score,
            'size_score': face_size_score,
            'overall_quality': overall_quality
        }

    def is_good_angle_for_enrollment(self, pitch: float, yaw: float, roll: float) -> bool:
        """
        Check if face angles are suitable for enrollment.
        
        Args:
            pitch: Vertical head rotation in degrees
            yaw: Horizontal head rotation in degrees
            roll: Head tilt in degrees
            
        Returns:
            Boolean indicating if angles are good for enrollment
        """
        return (
            abs(pitch) < 20 and  # Looking too up/down
            abs(yaw) < 30 and    # Looking too left/right
            abs(roll) < 15       # Head tilted too much
        )

    def get_angle_quality_score(self, pitch: float, yaw: float, roll: float) -> float:
        """
        Calculate a quality score based on face angles.
        
        Args:
            pitch: Vertical head rotation in degrees
            yaw: Horizontal head rotation in degrees
            roll: Head tilt in degrees
            
        Returns:
            Quality score between 0 and 1
        """
        # Normalize angles to 0-1 range where 1 is ideal (straight on)
        pitch_score = max(0, 1 - abs(pitch) / 45)  # 45 degrees max
        yaw_score = max(0, 1 - abs(yaw) / 45)      # 45 degrees max
        roll_score = max(0, 1 - abs(roll) / 30)    # 30 degrees max
        
        # Weight the scores (yaw is most important, then pitch, then roll)
        return 0.4 * yaw_score + 0.35 * pitch_score + 0.25 * roll_score 