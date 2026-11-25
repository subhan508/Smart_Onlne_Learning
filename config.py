"""
Configuration for Smart Online Learning System.
Loads settings from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

class Config:
    """Application configuration."""

    # Flask secret key — used for session signing
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smartlearn-dev-secret-change-in-production')

    # Database
    DATABASE = os.environ.get('DATABASE', os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'smart_learn.db'
    ))

    # SQLAlchemy / PostgreSQL Configuration
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Handle Render/Railway legacy postgres:// scheme
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail / SMTP Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 'yes')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@smartlearn.com')

    # OTP Configuration
    OTP_EXPIRY_MINUTES = int(os.environ.get('OTP_EXPIRY_MINUTES', 10))
    OTP_COOLDOWN_SECONDS = int(os.environ.get('OTP_COOLDOWN_SECONDS', 60))
    OTP_MAX_ATTEMPTS = int(os.environ.get('OTP_MAX_ATTEMPTS', 5))

    # Upload folder for teacher-uploaded files
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'uploads'
    ))

    # Maximum upload size (16 MB)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # Allowed file extensions for uploads
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm'}

    # Emotion model path
    MODEL_PATH = os.environ.get('MODEL_PATH', os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'models', 'emotion_model.h5'
    ))

    # Haar Cascade path for face detection
    HAAR_CASCADE_PATH = os.environ.get('HAAR_CASCADE_PATH', None)  # Uses OpenCV default if None

    # Emotion detection settings
    EMOTION_DETECTION_INTERVAL = 3  # seconds between detections
    EMOTION_LABELS = ['Happy', 'Sad', 'Neutral', 'Confused', 'Bored', 'Focused']

    # Session settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
