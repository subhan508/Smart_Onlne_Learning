"""
Adaptive Learning Response Engine
=================================
Generates personalised learning recommendations based on detected student emotions.

Rules are based on educational psychology principles:
  - Confused students need simpler explanations and scaffolding.
  - Bored students need engagement and variety.
  - Sad/frustrated students need support and encouragement.
  - Focused students should continue without interruption.
  - Happy students are receptive to challenges.
  - Neutral is the default "continue as normal" state.

IMPORTANT: This module does NOT make medical or psychological diagnoses.
It only suggests educational responses based on AI-estimated facial expressions.
"""

import random
from datetime import datetime


# ── Recommendation Templates ──
# Each emotion maps to a list of possible recommendations.
# The system picks contextually appropriate ones and avoids repetition.

RECOMMENDATIONS = {
    'Confused': [
        {
            'message': "It looks like you might be finding this challenging. Consider revisiting the key concepts from the beginning of this lesson.",
            'action': 'review',
            'icon': 'question-circle'
        },
        {
            'message': "Would you like a simplified explanation? Sometimes a different perspective helps clarify things.",
            'action': 'simplify',
            'icon': 'lightbulb'
        },
        {
            'message': "Try taking the related quiz — it can help identify which specific concepts need more attention.",
            'action': 'quiz',
            'icon': 'patch-question'
        },
        {
            'message': "Looking at the prerequisite material might help build a stronger foundation for this topic.",
            'action': 'prerequisite',
            'icon': 'arrow-counterclockwise'
        },
        {
            'message': "Don't worry — complex topics take time. Try reading the notes alongside the video for better understanding.",
            'action': 'notes',
            'icon': 'journal-text'
        },
    ],

    'Bored': [
        {
            'message': "Let's make things more interactive! Try the quiz to test your knowledge on this topic.",
            'action': 'quiz',
            'icon': 'controller'
        },
        {
            'message': "You seem comfortable with this material. Would you like to skip ahead to the next lesson?",
            'action': 'next',
            'icon': 'skip-forward'
        },
        {
            'message': "Try a hands-on exercise — applying what you've learned can make it more engaging.",
            'action': 'exercise',
            'icon': 'code-slash'
        },
        {
            'message': "Consider exploring additional resources on this topic for a deeper understanding.",
            'action': 'resources',
            'icon': 'link-45deg'
        },
    ],

    'Sad': [
        {
            'message': "It's okay to take a short break. Rest can help you come back refreshed and ready to learn.",
            'action': 'break',
            'icon': 'cup-hot'
        },
        {
            'message': "Would you like to review some easier material first? Building confidence helps with learning.",
            'action': 'review',
            'icon': 'arrow-counterclockwise'
        },
        {
            'message': "Remember, learning is a journey. Every step forward counts, even small ones.",
            'action': 'encouragement',
            'icon': 'emoji-smile'
        },
        {
            'message': "Try the simpler quiz to build your confidence before tackling harder content.",
            'action': 'easy_quiz',
            'icon': 'star'
        },
    ],

    'Happy': [
        {
            'message': "Great to see you're enjoying this! Keep up the momentum.",
            'action': 'continue',
            'icon': 'emoji-laughing'
        },
        {
            'message': "You're doing well! Ready for a challenge? Try the quiz to test your understanding.",
            'action': 'quiz',
            'icon': 'trophy'
        },
        {
            'message': "Excellent mood! This is a great time to tackle advanced material on this topic.",
            'action': 'advanced',
            'icon': 'rocket-takeoff'
        },
    ],

    'Focused': [
        {
            'message': "You're deeply focused — excellent! Continue at your own pace.",
            'action': 'continue',
            'icon': 'bullseye'
        },
        {
            'message': "Great concentration! When you're ready, the quiz will help reinforce what you've learned.",
            'action': 'quiz_later',
            'icon': 'clock'
        },
    ],

    'Neutral': [
        {
            'message': "You're progressing steadily. Keep going!",
            'action': 'continue',
            'icon': 'check-circle'
        },
        {
            'message': "Take your time with the material. Consider making notes for better retention.",
            'action': 'notes',
            'icon': 'pencil'
        },
    ],
}


def get_recommendation(emotion, recent_emotions=None):
    """
    Get an adaptive learning recommendation based on the detected emotion.

    Args:
        emotion: Current detected emotion string (e.g. 'Confused').
        recent_emotions: Optional list of recent emotion strings for trend analysis.

    Returns:
        dict with:
            'message': Recommendation text.
            'action': Action type (e.g. 'quiz', 'review', 'break').
            'icon': Bootstrap icon name.
            'urgency': 'low', 'medium', or 'high'.
            'emotion': The emotion this recommendation is based on.
    """
    emotion = emotion.strip().capitalize() if emotion else 'Neutral'

    # Default to Neutral if unrecognised
    if emotion not in RECOMMENDATIONS:
        emotion = 'Neutral'

    # Check for persistent negative emotions (trend analysis)
    urgency = 'low'
    if recent_emotions and len(recent_emotions) >= 3:
        recent_3 = recent_emotions[-3:]
        negative_emotions = {'Confused', 'Bored', 'Sad'}

        neg_count = sum(1 for e in recent_3 if e in negative_emotions)
        if neg_count >= 3:
            urgency = 'high'
        elif neg_count >= 2:
            urgency = 'medium'

    # Select a recommendation (varies to avoid repetition)
    options = RECOMMENDATIONS[emotion]
    rec = random.choice(options)

    # For high urgency, prefer more supportive actions
    if urgency == 'high' and emotion in ('Confused', 'Bored', 'Sad'):
        # Pick a recommendation with a supportive action
        supportive = [r for r in options if r['action'] in ('break', 'review', 'simplify', 'prerequisite')]
        if supportive:
            rec = random.choice(supportive)

    return {
        'message': rec['message'],
        'action': rec['action'],
        'icon': rec['icon'],
        'urgency': urgency,
        'emotion': emotion,
        'timestamp': datetime.now().isoformat()
    }


def get_engagement_level(recent_emotions):
    """
    Calculate an engagement level from recent emotion history.

    Args:
        recent_emotions: List of emotion strings (most recent last).

    Returns:
        dict with:
            'level': 'high', 'medium', or 'low'.
            'score': Numeric engagement score (0-100).
            'description': Human-readable engagement description.
    """
    if not recent_emotions:
        return {'level': 'medium', 'score': 50, 'description': 'No data yet'}

    # Assign engagement scores to emotions
    engagement_scores = {
        'Focused': 90,
        'Happy': 80,
        'Neutral': 60,
        'Confused': 40,
        'Sad': 30,
        'Bored': 20,
    }

    scores = [engagement_scores.get(e, 50) for e in recent_emotions]
    avg_score = sum(scores) / len(scores)

    if avg_score >= 70:
        level = 'high'
        desc = 'Highly engaged — student is focused and attentive.'
    elif avg_score >= 45:
        level = 'medium'
        desc = 'Moderately engaged — mix of attention levels.'
    else:
        level = 'low'
        desc = 'Low engagement — student may need support or a break.'

    return {
        'level': level,
        'score': round(avg_score),
        'description': desc
    }
