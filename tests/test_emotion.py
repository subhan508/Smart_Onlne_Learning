"""
Tests for emotion detection — Face detection, prediction, preprocessing.
"""

import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPreprocessing:
    """Test image preprocessing functions."""

    def test_preprocess_valid_face(self):
        from emotion.preprocessing import preprocess_face
        # Create a dummy 48x48 grayscale face image
        face = np.random.randint(0, 256, (48, 48), dtype=np.uint8)
        result = preprocess_face(face)
        assert result is not None
        assert result.shape == (1, 48, 48, 1)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_preprocess_bgr_face(self):
        from emotion.preprocessing import preprocess_face
        # BGR image (3 channels)
        face = np.random.randint(0, 256, (48, 48, 3), dtype=np.uint8)
        result = preprocess_face(face)
        assert result is not None
        assert result.shape == (1, 48, 48, 1)

    def test_preprocess_wrong_size(self):
        from emotion.preprocessing import preprocess_face
        # Different size — should resize
        face = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        result = preprocess_face(face)
        assert result is not None
        assert result.shape == (1, 48, 48, 1)

    def test_preprocess_none_input(self):
        from emotion.preprocessing import preprocess_face
        result = preprocess_face(None)
        assert result is None

    def test_preprocess_empty_array(self):
        from emotion.preprocessing import preprocess_face
        result = preprocess_face(np.array([]))
        assert result is None

    def test_decode_base64_invalid(self):
        from emotion.preprocessing import decode_image_from_base64
        result = decode_image_from_base64('invalid_base64_string')
        assert result is None


class TestFaceDetector:
    """Test face detection."""

    def test_detector_init(self):
        from emotion.detector import FaceDetector
        detector = FaceDetector()
        assert detector.cascade is not None

    def test_detect_no_face(self):
        from emotion.detector import FaceDetector
        detector = FaceDetector()
        # Black image — no face
        image = np.zeros((240, 320, 3), dtype=np.uint8)
        faces = detector.detect_faces(image)
        assert len(faces) == 0

    def test_detect_and_extract_no_face(self):
        from emotion.detector import FaceDetector
        detector = FaceDetector()
        image = np.zeros((240, 320, 3), dtype=np.uint8)
        result = detector.detect_and_extract(image)
        assert result['status'] == 'no_face'
        assert result['face'] is None
        assert result['face_count'] == 0


class TestEmotionPredictor:
    """Test emotion prediction."""

    def test_predictor_fallback_mode(self):
        from emotion.predictor import EmotionPredictor
        # No model file — should use fallback
        predictor = EmotionPredictor(model_path='nonexistent.h5')
        assert not predictor.model_loaded

    def test_fallback_prediction(self):
        from emotion.predictor import EmotionPredictor
        predictor = EmotionPredictor(model_path=None)

        # Create dummy preprocessed face
        face = np.random.rand(1, 48, 48, 1).astype('float32')
        result = predictor.predict(face)

        assert 'emotion' in result
        assert 'confidence' in result
        assert 'all_predictions' in result
        assert result['is_fallback'] is True
        assert result['emotion'] in ['Happy', 'Sad', 'Neutral', 'Confused', 'Bored', 'Focused']
        assert 0.0 <= result['confidence'] <= 1.0

    def test_predict_none_input(self):
        from emotion.predictor import EmotionPredictor
        predictor = EmotionPredictor(model_path=None)
        result = predictor.predict(None)
        assert result['emotion'] == 'Neutral'
        assert result['confidence'] == 0.0

    def test_all_predictions_sum_to_one(self):
        from emotion.predictor import EmotionPredictor
        predictor = EmotionPredictor(model_path=None)
        face = np.random.rand(1, 48, 48, 1).astype('float32')
        result = predictor.predict(face)

        total = sum(result['all_predictions'].values())
        assert abs(total - 1.0) < 0.01  # Should approximately sum to 1


class TestAdaptiveEngine:
    """Test adaptive recommendation engine."""

    def test_get_recommendation(self):
        from emotion.adaptive import get_recommendation
        rec = get_recommendation('Confused')
        assert 'message' in rec
        assert 'action' in rec
        assert 'icon' in rec
        assert 'urgency' in rec
        assert rec['emotion'] == 'Confused'

    def test_recommendation_for_all_emotions(self):
        from emotion.adaptive import get_recommendation
        for emotion in ['Happy', 'Sad', 'Neutral', 'Confused', 'Bored', 'Focused']:
            rec = get_recommendation(emotion)
            assert rec['emotion'] == emotion
            assert len(rec['message']) > 0

    def test_high_urgency_for_persistent_negative(self):
        from emotion.adaptive import get_recommendation
        recent = ['Confused', 'Confused', 'Confused']
        rec = get_recommendation('Confused', recent_emotions=recent)
        assert rec['urgency'] in ('medium', 'high')

    def test_engagement_level(self):
        from emotion.adaptive import get_engagement_level
        result = get_engagement_level(['Focused', 'Focused', 'Happy'])
        assert result['level'] == 'high'
        assert result['score'] >= 70

    def test_low_engagement(self):
        from emotion.adaptive import get_engagement_level
        result = get_engagement_level(['Bored', 'Bored', 'Sad'])
        assert result['level'] == 'low'
        assert result['score'] < 45

    def test_empty_engagement(self):
        from emotion.adaptive import get_engagement_level
        result = get_engagement_level([])
        assert result['level'] == 'medium'
