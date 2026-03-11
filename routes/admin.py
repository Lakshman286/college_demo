import sqlite3
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash, current_app)
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

admin_bp = Blueprint('admin', __name__)


def get_db():
    conn = sqlite3.connect(current_app.config['DB_PATH'])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def admin_required(f):

    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Access denied. Admin login required.', 'danger')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)

    return decorated


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('role') == 'admin':
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? AND role = 'admin'",
            (username, )).fetchone()
        db.close()
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = 'admin'
            return redirect(url_for('admin.dashboard'))
        flash('Invalid admin credentials.', 'danger')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin.login'))


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    db = get_db()
    faculty_count = db.execute(
        "SELECT COUNT(*) FROM faculty_profiles").fetchone()[0]
    student_count = db.execute(
        "SELECT COUNT(*) FROM student_profiles").fetchone()[0]
    dept_count = db.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
    section_count = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    attendance_count = db.execute(
        "SELECT COUNT(*) FROM attendance").fetchone()[0]
    db.close()
    return render_template('admin/dashboard.html',
                           faculty_count=faculty_count,
                           student_count=student_count,
                           dept_count=dept_count,
                           section_count=section_count,
                           attendance_count=attendance_count)


@admin_bp.route('/departments', methods=['GET', 'POST'])
@admin_required
def departments():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            if name:
                try:
                    db.execute("INSERT INTO departments (name) VALUES (?)",(name, ))
                    db.commit()
                    flash(f'Department/Branch "{name}" added.', 'success')
                except sqlite3.IntegrityError:
                    flash('Entry already exists.', 'danger')
        elif action == 'delete':
            dept_id = request.form.get('dept_id')

            count = db.execute(
                "SELECT COUNT(*) FROM faculty_profiles WHERE department_id=?",
                (dept_id,)
            ).fetchone()[0]

            if count > 0:
                flash("Cannot delete department with faculty assigned", "danger")
            else:
                db.execute("DELETE FROM departments WHERE id=?", (dept_id,))
                db.commit()
                flash("Department deleted", "success")
                


        db.close()
        return redirect(url_for('admin.departments'))
    depts = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    db.close()
    return render_template('admin/departments.html', departments=depts)


@admin_bp.route('/sections', methods=['GET', 'POST'])
@admin_required
def sections():
    db = get_db()
    filter_branch = request.args.get('branch_id', '')
    filter_year = request.args.get('year_id', '')

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            branch_id = request.form.get('branch_id')
            year_id = request.form.get('year_id')
            name = request.form.get('name', '').strip().upper()
            if branch_id and year_id and name:
                try:
                    db.execute(
                        "INSERT INTO sections (branch_id, year_id, name) VALUES (?,?,?)",
                        (branch_id, year_id, name))
                    db.commit()
                    flash(f'Section {name} added.', 'success')
                except sqlite3.IntegrityError:
                    flash('Section already exists for this branch/year.',
                          'danger')
        elif action == 'delete':
            section_id = request.form.get('section_id')
            count = db.execute(
                "SELECT COUNT(*) FROM student_profiles WHERE section_id=?",
                (section_id,)
            ).fetchone()[0]

            if count > 0:
                flash("Cannot delete section with students assigned", "danger")
            else:
                db.execute("DELETE FROM sections WHERE id=?", (section_id,))
                db.commit()
                flash("Section deleted.", "success")

        db.close()
        return redirect(
            url_for('admin.sections',
                    branch_id=filter_branch,
                    year_id=filter_year))

    query = '''SELECT s.id, s.name, d.name as branch_name, y.year_number,
                      s.branch_id, y.id as year_id
               FROM sections s
               JOIN departments d ON s.branch_id = d.id
               JOIN years y ON s.year_id = y.id
               WHERE 1=1'''
    params = []
    if filter_branch:
        query += ' AND s.branch_id = ?'
        params.append(filter_branch)
    if filter_year:
        query += ' AND s.year_id = ?'
        params.append(filter_year)
    query += ' ORDER BY d.name, y.year_number, s.name'

    section_list = db.execute(query, params).fetchall()
    branch_list = db.execute(
        "SELECT * FROM departments ORDER BY name").fetchall()
    year_list = db.execute(
        "SELECT * FROM years ORDER BY year_number").fetchall()
    db.close()
    return render_template('admin/sections.html',
                           sections=section_list,
                           branches=branch_list,
                           years=year_list,
                           filter_branch=filter_branch,
                           filter_year=filter_year)


@admin_bp.route('/create-faculty', methods=['GET', 'POST'])
@admin_required
def create_faculty():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        department_id = request.form.get('department_id') or None
        if not all([name, employee_id, username, password]):
            flash('All fields except department are required.', 'danger')
        else:
            try:
                pwd_hash = generate_password_hash(password)
                cursor = db.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                    (username, pwd_hash, 'faculty')
                )
                user_id = cursor.lastrowid
                db.execute(
                    "INSERT INTO faculty_profiles (user_id, department_id, name, employee_id) VALUES (?,?,?,?)",
                    (user_id, department_id, name, employee_id))
                db.commit()
                flash(f'Faculty "{name}" created successfully.', 'success')
                db.close()
                return redirect(url_for('admin.manage_faculty'))
            except sqlite3.IntegrityError as e:
                db.rollback()
                if 'username' in str(e):
                    flash('Username already exists.', 'danger')
                elif 'employee_id' in str(e):
                    flash('Employee ID already exists.', 'danger')
                else:
                    flash('Error creating faculty.', 'danger')
    departments = db.execute(
        "SELECT * FROM departments ORDER BY name").fetchall()
    db.close()
    return render_template('admin/create_faculty.html',
                           departments=departments)


@admin_bp.route('/manage-faculty')
@admin_required
def manage_faculty():
    db = get_db()
    filter_dept = request.args.get('department_id', '')
    query = '''SELECT fp.id, fp.name, fp.employee_id, u.username,
                      d.name as dept_name, d.id as dept_id
               FROM faculty_profiles fp
               JOIN users u ON fp.user_id = u.id
               LEFT JOIN departments d ON fp.department_id = d.id
               WHERE 1=1'''
    params = []
    if filter_dept:
        query += ' AND fp.department_id = ?'
        params.append(filter_dept)
    query += ' ORDER BY fp.name'
    faculty_list = db.execute(query, params).fetchall()
    departments = db.execute(
        "SELECT * FROM departments ORDER BY name").fetchall()
    db.close()
    return render_template('admin/manage_faculty.html',
                           faculty_list=faculty_list,
                           departments=departments,
                           filter_dept=filter_dept)


@admin_bp.route('/edit-faculty/<int:faculty_id>', methods=['GET', 'POST'])
@admin_required
def edit_faculty(faculty_id):
    db = get_db()
    faculty = db.execute(
        '''SELECT fp.*, u.username FROM faculty_profiles fp
           JOIN users u ON fp.user_id = u.id WHERE fp.id = ?''',
        (faculty_id, )).fetchone()
    if not faculty:
        flash('Faculty not found.', 'danger')
        db.close()
        return redirect(url_for('admin.manage_faculty'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        department_id = request.form.get('department_id') or None
        new_password = request.form.get('password', '').strip()
        try:
            db.execute(
                "UPDATE faculty_profiles SET name=?, employee_id=?, department_id=? WHERE id=?",
                (name, employee_id, department_id, faculty_id))
            if new_password:
                pwd_hash = generate_password_hash(new_password)
                db.execute("UPDATE users SET password_hash=? WHERE id=?",
                           (pwd_hash, faculty['user_id']))
            db.commit()
            flash('Faculty updated successfully.', 'success')
            db.close()
            return redirect(url_for('admin.manage_faculty'))
        except sqlite3.IntegrityError:
            db.rollback()
            flash('Employee ID already exists.', 'danger')

    departments = db.execute(
        "SELECT * FROM departments ORDER BY name").fetchall()
    db.close()
    return render_template('admin/edit_faculty.html',
                           faculty=faculty,
                           departments=departments)


@admin_bp.route('/delete-faculty/<int:faculty_id>', methods=['POST'])
@admin_required
def delete_faculty(faculty_id):
    db = get_db()
    fp = db.execute("SELECT user_id FROM faculty_profiles WHERE id=?",
                    (faculty_id, )).fetchone()
    if fp:
        db.execute("DELETE FROM faculty_profiles WHERE id=?", (faculty_id,))
        db.execute("DELETE FROM users WHERE id=?", (fp['user_id'],))
        db.commit()
        flash('Faculty deleted.', 'success')
    db.close()
    return redirect(url_for('admin.manage_faculty'))


@admin_bp.route('/create-student', methods=['GET', 'POST'])
@admin_required
def create_student():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        branch_id = request.form.get('branch_id') or None
        year_id = request.form.get('year_id') or None
        section_id = request.form.get('section_id') or None
        if not all([name, roll_number, username, password]):
            flash('Name, roll number, username, and password are required.',
                  'danger')
        else:
            try:
                pwd_hash = generate_password_hash(password)
                cursor = db.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                    (username, pwd_hash, 'student')
                )
                user_id = cursor.lastrowid
                db.execute(
                    '''INSERT INTO student_profiles
                              (user_id, section_id, branch_id, year_id, name, roll_number)
                              VALUES (?,?,?,?,?,?)''',
                    (user_id, section_id, branch_id, year_id, name,
                     roll_number))
                db.commit()
                flash(f'Student "{name}" created successfully.', 'success')
                db.close()
                return redirect(url_for('admin.manage_students'))
            except sqlite3.IntegrityError as e:
                db.rollback()
                if 'username' in str(e):
                    flash('Username already exists.', 'danger')
                elif 'roll_number' in str(e):
                    flash('Roll number already exists.', 'danger')
                else:
                    flash('Error creating student.', 'danger')

    branches = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    years = db.execute("SELECT * FROM years ORDER BY year_number").fetchall()
    sections = db.execute(
        '''SELECT s.id, s.name, d.name as branch_name, y.year_number, s.branch_id, s.year_id
           FROM sections s JOIN departments d ON s.branch_id=d.id
           JOIN years y ON s.year_id=y.id ORDER BY d.name, y.year_number, s.name'''
    ).fetchall()
    db.close()
    return render_template('admin/create_student.html',
                           branches=branches,
                           years=years,
                           sections=sections)


@admin_bp.route('/manage-students')
@admin_required
def manage_students():
    db = get_db()
    filter_branch = request.args.get('branch_id', '')
    filter_year = request.args.get('year_id', '')
    filter_section = request.args.get('section_id', '')
    query = '''SELECT sp.id, sp.name, sp.roll_number, u.username,
                      d.name as branch_name, y.year_number, sec.name as section_name,
                      sp.branch_id, y.id as year_id, sec.id as section_id
               FROM student_profiles sp
               JOIN users u ON sp.user_id = u.id
               LEFT JOIN departments d ON sp.branch_id = d.id
               LEFT JOIN years y ON sp.year_id = y.id
               LEFT JOIN sections sec ON sp.section_id = sec.id
               WHERE 1=1'''
    params = []
    if filter_branch:
        query += ' AND sp.branch_id = ?'
        params.append(filter_branch)
    if filter_year:
        query += ' AND sp.year_id = ?'
        params.append(filter_year)
    if filter_section:
        query += ' AND sp.section_id = ?'
        params.append(filter_section)
    query += ' ORDER BY sp.name'
    students = db.execute(query, params).fetchall()
    branches = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    years = db.execute("SELECT * FROM years ORDER BY year_number").fetchall()
    sections = db.execute(
        '''SELECT s.id, s.name, d.name as branch_name, y.year_number
           FROM sections s JOIN departments d ON s.branch_id=d.id
           JOIN years y ON s.year_id=y.id ORDER BY d.name, y.year_number, s.name'''
    ).fetchall()
    db.close()
    return render_template('admin/manage_students.html',
                           students=students,
                           branches=branches,
                           years=years,
                           sections=sections,
                           filter_branch=filter_branch,
                           filter_year=filter_year,
                           filter_section=filter_section)


@admin_bp.route('/edit-student/<int:student_id>', methods=['GET', 'POST'])
@admin_required
def edit_student(student_id):
    db = get_db()
    student = db.execute(
        '''SELECT sp.*, u.username FROM student_profiles sp
           JOIN users u ON sp.user_id = u.id WHERE sp.id = ?''',
        (student_id, )).fetchone()
    if not student:
        flash('Student not found.', 'danger')
        db.close()
        return redirect(url_for('admin.manage_students'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        branch_id = request.form.get('branch_id') or None
        year_id = request.form.get('year_id') or None
        section_id = request.form.get('section_id') or None
        new_password = request.form.get('password', '').strip()
        try:
            db.execute(
                '''UPDATE student_profiles
                          SET name=?, roll_number=?, branch_id=?, year_id=?, section_id=?
                          WHERE id=?''', (name, roll_number, branch_id,
                                          year_id, section_id, student_id))
            if new_password:
                pwd_hash = generate_password_hash(new_password)
                db.execute("UPDATE users SET password_hash=? WHERE id=?",
                           (pwd_hash, student['user_id']))
            db.commit()
            flash('Student updated.', 'success')
            db.close()
            return redirect(url_for('admin.manage_students'))
        except sqlite3.IntegrityError:
            db.rollback()
            flash('Roll number already exists.', 'danger')

    branches = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    years = db.execute("SELECT * FROM years ORDER BY year_number").fetchall()
    sections = db.execute(
        '''SELECT s.id, s.name, d.name as branch_name, y.year_number
           FROM sections s JOIN departments d ON s.branch_id=d.id
           JOIN years y ON s.year_id=y.id ORDER BY d.name, y.year_number, s.name'''
    ).fetchall()
    db.close()
    return render_template('admin/edit_student.html',
                           student=student,
                           branches=branches,
                           years=years,
                           sections=sections)


@admin_bp.route('/delete-student/<int:student_id>', methods=['POST'])
@admin_required
def delete_student(student_id):
    db = get_db()
    sp = db.execute("SELECT user_id FROM student_profiles WHERE id=?",
                    (student_id, )).fetchone()
    if sp:
        db.execute("DELETE FROM student_profiles WHERE id=?", (student_id,))
        db.execute("DELETE FROM users WHERE id=?", (sp['user_id'], ))
        db.commit()
        flash('Student deleted.', 'success')
    db.close()
    return redirect(url_for('admin.manage_students'))


@admin_bp.route('/timetable', methods=['GET', 'POST'])
@admin_required
def timetable():
    db = get_db()
    recent_entry = None

    # -------------------------
    # HANDLE ADD / DELETE
    # -------------------------
    if request.method == 'POST':
        action = request.form.get('action')

        # -------- ADD --------
        if action == 'add':
            faculty_id = request.form.get('faculty_id')
            section_id = request.form.get('section_id')
            if not faculty_id or not section_id:
                flash("Select both faculty and section", "danger")
                return redirect(url_for('admin.timetable'))


            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

            inserted = 0

            for day in days:
                for period in range(1,8):

                    key = f"tt_{day}_{period}"

                    if key in request.form:

                        try:
                            db.execute(
                                """
                                INSERT INTO timetable (faculty_id, section_id, period_number, day_of_week)
                                VALUES (?,?,?,?)
                                """,
                                (faculty_id, section_id, period, day)
                            )
                            inserted += 1

                        except sqlite3.IntegrityError:
                            flash("Duplicate timetable entry skipped", "warning")

            db.commit()

            flash(f"{inserted} timetable periods assigned successfully.", "success")


        # -------- DELETE --------
        elif action == 'delete':
            tt_id = request.form.get('tt_id')
            db.execute("DELETE FROM timetable WHERE id=?", (tt_id, ))
            db.commit()
            flash('Timetable entry removed.', 'success')

    # -------------------------
    # FILTER VALUES
    # -------------------------
    filter_department = request.args.get('department_id', '')
    filter_faculty = request.args.get('faculty_id', '')

    # -------------------------
    # DEPARTMENTS
    # -------------------------
    departments = db.execute(
        "SELECT * FROM departments ORDER BY name").fetchall()

    # -------------------------
    # FACULTY LIST (Filtered)
    # -------------------------
    faculty_query = """
        SELECT * FROM faculty_profiles
        WHERE 1=1
    """
    faculty_params = []

    if filter_department:
        faculty_query += " AND department_id = ?"
        faculty_params.append(filter_department)

    faculty_query += " ORDER BY name"

    faculty_list = db.execute(faculty_query, faculty_params).fetchall()

    # -------------------------
    # SECTIONS
    # -------------------------
    sections = db.execute(
        '''SELECT s.id, s.name, d.name as branch_name, y.year_number
           FROM sections s
           JOIN departments d ON s.branch_id=d.id
           JOIN years y ON s.year_id=y.id
           ORDER BY d.name, y.year_number, s.name''').fetchall()

    db.close()

    return render_template('admin/timetable.html',
                           faculty_list=faculty_list,
                           sections=sections,
                           departments=departments,
                           periods=range(1, 8),
                           days=[
                               "Monday", "Tuesday", "Wednesday", "Thursday",
                               "Friday", "Saturday"
                           ],
                           filter_faculty=filter_faculty,
                           filter_department=filter_department,
                           recent_entry=recent_entry)


@admin_bp.route('/timetable-view')
@admin_required
def timetable_view():
    db = get_db()

    tt_query = '''
        SELECT t.id,
               t.section_id,
               fp.name as faculty_name,
               d.name as branch_name,
               y.year_number,
               sec.name as section_name,
               t.period_number,
               t.day_of_week
        FROM timetable t
        JOIN faculty_profiles fp ON t.faculty_id = fp.id
        JOIN sections sec ON t.section_id = sec.id
        JOIN departments d ON sec.branch_id = d.id
        JOIN years y ON sec.year_id = y.id
        ORDER BY d.name, y.year_number, sec.name, t.day_of_week, t.period_number
    '''

    entries = db.execute(tt_query).fetchall()

    # -------- GROUP SECTION WISE --------
    section_tables = {}

    for e in entries:
        key = f"{e['branch_name']} - Year {e['year_number']} - {e['section_name']}"

        if key not in section_tables:
            section_tables[key] = {
                "branch": e['branch_name'],
                "year": e['year_number'],
                "section": e['section_name'],
                "section_id": None,
                "data": {}
            }

        # Fetch section_id only once
        if section_tables[key]["section_id"] is None:
            section_tables[key]["section_id"] = e["section_id"]

        section_tables[key]["data"][(e['day_of_week'],
                                     e['period_number'])] = e['faculty_name']

    db.close()

    return render_template('admin/timetable_view.html',
                           section_tables=section_tables,
                           periods=range(1, 8),
                           days=[
                               "Monday", "Tuesday", "Wednesday", "Thursday",
                               "Friday", "Saturday"
                           ])


@admin_bp.route('/delete-section-timetable', methods=['POST'])
@admin_required
def delete_section_timetable():
    section_id = request.form.get('section_id')

    if not section_id:
        flash("Invalid section selected", "danger")
        return redirect(url_for('admin.timetable_view'))

    db = get_db()
    db.execute("DELETE FROM timetable WHERE section_id = ?", (section_id,))
    db.commit()
    db.close()

    flash("Section timetable deleted successfully!", "success")
    return redirect(url_for('admin.timetable_view'))


@admin_bp.route('/attendance')
@admin_required
def view_attendance():
    db = get_db()
    filter_branch = request.args.get('branch_id', '')
    filter_year = request.args.get('year_id', '')
    filter_section = request.args.get('section_id', '')
    filter_date = request.args.get('date', '')

    query = '''SELECT a.id, sp.name as student_name, sp.roll_number,
                      d.name as branch_name, y.year_number, sec.name as section_name,
                      a.date, a.period_number, a.status, fp.name as faculty_name
               FROM attendance a
               JOIN student_profiles sp ON a.student_id = sp.id
               JOIN sections sec ON a.section_id = sec.id
               JOIN departments d ON sec.branch_id = d.id
               JOIN years y ON sec.year_id = y.id
               JOIN faculty_profiles fp ON a.faculty_id = fp.id
               WHERE 1=1'''
    params = []
    if filter_branch:
        query += ' AND sec.branch_id = ?'
        params.append(filter_branch)
    if filter_year:
        query += ' AND sec.year_id = ?'
        params.append(filter_year)
    if filter_section:
        query += ' AND a.section_id = ?'
        params.append(filter_section)
    if filter_date:
        query += ' AND a.date = ?'
        params.append(filter_date)
    query += ' ORDER BY a.date DESC, a.period_number, sp.name'

    records = db.execute(query, params).fetchall()
    branches = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    years = db.execute("SELECT * FROM years ORDER BY year_number").fetchall()
    sections = db.execute(
        '''SELECT s.id, s.name, d.name as branch_name, y.year_number
           FROM sections s JOIN departments d ON s.branch_id=d.id
           JOIN years y ON s.year_id=y.id ORDER BY d.name, y.year_number, s.name'''
    ).fetchall()
    db.close()
    return render_template('admin/view_attendance.html',
                           records=records,
                           branches=branches,
                           years=years,
                           sections=sections,
                           filter_branch=filter_branch,
                           filter_year=filter_year,
                           filter_section=filter_section,
                           filter_date=filter_date)


@admin_bp.route('/delete-attendance', methods=['POST'])
@admin_required
def delete_attendance():
    db = get_db()

    branch_id = request.form.get('branch_id')
    year_id = request.form.get('year_id')
    section_id = request.form.get('section_id')
    date = request.form.get('date')

    query = "DELETE FROM attendance WHERE 1=1"
    if not any([branch_id, year_id, section_id, date]):
        db.close()
        flash("Select at least one filter before deleting", "danger")
        return redirect(url_for('admin.view_attendance'))
    params = []

    if branch_id:
        query += " AND section_id IN (SELECT id FROM sections WHERE branch_id=?)"
        params.append(branch_id)

    if year_id:
        query += " AND section_id IN (SELECT id FROM sections WHERE year_id = ?)"
        params.append(year_id)

    if section_id:
        query += " AND section_id = ?"
        params.append(section_id)

    if date:
        query += " AND date = ?"
        params.append(date)

    db.execute(query, params)
    db.commit()
    db.close()

    flash("Filtered attendance records deleted successfully.", "success")
    return redirect(
        url_for('admin.view_attendance',
                branch_id=branch_id,
                year_id=year_id,
                section_id=section_id,
                date=date))
