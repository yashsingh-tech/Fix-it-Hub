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
            password TEXT,
            address TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            customer_phone TEXT,
            customer_address TEXT,
            service TEXT,
            worker_id INTEGER,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/workers/<service>")
def workers(service):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, name, phone, service, address FROM workers WHERE service=?", (service,))
    data = c.fetchall()
    conn.close()
    return render_template("workers.html", workers=data, service=service)

@app.route("/worker/register", methods=["GET", "POST"])
def worker_register():
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        service = request.form["service"]
        email = request.form["email"]
        address = request.form["address"]
        password = generate_password_hash(request.form["password"])
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO workers (name, phone, service, email, password, address) VALUES (?, ?, ?, ?, ?, ?)",
                  (name, phone, service, email, password, address))
        conn.commit()
        conn.close()
        return redirect("/worker/login")
    return render_template("worker_register.html")

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

@app.route("/worker/dashboard")
def worker_dashboard():
    if 'worker_id' not in session:
        return redirect("/worker/login")
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bookings WHERE worker_id=?", (session['worker_id'],))
    bookings = c.fetchall()
    conn.close()
    pending_count  = sum(1 for b in bookings if b[6] == 'pending')
    accepted_count = sum(1 for b in bookings if b[6] == 'accepted')
    rejected_count = sum(1 for b in bookings if b[6] == 'rejected')
    return render_template("worker_dashboard.html",
                           name=session['worker_name'],
                           service=session['worker_service'],
                           bookings=bookings,
                           pending_count=pending_count,
                           accepted_count=accepted_count,
                           rejected_count=rejected_count)

@app.route("/booking/accept/<int:booking_id>", methods=["POST"])
def accept_booking(booking_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE bookings SET status='accepted' WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()
    return redirect("/worker/dashboard")

@app.route("/booking/reject/<int:booking_id>", methods=["POST"])
def reject_booking(booking_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE bookings SET status='rejected' WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()
    return redirect("/worker/dashboard")

@app.route("/worker/logout")
def worker_logout():
    session.clear()
    return redirect("/")

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

@app.route("/book/<int:worker_id>", methods=["GET", "POST"])
def book_worker(worker_id):
    if request.method == "POST":
        customer_name = request.form["customer_name"]
        customer_phone = request.form["customer_phone"]
        customer_address = request.form["customer_address"]
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT service FROM workers WHERE id=?", (worker_id,))
        worker = c.fetchone()
        c.execute("INSERT INTO bookings (customer_name, customer_phone, customer_address, service, worker_id) VALUES (?, ?, ?, ?, ?)",
                  (customer_name, customer_phone, customer_address, worker[0], worker_id))
        conn.commit()
        conn.close()
        return redirect("/booking_success")
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM workers WHERE id=?", (worker_id,))
    worker = c.fetchone()
    conn.close()
    return render_template("booking.html", worker=worker)

@app.route("/booking_success")
def booking_success():
    return render_template("booking_success.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == "yash" and password == "fixithub@123":
            session['admin'] = True
            return redirect("/admin")
        else:
            return render_template("admin_login.html", error="Wrong username or password!")
    
    if not session.get('admin'):
        return render_template("admin_login.html", error="")
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM workers")
    total_workers = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bookings")
    total_bookings = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bookings WHERE status='pending'")
    pending_bookings = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bookings WHERE status='accepted'")
    accepted_bookings = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bookings WHERE status='rejected'")
    rejected_bookings = c.fetchone()[0]
    c.execute("SELECT * FROM workers")
    workers = c.fetchall()
    c.execute("SELECT * FROM bookings")
    bookings = c.fetchall()
    conn.close()
    return render_template("admin.html",
                           total_workers=total_workers,
                           total_bookings=total_bookings,
                           pending_bookings=pending_bookings,
                           accepted_bookings=accepted_bookings,
                           rejected_bookings=rejected_bookings,
                           workers=workers,
                           bookings=bookings)

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin', None)
    return redirect("/")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)   