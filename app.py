"""
Smart Online Learning System Using Emotion Detection
=====================================================
Main Flask application entry point.
Registers all blueprints, initializes database, and configures sessions.
"""

import os
from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager, current_user
from config import Config
from database.database import get_db, close_db, init_db

# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure required directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, 'images'), exist_ok=True)

    # -----------------------------------------------------------------------
    # Reverse proxy support (for Render / HTTPS edge SSL termination)
    # -----------------------------------------------------------------------
    if os.environ.get('RENDER') or app.config.get('SESSION_COOKIE_SECURE'):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # -----------------------------------------------------------------------
    # Initialize SQLAlchemy ORM
    # -----------------------------------------------------------------------
    from database.models import db
    db.init_app(app)

    # -----------------------------------------------------------------------
    # Database teardown — close connection at end of each request
    # -----------------------------------------------------------------------
    app.teardown_appcontext(close_db)

    # -----------------------------------------------------------------------
    # Flask-Login setup
    # -----------------------------------------------------------------------
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    from database.database import query_db

    class User:
        """User class for Flask-Login."""
        def __init__(self, user_row):
            self.id = user_row['id']
            self.name = user_row['name']
            self.email = user_row['email']
            self.role = user_row['role']
            keys = user_row.keys() if hasattr(user_row, 'keys') else []
            self.status = user_row['status'] if 'status' in keys else 'approved'
            self.rejection_reason = user_row['rejection_reason'] if 'rejection_reason' in keys else None
            self.is_active_user = user_row['is_active']

        @property
        def is_authenticated(self):
            return True

        @property
        def is_active(self):
            return bool(self.is_active_user)

        @property
        def is_approved(self):
            return self.status == 'approved'

        @property
        def is_anonymous(self):
            return False

        def get_id(self):
            return str(self.id)

    # Store User class on app for access elsewhere
    app.User = User

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login session management."""
        row = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
        if row:
            return User(row)
        return None

    # -----------------------------------------------------------------------
    # Register Blueprints
    # -----------------------------------------------------------------------
    from routes.auth import auth_bp
    from routes.student import student_bp
    from routes.teacher import teacher_bp
    from routes.admin import admin_bp
    from routes.learning import learning_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(learning_bp, url_prefix='/learn')
    app.register_blueprint(api_bp, url_prefix='/api')

    # -----------------------------------------------------------------------
    # Health check endpoint (for Render / Railway / uptime monitors)
    # -----------------------------------------------------------------------
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'smartlearn'}, 200

    # -----------------------------------------------------------------------
    # Root route — redirect based on role & approval status
    # -----------------------------------------------------------------------
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if getattr(current_user, 'status', 'approved') != 'approved':
                return redirect(url_for('auth.account_status'))
            if current_user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif current_user.role == 'teacher':
                return redirect(url_for('teacher.dashboard'))
            else:
                return redirect(url_for('student.dashboard'))
        return redirect(url_for('auth.login'))

    # -----------------------------------------------------------------------
    # Error handlers
    # -----------------------------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    # -----------------------------------------------------------------------
    # CLI command to initialise the database
    # -----------------------------------------------------------------------
    @app.cli.command('init-db')
    def init_db_command():
        """Clear existing data and create fresh tables."""
        init_db(app)
        print('Database initialised.')

    @app.cli.command('seed-db')
    def seed_db_command():
        """Seed the database with demo data."""
        from database.seed import seed_all
        seed_all(app)
        print('Database seeded with demo data.')

    return app


# ---------------------------------------------------------------------------
# Run the application
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app = create_app()
    # Initialize DB if it doesn't exist yet
    db_path = app.config.get('DATABASE', 'smart_learn.db')
    if not os.path.exists(db_path):
        init_db(app)
        from database.seed import seed_all
        seed_all(app)
        print('[INFO] Database created and seeded with demo data.')
    
    port = int(os.environ.get('PORT', 5000))
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
            test_sock.bind(('0.0.0.0', port))
    except OSError:
        port = 5001

    print(f'[INFO] Starting server on http://localhost:{port}')
    app.run(debug=True, host='0.0.0.0', port=port)
