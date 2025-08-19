from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify
import sqlite3, os, json
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")

app = Flask(__name__)
# change this secret key before deploying
app.secret_key = "replace_this_with_a_random_secret_key"

# ---------- DB helpers ----------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def init_db():
    db = get_db()
    with app.open_resource("schema.sql", mode="r") as f:
        db.executescript(f.read())
    db.commit()

# Initialize DB if missing
if not os.path.exists(DB_PATH):
    with app.app_context():
        init_db()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# ---------- Auth helpers ----------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return query_db("SELECT id, username, email FROM users WHERE id = ?", (uid,), one=True)

# ---------- Routes ----------
@app.route("/")
def home():
    return render_template("home.html", user=current_user())

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not username or not email or not password:
            flash("Please fill all fields.", "danger")
            return redirect(url_for("register"))
        exists = query_db("SELECT id FROM users WHERE email = ? OR username = ?", (email, username), one=True)
        if exists:
            flash("User with that email or username already exists.", "danger")
            return redirect(url_for("register"))
        pw_hash = generate_password_hash(password)
        db = get_db()
        db.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, pw_hash))
        db.commit()
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", user=current_user())

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("home"))
        flash("Invalid credentials.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html", user=current_user())

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("home"))

# List/browse quizzes
@app.route("/quizzes")
def quizzes():
    items = query_db("""
        SELECT q.id, q.title, q.subject, u.username, q.created_at
        FROM quizzes q
        LEFT JOIN users u ON q.created_by = u.id
        ORDER BY q.created_at DESC
    """)
    # group by subject for display
    quizzes_by_subject = {}
    for q in items:
        subj = q["subject"] if q["subject"] else "General"
        quizzes_by_subject.setdefault(subj, []).append(q)
    return render_template("quizzes.html", quizzes_by_subject=quizzes_by_subject, user=current_user())

# Create quiz (protected)
@app.route("/create", methods=["GET","POST"])
def create_quiz():
    user = current_user()
    if not user:
        flash("You must be logged in to create a quiz.", "warning")
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form.get("title","").strip()
        subject = request.form.get("subject","General")
        data = request.form.get("data","")
        if not title or not data:
            flash("Title and questions are required.", "danger")
            return redirect(url_for("create_quiz"))
        try:
            questions = json.loads(data)
        except Exception:
            flash("Invalid question data.", "danger")
            return redirect(url_for("create_quiz"))
        db = get_db()
        cur = db.execute("INSERT INTO quizzes (title, subject, created_by, created_at) VALUES (?, ?, ?, ?)",
                         (title, subject, user["id"], datetime.utcnow()))
        quiz_id = cur.lastrowid
        for q in questions:
            text = q.get("question","").strip()
            opts = q.get("options",[])
            correct = int(q.get("correct",0))
            if not text or len(opts) < 2:
                continue
            cur_q = db.execute("INSERT INTO questions (quiz_id, question_text) VALUES (?, ?)", (quiz_id, text))
            qid = cur_q.lastrowid
            for idx, o in enumerate(opts):
                is_correct = 1 if idx == correct else 0
                db.execute("INSERT INTO options (question_id, option_text, is_correct) VALUES (?, ?, ?)", (qid, o, is_correct))
        db.commit()
        flash("Quiz created successfully.", "success")
        return redirect(url_for("quizzes"))
    return render_template("create.html", user=user)

# Take quiz
@app.route("/quiz/<int:quiz_id>")
def take_quiz(quiz_id):
    q = query_db("SELECT id, title FROM quizzes WHERE id = ?", (quiz_id,), one=True)
    if not q:
        flash("Quiz not found.", "danger")
        return redirect(url_for("quizzes"))
    questions = query_db("SELECT id, question_text FROM questions WHERE quiz_id = ?", (quiz_id,))
    out = []
    for question in questions:
        opts = query_db("SELECT id, option_text FROM options WHERE question_id = ?", (question["id"],))
        out.append({"id": question["id"], "question": question["question_text"], "options": [dict(o) for o in opts]})
    return render_template("take_quiz.html", quiz=q, questions=out, user=current_user())

# Submit quiz (AJAX)
@app.route("/submit/<int:quiz_id>", methods=["POST"])
def submit_quiz(quiz_id):
    user = current_user()
    answers = request.get_json().get("answers", {})
    total = 0
    correct_count = 0
    db = get_db()
    qs = query_db("SELECT id FROM questions WHERE quiz_id = ?", (quiz_id,))
    total = len(qs)
    details = []
    for q in qs:
        qid = q["id"]
        selected_opt_id = answers.get(str(qid))
        opt = query_db("SELECT id, is_correct, option_text FROM options WHERE id = ?", (selected_opt_id,), one=True) if selected_opt_id else None
        is_corr = 0
        if opt and opt["is_correct"] == 1:
            is_corr = 1
            correct_count += 1
        corr = query_db("SELECT id, option_text FROM options WHERE question_id = ? AND is_correct = 1", (qid,), one=True)
        details.append({"question_id": qid, "selected": dict(opt) if opt else None, "correct": dict(corr) if corr else None, "is_correct": is_corr})
    # store result if user logged in
    if user:
        db.execute("INSERT INTO results (user_id, quiz_id, score, total, taken_at) VALUES (?, ?, ?, ?, ?)",
                   (user["id"], quiz_id, correct_count, total, datetime.utcnow()))
        db.commit()
    return jsonify({"score": correct_count, "total": total, "details": details})

# Results (for current user)
@app.route("/results")
def results():
    user = current_user()
    if not user:
        flash("Login to view your results history.", "warning")
        return redirect(url_for("login"))
    items = query_db("""SELECT r.id, r.score, r.total, r.taken_at, q.title 
                        FROM results r LEFT JOIN quizzes q ON r.quiz_id = q.id 
                        WHERE r.user_id = ? ORDER BY r.taken_at DESC""", (user["id"],))
    return render_template("results.html", items=items, user=user)

if __name__ == "__main__":
    app.run(debug=True)
