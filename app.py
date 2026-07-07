from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import string
import random
import os
from functools import wraps
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_fallback_secret_key')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

# --- Database Setup ---
def get_db_connection():
    conn = sqlite3.connect('job_portal.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL, job_type TEXT NOT NULL,
        qualifications TEXT, paycheck TEXT, location TEXT, working_hours TEXT, job_nature TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, application_code TEXT UNIQUE, job_id INTEGER,
        company_applied TEXT, applicant_name TEXT NOT NULL, contact_details TEXT NOT NULL,
        resume_text TEXT, sop_text TEXT, status TEXT DEFAULT 'Pending',
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

def generate_unique_code():
    return 'APP-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# --- SECURITY DECORATOR ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If 'admin_logged_in' is not in the session, kick them out
        if 'admin_logged_in' not in session:
            flash('Please log in to access the admin portal.', 'danger')
            # Saves the page they tried to visit so we can redirect them back after login
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# WEBSITE 1: PUBLIC JOB PORTAL (Unchanged)
# ==========================================

@app.route('/')
def public_index():
    conn = get_db_connection()
    keyword = request.args.get('keyword', '').strip()
    company = request.args.get('company', '').strip()
    job_type = request.args.get('job_type', '').strip()
    job_nature = request.args.get('job_nature', '').strip()
    
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    
    if keyword:
        query += " AND (company LIKE ? OR qualifications LIKE ? OR job_type LIKE ? OR location LIKE ?)"
        like_kw = f"%{keyword}%"
        params.extend([like_kw, like_kw, like_kw, like_kw])
    if company:
        query += " AND company LIKE ?"
        params.append(f"%{company}%")
    if job_type:
        query += " AND job_type LIKE ?"
        params.append(f"%{job_type}%")
    if job_nature:
        query += " AND job_nature = ?"
        params.append(job_nature)
        
    query += " ORDER BY id DESC"
    jobs = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('public/index.html', jobs=jobs, keyword=keyword, company=company, job_type=job_type, job_nature=job_nature)

@app.route('/apply/<int:job_id>', methods=('GET', 'POST'))
def apply_job(job_id):
    conn = get_db_connection()
    job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    
    if not job:
        conn.close()
        return redirect('/')
        
    if request.method == 'POST':
        name = request.form['name']
        contact = request.form['contact']
        
        try:
            resume_text = request.files['resume'].read().decode('utf-8')
            sop_text = request.files['sop'].read().decode('utf-8')
        except:
            flash("Error reading files. Please ensure they are plain .txt files.")
            conn.close()
            return render_template('public/apply.html', job=job)

        existing = conn.execute('SELECT id FROM applications WHERE job_id = ? AND contact_details = ?', (job_id, contact)).fetchone()
        if existing:
            flash("You have already applied for this job with these contact details.")
            conn.close()
            return render_template('public/apply.html', job=job)

        app_code = generate_unique_code()
        conn.execute('''INSERT INTO applications (application_code, job_id, company_applied, applicant_name, contact_details, resume_text, sop_text)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''', (app_code, job_id, job['company'], name, contact, resume_text, sop_text))
        conn.commit()
        conn.close()
        return render_template('public/success.html', code=app_code, name=name, company=job['company'])

    conn.close()
    return render_template('public/apply.html', job=job)

@app.route('/my-applications', methods=('GET', 'POST'))
def my_applications():
    applications = []
    contact = ""
    accepted_count = rejected_count = pending_count = 0

    if request.method == 'POST':
        contact = request.form.get('contact', '').strip()
        if contact:
            conn = get_db_connection()
            applications = conn.execute('SELECT * FROM applications WHERE contact_details = ? ORDER BY applied_at DESC', (contact,)).fetchall()
            conn.close()
            for app in applications:
                if app['status'] == 'Accepted': accepted_count += 1
                elif app['status'] == 'Rejected': rejected_count += 1
                else: pending_count += 1

    return render_template('public/my_applications.html', applications=applications, contact=contact, accepted_count=accepted_count, rejected_count=rejected_count, pending_count=pending_count)

# ==========================================
# WEBSITE 2: ADMIN HR PORTAL (SECURED)
# ==========================================

@app.route('/admin/login', methods=('GET', 'POST'))
def admin_login():
    # If already logged in, go to dashboard
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Logged in successfully!', 'success')
            # Redirect to the page they tried to visit, or default to dashboard
            next_page = request.args.get('next') or url_for('admin_dashboard')
            return redirect(next_page)
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('admin_login'))

# --- Add @admin_required below all admin routes ---

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    jobs = conn.execute('SELECT * FROM jobs ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin/dashboard.html', jobs=jobs)

@app.route('/admin/jobs/add', methods=('GET', 'POST'))
@admin_required
def admin_add_job():
    if request.method == 'POST':
        company = request.form['company']
        job_type = request.form['job_type']
        qualifications = request.form['qualifications']
        paycheck = request.form['paycheck']
        location = request.form['location']
        working_hours = request.form['working_hours']
        job_nature = request.form['job_nature']

        conn = get_db_connection()
        conn.execute('''INSERT INTO jobs (company, job_type, qualifications, paycheck, location, working_hours, job_nature)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''', (company, job_type, qualifications, paycheck, location, working_hours, job_nature))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/add_job.html')

@app.route('/admin/jobs/delete/<int:job_id>')
@admin_required
def admin_delete_job(job_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/applications')
@admin_required
def admin_applications():
    conn = get_db_connection()
    status_filter = request.args.get('status', 'Pending')
    if status_filter == 'All':
        applications = conn.execute('SELECT * FROM applications ORDER BY applied_at DESC').fetchall()
    else:
        applications = conn.execute('SELECT * FROM applications WHERE status = ? ORDER BY applied_at DESC', (status_filter,)).fetchall()
    conn.close()
    return render_template('admin/applications.html', applications=applications, current_status=status_filter)

@app.route('/admin/applications/update/<int:app_id>/<action>')
@admin_required
def admin_update_application(app_id, action):
    if action not in ['Accept', 'Reject']:
        return redirect(url_for('admin_applications'))
        
    conn = get_db_connection()
    conn.execute('UPDATE applications SET status = ? WHERE id = ?', (action + 'ed', app_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_applications'))

if __name__ == '__main__':
    app.run(debug=True)