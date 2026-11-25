"""
Emotion Prediction Module
=========================
Loads a trained model and predicts emotions from preprocessed face images.

Supports:
    1. Scikit-learn pipeline (.joblib file) — Multi-region HOG + MLP with probability calibration.
    2. Full TensorFlow/Keras model (.h5 file) — if TensorFlow is installed.
    3. Fallback heuristic prediction — if no model is available (dev/demo).

Includes:
    - Temporal Probability Smoothing (EMA): Prevents frame-to-frame emotion jittering/flicker.
    - Hysteresis & Stability Dampening: Ensures stable, natural emotion transitions.
"""

import numpy as np
import os
import time
import cv2


# FER2013 original class labels (in index order)
FER2013_LABELS = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

# Project emotion labels
PROJECT_LABELS = ['Happy', 'Sad', 'Neutral', 'Confused', 'Bored', 'Focused']

# Mapping from FER2013 index to project label
FER2013_TO_PROJECT = {
    0: 'Focused',   # Angry → Focused (concentration / intensity)
    1: 'Bored',     # Disgust → Bored
    2: 'Confused',  # Fear → Confused
    3: 'Happy',     # Happy → Happy
    4: 'Sad',       # Sad → Sad
    5: 'Confused',  # Surprise → Confused
    6: 'Neutral',   # Neutral → Neutral
}

# HOG descriptors
_hog_full = cv2.HOGDescriptor((48, 48), (16, 16), (8, 8), (8, 8), 9)
_hog_region = cv2.HOGDescriptor((48, 24), (16, 16), (8, 8), (8, 8), 9)


def _extract_features_for_model(gray48, expected_dims=None):
    """
    Extract facial features matching the model's expected dimension.
    Supports both 1684-dim (multi-region) and 964-dim (single-region) models.
    """
    if gray48.shape != (48, 48):
        gray48 = cv2.resize(gray48, (48, 48))

    f_full = _hog_full.compute(gray48).flatten()
    small = cv2.resize(gray48, (8, 8)).flatten().astype(np.float32) / 255.0

    if expected_dims == 964:
        return np.hstack([f_full, small])

    # Default to 1684 dims (multi-region: full + upper brows/eyes + lower mouth/chin)
    f_upper = _hog_region.compute(gray48[0:24, :]).flatten()
    f_lower = _hog_region.compute(gray48[24:48, :]).flatten()
    return np.hstack([f_full, f_upper, f_lower, small])


class EmotionPredictor:
    """
    Predicts facial emotions using a trained model.
    Applies per-student temporal smoothing and hysteresis to eliminate
    frame-to-frame flicker and ensure smooth, natural emotion transitions.
    """

    def __init__(self, model_path=None):
        self.model = None
        self.sklearn_pipeline = None
        self.sklearn_classes = None
        self.model_loaded = False
        self.model_type = None  # 'sklearn', 'keras', or None
        self.model_path = model_path
        self.expected_features = 1684

        # Temporal smoothing state per student session: {student_id: {'probs': dict, 'dominant': str, 'last_time': float}}
        self.smoothed_states = {}
        self.smoothing_alpha = 0.35      # 35% current frame, 65% history for smooth transitions
        self.hysteresis_margin = 0.08    # New emotion needs 8% margin over current dominant to switch

        # Derive possible paths for both model types
        joblib_path = None
        h5_path = None

        if model_path:
            base, ext = os.path.splitext(model_path)
            joblib_path = base + '.joblib'
            h5_path = base + '.h5'
            if ext == '.joblib':
                joblib_path = model_path
            elif ext == '.h5':
                h5_path = model_path

        # --- Try scikit-learn .joblib first ---
        if joblib_path and os.path.exists(joblib_path):
            try:
                import joblib
                data = joblib.load(joblib_path)
                if isinstance(data, dict) and 'pipeline' in data:
                    self.sklearn_pipeline = data['pipeline']
                    self.sklearn_classes = data.get('classes', list(data['pipeline'].classes_))
                else:
                    self.sklearn_pipeline = data
                    self.sklearn_classes = list(data.classes_)

                # Inspect expected feature dimension
                try:
                    scaler = self.sklearn_pipeline.named_steps.get('scaler')
                    if scaler and hasattr(scaler, 'n_features_in_'):
                        self.expected_features = int(scaler.n_features_in_)
                except Exception:
                    self.expected_features = 1684

                self.model_loaded = True
                self.model_type = 'sklearn'
                print(f'[EmotionPredictor] Sklearn model loaded from {joblib_path} (features: {self.expected_features})')
                return
            except Exception as e:
                print(f'[EmotionPredictor] Failed to load sklearn model: {e}')

        # --- Try TensorFlow/Keras .h5 ---
        if h5_path and os.path.exists(h5_path):
            try:
                import tensorflow as tf
                os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
                tf.get_logger().setLevel('ERROR')
                self.model = tf.keras.models.load_model(h5_path, compile=False)
                self.model_loaded = True
                self.model_type = 'keras'
                print(f'[EmotionPredictor] Keras model loaded from {h5_path}')
                return
            except Exception as e:
                print(f'[EmotionPredictor] Failed to load Keras model: {e}')

        print('[EmotionPredictor] No model file found. Using fallback prediction mode.')

    def predict(self, preprocessed_face, student_id=None):
        """
        Predict emotion from preprocessed face with temporal smoothing.

        Args:
            preprocessed_face: (1, 48, 48, 1) normalized numpy array.
            student_id: Optional ID of the student session for temporal continuity.

        Returns:
            dict with:
                'emotion': Smoothed, stable dominant emotion label.
                'confidence': Confidence of dominant emotion.
                'all_predictions': Smoothed probability distribution.
                'raw_predictions': Instant frame probability distribution.
                'is_fallback': Boolean flag.
        """
        if preprocessed_face is None:
            return self._empty_prediction()

        # 1. Obtain raw single-frame probability scores
        if self.model_loaded and self.model_type == 'sklearn':
            raw_scores = self._sklearn_raw_predict(preprocessed_face)
        elif self.model_loaded and self.model_type == 'keras':
            raw_scores = self._keras_raw_predict(preprocessed_face)
        else:
            return self._fallback_predict(preprocessed_face)

        if not raw_scores:
            return self._empty_prediction()

        # 2. Apply temporal smoothing (EMA) and hysteresis per student session
        key = str(student_id if student_id is not None else 'default')
        now = time.time()
        state = self.smoothed_states.get(key)

        # Reset smoothing if previous frame was more than 15 seconds ago
        if state is None or (now - state.get('last_time', 0) > 15.0):
            smoothed_scores = dict(raw_scores)
            dominant = max(smoothed_scores, key=smoothed_scores.get)
        else:
            prev_probs = state['probs']
            prev_dominant = state['dominant']

            # Exponential Moving Average: S_t = alpha * P_t + (1 - alpha) * S_{t-1}
            smoothed_scores = {}
            for label in PROJECT_LABELS:
                smoothed_scores[label] = (
                    self.smoothing_alpha * raw_scores.get(label, 0.0) +
                    (1.0 - self.smoothing_alpha) * prev_probs.get(label, 0.0)
                )

            # Re-normalize to sum to 1.0
            tot = sum(smoothed_scores.values())
            if tot > 0:
                smoothed_scores = {k: v / tot for k, v in smoothed_scores.items()}

            # Hysteresis dampening: only switch if candidate is significantly stronger
            candidate_dominant = max(smoothed_scores, key=smoothed_scores.get)
            if candidate_dominant != prev_dominant:
                candidate_prob = smoothed_scores[candidate_dominant]
                prev_prob = smoothed_scores.get(prev_dominant, 0.0)

                if (candidate_prob > prev_prob + self.hysteresis_margin) or (prev_prob < 0.20):
                    dominant = candidate_dominant
                else:
                    dominant = prev_dominant
            else:
                dominant = candidate_dominant

        # Save state
        self.smoothed_states[key] = {
            'probs': smoothed_scores,
            'dominant': dominant,
            'last_time': now
        }

        confidence = smoothed_scores[dominant]

        return {
            'emotion': str(dominant),
            'confidence': round(float(confidence), 4),
            'all_predictions': {str(k): round(float(v), 4) for k, v in sorted(
                smoothed_scores.items(), key=lambda x: x[1], reverse=True
            )},
            'raw_predictions': {str(k): round(float(v), 4) for k, v in sorted(
                raw_scores.items(), key=lambda x: x[1], reverse=True
            )},
            'is_fallback': False
        }

    def _sklearn_raw_predict(self, preprocessed_face):
        """Predict raw probabilities using scikit-learn pipeline."""
        try:
            face = (preprocessed_face.reshape(48, 48) * 255).astype(np.uint8)
            features = _extract_features_for_model(face, expected_dims=self.expected_features).reshape(1, -1)

            proba = self.sklearn_pipeline.predict_proba(features)[0]
            classes = list(self.sklearn_pipeline.classes_)

            scores = {cls: float(prob) for cls, prob in zip(classes, proba)}
            for label in PROJECT_LABELS:
                scores.setdefault(label, 0.0)

            return scores
        except Exception as e:
            print(f'[EmotionPredictor] Sklearn prediction error: {e}')
            return None

    def _keras_raw_predict(self, preprocessed_face):
        """Predict raw probabilities using Keras model."""
        try:
            predictions = self.model.predict(preprocessed_face, verbose=0)[0]
            project_scores = {}
            for idx, score in enumerate(predictions):
                project_label = FER2013_TO_PROJECT.get(idx, 'Neutral')
                project_scores[project_label] = project_scores.get(project_label, 0) + float(score)

            total = sum(project_scores.values())
            if total > 0:
                project_scores = {k: v / total for k, v in project_scores.items()}

            return project_scores
        except Exception as e:
            print(f'[EmotionPredictor] Keras prediction error: {e}')
            return None

    def _fallback_predict(self, preprocessed_face):
        """Fallback prediction when no model is available."""
        try:
            face = preprocessed_face.reshape(48, 48)
            mean_val = float(np.mean(face))
            std_val = float(np.std(face))

            face_uint8 = (face * 255).astype(np.uint8)
            edges = cv2.Sobel(face_uint8, cv2.CV_64F, 1, 1, ksize=3)
            edge_density = float(np.mean(np.abs(edges))) / 255.0

            scores = {
                'Happy':    0.1 + mean_val * 0.3 + edge_density * 0.2,
                'Sad':      0.1 + (1 - mean_val) * 0.2,
                'Neutral':  0.2 + (1 - abs(mean_val - 0.5)) * 0.3,
                'Confused': 0.1 + std_val * 0.3,
                'Bored':    0.1 + (1 - edge_density) * 0.2,
                'Focused':  0.1 + edge_density * 0.3 + std_val * 0.1,
            }

            noise = np.random.dirichlet(np.ones(6)) * 0.15
            for i, label in enumerate(PROJECT_LABELS):
                scores[label] += noise[i]

            total = sum(scores.values())
            scores = {k: v / total for k, v in scores.items()}
            dominant = max(scores, key=scores.get)

            return {
                'emotion': str(dominant),
                'confidence': round(float(scores[dominant]), 4),
                'all_predictions': {str(k): round(float(v), 4) for k, v in sorted(
                    scores.items(), key=lambda x: x[1], reverse=True
                )},
                'is_fallback': True
            }
        except Exception:
            return self._empty_prediction()

    def _empty_prediction(self):
        return {
            'emotion': 'Neutral',
            'confidence': 0.0,
            'all_predictions': {label: 0.0 for label in PROJECT_LABELS},
            'is_fallback': True
        }
