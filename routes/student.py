import sqlite3
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash, current_app)
from werkzeug.security import check_password_hash
from functools import wraps

student_bp = Blueprint('student', __name__)


def get_db():
    conn = sqlite3.connect(current_app.config['DB_PATH'])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def student_required(f):

    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'student':
            flash('Access denied. Student login required.', 'danger')
            return redirect(url_for('student.login'))
        return f(*args, **kwargs)

    return decorated


@student_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('role') == 'student':
        return redirect(url_for('student.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND role='student'",
            (username, )).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            sp = db.execute("SELECT * FROM student_profiles WHERE user_id=?",
                            (user['id'], )).fetchone()
            db.close()
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = 'student'
            session['student_id'] = sp['id'] if sp else None
            session['student_name'] = sp['name'] if sp else user['username']
            return redirect(url_for('student.dashboard'))
        db.close()
        flash('Invalid student credentials.', 'danger')
    return render_template('student/login.html')


@student_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('student.login'))


@student_bp.route('/dashboard')
@student_required
def dashboard():
    db = get_db()
    student_id = session.get('student_id')
    sp = db.execute(
        '''SELECT sp.*, b.name as branch_name, y.year_number, sec.name as section_name
           FROM student_profiles sp
           LEFT JOIN branches b ON sp.branch_id = b.id
           LEFT JOIN years y ON sp.year_id = y.id
           LEFT JOIN sections sec ON sp.section_id = sec.id
           WHERE sp.id = ?''', (student_id, )).fetchone()
    total = db.execute("SELECT COUNT(*) FROM attendance WHERE student_id=?",
                       (student_id, )).fetchone()[0]
    present = db.execute(
        "SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='present'",
        (student_id, )).fetchone()[0]
    percentage = round((present / total * 100), 2) if total > 0 else 0
    recent = db.execute(
        '''SELECT a.date, a.period_number, a.status
           FROM attendance a WHERE a.student_id=?
           ORDER BY a.date DESC, a.period_number DESC LIMIT 10''',
        (student_id, )).fetchall()
    db.close()
    return render_template('student/dashboard.html',
                           student=sp,
                           total=total,
                           present=present,
                           absent=total - present,
                           percentage=percentage,
                           recent=recent)


@student_bp.route('/attendance')
@student_required
def view_attendance():
    db = get_db()
    student_id = session.get('student_id')
    filter_date = request.args.get('date', '')
    filter_period = request.args.get('period_number', '')
    filter_status = request.args.get('status', '')

    query = '''SELECT a.date, a.period_number, a.status, fp.name as faculty_name
               FROM attendance a
               JOIN faculty_profiles fp ON a.faculty_id = fp.id
               WHERE a.student_id = ?'''
    params = [student_id]
    if filter_date:
        query += ' AND a.date = ?'
        params.append(filter_date)
    if filter_period:
        query += ' AND a.period_number = ?'
        params.append(int(filter_period))
    if filter_status:
        query += ' AND a.status = ?'
        params.append(filter_status)
    query += ' ORDER BY a.date DESC, a.period_number'
    rows = db.execute(query, params).fetchall()

    attendance_by_date = {}

    for r in rows:
        d = r['date']
        p = r['period_number']

        if d not in attendance_by_date:
            attendance_by_date[d] = {}

        attendance_by_date[d][p] = r['status']

    total = db.execute("SELECT COUNT(*) FROM attendance WHERE student_id=?",
                       (student_id, )).fetchone()[0]
    present = db.execute(
        "SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='present'",
        (student_id, )).fetchone()[0]
    percentage = round((present / total * 100), 2) if total > 0 else 0
    db.close()
    return render_template('student/view_attendance.html',
                           attendance_by_date=attendance_by_date,
                           total=total,
                           present=present,
                           absent=total - present,
                           percentage=percentage,
                           periods=range(1, 8),
                           filter_date=filter_date,
                           filter_period=filter_period,
                           filter_status=filter_status)
