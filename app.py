# NextPay - app for tontine groups in Burundi
# Step 21: the app now remembers who is logged in (session)

import os
import secrets
import sqlite3
from flask import Flask, render_template, request, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash

# this creates my app, everything else will be added to it later
app = Flask(__name__)

# new: the session needs a secret key so nobody can fake a login
# I save it in a file called .secret_key, which is in my .gitignore so it never goes to GitHub
# if the file does not exist yet, I make a new random key
if not os.path.exists(".secret_key"):
    with open(".secret_key", "w") as f:
        f.write(secrets.token_hex(32))
with open(".secret_key") as f:
    app.secret_key = f.read()

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


# this runs when the user clicks "Create account"
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


# this shows the login page from the templates folder
@app.get("/login")
def login_page():
    return render_template("login.html")


# this runs when the user clicks "Log in"
@app.post("/login")
def login():
    # I take what the user typed in the form
    email = request.form["email"].strip().lower()
    password = request.form["password"]

    # new: I now also take the user_id and the role from the database
    conn = sqlite3.connect(DB_NAME)
    user = conn.execute(
        "SELECT user_id, full_name, password_hash, role FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()

    # check_password_hash compares what the user typed with the saved hash
    # I use the same message for both mistakes, so nobody can guess which emails exist
    if user is None or not check_password_hash(user[2], password):
        return "Email or password is wrong. Please try again."

    # new: I save who the user is in the session, so the app remembers them
    session["user_id"] = user[0]
    session["name"] = user[1]
    session["role"] = user[3]

    # new: after login I send the user to their dashboard
    return redirect("/dashboard")


# new: the dashboard is the page users see after they log in
@app.get("/dashboard")
def dashboard():
    # if nobody is logged in, I send them back to the login page
    if "user_id" not in session:
        return redirect("/login")
    return "Hello, " + session["name"] + ". You are logged in as " + session["role"] + ". <a href='/logout'>Log out</a>"


# new: logout clears the session, so the app forgets the user
@app.get("/logout")
def logout():
    session.clear()
    return redirect("/login")


# I call init_db() here so the table is ready every time the app starts
init_db()

# debug=True so the page reloads by itself when I change my code
if __name__ == "__main__":
    app.run(debug=True)