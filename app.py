from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
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
    return render_template('home.html', jobs=jobs, title="TalentHub")

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
@app.route('/job_detail/<int:job_id>')
def job_detail(job_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    job = c.fetchone()
    conn.close()
    return render_template('job_detail.html', job=job)

# Apply job
@app.route('/apply/<int:job_id>', methods=['POST'])
def apply(job_id):
    if 'username' not in session or session.get('role') != 'candidate':
        return redirect(url_for('login'))

    if 'resume' not in request.files:
        return "No file part"
    file = request.files['resume']
    if file.filename == '':
        return "No selected file"
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO applications (job_id, candidate_name, resume) VALUES (?,?,?)",
                  (job_id, session['username'], filename))
        conn.commit()
        conn.close()

        return redirect(url_for('candidate_dashboard'))

    return "Invalid file type"

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

    title = request.form['title']
    location = request.form['location']
    description = request.form['description']
    company = session['username']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO jobs (title, company, location, description) VALUES (?,?,?,?)",
              (title, company, location, description))
    conn.commit()
    conn.close()

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
