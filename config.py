"""
Configuration for Smart Online Learning System.
Loads settings from environment variables with sensible defaults.
"""

import os
import re
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


def normalize_database_url(raw_url, default_sqlite_path):
    """
    Safely normalize and validate database URL for SQLAlchemy and cloud deployments.
    - Explicitly sets driver dialect to 'postgresql+psycopg2://' so SQLAlchemy loads
      the installed psycopg2-binary driver and avoids driver mismatches.
    - Strips surrounding whitespace and quotes (' or \") from environment variable definitions.
    - Gracefully falls back to SQLite when DATABASE_URL is unset, empty, or whitespace.
    - Validates connection string syntax and produces a clear, descriptive error message
      instead of an obscure startup traceback.
    """
    if raw_url is None:
        return f"sqlite:///{default_sqlite_path}"

    cleaned = str(raw_url).strip().strip("'\"")
    if not cleaned:
        return f"sqlite:///{default_sqlite_path}"

    # Handle Render/Railway legacy postgres:// scheme and standard postgresql://
    # Map to postgresql+psycopg2:// so SQLAlchemy 2.0+ explicitly uses psycopg2
    if cleaned.startswith('postgres://'):
        cleaned = cleaned.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif cleaned.startswith('postgresql://'):
        cleaned = cleaned.replace('postgresql://', 'postgresql+psycopg2://', 1)

    # Validate with SQLAlchemy make_url
    try:
        from sqlalchemy.engine import make_url
        parsed = make_url(cleaned)
        if not parsed.drivername:
            raise ValueError("Missing database scheme in DATABASE_URL")
        return cleaned
    except Exception as err:
        raise ValueError(
            f"Invalid DATABASE_URL configuration: {raw_url!r}. "
            f"Failed to parse database connection string: {err}. "
            f"For PostgreSQL on Render, ensure DATABASE_URL has the format "
            f"'postgresql://user:password@host:port/database' or leave it unset to use local SQLite."
        ) from err


class Config:
    """Application configuration."""

    # Flask secret key — used for session signing
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smartlearn-dev-secret-change-in-production')

    # Environment & Host
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    APP_URL = os.environ.get('APP_URL', 'http://localhost:5000')

    # Database path for local SQLite development
    DATABASE = os.environ.get('DATABASE', os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'smart_learn.db'
    ))

    # SQLAlchemy / PostgreSQL Configuration
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.environ.get('DATABASE_URL'),
        DATABASE
    )
    DATABASE_URL = os.environ.get('DATABASE_URL')
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

    # Emotion model path — defaults to scikit-learn pipeline (.joblib)
    MODEL_PATH = os.environ.get('MODEL_PATH', os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'models', 'emotion_model.joblib'
    ))

    # Haar Cascade path for face detection
    HAAR_CASCADE_PATH = os.environ.get('HAAR_CASCADE_PATH', None)  # Uses OpenCV default if None

    # Emotion detection settings
    EMOTION_DETECTION_INTERVAL = 3  # seconds between detections
    EMOTION_LABELS = ['Happy', 'Sad', 'Neutral', 'Confused', 'Bored', 'Focused']

    # Session settings & HTTPS Cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Enable secure cookies when running on Render or when explicitly set
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1', 'yes') or bool(os.environ.get('RENDER'))
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
