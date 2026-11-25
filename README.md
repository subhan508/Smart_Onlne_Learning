# Smart Online Learning System Using Emotion Detection

An intelligent online learning platform that detects student emotions in real time using webcam-based AI facial expression recognition, then provides adaptive learning recommendations to enhance the educational experience.

## 📋 Problem Statement

Traditional online learning platforms lack the ability to understand a student's emotional state during learning sessions. This leads to:

- **Limited engagement**: Students may become bored, confused, or frustrated without the teacher noticing.
- **Non-personalised content**: All students receive the same learning experience regardless of their emotional state.
- **Reduced teacher insight**: Teachers cannot easily identify which students need additional support in a virtual setting.

This system addresses these issues by detecting facial expressions through a webcam, classifying them into emotional categories, and providing adaptive learning responses.

## 🎯 Key Features

### For Students
- 📚 Browse and enrol in courses
- 🎥 Watch video lessons and read notes
- 📝 Take interactive quizzes
- 📷 Real-time webcam emotion detection
- 🤖 AI-powered adaptive learning recommendations
- 📊 Personal emotion and performance analytics
- 📈 Learning progress tracking

### For Teachers
- ✏️ Create and manage courses, lessons, and quizzes
- 👥 View enrolled students
- 📊 Student performance analytics
- 😊 Emotion distribution and engagement analytics
- ⚠️ Identify students needing additional support

### For Administrators
- 👤 User management (activate/deactivate accounts)
- 📋 Course oversight and moderation
- 📈 Platform-wide statistics

### AI/ML Capabilities
- 🔍 Real-time face detection (OpenCV Haar Cascade)
- 🧠 CNN-based facial emotion classification
- 📊 6 emotion categories: Happy, Sad, Neutral, Confused, Bored, Focused
- 💡 Rule-based adaptive recommendation engine
- 📈 Emotion trend analysis and engagement scoring

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Browser   │────▶│  Flask App   │────▶│    SQLite DB    │
│  (HTML/JS)  │◀────│  (Python)    │◀────│                 │
└──────┬──────┘     └──────┬───────┘     └─────────────────┘
       │                   │
  Webcam Frame        ┌────┴────┐
  (base64 JPEG)       │         │
       │          ┌────┴───┐ ┌──┴──────────┐
       ▼          │ OpenCV │ │ TensorFlow  │
  ┌─────────┐    │ (Face  │ │ Keras CNN   │
  │ REST API │───▶│ Detect)│─▶│ (Emotion   │
  └─────────┘    └────────┘  │  Predict)   │
                             └─────────────┘
```

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js |
| **Backend** | Python 3.10+, Flask, Flask-Login |
| **Database** | SQLite (upgrade-ready to MySQL) |
| **AI/CV** | OpenCV, TensorFlow/Keras, CNN |
| **Dataset** | FER2013 (35,887 facial expression images) |

## 📁 Project Structure

```
project/
├── app.py                      # Main Flask application
├── config.py                   # Configuration settings
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
│
├── database/
│   ├── schema.sql              # Database DDL (all tables)
│   ├── database.py             # DB helper functions
│   └── seed.py                 # Demo data seeder
│
├── emotion/
│   ├── detector.py             # Face detection (OpenCV Haar Cascade)
│   ├── preprocessing.py        # Image preprocessing pipeline
│   ├── predictor.py            # CNN emotion prediction
│   ├── adaptive.py             # Adaptive recommendation engine
│   └── train_model.py          # Model training pipeline
│
├── models/
│   └── emotion_model.h5        # Trained CNN model (see setup)
│
├── routes/
│   ├── auth.py                 # Authentication (login/register/logout)
│   ├── student.py              # Student dashboard & analytics
│   ├── teacher.py              # Teacher dashboard & course management
│   ├── admin.py                # Admin user & course management
│   ├── learning.py             # Course browsing, lessons, quizzes
│   └── api.py                  # REST API (emotion detection)
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Base layout template
│   ├── login.html / register.html
│   ├── student_dashboard.html / teacher_dashboard.html / admin_dashboard.html
│   ├── courses.html / course_detail.html / lesson.html
│   ├── quiz.html / quiz_result.html
│   └── ...more templates
│
├── static/
│   ├── css/style.css           # Main stylesheet (dark theme)
│   └── js/
│       ├── main.js             # General UI utilities
│       ├── emotion_detection.js # Webcam client
│       └── charts.js           # Chart.js analytics
│
├── tests/                      # Test suite
│   ├── test_auth.py
│   ├── test_learning.py
│   ├── test_emotion.py
│   └── test_database.py
│
└── uploads/                    # Teacher-uploaded files
```

## 💻 System Requirements

- **Python**: 3.10 or higher
- **Operating System**: Windows, macOS, or Linux
- **RAM**: 4 GB minimum (8 GB recommended for model training)
- **Webcam**: Required for emotion detection feature
- **Browser**: Chrome, Firefox, or Edge (with webcam support)

## 🚀 Installation & Setup

### 1. Clone/Download the Project

```bash
cd your-project-folder
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note**: TensorFlow is ~500 MB. If you only need inference (not training), you can optionally use `tensorflow-lite` instead.

### 4. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env and set a secure SECRET_KEY
```

### 5. Run the Application

```bash
python app.py
```

The app will automatically:
- Create the SQLite database
- Apply the schema
- Seed demo data (users, courses, lessons, quizzes)
- Start the Flask development server on `http://localhost:5000`

## 🗃️ Database Setup

The database is automatically created on first run. To manually reset:

```bash
# Using Flask CLI
flask init-db    # Create tables
flask seed-db    # Insert demo data
```

To switch to **MySQL**, update `config.py` with your MySQL connection string and modify `database.py` to use a MySQL connector instead of `sqlite3`.

## 🧠 Emotion Model Setup

### Option A: Use Fallback Mode (No Training Required)
The app works immediately in **fallback mode** without a trained model. Emotion predictions will be heuristic-based (suitable for UI demonstration).

### Option B: Train the Model

1. **Download FER2013 dataset** from [Kaggle](https://www.kaggle.com/datasets/msambare/fer2013) and place `fer2013.csv` in the project root.

2. **Train the model**:
```bash
python -m emotion.train_model --data_path fer2013.csv --epochs 50 --save_path models/emotion_model.h5
```

3. The trained model is saved to `models/emotion_model.h5` and loaded automatically on next app start.

### Option C: Use a Pre-trained Model
Place any FER2013-compatible `.h5` model in `models/emotion_model.h5`. The system maps FER2013's 7 classes to the project's 6 categories automatically.

### FER2013 → Project Label Mapping
| FER2013 Class | Project Label |
|---------------|--------------|
| Angry | Focused |
| Disgust | Bored |
| Fear | Confused |
| Happy | Happy |
| Sad | Sad |
| Surprise | Confused |
| Neutral | Neutral |

## 🔑 Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| **Admin** | admin@smartlearn.com | admin123 |
| **Teacher** | teacher@smartlearn.com | teacher123 |
| **Student** | student@smartlearn.com | student123 |

## 🎬 Demonstration Workflow

1. **Login** as student → View dashboard with courses, quiz scores, emotion data
2. **Browse courses** → Enrol in a course
3. **Open a lesson** → Watch video, read notes
4. **Enable webcam** → Click "Start Detection" for real-time emotion detection
5. **View recommendations** → AI-generated based on detected emotion
6. **Take a quiz** → Answer MCQs, view score and review
7. **Check analytics** → Emotion distribution, quiz performance trends
8. **Login as teacher** → View student performance, emotion analytics, create courses
9. **Login as admin** → Manage users and courses

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_emotion.py -v
python -m pytest tests/test_learning.py -v
python -m pytest tests/test_database.py -v
```

## 🔒 Security Features

- **Password hashing**: Werkzeug bcrypt-based hashing (passwords never stored in plain text)
- **Role-based access control**: Students, teachers, and admins have separate permissions
- **Protected routes**: Login-required decorators on all sensitive endpoints
- **Session management**: Secure cookies with HttpOnly and SameSite flags
- **Input validation**: Server-side validation for all forms
- **CSRF protection**: Form-based actions use POST methods

## 🔏 Privacy

- Webcam permission is explicitly requested before activation
- **No raw video is stored** — only derived emotion labels and confidence scores
- Users can stop emotion detection at any time
- Clear explanation of why the webcam is being used
- Emotion data is labelled as AI estimation, not psychological assessment

## ⚠️ Limitations

1. **Emotion detection accuracy**: Facial expression detection is an AI estimation and may not always reflect actual emotions. It should not be used for psychological diagnosis.
2. **Lighting sensitivity**: Face detection works best in well-lit environments.
3. **Single face**: Optimised for single-user scenarios; multi-face detection uses the largest face.
4. **FER2013 dataset bias**: The model inherits biases from the training dataset.
5. **No real-time video streaming**: Frames are captured periodically (every 3 seconds) for efficiency.
6. **SQLite concurrency**: SQLite may have write contention under heavy multi-user load; switch to MySQL/PostgreSQL for production.

## 🚀 Future Enhancements

- Voice/speech-based emotion detection
- Real-time video streaming with WebRTC
- Discussion forums and peer interaction
- Certificate generation on course completion
- Mobile responsive native app
- Integration with external LMS platforms
- Multi-language support
- Advanced ML models (transformer-based emotion recognition)
- Student-teacher messaging/chat system
- Gamification (badges, leaderboards)

## 📄 License

This project is developed as an academic project for educational purposes.

---

**Disclaimer**: The emotion detection feature in this system is based on AI facial expression analysis and provides estimations only. It does not provide medical, psychological, or clinical diagnoses. Detected emotions are approximate and should be interpreted accordingly.
