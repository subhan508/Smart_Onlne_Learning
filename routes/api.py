"""
REST API routes — Emotion detection endpoint, analytics, and recommendations.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from database.database import query_db, execute_db
from emotion.preprocessing import decode_image_from_base64, preprocess_face
from emotion.adaptive import get_recommendation, get_engagement_level

api_bp = Blueprint('api', __name__)

# Module-level singletons (initialised lazily)
_face_detector = None
_emotion_predictor = None


def _get_detector():
    """Lazily initialise the face detector."""
    global _face_detector
    if _face_detector is None:
        from emotion.detector import FaceDetector
        cascade_path = current_app.config.get('HAAR_CASCADE_PATH')
        _face_detector = FaceDetector(cascade_path=cascade_path)
    return _face_detector


def _get_predictor():
    """Lazily initialise the emotion predictor."""
    global _emotion_predictor
    if _emotion_predictor is None:
        from emotion.predictor import EmotionPredictor
        model_path = current_app.config.get('MODEL_PATH')
        _emotion_predictor = EmotionPredictor(model_path=model_path)
    return _emotion_predictor


@api_bp.route('/detect_emotion', methods=['POST'])
@login_required
def detect_emotion():
    """
    Receive a webcam frame, detect face, predict emotion, store log,
    and return the result with an adaptive recommendation.

    Expects JSON body:
    {
        "image": "data:image/jpeg;base64,...",
        "course_id": 1,       (optional)
        "lesson_id": 1        (optional)
    }

    Returns JSON:
    {
        "success": true,
        "emotion": "Happy",
        "confidence": 0.87,
        "all_predictions": { ... },
        "face_count": 1,
        "face_status": "ok",
        "recommendation": { ... },
        "engagement": { ... },
        "is_fallback": false
    }
    """
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'success': False, 'error': 'No image data provided.'}), 400

        image_data = data['image']
        course_id = data.get('course_id')
        lesson_id = data.get('lesson_id')

        # 1. Decode base64 image
        image = decode_image_from_base64(image_data)
        if image is None:
            return jsonify({'success': False, 'error': 'Failed to decode image.'}), 400

        # 2. Detect face
        detector = _get_detector()
        result = detector.detect_and_extract(image, target_size=(48, 48))

        if result['status'] == 'no_face':
            return jsonify({
                'success': False,
                'error': 'No face detected. Please ensure your face is visible to the camera.',
                'face_count': 0,
                'face_status': 'no_face'
            })

        face_warning = None
        if result['status'] == 'multiple_faces':
            face_warning = 'Multiple faces detected. Using the largest face.'

        # 3. Preprocess face
        preprocessed = preprocess_face(result['face'])
        if preprocessed is None:
            return jsonify({'success': False, 'error': 'Failed to preprocess face image.'}), 400

        # 4. Predict emotion (with temporal smoothing per student session)
        predictor = _get_predictor()
        prediction = predictor.predict(preprocessed, student_id=current_user.id)

        # 5. Get recent emotions for trend analysis
        recent = query_db('''
            SELECT emotion FROM emotion_logs
            WHERE student_id = ?
            ORDER BY timestamp DESC LIMIT 10
        ''', [current_user.id])
        recent_emotions = [r['emotion'] for r in recent]

        # 6. Get adaptive recommendation
        recommendation = get_recommendation(prediction['emotion'], recent_emotions)

        # 7. Get engagement level
        engagement = get_engagement_level(recent_emotions + [prediction['emotion']])

        # 8. Store emotion log in database
        execute_db('''
            INSERT INTO emotion_logs (student_id, course_id, lesson_id, emotion, confidence)
            VALUES (?, ?, ?, ?, ?)
        ''', (current_user.id, course_id, lesson_id,
              prediction['emotion'], prediction['confidence']))

        # 9. Store recommendation if urgency is not low
        if recommendation['urgency'] != 'low':
            execute_db('''
                INSERT INTO recommendations (student_id, course_id, lesson_id, emotion, recommendation, action_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (current_user.id, course_id, lesson_id,
                  prediction['emotion'], recommendation['message'], recommendation['action']))

        # 10. Build response
        response = {
            'success': True,
            'emotion': prediction['emotion'],
            'confidence': prediction['confidence'],
            'all_predictions': prediction['all_predictions'],
            'face_count': result['face_count'],
            'face_status': result['status'],
            'recommendation': recommendation,
            'engagement': engagement,
            'is_fallback': prediction['is_fallback']
        }

        if face_warning:
            response['warning'] = face_warning

        return jsonify(response)

    except Exception as e:
        print(f'[API] Error in detect_emotion: {e}')
        return jsonify({'success': False, 'error': 'Internal server error.'}), 500


@api_bp.route('/emotion_history')
@login_required
def emotion_history():
    """Get emotion history for the current student."""
    limit = request.args.get('limit', 50, type=int)
    course_id = request.args.get('course_id', type=int)

    query = '''
        SELECT emotion, confidence, timestamp, course_id, lesson_id
        FROM emotion_logs WHERE student_id = ?
    '''
    params = [current_user.id]

    if course_id:
        query += ' AND course_id = ?'
        params.append(course_id)

    query += ' ORDER BY timestamp DESC LIMIT ?'
    params.append(limit)

    logs = query_db(query, params)

    return jsonify({
        'success': True,
        'logs': [dict(log) for log in logs]
    })


@api_bp.route('/emotion_distribution')
@login_required
def emotion_distribution():
    """Get emotion distribution for the current student."""
    student_id = request.args.get('student_id', current_user.id, type=int)

    # Teachers can view their students' data
    if current_user.role == 'teacher' and student_id != current_user.id:
        pass  # Allow teachers to query student data
    elif current_user.role == 'admin':
        pass  # Admins can see everything
    else:
        student_id = current_user.id  # Students can only see their own data

    dist = query_db('''
        SELECT emotion, COUNT(*) as count, AVG(confidence) as avg_confidence
        FROM emotion_logs WHERE student_id = ?
        GROUP BY emotion ORDER BY count DESC
    ''', [student_id])

    return jsonify({
        'success': True,
        'distribution': [dict(d) for d in dist]
    })
