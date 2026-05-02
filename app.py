from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

# Initialize database
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            service TEXT
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

# Add worker
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
