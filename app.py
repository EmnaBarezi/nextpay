# NextPay - app for tontine groups in Burundi
# Step 28: members now see a reminder when a contribution is due soon

import calendar
import os
import secrets
import sqlite3
from datetime import date, timedelta
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

# the only schedules I allow for a group
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

    # the memberships table, from the Membership class in my class diagram
    # one row = one member inside one group, so the same member can be in many groups
    # the PRIMARY KEY on (group_id, user_id) stops me from adding the same person twice
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memberships (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            join_order INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            reliability_score REAL,
            PRIMARY KEY (group_id, user_id),
            FOREIGN KEY (group_id) REFERENCES tontine_groups (group_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    # the contributions table, from the Contribution class in my class diagram
    # one row = one payment made by one member of one group
    # status starts as Recorded, later it will change to Confirmed or Flagged
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contributions (
            contribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Recorded',
            FOREIGN KEY (group_id, user_id) REFERENCES memberships (group_id, user_id)
        )
    """)

    # the payouts table, from the Payout class in my class diagram
    # one row = the money one member received in one round
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payouts (
            payout_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            amount REAL NOT NULL,
            payout_date TEXT NOT NULL,
            FOREIGN KEY (group_id) REFERENCES tontine_groups (group_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)
    conn.commit()
    conn.close()


# new: this adds a number of months to a date, and it can also go backwards with a negative number
# if the day does not exist in that month (for example the 31st), I use the last day of the month
def add_months(d, months):
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# new: this finds the next due date of a group, and the due date before it
# the group starts on start_date and then repeats every week, every 2 weeks or every month
def next_due_date(start_date, frequency, today):
    start = date.fromisoformat(start_date)

    if frequency == "monthly":
        # I count how many months passed since the start
        k = (today.year - start.year) * 12 + (today.month - start.month)
        if k < 0:
            k = 0
        # if this month's due date already passed, the next one is next month
        if add_months(start, k) < today:
            k += 1
        return add_months(start, k), add_months(start, k - 1)

    # weekly is every 7 days, every 2 weeks is every 14 days
    step = 7 if frequency == "weekly" else 14
    if start >= today:
        due = start
    else:
        # I count how many full steps passed, and I round up to the next one
        passed = (today - start).days
        due = start + timedelta(days=((passed + step - 1) // step) * step)
    return due, due - timedelta(days=step)


# this works out the payout turn for a group
# the order is the join order: member 1 gets round 1, member 2 gets round 2, and so on
# when everybody has received once, it starts again from member 1 (a new cycle)
def next_turn(conn, group_id):
    members = conn.execute(
        """
        SELECT u.user_id, u.full_name
        FROM memberships m
        JOIN users u ON u.user_id = m.user_id
        WHERE m.group_id = ?
        ORDER BY m.join_order
        """,
        (group_id,),
    ).fetchall()

    # how many payouts were already given, and how much money was paid out
    done, paid_out = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payouts WHERE group_id = ?",
        (group_id,),
    ).fetchone()

    # all the money members paid into the group
    total_in = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM contributions WHERE group_id = ?",
        (group_id,),
    ).fetchone()[0]

    # the round number is the number of payouts done plus one
    round_number = done + 1

    # % gives the remainder, so after the last member it goes back to the first one
    next_member = None
    if len(members) > 0:
        next_member = members[done % len(members)]

    # the pot is the money in the group that was not paid out yet
    return round_number, next_member, total_in - paid_out


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

    # only an admin sees the link to create a group
    if session["role"] == "admin":
        page += " <a href='/groups/new'>Create a group</a>"

    # I get the groups the user runs (as admin) or belongs to (as member)
    # a member can be in many groups, so this list can have more than one group
    conn = sqlite3.connect(DB_NAME)
    groups = conn.execute(
        """
        SELECT group_id, name, amount_due, frequency, start_date, admin_id
        FROM tontine_groups
        WHERE admin_id = ?
           OR group_id IN (SELECT group_id FROM memberships WHERE user_id = ?)
        """,
        (session["user_id"], session["user_id"]),
    ).fetchall()

    # new: reminders, I look at each group where the user is a member
    reminders = ""
    today = date.today()
    for g in groups:
        # the admin does not pay into the group, so no reminder for the admin
        if g[5] == session["user_id"]:
            continue

        due, previous = next_due_date(g[4], g[3], today)
        days_left = (due - today).days

        # I only remind when the due date is today, tomorrow or in 2 days
        if days_left > 2:
            continue

        # if the member already paid after the previous due date, no reminder is needed
        paid = conn.execute(
            "SELECT 1 FROM contributions WHERE group_id = ? AND user_id = ? AND payment_date > ?",
            (g[0], session["user_id"], previous.isoformat()),
        ).fetchone()
        if paid:
            continue

        if days_left == 0:
            when = "today"
        elif days_left == 1:
            when = "tomorrow"
        else:
            when = "in 2 days"
        reminders += (
            "<p><strong>Reminder:</strong> your contribution of " + str(g[2]) + " BIF to "
            + str(escape(g[1])) + " is due " + when + " (" + due.isoformat() + ").</p>"
        )
    conn.close()

    # the reminders show first, so the member sees them straight away
    page += reminders

    page += "<h2>Your groups</h2>"
    if len(groups) == 0:
        if session["role"] == "admin":
            page += "<p>You have no groups yet. Create your first group.</p>"
        else:
            page += "<p>You are not in a group yet. Ask your group admin to add you using your email.</p>"
    for g in groups:
        # escape() makes sure a group name cannot break my page
        # the name is a link to the page of that group
        page += (
            "<p><a href='/groups/" + str(g[0]) + "'>" + str(escape(g[1])) + "</a>: "
            + str(g[2]) + " BIF, " + g[3] + ", starts " + g[4] + "</p>"
        )

    page += "<p><a href='/logout'>Log out</a></p>"
    return page


# this shows the page where an admin creates a group
@app.get("/groups/new")
def new_group_page():
    if "user_id" not in session:
        return redirect("/login")
    # business rule: only an admin can create a group
    if session["role"] != "admin":
        return "Only an admin can create a group."
    return render_template("create_group.html")


# this runs when the admin clicks "Create group"
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


# this shows the page of one group with its members
@app.get("/groups/<int:group_id>")
def group_page(group_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    group = conn.execute(
        "SELECT group_id, name, amount_due, frequency, start_date, admin_id FROM tontine_groups WHERE group_id = ?",
        (group_id,),
    ).fetchone()

    # if the group does not exist I stop here
    if group is None:
        conn.close()
        return "This group does not exist."

    # I check if the logged in user is the admin or a member of this group
    is_admin = group[5] == session["user_id"]
    is_member = conn.execute(
        "SELECT 1 FROM memberships WHERE group_id = ? AND user_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()

    # people who are not in the group cannot see its data
    if not is_admin and not is_member:
        conn.close()
        return "You cannot open this group."

    # I get the members in the order they joined, this order will be used for the payouts
    members = conn.execute(
        """
        SELECT m.join_order, u.full_name, u.email, u.user_id
        FROM memberships m
        JOIN users u ON u.user_id = m.user_id
        WHERE m.group_id = ?
        ORDER BY m.join_order
        """,
        (group_id,),
    ).fetchall()

    # I get the contributions of this group, the newest first
    contributions = conn.execute(
        """
        SELECT c.payment_date, u.full_name, c.amount, c.status
        FROM contributions c
        JOIN users u ON u.user_id = c.user_id
        WHERE c.group_id = ?
        ORDER BY c.payment_date DESC, c.contribution_id DESC
        """,
        (group_id,),
    ).fetchall()

    # whose turn it is, and the payouts that were already given
    round_number, next_member, pot = next_turn(conn, group_id)
    payouts = conn.execute(
        """
        SELECT p.round_number, u.full_name, p.amount, p.payout_date
        FROM payouts p
        JOIN users u ON u.user_id = p.user_id
        WHERE p.group_id = ?
        ORDER BY p.round_number DESC
        """,
        (group_id,),
    ).fetchall()
    conn.close()

    # today is used as the default date in the form
    return render_template(
        "group.html",
        group=group,
        members=members,
        contributions=contributions,
        round_number=round_number,
        next_member=next_member,
        pot=pot,
        payouts=payouts,
        is_admin=is_admin,
        today=date.today().isoformat(),
    )


# this runs when the admin clicks "Add member"
@app.post("/groups/<int:group_id>/members")
def add_member(group_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)

    # business rule: only the admin of THIS group can add members
    group = conn.execute(
        "SELECT 1 FROM tontine_groups WHERE group_id = ? AND admin_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()
    if group is None:
        conn.close()
        return "Only the admin of this group can add members."

    # I look for a member account with the email the admin typed
    email = request.form["email"].strip().lower()
    user = conn.execute(
        "SELECT user_id FROM users WHERE email = ? AND role = 'member'", (email,)
    ).fetchone()
    if user is None:
        conn.close()
        return "No member account found with this email. Ask them to register as a Member first."

    # I check that this person is not already in the group
    already = conn.execute(
        "SELECT 1 FROM memberships WHERE group_id = ? AND user_id = ?",
        (group_id, user[0]),
    ).fetchone()
    if already:
        conn.close()
        return "This person is already in the group."

    # the new member gets the next join order: 1, 2, 3...
    next_order = conn.execute(
        "SELECT COALESCE(MAX(join_order), 0) + 1 FROM memberships WHERE group_id = ?",
        (group_id,),
    ).fetchone()[0]

    conn.execute(
        "INSERT INTO memberships (group_id, user_id, join_order, joined_at) VALUES (?, ?, ?, ?)",
        (group_id, user[0], next_order, date.today().isoformat()),
    )
    conn.commit()
    conn.close()

    # I send the admin back to the group page, where the new member shows in the list
    return redirect("/groups/" + str(group_id))


# this runs when the admin clicks "Remove" next to a member
@app.post("/groups/<int:group_id>/members/<int:user_id>/remove")
def remove_member(group_id, user_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)

    # business rule: only the admin of THIS group can remove members
    group = conn.execute(
        "SELECT 1 FROM tontine_groups WHERE group_id = ? AND admin_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()
    if group is None:
        conn.close()
        return "Only the admin of this group can remove members."

    # I delete only this person's membership, their account stays and they can be in other groups
    # the other members keep their join order, I do not renumber them
    conn.execute(
        "DELETE FROM memberships WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    conn.commit()
    conn.close()

    return redirect("/groups/" + str(group_id))


# this runs when the admin clicks "Record contribution"
@app.post("/groups/<int:group_id>/contributions")
def record_contribution(group_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)

    # business rule: only the admin of THIS group can record contributions
    group = conn.execute(
        "SELECT 1 FROM tontine_groups WHERE group_id = ? AND admin_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()
    if group is None:
        conn.close()
        return "Only the admin of this group can record contributions."

    # I take what the admin typed in the form and check it
    payment_date = request.form["payment_date"]
    try:
        member_id = int(request.form["member_id"])
        amount = float(request.form["amount"])
    except ValueError:
        conn.close()
        return "Please choose a member and enter the amount as a number."
    if amount <= 0:
        conn.close()
        return "Contribution amount must be more than 0. Please enter an amount."
    if payment_date == "":
        conn.close()
        return "Please pick the payment date."

    # the person must really be a member of this group
    is_member = conn.execute(
        "SELECT 1 FROM memberships WHERE group_id = ? AND user_id = ?",
        (group_id, member_id),
    ).fetchone()
    if is_member is None:
        conn.close()
        return "This person is not a member of the group."

    # I save the contribution with the status Recorded
    conn.execute(
        "INSERT INTO contributions (group_id, user_id, amount, payment_date) VALUES (?, ?, ?, ?)",
        (group_id, member_id, amount, payment_date),
    )
    conn.commit()
    conn.close()

    return redirect("/groups/" + str(group_id))


# this runs when the admin clicks "Record payout"
@app.post("/groups/<int:group_id>/payouts")
def record_payout(group_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)

    # business rule: only the admin of THIS group can record a payout
    group = conn.execute(
        "SELECT 1 FROM tontine_groups WHERE group_id = ? AND admin_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()
    if group is None:
        conn.close()
        return "Only the admin of this group can record a payout."

    # the app decides who gets the payout, the admin cannot choose (business rule)
    round_number, next_member, pot = next_turn(conn, group_id)
    if next_member is None:
        conn.close()
        return "Add members to the group first."
    if pot <= 0:
        conn.close()
        return "There is no money in the pot yet. Record contributions first."

    # the person who is next receives the whole pot
    conn.execute(
        "INSERT INTO payouts (group_id, user_id, round_number, amount, payout_date) VALUES (?, ?, ?, ?, ?)",
        (group_id, next_member[0], round_number, pot, date.today().isoformat()),
    )
    conn.commit()
    conn.close()

    return redirect("/groups/" + str(group_id))


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