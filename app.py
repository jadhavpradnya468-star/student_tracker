from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, jsonify, session
from flask_mysqldb import MySQL
import bcrypt
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# MySQL Config from environment variables
app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_PORT'] = int(config.MYSQL_PORT)
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB

mysql = MySQL(app)

# ---------------- AUTH ---------------- #

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO users(username, password) VALUES(%s, %s)", (username, hashed))
    mysql.connection.commit()

    return redirect('/')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", [username])
    user = cur.fetchone()

    if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
        session['user'] = user[0]
        return redirect('/')

    return "Invalid credentials"

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

# ---------------- HOME ---------------- #

@app.route('/')
def index():
    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT s.id, s.name, s.is_major, MAX(d.date), st.current_streak, st.longest_streak
    FROM subjects s
    LEFT JOIN daily_logs d ON s.id = d.subject_id
    LEFT JOIN streaks st ON s.id = st.subject_id
    GROUP BY s.id
    """)
    
    data = cur.fetchall()

    subjects = []

    for row in data:
        last_date = row[3]
        color = "red"

        if last_date:
            diff = (date.today() - last_date).days
            if diff <= 3:
                color = "green"
            elif diff <= 7:
                color = "yellow"
            elif diff <= 30:
                color = "orange"

        subjects.append((row[0], row[1], row[2], row[4], row[5], color))

    warning = burnout_check()
    score = calculate_focus_score()
    progress = calculate_progress()

    return render_template("index.html",
                           subjects=subjects,
                           warning=warning,
                           score=score,
                           progress=progress)

# ---------------- SUBJECTS ---------------- #

@app.route('/add_subject', methods=['POST'])
def add_subject():
    name = request.form['name']
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO subjects(name) VALUES(%s)", [name])
    mysql.connection.commit()
    return redirect('/')

@app.route('/delete_subject/<int:id>')
def delete_subject(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM subjects WHERE id=%s", [id])
    cur.execute("DELETE FROM daily_logs WHERE subject_id=%s", [id])
    cur.execute("DELETE FROM streaks WHERE subject_id=%s", [id])
    mysql.connection.commit()
    return redirect('/')

@app.route('/set_major/<int:id>')
def set_major(id):
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM subjects WHERE is_major=1")
    count = cur.fetchone()[0]

    cur.execute("SELECT is_major FROM subjects WHERE id=%s", [id])
    is_major = cur.fetchone()[0]

    if is_major == 0 and count >= 2:
        return "Only 2 major subjects allowed!"

    cur.execute("UPDATE subjects SET is_major = NOT is_major WHERE id=%s", [id])
    mysql.connection.commit()

    return redirect('/')

# ---------------- LOGS ---------------- #

@app.route('/log/<int:subject_id>')
def log_page(subject_id):
    return render_template("add_log.html", subject_id=subject_id)

@app.route('/save_log', methods=['POST'])
def save_log():
    subject_id = request.form['subject_id']
    learning_text = request.form['learning_text']
    hours = request.form['hours']
    completed = 1 if 'completed' in request.form else 0

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO daily_logs(subject_id, date, learning_text, hours, completed)
        VALUES(%s, %s, %s, %s, %s)
    """, (subject_id, date.today(), learning_text, hours, completed))
    mysql.connection.commit()

    return redirect('/')

# ---------------- TASKS ---------------- #

@app.route('/tasks')
def tasks():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM tasks")
    tasks = cur.fetchall()
    return render_template("tasks.html", tasks=tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    task = request.form['task']
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO tasks(task, date, completed) VALUES(%s, %s, 0)",
                (task, date.today()))
    mysql.connection.commit()
    return redirect('/tasks')

@app.route('/complete_task/<int:id>')
def complete_task(id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE tasks SET completed=1 WHERE id=%s", [id])
    mysql.connection.commit()
    return redirect('/tasks')

@app.route('/delete_task/<int:id>')
def delete_task(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM tasks WHERE id=%s", [id])
    mysql.connection.commit()
    return redirect('/tasks')

# ---------------- NOTES ---------------- #

@app.route('/notes/<int:subject_id>')
def notes(subject_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM notes WHERE subject_id=%s", [subject_id])
    notes = cur.fetchall()
    return render_template("notes.html", notes=notes, subject_id=subject_id)

@app.route('/add_note', methods=['POST'])
def add_note():
    subject_id = request.form['subject_id']
    content = request.form['content']

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO notes(subject_id, content, created_at)
        VALUES(%s,%s,CURDATE())
    """, (subject_id, content))

    mysql.connection.commit()
    return redirect(f'/notes/{subject_id}')

# ---------------- ANALYTICS ---------------- #

@app.route('/graph_data')
def graph_data():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT date, IFNULL(SUM(hours),0)
        FROM daily_logs
        GROUP BY date
        ORDER BY date
    """)

    data = cur.fetchall()

    dates = [str(row[0]) for row in data]
    hours = [float(row[1]) for row in data]

    return jsonify({"dates": dates, "hours": hours})

@app.route('/heatmap_data')
def heatmap_data():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT date, SUM(hours)
        FROM daily_logs
        GROUP BY date
    """)

    data = cur.fetchall()
    result = [{"date": str(d[0]), "hours": float(d[1])} for d in data]

    return jsonify(result)

# ---------------- SMART FEATURES ---------------- #

def burnout_check():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT SUM(hours) FROM daily_logs
        WHERE date >= DATE_SUB(CURDATE(), INTERVAL 3 DAY)
    """)
    recent = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT SUM(hours) FROM daily_logs
        WHERE date BETWEEN DATE_SUB(CURDATE(), INTERVAL 6 DAY)
        AND DATE_SUB(CURDATE(), INTERVAL 3 DAY)
    """)
    old = cur.fetchone()[0] or 0

    if old > 0 and recent < old * 0.5:
        return "⚠️ Burnout detected! Take rest."

    return None

def calculate_focus_score():
    cur = mysql.connection.cursor()

    cur.execute("SELECT SUM(hours) FROM daily_logs")
    hours = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM tasks WHERE completed=1")
    tasks_done = cur.fetchone()[0]

    cur.execute("SELECT SUM(current_streak) FROM streaks")
    streak = cur.fetchone()[0] or 0

    score = (hours * 1.2) + (tasks_done * 2) + (streak * 2)

    return min(int(score), 100)

def calculate_progress():
    cur = mysql.connection.cursor()

    cur.execute("SELECT SUM(hours) FROM daily_logs")
    done = cur.fetchone()[0] or 0

    target = 50
    return min(int((done / target) * 100), 100)

# ---------------- AI ---------------- #

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.json['message'].lower()

    if "focus" in msg:
        reply = "Try Pomodoro technique 🔥"
    elif "low" in msg:
        reply = "Start small goals 💡"
    elif "subject" in msg:
        reply = "Focus on weakest subject 📚"
    else:
        reply = "Keep going! 🚀"

    return jsonify({"reply": reply})


@app.route('/graph')
def analytics():
    return render_template("analytics.html")


@app.route('/insights')
def insights():
    cur = mysql.connection.cursor()

    # Top subject
    cur.execute("""
        SELECT s.name, SUM(d.hours) as total
        FROM subjects s
        JOIN daily_logs d ON s.id = d.subject_id
        GROUP BY s.id
        ORDER BY total DESC
        LIMIT 1
    """)

    top = cur.fetchone()

    message = []

    if top:
        message.append(f"🔥 You focused most on {top[0]}")

    cur.execute("SELECT SUM(hours) FROM daily_logs")
    total = cur.fetchone()[0] or 0

    if total > 20:
        message.append("📈 Great consistency this week!")

    return "<br>".join(message)


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app.run(debug=True)