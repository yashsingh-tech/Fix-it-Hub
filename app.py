from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'fixithub_secret_123'

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            service TEXT,
            email TEXT,
            password TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Home page
@app.route("/")
def home():
    return render_template("home.html")

# Show workers by service
@app.route("/workers/<service>")
def workers(service):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT name, phone FROM workers WHERE service=?", (service,))
    data = c.fetchall()
    conn.close()
    return render_template("workers.html", workers=data, service=service)

# Worker Register
@app.route("/worker/register", methods=["GET", "POST"])
def worker_register():
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        service = request.form["service"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO workers (name, phone, service, email, password) VALUES (?, ?, ?, ?, ?)",
                  (name, phone, service, email, password))
        conn.commit()
        conn.close()
        return redirect("/worker/login")
    return render_template("worker_register.html")

# Worker Login
@app.route("/worker/login", methods=["GET", "POST"])
def worker_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM workers WHERE email=?", (email,))
        worker = c.fetchone()
        conn.close()
        if worker and check_password_hash(worker[5], password):
            session['worker_id'] = worker[0]
            session['worker_name'] = worker[1]
            session['worker_service'] = worker[3]
            return redirect("/worker/dashboard")
        else:
            flash("Invalid email or password!")
            return redirect("/worker/login")
    return render_template("worker_login.html")

# Worker Dashboard
@app.route("/worker/dashboard")
def worker_dashboard():
    if 'worker_id' not in session:
        return redirect("/worker/login")
    return render_template("worker_dashboard.html",
                           name=session['worker_name'],
                           service=session['worker_service'])

# Worker Logout
@app.route("/worker/logout")
def worker_logout():
    session.clear()
    return redirect("/")

# Add worker (old route — ab bhi kaam karega)
@app.route("/add_worker", methods=["POST"])
def add_worker():
    name = request.form["name"]
    phone = request.form["phone"]
    service = request.form["service"]
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO workers (name, phone, service) VALUES (?, ?, ?)",
              (name, phone, service))
    conn.commit()
    conn.close()
    return redirect("/")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)