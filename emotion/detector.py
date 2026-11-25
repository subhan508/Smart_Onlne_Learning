"""
Face Detection Module
=====================
Uses OpenCV Haar Cascade for face detection.
Extracts face region from webcam frames for emotion classification.

Separated from emotion prediction so either component can be replaced independently.
"""

import cv2
import numpy as np
import os


class FaceDetector:
    """
    Detects faces in images using OpenCV's pre-trained Haar Cascade classifier.
    
    The Haar Cascade is a fast, lightweight face detection method suitable for
    real-time applications. While not as accurate as deep learning methods
    like MTCNN, it provides good performance for frontal face detection.
    """

    def __init__(self, cascade_path=None, scale_factor=1.1, min_neighbors=3, min_size=(30, 30)):
        """
        Initialise the face detector.

        Args:
            cascade_path: Path to Haar Cascade XML file.
                         If None, uses OpenCV's built-in frontalface cascade.
            scale_factor: How much the image size is reduced at each image scale.
            min_neighbors: Minimum number of neighbors each candidate rectangle should have.
            min_size: Minimum possible face size (width, height).
        """
        # Primary cascade — alt2 is more robust to partial occlusion
        if cascade_path and os.path.exists(cascade_path):
            self.cascade = cv2.CascadeClassifier(cascade_path)
        else:
            cascade_file = cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml'
            self.cascade = cv2.CascadeClassifier(cascade_file)

        if self.cascade.empty():
            raise RuntimeError('Failed to load Haar Cascade classifier.')

        # Fallback cascade for when the primary misses a face
        fallback_file = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.fallback_cascade = cv2.CascadeClassifier(fallback_file)

        # Profile cascade for side-facing faces
        profile_file = cv2.data.haarcascades + 'haarcascade_profileface.xml'
        self.profile_cascade = cv2.CascadeClassifier(profile_file)

        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_size = min_size

        # Temporal face tracking / smoothing for momentary partial occlusions
        self.last_face_rect = None
        self.missed_frames = 0
        self.max_missed = 2

    def detect_faces(self, image):
        """
        Detect all faces in the given image.

        Uses a multi-cascade strategy: tries the primary (alt2) cascade first,
        then falls back to the default frontal cascade, and finally a profile
        cascade, so partially-covered or slightly-turned faces are still found.

        Args:
            image: BGR or grayscale numpy array (from OpenCV).

        Returns:
            List of face bounding boxes as (x, y, w, h) tuples.
            Empty list if no faces are found.
        """
        # Convert to grayscale if necessary
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Equalise histogram for better detection under varying lighting
        gray = cv2.equalizeHist(gray)

        # Try primary cascade (alt2 — more tolerant of occlusion)
        faces = self.cascade.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_size,
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        # Fallback: try the default frontal cascade with even more lenient settings
        if len(faces) == 0 and not self.fallback_cascade.empty():
            faces = self.fallback_cascade.detectMultiScale(
                gray,
                scaleFactor=1.05,
                minNeighbors=2,
                minSize=self.min_size,
                flags=cv2.CASCADE_SCALE_IMAGE
            )

        # Last resort: try profile cascade (for turned heads)
        if len(faces) == 0 and not self.profile_cascade.empty():
            faces = self.profile_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=2,
                minSize=self.min_size,
                flags=cv2.CASCADE_SCALE_IMAGE
            )

        if len(faces) == 0:
            return []

        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def extract_face(self, image, face_rect, target_size=(48, 48)):
        """
        Extract and resize a single face region from the image.

        Adds a 15% padding around the detected bounding box so slight
        occlusion or tight crops don't cut off important facial features.

        Args:
            image: BGR or grayscale numpy array.
            face_rect: Bounding box tuple (x, y, w, h).
            target_size: Output size (width, height) for the face image.

        Returns:
            Grayscale face image resized to target_size, or None on error.
        """
        x, y, w, h = face_rect

        # Convert to grayscale if necessary
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Add 15% padding around the face bounding box
        pad_w = int(w * 0.15)
        pad_h = int(h * 0.15)

        # Crop face region with bounds checking (including padding)
        h_img, w_img = gray.shape[:2]
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(w_img, x + w + pad_w)
        y2 = min(h_img, y + h + pad_h)

        face_roi = gray[y1:y2, x1:x2]

        if face_roi.size == 0:
            return None

        # Resize to target size
        face_resized = cv2.resize(face_roi, target_size, interpolation=cv2.INTER_AREA)

        return face_resized

    def detect_and_extract(self, image, target_size=(48, 48)):
        """
        Convenience method: detect faces and extract the largest one.
        Maintains temporal persistence across brief occlusions so covering
        part of the face momentarily does not immediately fail detection.

        Args:
            image: BGR or grayscale numpy array.
            target_size: Output size for the face image.

        Returns:
            dict with keys:
                'face': Grayscale face image (or None if no face).
                'rect': Bounding box (x, y, w, h) or None.
                'face_count': Total number of faces detected.
                'status': 'ok', 'no_face', or 'multiple_faces'.
        """
        faces = self.detect_faces(image)

        if len(faces) == 0:
            # Check if we have a recent face position to fall back to during momentary occlusion
            if self.last_face_rect is not None and self.missed_frames < self.max_missed:
                self.missed_frames += 1
                face_img = self.extract_face(image, self.last_face_rect, target_size)
                if face_img is not None:
                    return {
                        'face': face_img,
                        'rect': self.last_face_rect,
                        'face_count': 1,
                        'status': 'ok'
                    }

            self.last_face_rect = None
            return {
                'face': None,
                'rect': None,
                'face_count': 0,
                'status': 'no_face'
            }

        # Pick the largest face (by area)
        largest = max(faces, key=lambda f: f[2] * f[3])
        self.last_face_rect = largest
        self.missed_frames = 0
        face_img = self.extract_face(image, largest, target_size)

        status = 'ok' if len(faces) == 1 else 'multiple_faces'

        return {
            'face': face_img,
            'rect': largest,
            'face_count': len(faces),
            'status': status
        }
