import sqlite3
from datetime import date, datetime
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash, current_app)
from werkzeug.security import check_password_hash
from functools import wraps

faculty_bp = Blueprint('faculty', __name__)

# -------------------- DATABASE CONNECTION --------------------


def get_db():
    conn = sqlite3.connect(current_app.config['DB_PATH'])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# -------------------- AUTH DECORATOR --------------------


def faculty_required(f):

    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'faculty':
            flash('Access denied. Faculty login required.', 'danger')
            return redirect(url_for('faculty.login'))
        return f(*args, **kwargs)

    return decorated


# -------------------- LOGIN --------------------


@faculty_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('role') == 'faculty':
        return redirect(url_for('faculty.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND role='faculty'",
            (username, )).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            fp = db.execute("SELECT * FROM faculty_profiles WHERE user_id=?",
                            (user['id'], )).fetchone()

            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = 'faculty'
            session['faculty_id'] = fp['id'] if fp else None
            session['faculty_name'] = fp['name'] if fp else user['username']

            db.close()
            return redirect(url_for('faculty.dashboard'))

        db.close()
        flash('Invalid faculty credentials.', 'danger')

    return render_template('faculty/login.html')


# -------------------- LOGOUT --------------------


@faculty_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('faculty.login'))


# -------------------- DASHBOARD --------------------


@faculty_bp.route('/dashboard')
@faculty_required
def dashboard():
    db = get_db()
    faculty_id = session.get('faculty_id')

    fp = db.execute(
        '''SELECT fp.*, d.name as dept_name
           FROM faculty_profiles fp
           LEFT JOIN departments d ON fp.department_id = d.id
           WHERE fp.id = ?''', (faculty_id, )).fetchone()

    assignments = db.execute(
        '''SELECT DISTINCT sec.id, d.name as branch_name,
                  y.year_number, sec.name as section_name
           FROM timetable t
           JOIN sections sec ON t.section_id = sec.id
           JOIN departments d ON sec.branch_id = d.id
           JOIN years y ON sec.year_id = y.id
           WHERE t.faculty_id = ?
           ORDER BY d.name, y.year_number, sec.name''',
        (faculty_id, )).fetchall()

    today_count = db.execute(
        "SELECT COUNT(*) FROM attendance WHERE faculty_id=? AND date=?",
        (faculty_id, date.today().isoformat())).fetchone()[0]

    total_count = db.execute(
        "SELECT COUNT(*) FROM attendance WHERE faculty_id=?",
        (faculty_id, )).fetchone()[0]

    db.close()

    return render_template('faculty/dashboard.html',
                           faculty=fp,
                           assignments=assignments,
                           today_count=today_count,
                           total_count=total_count,
                           today=date.today().isoformat())


# -------------------- MARK ATTENDANCE --------------------


@faculty_bp.route('/mark-attendance', methods=['GET', 'POST'])
@faculty_required
def mark_attendance():

    db = get_db()
    faculty_id = session.get('faculty_id')

    # Get sections assigned to faculty
    assigned_sections = db.execute(
        '''SELECT DISTINCT sec.id, d.name as branch_name,
                  y.year_number, sec.name as section_name
           FROM timetable t
           JOIN sections sec ON t.section_id = sec.id
           JOIN departments d ON sec.branch_id = d.id
           JOIN years y ON sec.year_id = y.id
           WHERE t.faculty_id = ?
           ORDER BY d.name, y.year_number, sec.name''',
        (faculty_id, )).fetchall()

    selected_section_id = request.args.get('section_id') or request.form.get(
        'section_id')
    selected_date = request.args.get('date') or request.form.get(
        'date') or date.today().isoformat()

    assigned_periods = []
    students = []
    selected_periods = []
    day_name = None

    if selected_section_id and selected_date:
        day_name = datetime.strptime(selected_date, "%Y-%m-%d").strftime("%A").capitalize()

        assigned_periods = db.execute(
            '''SELECT period_number
               FROM timetable
               WHERE faculty_id=?
               AND section_id=?
               AND day_of_week=?
               ORDER BY period_number''',
            (faculty_id, selected_section_id, day_name)).fetchall()
        
        # We always treat all assigned periods for that day as selected
        selected_periods = [str(p['period_number']) for p in assigned_periods]

        if assigned_periods:
            students = db.execute(
                '''SELECT id, name, roll_number
                   FROM student_profiles
                   WHERE section_id=?
                   ORDER BY roll_number''',
                (selected_section_id, )).fetchall()

    # -------------------- SUBMIT ATTENDANCE --------------------

    if request.method == 'POST' and request.form.get('submit_attendance'):

        if not selected_section_id or not selected_periods:
            flash('Please select section and valid periods.', 'danger')
        else:
            success_count = 0
            for period in selected_periods:
                for student in students:
                    # Checkbox logic: if checked, value is 'present', otherwise absent
                    status = request.form.get(f'status_{student["id"]}_{period}', 'absent')
                    try:
                        existing = db.execute(
                            '''SELECT id FROM attendance
                            WHERE student_id=? AND date=? AND period_number=? AND section_id=?''',
                            (student['id'], selected_date, int(period), int(selected_section_id))
                        ).fetchone()

                        if existing:
                            db.execute(
                                '''UPDATE attendance
                                SET status=?
                                WHERE student_id=? AND date=? AND period_number=? AND section_id=?''',
                                (status, student['id'], selected_date, int(period), int(selected_section_id))
                            )
                        else:
                            db.execute(
                                '''INSERT INTO attendance
                                (student_id, date, period_number, status, faculty_id, section_id)
                                VALUES (?, ?, ?, ?, ?, ?)''',
                                (student['id'], selected_date, int(period),
                                status, faculty_id, int(selected_section_id))
                            )
                    except Exception as e:
                        print("Attendance error:", e)



            db.commit()
            flash(f'Attendance marked successfully.', 'success')
            db.close()
            return redirect(url_for('faculty.view_attendance'))

    db.close()

    return render_template('faculty/mark_attendance.html',
                           assigned_sections=assigned_sections,
                           assigned_periods=assigned_periods,
                           students=students,
                           selected_section_id=selected_section_id,
                           selected_periods=selected_periods,
                           selected_date=selected_date,
                           periods=range(1, 8),
                           today=date.today().isoformat())


# -------------------- VIEW ATTENDANCE --------------------


@faculty_bp.route('/attendance')
@faculty_required
def view_attendance():

    db = get_db()
    faculty_id = session.get('faculty_id')

    filter_date = request.args.get('date', '')
    filter_section = request.args.get('section_id', '')
    filter_period = request.args.get('period_number', '')

    query = '''SELECT a.id, sp.name as student_name,
                      sp.roll_number,
                      d.name as branch_name,
                      y.year_number,
                      sec.name as section_name,
                      a.date, a.period_number, a.status,
                      sec.id as section_id
               FROM attendance a
               JOIN student_profiles sp ON a.student_id = sp.id
               JOIN sections sec ON a.section_id = sec.id
               JOIN departments d ON sec.branch_id = d.id
               JOIN years y ON sec.year_id = y.id
               WHERE a.faculty_id = ?'''

    params = [faculty_id]

    if filter_date:
        query += ' AND a.date = ?'
        params.append(filter_date)

    if filter_section:
        query += ' AND a.section_id = ?'
        params.append(filter_section)

    if filter_period:
        query += ' AND a.period_number = ?'
        params.append(int(filter_period))

    query += ' ORDER BY a.date DESC, a.period_number, sp.name'

    records = db.execute(query, params).fetchall()

    assigned_sections = db.execute(
        '''SELECT DISTINCT sec.id, d.name as branch_name,
                  y.year_number, sec.name as section_name
           FROM timetable t
           JOIN sections sec ON t.section_id = sec.id
           JOIN departments d ON sec.branch_id = d.id
           JOIN years y ON sec.year_id = y.id
           WHERE t.faculty_id = ?
           ORDER BY d.name, y.year_number, sec.name''',
        (faculty_id, )).fetchall()

    db.close()

    return render_template('faculty/view_attendance.html',
                           records=records,
                           assigned_sections=assigned_sections,
                           periods=range(1, 8),
                           filter_date=filter_date,
                           filter_section=filter_section,
                           filter_period=filter_period)
