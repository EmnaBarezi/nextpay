# NextPay - app for tontine groups in Burundi
# Step 23: admins can now create a tontine group

import os
import secrets
import sqlite3
from flask import Flask, render_template, request, session, redirect
from markupsafe import escape
from werkzeug.security import generate_password_hash, check_password_hash

# this creates my app, everything else will be added to it later
app = Flask(__name__)

# the session needs a secret key so nobody can fake a login
# I save it in a file called .secret_key, which is in my .gitignore so it never goes to GitHub
# if the file does not exist yet, I make a new random key
if not os.path.exists(".secret_key"):
    with open(".secret_key", "w") as f:
        f.write(secrets.token_hex(32))
with open(".secret_key") as f:
    app.secret_key = f.read()

# the name of the file where all my data will be saved
DB_NAME = "nextpay.db"

# new: the only schedules I allow for a group
FREQUENCIES = ["weekly", "every 2 weeks", "monthly"]


# this function creates my tables if they do not exist yet
def init_db():
    conn = sqlite3.connect(DB_NAME)

    # the users table, the columns come from the User class in my class diagram
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    # the table for the tontine groups, from the TontineGroup class
    # admin_id says which admin created the group, it points to a user in the users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tontine_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount_due REAL NOT NULL,
            frequency TEXT NOT NULL,
            start_date TEXT NOT NULL,
            admin_id INTEGER NOT NULL,
            FOREIGN KEY (admin_id) REFERENCES users (user_id)
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

    # I take the user_id and the role from the database too
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

    # I save who the user is in the session, so the app remembers them
    session["user_id"] = user[0]
    session["name"] = user[1]
    session["role"] = user[3]

    # after login I send the user to their dashboard
    return redirect("/dashboard")


# the dashboard is the page users see after they log in
@app.get("/dashboard")
def dashboard():
    # if nobody is logged in, I send them back to the login page
    if "user_id" not in session:
        return redirect("/login")

    page = "Hello, " + session["name"] + ". You are logged in as " + session["role"] + "."

    # new: only an admin sees the link to create a group and the list of their groups
    if session["role"] == "admin":
        page += " <a href='/groups/new'>Create a group</a>"

        conn = sqlite3.connect(DB_NAME)
        groups = conn.execute(
            "SELECT name, amount_due, frequency, start_date FROM tontine_groups WHERE admin_id = ?",
            (session["user_id"],),
        ).fetchall()
        conn.close()

        page += "<h2>Your groups</h2>"
        if len(groups) == 0:
            page += "<p>You have no groups yet. Create your first group.</p>"
        for g in groups:
            # escape() makes sure a group name cannot break my page
            page += "<p>" + str(escape(g[0])) + ": " + str(g[1]) + " BIF, " + g[2] + ", starts " + g[3] + "</p>"

    page += "<p><a href='/logout'>Log out</a></p>"
    return page


# new: this shows the page where an admin creates a group
@app.get("/groups/new")
def new_group_page():
    if "user_id" not in session:
        return redirect("/login")
    # business rule: only an admin can create a group
    if session["role"] != "admin":
        return "Only an admin can create a group."
    return render_template("create_group.html")


# new: this runs when the admin clicks "Create group"
@app.post("/groups")
def create_group():
    if "user_id" not in session:
        return redirect("/login")
    # I check the role here too, because someone could send the form without using my page
    if session["role"] != "admin":
        return "Only an admin can create a group."

    # I take what the admin typed in the form
    name = request.form["name"].strip()
    frequency = request.form["frequency"]
    start_date = request.form["start_date"]

    # I check the details and give a clear message if something is wrong
    if name == "":
        return "Group name cannot be empty. Please enter a name."
    try:
        amount_due = float(request.form["amount_due"])
    except ValueError:
        return "Contribution amount must be a number. Please enter an amount."
    if amount_due <= 0:
        return "Contribution amount must be more than 0. Please enter an amount."
    if frequency not in FREQUENCIES:
        return "Please choose how often members pay."
    if start_date == "":
        return "Please pick the first contribution date."

    # I save the group, and admin_id is the admin who is logged in
    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        "INSERT INTO tontine_groups (name, amount_due, frequency, start_date, admin_id) VALUES (?, ?, ?, ?, ?)",
        (name, amount_due, frequency, start_date, session["user_id"]),
    )
    conn.commit()
    conn.close()

    # I send the admin back to the dashboard, where the new group shows in the list
    return redirect("/dashboard")


# logout clears the session, so the app forgets the user
@app.get("/logout")
def logout():
    session.clear()
    return redirect("/login")


# I call init_db() here so the tables are ready every time the app starts
init_db()

# debug=True so the page reloads by itself when I change my code
if __name__ == "__main__":
    app.run(debug=True)