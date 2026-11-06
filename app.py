# NextPay - app for tontine groups in Burundi
# Step 18: I added the register page so users can see the form

import sqlite3
from flask import Flask, render_template

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


# new: this shows the register page from the templates folder
# right now the form only shows up, saving the user comes in the next step
@app.get("/register")
def register_page():
    return render_template("register.html")


# I call init_db() here so the table is ready every time the app starts
init_db()

# debug=True so the page reloads by itself when I change my code
if __name__ == "__main__":
    app.run(debug=True)