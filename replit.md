# Student Attendance Management System

## Overview
A complete Student Attendance Management System built with Python 3 and Flask. Features role-based access control for Admin, Faculty, and Student roles with SQLite database.

## Architecture
- **Framework**: Flask with Blueprint-based routing
- **Database**: SQLite (database.db)
- **Authentication**: Session-based login with Werkzeug password hashing
- **Frontend**: Jinja2 templates with custom CSS (no JS framework)

## Project Structure
```
app.py                   # Main app, DB initialization, Middleware
routes/
  admin.py               # Admin portal: Faculty, Student, Section, Timetable mgmt
  faculty.py             # Faculty portal: Multi-period attendance marking
  student.py             # Student portal: Attendance percentage & history
templates/
  base.html              # Modern, responsive layout with mobile sidebar toggle
  admin/                 # Administrative management views
  faculty/               # Attendance marking and period-wise records
  student/               # Personal attendance reports
static/
  css/style.css          # Clean, modern UI with responsive breakpoints
  img/logo.png           # Institution branding
database.db              # SQLite database (auto-initialized with default admin)
instructions.txt         # Quick start & password recovery guide
```

## Login URLs
- Admin: `/admin/login` — username: `admin`, password: `admin123`
- Faculty: `/faculty/login`
- Student: `/student/login`

## Database Schema
- **users**: All user accounts (admin/faculty/student roles)
- **departments**: Academic departments & Branches (unified)
- **years**: Academic years (1-4)
- **sections**: Branch+Year+SectionName combinations
- **faculty_profiles**: Faculty details linked to users and departments
- **student_profiles**: Student details linked to users, branch, year, section
- **timetable**: Faculty-Section-Period assignments
- **attendance**: Daily period-wise attendance records (unique constraint prevents duplicates)

## Key Features
- **Smart Timetable**: Conflict-detected period assignments with Day-of-Week support.
- **Bulk Attendance**: Faculty can mark multiple periods (e.g., P1 & P2) in one go.
- **Dynamic Filtering**: Cascading dropdowns (Branch -> Year -> Section) for data entry.
- **Mobile First**: Responsive sidebar and touch-friendly controls.
- **Role Security**: Session-based isolation with encrypted password hashing.
- **Real-World Ready**: Automatic data initialization (Years, standard Branches) on first run.

## Dependencies
- flask
- werkzeug

## Running
```bash
python3 app.py
```
App runs on port 5000.
