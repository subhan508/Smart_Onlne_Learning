"""
Database seeder — populates the database with demo data for demonstration.
Creates default admin, teacher, and student accounts, plus sample courses,
lessons, quizzes, and questions.
"""

from werkzeug.security import generate_password_hash
from database.database import get_db, close_db


def seed_all(app):
    """Seed all demo data inside an app context."""
    with app.app_context():
        db = get_db()

        # ------------------------------------------------------------------
        # 1. Demo Users
        # ------------------------------------------------------------------
        users = [
            ('Admin User', 'admin@smartlearn.com', generate_password_hash('admin123'), 'admin'),
            ('Dr. Sarah Johnson', 'teacher@smartlearn.com', generate_password_hash('teacher123'), 'teacher'),
            ('Prof. Michael Chen', 'teacher2@smartlearn.com', generate_password_hash('teacher123'), 'teacher'),
            ('Alex Student', 'student@smartlearn.com', generate_password_hash('student123'), 'student'),
            ('Maria Garcia', 'maria@smartlearn.com', generate_password_hash('student123'), 'student'),
            ('James Wilson', 'james@smartlearn.com', generate_password_hash('student123'), 'student'),
        ]

        for name, email, pw, role in users:
            existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if not existing:
                db.execute(
                    "INSERT INTO users (name, email, password_hash, role, status) VALUES (?, ?, ?, ?, 'approved')",
                    (name, email, pw, role)
                )

        db.commit()

        # Fetch IDs
        teacher1 = db.execute("SELECT id FROM users WHERE email = 'teacher@smartlearn.com'").fetchone()['id']
        teacher2 = db.execute("SELECT id FROM users WHERE email = 'teacher2@smartlearn.com'").fetchone()['id']
        student1 = db.execute("SELECT id FROM users WHERE email = 'student@smartlearn.com'").fetchone()['id']
        student2 = db.execute("SELECT id FROM users WHERE email = 'maria@smartlearn.com'").fetchone()['id']

        # ------------------------------------------------------------------
        # 2. Demo Courses
        # ------------------------------------------------------------------
        courses_data = [
            ('Introduction to Python Programming', 
             'Learn Python from scratch — variables, loops, functions, OOP, and more. Perfect for beginners who want to start their programming journey.',
             teacher1, 'Programming', 1),
            ('Data Structures and Algorithms', 
             'Master fundamental data structures (arrays, linked lists, trees, graphs) and algorithms (sorting, searching, dynamic programming).',
             teacher1, 'Computer Science', 1),
            ('Web Development Fundamentals', 
             'Build modern websites with HTML5, CSS3, and JavaScript. Learn responsive design, DOM manipulation, and web APIs.',
             teacher2, 'Web Development', 1),
            ('Machine Learning Basics', 
             'Introduction to machine learning concepts — supervised learning, classification, regression, neural networks, and model evaluation.',
             teacher2, 'AI / ML', 1),
        ]

        for title, desc, tid, cat, pub in courses_data:
            existing = db.execute('SELECT id FROM courses WHERE title = ?', (title,)).fetchone()
            if not existing:
                db.execute(
                    'INSERT INTO courses (title, description, teacher_id, category, is_published) VALUES (?, ?, ?, ?, ?)',
                    (title, desc, tid, cat, pub)
                )

        db.commit()

        # Fetch course IDs
        course_ids = {}
        for title, *_ in courses_data:
            row = db.execute('SELECT id FROM courses WHERE title = ?', (title,)).fetchone()
            course_ids[title] = row['id']

        python_id = course_ids['Introduction to Python Programming']
        dsa_id = course_ids['Data Structures and Algorithms']
        web_id = course_ids['Web Development Fundamentals']
        ml_id = course_ids['Machine Learning Basics']

        # ------------------------------------------------------------------
        # 3. Demo Lessons
        # ------------------------------------------------------------------
        lessons_data = [
            # Python course
            (python_id, 'Getting Started with Python', 'Install Python, set up your IDE, and write your first program.',
             'https://www.youtube.com/embed/kqtD5dpn9C8', 
             '# Getting Started\n\nPython is a high-level, interpreted programming language known for its simplicity.\n\n## Installing Python\n1. Visit python.org\n2. Download the latest version\n3. Run the installer\n\n## Your First Program\n```python\nprint("Hello, World!")\n```', 1),
            (python_id, 'Variables and Data Types', 'Learn about integers, floats, strings, booleans, and type conversion.',
             'https://www.youtube.com/embed/cQT33yu9pY8',
             '# Variables & Data Types\n\n## Creating Variables\n```python\nname = "Alice"\nage = 25\nheight = 5.6\nis_student = True\n```\n\n## Data Types\n- **int**: Whole numbers\n- **float**: Decimal numbers\n- **str**: Text\n- **bool**: True/False', 2),
            (python_id, 'Control Flow — If/Else and Loops', 'Master conditional statements and loops in Python.',
             'https://www.youtube.com/embed/Zp5MuPOtsSY',
             '# Control Flow\n\n## If/Else\n```python\nif age >= 18:\n    print("Adult")\nelse:\n    print("Minor")\n```\n\n## For Loop\n```python\nfor i in range(5):\n    print(i)\n```\n\n## While Loop\n```python\ncount = 0\nwhile count < 5:\n    print(count)\n    count += 1\n```', 3),
            (python_id, 'Functions and Modules', 'Create reusable functions, understand scope, and import modules.',
             'https://www.youtube.com/embed/9Os0o3wzS_I',
             '# Functions\n\n## Defining a Function\n```python\ndef greet(name):\n    return f"Hello, {name}!"\n\nprint(greet("Alice"))\n```\n\n## Parameters & Return Values\nFunctions can accept parameters and return computed values.', 4),

            # DSA course
            (dsa_id, 'Arrays and Lists', 'Understand arrays, dynamic arrays, and Python lists.',
             'https://www.youtube.com/embed/gDqQf4Ekr2A',
             '# Arrays & Lists\n\nAn array is a contiguous block of memory storing elements of the same type.\n\n## Python Lists\n```python\nnumbers = [1, 2, 3, 4, 5]\nnumbers.append(6)\nprint(numbers[0])  # 1\n```', 1),
            (dsa_id, 'Linked Lists', 'Implement singly and doubly linked lists from scratch.',
             'https://www.youtube.com/embed/R9PTBwOzceo',
             '# Linked Lists\n\nA linked list stores elements in nodes, where each node points to the next.\n\n## Node Class\n```python\nclass Node:\n    def __init__(self, data):\n        self.data = data\n        self.next = None\n```', 2),
            (dsa_id, 'Sorting Algorithms', 'Learn Bubble Sort, Selection Sort, Merge Sort, and Quick Sort.',
             'https://www.youtube.com/embed/kPRA0W1kECg',
             '# Sorting Algorithms\n\n## Bubble Sort — O(n²)\n```python\ndef bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n```', 3),

            # Web Dev course
            (web_id, 'HTML5 Fundamentals', 'Learn HTML tags, structure, forms, and semantic elements.',
             'https://www.youtube.com/embed/UB1O30fR-EE',
             '# HTML5 Fundamentals\n\n## Basic Structure\n```html\n<!DOCTYPE html>\n<html>\n<head><title>My Page</title></head>\n<body>\n  <h1>Hello World</h1>\n</body>\n</html>\n```', 1),
            (web_id, 'CSS3 Styling', 'Style your pages with CSS — selectors, box model, flexbox, grid.',
             'https://www.youtube.com/embed/1PnVor36_40',
             '# CSS3 Styling\n\n## Selectors\n```css\nh1 { color: blue; }\n.container { max-width: 1200px; margin: auto; }\n#header { background: #333; }\n```', 2),
            (web_id, 'JavaScript Basics', 'Add interactivity — variables, DOM manipulation, events.',
             'https://www.youtube.com/embed/W6NZfCO5SIk',
             '# JavaScript Basics\n\n## Variables\n```javascript\nlet name = "Alice";\nconst PI = 3.14;\n```\n\n## DOM Manipulation\n```javascript\ndocument.getElementById("btn").addEventListener("click", () => {\n    alert("Clicked!");\n});\n```', 3),

            # ML course
            (ml_id, 'What is Machine Learning?', 'Overview of ML — types, applications, and the ML workflow.',
             'https://www.youtube.com/embed/ukzFI9rgwfU',
             '# What is Machine Learning?\n\nMachine Learning is a subset of AI that enables systems to learn from data.\n\n## Types\n1. **Supervised Learning** — Labeled data\n2. **Unsupervised Learning** — No labels\n3. **Reinforcement Learning** — Reward-based', 1),
            (ml_id, 'Linear Regression', 'Learn the simplest ML algorithm — predicting continuous values.',
             'https://www.youtube.com/embed/nk2CQITm_eo',
             '# Linear Regression\n\nPredicts a continuous output based on input features.\n\n## Formula\ny = mx + b\n\n## Python Implementation\n```python\nfrom sklearn.linear_model import LinearRegression\nmodel = LinearRegression()\nmodel.fit(X_train, y_train)\n```', 2),
        ]

        for course_id, title, desc, video, notes, order in lessons_data:
            existing = db.execute(
                'SELECT id FROM lessons WHERE course_id = ? AND title = ?',
                (course_id, title)
            ).fetchone()
            if not existing:
                db.execute(
                    'INSERT INTO lessons (course_id, title, description, video_url, notes, order_number) VALUES (?, ?, ?, ?, ?, ?)',
                    (course_id, title, desc, video, notes, order)
                )

        db.commit()

        # ------------------------------------------------------------------
        # 4. Demo Enrollments
        # ------------------------------------------------------------------
        enrollments = [
            (student1, python_id),
            (student1, dsa_id),
            (student1, ml_id),
            (student2, python_id),
            (student2, web_id),
        ]

        for sid, cid in enrollments:
            existing = db.execute(
                'SELECT id FROM enrollments WHERE student_id = ? AND course_id = ?',
                (sid, cid)
            ).fetchone()
            if not existing:
                db.execute(
                    'INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)',
                    (sid, cid)
                )

        db.commit()

        # ------------------------------------------------------------------
        # 5. Demo Quizzes with Questions & Options
        # ------------------------------------------------------------------
        # Get first lesson of Python course
        py_lesson1 = db.execute(
            'SELECT id FROM lessons WHERE course_id = ? ORDER BY order_number LIMIT 1',
            (python_id,)
        ).fetchone()['id']

        existing_quiz = db.execute(
            'SELECT id FROM quizzes WHERE course_id = ? AND title = ?',
            (python_id, 'Python Basics Quiz')
        ).fetchone()

        if not existing_quiz:
            quiz_id = db.execute(
                'INSERT INTO quizzes (course_id, lesson_id, title, description) VALUES (?, ?, ?, ?)',
                (python_id, py_lesson1, 'Python Basics Quiz',
                 'Test your understanding of Python fundamentals.')
            ).lastrowid

            questions_data = [
                ('What is the correct way to declare a variable in Python?', [
                    ('var x = 10', False),
                    ('int x = 10', False),
                    ('x = 10', True),
                    ('declare x = 10', False),
                ]),
                ('Which of the following is a valid Python data type?', [
                    ('character', False),
                    ('string', False),
                    ('str', True),
                    ('text', False),
                ]),
                ('What does the print() function do?', [
                    ('Reads input from the user', False),
                    ('Displays output to the console', True),
                    ('Saves data to a file', False),
                    ('Creates a new variable', False),
                ]),
                ('Which keyword is used to define a function in Python?', [
                    ('function', False),
                    ('func', False),
                    ('define', False),
                    ('def', True),
                ]),
                ('What is the output of: print(type(3.14))?', [
                    ("<class 'int'>", False),
                    ("<class 'float'>", True),
                    ("<class 'str'>", False),
                    ("<class 'double'>", False),
                ]),
            ]

            for i, (q_text, opts) in enumerate(questions_data, 1):
                q_id = db.execute(
                    'INSERT INTO questions (quiz_id, question_text, order_number) VALUES (?, ?, ?)',
                    (quiz_id, q_text, i)
                ).lastrowid

                for opt_text, is_correct in opts:
                    db.execute(
                        'INSERT INTO options (question_id, option_text, is_correct) VALUES (?, ?, ?)',
                        (q_id, opt_text, int(is_correct))
                    )

        # Second quiz for DSA
        dsa_lesson1 = db.execute(
            'SELECT id FROM lessons WHERE course_id = ? ORDER BY order_number LIMIT 1',
            (dsa_id,)
        ).fetchone()['id']

        existing_quiz2 = db.execute(
            'SELECT id FROM quizzes WHERE course_id = ? AND title = ?',
            (dsa_id, 'Arrays & Lists Quiz')
        ).fetchone()

        if not existing_quiz2:
            quiz_id2 = db.execute(
                'INSERT INTO quizzes (course_id, lesson_id, title, description) VALUES (?, ?, ?, ?)',
                (dsa_id, dsa_lesson1, 'Arrays & Lists Quiz',
                 'Test your knowledge of arrays and list operations.')
            ).lastrowid

            questions_data2 = [
                ('What is the time complexity of accessing an element in an array by index?', [
                    ('O(n)', False),
                    ('O(1)', True),
                    ('O(log n)', False),
                    ('O(n²)', False),
                ]),
                ('Which Python method adds an element to the end of a list?', [
                    ('insert()', False),
                    ('add()', False),
                    ('append()', True),
                    ('push()', False),
                ]),
                ('What is the main advantage of linked lists over arrays?', [
                    ('Faster access by index', False),
                    ('Less memory usage', False),
                    ('Dynamic size and efficient insertion/deletion', True),
                    ('Better cache performance', False),
                ]),
            ]

            for i, (q_text, opts) in enumerate(questions_data2, 1):
                q_id = db.execute(
                    'INSERT INTO questions (quiz_id, question_text, order_number) VALUES (?, ?, ?)',
                    (quiz_id2, q_text, i)
                ).lastrowid

                for opt_text, is_correct in opts:
                    db.execute(
                        'INSERT INTO options (question_id, option_text, is_correct) VALUES (?, ?, ?)',
                        (q_id, opt_text, int(is_correct))
                    )

        db.commit()
        close_db()

        print('[SEED] Demo data inserted successfully.')
