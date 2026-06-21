import hmac
import os
import re
from secrets import token_urlsafe

from flask import Flask, abort, flash, redirect, render_template, request, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.environ.get("FLASK_SECRET_KEY") or "dev-only-change-me"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").lower() == "true"
    or bool(os.environ.get("RENDER")),
)

DB_PATH = os.environ.get("SQLITE_DB_PATH", "database.db")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

SERVICES = {
    "plumber": "Plumber",
    "ac_repair": "AC Repair",
    "carpenter": "Carpenter",
    "electrician": "Electrician",
    "water_supply": "Water Supply",
    "cleaning": "Cleaning",
    "iron_service": "Iron Service",
}

PHONE_RE = re.compile(r"^[0-9+\-\s()]{7,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean(value, max_length=120):
    return (value or "").strip()[:max_length]


def is_valid_phone(phone):
    return bool(PHONE_RE.fullmatch(phone or ""))


def is_valid_email(email):
    return bool(EMAIL_RE.fullmatch(email or ""))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def csrf_protect():
    if request.method != "POST":
        return
    expected = session.get("_csrf_token", "")
    supplied = request.form.get("_csrf_token", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        abort(400, description="Invalid form token. Please refresh the page and try again.")

def init_db():
    conn = get_db()
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
    try:
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_workers_email_unique
            ON workers(email COLLATE NOCASE)
            WHERE email IS NOT NULL AND email != ''
        """)
    except sqlite3.IntegrityError:
        pass
    c.execute("CREATE INDEX IF NOT EXISTS idx_workers_service ON workers(service)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_worker_id ON bookings(worker_id)")
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/workers/<service>")
def workers(service):
    if service not in SERVICES:
        abort(404)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, phone, service, address FROM workers WHERE service=?", (service,))
    data = c.fetchall()
    conn.close()
    return render_template("workers.html", workers=data, service=service)

@app.route("/worker/register", methods=["GET", "POST"])
def worker_register():
    if request.method == "POST":
        name = clean(request.form.get("name"), 80)
        phone = clean(request.form.get("phone"), 20)
        service = clean(request.form.get("service"), 40)
        email = clean(request.form.get("email"), 120).lower()
        address = clean(request.form.get("address"), 180)
        raw_password = request.form.get("password", "")

        error = None
        if not all([name, phone, service, email, address, raw_password]):
            error = "Please complete all fields."
        elif service not in SERVICES:
            error = "Please select a valid service."
        elif not is_valid_phone(phone):
            error = "Please enter a valid phone number."
        elif not is_valid_email(email):
            error = "Please enter a valid email address."
        elif len(raw_password) < 8:
            error = "Password must be at least 8 characters."

        if error:
            return render_template("worker_register.html", error=error), 400

        password = generate_password_hash(raw_password)
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM workers WHERE email = ? COLLATE NOCASE", (email,))
        if c.fetchone():
            conn.close()
            return render_template("worker_register.html", error="An account with this email already exists."), 409
        try:
            c.execute("INSERT INTO workers (name, phone, service, email, password, address) VALUES (?, ?, ?, ?, ?, ?)",
                      (name, phone, service, email, password, address))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("worker_register.html", error="An account with this email already exists."), 409
        conn.close()
        flash("Registration successful. Please log in.")
        return redirect("/worker/login")
    return render_template("worker_register.html", error="")

@app.route("/worker/login", methods=["GET", "POST"])
def worker_login():
    if request.method == "POST":
        email = clean(request.form.get("email"), 120).lower()
        password = request.form.get("password", "")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM workers WHERE email=?", (email,))
        worker = c.fetchone()
        conn.close()
        if worker and worker[5] and check_password_hash(worker[5], password):
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
    conn = get_db()
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
    if 'worker_id' not in session:
        return redirect("/worker/login")
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE bookings SET status='accepted' WHERE id=? AND worker_id=? AND status='pending'",
              (booking_id, session['worker_id']))
    conn.commit()
    if c.rowcount == 0:
        flash("Booking could not be accepted.")
    else:
        flash("Booking accepted.")
    conn.close()
    return redirect("/worker/dashboard")

@app.route("/booking/reject/<int:booking_id>", methods=["POST"])
def reject_booking(booking_id):
    if 'worker_id' not in session:
        return redirect("/worker/login")
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE bookings SET status='rejected' WHERE id=? AND worker_id=? AND status='pending'",
              (booking_id, session['worker_id']))
    conn.commit()
    if c.rowcount == 0:
        flash("Booking could not be rejected.")
    else:
        flash("Booking rejected.")
    conn.close()
    return redirect("/worker/dashboard")

@app.route("/worker/logout")
def worker_logout():
    session.clear()
    return redirect("/")

@app.route("/add_worker", methods=["POST"])
def add_worker():
    flash("Please use the worker registration form to create a complete account.")
    return redirect("/worker/register")

@app.route("/book/<int:worker_id>", methods=["GET", "POST"])
def book_worker(worker_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM workers WHERE id=?", (worker_id,))
    worker = c.fetchone()
    if not worker:
        conn.close()
        abort(404)

    if request.method == "POST":
        customer_name = clean(request.form.get("customer_name"), 80)
        customer_phone = clean(request.form.get("customer_phone"), 20)
        customer_address = clean(request.form.get("customer_address"), 180)
        error = None
        if not all([customer_name, customer_phone, customer_address]):
            error = "Please complete all booking fields."
        elif not is_valid_phone(customer_phone):
            error = "Please enter a valid phone number."

        if error:
            conn.close()
            return render_template("booking.html", worker=worker, error=error), 400

        c.execute("INSERT INTO bookings (customer_name, customer_phone, customer_address, service, worker_id) VALUES (?, ?, ?, ?, ?)",
                  (customer_name, customer_phone, customer_address, worker[3], worker_id))
        conn.commit()
        conn.close()
        return redirect("/booking_success")
    conn.close()
    return render_template("booking.html", worker=worker, error="")

@app.route("/booking_success")
def booking_success():
    return render_template("booking_success.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        username = clean(request.form.get("username"), 80)
        password = request.form.get("password", "")
        if hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD):
            session['admin'] = True
            return redirect("/admin")
        else:
            return render_template("admin_login.html", error="Wrong username or password!")
    
    if not session.get('admin'):
        return render_template("admin_login.html", error="")
    
    conn = get_db()
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
