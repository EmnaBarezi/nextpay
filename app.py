# NextPay - app for tontine groups in Burundi
# Step 19: the register form now saves the user in the database

import sqlite3
from flask import Flask, render_template, request
from werkzeug.security import generate_password_hash

# this creates my app, everything else will be added to it later
app = Flask(__name__)

# the name of the file where all my data will be saved
DB_NAME = "nextpay.db"


# this function creates the users table if it does not exist yet
# the columns come from the User class in my class diagram
def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# this is my test page, I will remove it later
@app.get("/")
def home():
    return "NextPay is running"


# this shows the register page from the templates folder
@app.get("/register")
def register_page():
    return render_template("register.html")


# new: this runs when the user clicks "Create account"
@app.post("/register")
def register():
    # I take what the user typed in the form
    full_name = request.form["full_name"].strip()
    email = request.form["email"].strip().lower()
    password = request.form["password"]
    role = request.form["role"]

    # I never save the real password, only a scrambled version of it (a hash)
    # this is for security, so nobody can read the passwords from the database
    password_hash = generate_password_hash(password)

    # I try to save the user in the users table
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (full_name, email, password_hash, role),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # email is UNIQUE in my table, so this happens when the email already has an account
        return "This email already has an account. Please log in instead."
    finally:
        conn.close()

    return "Account created. Welcome to NextPay, " + full_name + "."


# I call init_db() here so the table is ready every time the app starts
init_db()

# debug=True so the page reloads by itself when I change my code
if __name__ == "__main__":
    app.run(debug=True)