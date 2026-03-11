import os
import sqlite3
from flask import Flask, redirect, url_for
from werkzeug.security import generate_password_hash
from routes.admin import admin_bp
from routes.faculty import faculty_bp
from routes.student import student_bp

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET',
                                'dev-secret-key-change-in-production')

app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(faculty_bp, url_prefix='/faculty')
app.register_blueprint(student_bp, url_prefix='/student')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'faculty', 'student'))
        );

        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS years (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year_number INTEGER UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_id INTEGER NOT NULL,
            year_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(branch_id, year_id, name),
            FOREIGN KEY(branch_id) REFERENCES branches(id) ON DELETE CASCADE,
            FOREIGN KEY(year_id) REFERENCES years(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS faculty_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            department_id INTEGER,
            name TEXT NOT NULL,
            employee_id TEXT UNIQUE NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(department_id) REFERENCES departments(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS student_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            section_id INTEGER,
            branch_id INTEGER,
            year_id INTEGER,
            name TEXT NOT NULL,
            roll_number TEXT UNIQUE NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE SET NULL,
            FOREIGN KEY(branch_id) REFERENCES branches(id) ON DELETE SET NULL,
            FOREIGN KEY(year_id) REFERENCES years(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            section_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL,
            period_number INTEGER NOT NULL CHECK(period_number BETWEEN 1 AND 6),
            UNIQUE(faculty_id, section_id, day_of_week, period_number),
            FOREIGN KEY(faculty_id) REFERENCES faculty_profiles(id) ON DELETE CASCADE,
            FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            period_number INTEGER NOT NULL CHECK(period_number BETWEEN 1 AND 6),
            status TEXT NOT NULL CHECK(status IN ('present', 'absent')),
            faculty_id INTEGER NOT NULL,
            section_id INTEGER NOT NULL,
            UNIQUE(student_id, date, period_number),
            FOREIGN KEY(student_id) REFERENCES student_profiles(id) ON DELETE CASCADE,
            FOREIGN KEY(faculty_id) REFERENCES faculty_profiles(id) ON DELETE CASCADE,
            FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
        );
    ''')

    admin_user = c.execute(
        "SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not admin_user:
        pwd_hash = generate_password_hash('admin123')
        c.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ('admin', pwd_hash, 'admin'))

    for year_num in [1, 2, 3, 4]:
        c.execute("INSERT OR IGNORE INTO years (year_number) VALUES (?)",
                  (year_num, ))

    branches_data = [
        'B.Tech Computer Science and Engineering',
        'B.Tech Electronics and Communication Engineering',
        'B.Tech Mechanical Engineering', 'B.Tech Civil Engineering',
        'B.Tech Electrical and Electronics Engineering'
    ]
    for branch in branches_data:
        c.execute("INSERT OR IGNORE INTO branches (name) VALUES (?)",
                  (branch, ))

    departments_data = [
        'Computer Science and Engineering',
        'Electronics and Communication Engineering', 'Mechanical Engineering',
        'Civil Engineering', 'Electrical and Electronics Engineering'
    ]
    for dept in departments_data:
        c.execute("INSERT OR IGNORE INTO departments (name) VALUES (?)",
                  (dept, ))

    conn.commit()
    conn.close()


app.config['DB_PATH'] = DB_PATH


@app.route('/')
def index():
    return redirect(url_for('student.login'))

with app.app_context():
    try:
        init_db()
    except Exception as e:
        print("DB init error:", e)
      
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
