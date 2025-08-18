from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx','txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads folder if not exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Allowed file check
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Home page
@app.route('/')
def home():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM jobs LIMIT 5")
    jobs = c.fetchall()
    conn.close()

    website_info = {
        'phone': '+91-9876543210',
        'email': 'info@talenthub.com',
        'instagram': 'https://www.instagram.com/talenthub',
        'linkedin': 'https://www.linkedin.com/company/talenthub',
        'facebook': 'https://www.facebook.com/talenthub'
    }

    return render_template('home.html', jobs=jobs, website_info=website_info)


# All jobs
@app.route('/jobs')
def jobs():
    search = request.args.get('search', '')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if search:
        c.execute("SELECT * FROM jobs WHERE title LIKE ?", ('%' + search + '%',))
    else:
        c.execute("SELECT * FROM jobs")
    jobs_list = c.fetchall()
    conn.close()
    return render_template('jobs.html', jobs=jobs_list)

# Job detail
# Job detail page
@app.route('/job/<int:job_id>', methods=['GET', 'POST'])
def job_detail(job_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Fetch job details
    c.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    job = c.fetchone()
    conn.close()

    if request.method == 'POST':
        # Only candidates can apply
        if 'username' not in session or session.get('role') != 'candidate':
            flash("Please login as candidate to apply")
            return redirect(url_for('login'))

        user_id = request.form['user_id']
        mobile = request.form['mobile']

        if 'resume' not in request.files:
            flash("No file part")
            return redirect(url_for('job_detail', job_id=job_id))
        file = request.files['resume']
        if file.filename == '':
            flash("No selected file")
            return redirect(url_for('job_detail', job_id=job_id))
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Insert application into database
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("""
                INSERT INTO applications (job_id, candidate_name, user_id, mobile, resume)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, session['username'], user_id, mobile, filename))
            conn.commit()
            conn.close()

            flash("Application submitted successfully!")
            return redirect(url_for('candidate_dashboard'))

        else:
            flash("Invalid file type")
            return redirect(url_for('job_detail', job_id=job_id))

    return render_template('job_detail.html', job=job)


# Apply job
# Apply job route
@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
def apply(job_id):
    if 'username' not in session or session.get('role') != 'candidate':
        flash("Please login as candidate to apply for a job")
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    job = c.fetchone()
    conn.close()

    if not job:
        flash("Job not found")
        return redirect(url_for('jobs'))

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        mobile = request.form.get('mobile')
        file = request.files.get('resume')

        if not user_id or not mobile or not file:
            flash("All fields are required")
            return redirect(url_for('apply', job_id=job_id))

        if file.filename == '':
            flash("No selected file")
            return redirect(url_for('apply', job_id=job_id))

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Insert application into database
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("""
                INSERT INTO applications (job_id, candidate_name, user_id, mobile, resume)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, session['username'], user_id, mobile, filename))
            conn.commit()
            conn.close()

            flash("Application submitted successfully!")
            return redirect(url_for('candidate_dashboard'))
        else:
            flash("Invalid file type. Allowed: pdf, doc, docx")
            return redirect(url_for('apply', job_id=job_id))

    return render_template('apply_job.html', job=job)




# Candidate dashboard
@app.route('/candidate_dashboard')
def candidate_dashboard():
    if 'username' not in session or session.get('role') != 'candidate':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT a.id, j.title, j.company, a.resume FROM applications a JOIN jobs j ON a.job_id = j.id WHERE a.candidate_name=?", (session['username'],))
    applications = c.fetchall()
    conn.close()
    return render_template('candidate_dashboard.html', applications=applications)

# Employer dashboard
@app.route('/employer_dashboard')
def employer_dashboard():
    if 'username' not in session or session.get('role') != 'employer':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE company=?", (session['username'],))
    jobs_list = c.fetchall()
    conn.close()
    return render_template('employer_dashboard.html', jobs=jobs_list)

# Add job
@app.route('/add_job', methods=['POST'])
def add_job():
    if 'username' not in session or session.get('role') != 'employer':
        return redirect(url_for('login'))

    try:
        title = request.form['title']
        location = request.form['location']
        description = request.form['description']
        salary = request.form['salary']
        joining_date = request.form['joining_date']
        qualifications = request.form['qualifications']  
        experience = request.form['experience']          
        company = session['username']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO jobs 
            (title, company, location, description, salary, joining_date, qualifications, experience)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, company, location, description, salary, joining_date, qualifications, experience))
        conn.commit()
        conn.close()

        flash("Job added successfully!")
        return redirect(url_for('employer_dashboard'))

    except Exception as e:
        flash(f"Error adding job: {e}")
        return redirect(url_for('employer_dashboard'))


# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        role = request.form['role'].strip()

        print("Username:", username, "Password:", password, "Role:", role)

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=? AND role=?", (username, password, role))
        user = c.fetchone()
        conn.close()

        print("Fetched user:", user)

        if user:
            session['username'] = username
            session['role'] = role
            if role == 'candidate':
                return redirect(url_for('candidate_dashboard'))
            else:
                return redirect(url_for('employer_dashboard'))
        else:
            flash("Invalid credentials")
            return redirect(url_for('login'))

    return render_template('login.html')


#Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", (username, password, role))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))

    return render_template('register.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
