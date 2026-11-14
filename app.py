# NextPay - app for tontine groups in Burundi
# Step 31: nicer pages, payout rule and reliability score

import calendar
import os
import secrets
import sqlite3
from datetime import date, timedelta
from flask import Flask, render_template, request, session, redirect
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


# new: one function to show an error on a proper page, with a button to go back
# before, I returned plain text, which looked like a blank page
def message(text, back="/dashboard", status=400):
    return render_template("message.html", text=text, back=back), status


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
    # status starts as Recorded, then it can become Flagged and then Confirmed
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

    # the disputes table, from the Dispute class in my class diagram
    # one row = one complaint about one contribution
    # old_amount and new_amount keep a record of every correction (NFR 4)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS disputes (
            dispute_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            contribution_id INTEGER NOT NULL,
            raised_by INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            resolution_note TEXT,
            old_amount REAL,
            new_amount REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (group_id) REFERENCES tontine_groups (group_id),
            FOREIGN KEY (contribution_id) REFERENCES contributions (contribution_id),
            FOREIGN KEY (raised_by) REFERENCES users (user_id)
        )
    """)
    conn.commit()
    conn.close()


# this adds a number of months to a date, and it can also go backwards with a negative number
# if the day does not exist in that month (for example the 31st), I use the last day of the month
def add_months(d, months):
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# this finds the next due date of a group, and the due date before it
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


# new: the reliability score of one member in one group (FR 8.1)
# score = contributions paid on time / contributions due x 100
# a contribution is on time when it is paid after the previous due date and on or before this due date
# I only count the due dates since the member joined the group
def reliability(conn, group_id, user_id, start_date, frequency, joined_at, today):
    start = date.fromisoformat(start_date)
    joined = date.fromisoformat(joined_at)

    # I list every due date from the start of the group until today, with the one before it
    periods = []
    if frequency == "monthly":
        k = 0
        while add_months(start, k) <= today:
            periods.append((add_months(start, k - 1), add_months(start, k)))
            k += 1
    else:
        step = timedelta(days=7 if frequency == "weekly" else 14)
        d = start
        while d <= today:
            periods.append((d - step, d))
            d += step

    # I keep only the due dates after the member joined
    periods = [p for p in periods if p[1] >= joined]
    if len(periods) == 0:
        return None

    on_time = 0
    for previous, due in periods:
        paid = conn.execute(
            """
            SELECT 1 FROM contributions
            WHERE group_id = ? AND user_id = ? AND payment_date > ? AND payment_date <= ?
            """,
            (group_id, user_id, previous.isoformat(), due.isoformat()),
        ).fetchone()
        if paid:
            on_time += 1

    return round(on_time * 100 / len(periods))


# new: the names of the members who did not pay yet for this round
# in round 1 everybody needs at least 1 contribution, in round 2 at least 2, and so on
def unpaid_members(conn, group_id, round_number):
    rows = conn.execute(
        """
        SELECT u.full_name
        FROM memberships m
        JOIN users u ON u.user_id = m.user_id
        WHERE m.group_id = ?
          AND (SELECT COUNT(*) FROM contributions c
               WHERE c.group_id = m.group_id AND c.user_id = m.user_id) < ?
        ORDER BY m.join_order
        """,
        (group_id, round_number),
    ).fetchall()
    return [r[0] for r in rows]


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


# new: the home page sends the user to the right place
@app.get("/")
def home():
    if "user_id" in session:
        return redirect("/dashboard")
    return redirect("/login")


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

    # I check the details and give a clear message if something is wrong
    if full_name == "":
        return message("Full name cannot be empty. Please enter your name.", "/register")
    if "@" not in email or "." not in email:
        return message("This email does not look right. Please check it.", "/register")
    if len(password) < 8:
        return message("Password is too short. Please use at least 8 characters.", "/register")
    if role not in ("admin", "member"):
        return message("Please choose Admin or Member.", "/register")

    # I never save the real password, only a scrambled version of it (a hash)
    # this is for security, so nobody can read the passwords from the database
    password_hash = generate_password_hash(password)

    # I try to save the user in the users table
    conn = sqlite3.connect(DB_NAME)
    try:
        cursor = conn.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (full_name, email, password_hash, role),
        )
        conn.commit()
        new_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # email is UNIQUE in my table, so this happens when the email already has an account
        return message("This email already has an account. Please log in instead.", "/login", 409)
    finally:
        conn.close()

    # new: I log the user in straight away and send them to the dashboard
    session.clear()
    session["user_id"] = new_id
    session["name"] = full_name
    session["role"] = role
    return redirect("/dashboard")


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
        return message("Email or password is wrong. Please try again.", "/login", 401)

    # I save who the user is in the session, so the app remembers them
    session.clear()
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

    # I get the groups the user runs (as admin) or belongs to (as member)
    # a member can be in many groups, so this list can have more than one group
    conn = sqlite3.connect(DB_NAME)
    groups = conn.execute(
        """
        SELECT g.group_id, g.name, g.amount_due, g.frequency, g.start_date,
               (SELECT COUNT(*) FROM memberships m WHERE m.group_id = g.group_id),
               g.admin_id
        FROM tontine_groups g
        WHERE g.admin_id = ?
           OR g.group_id IN (SELECT group_id FROM memberships WHERE user_id = ?)
        ORDER BY g.group_id DESC
        """,
        (session["user_id"], session["user_id"]),
    ).fetchall()

    # reminders, I look at each group where the user is a member
    reminders = []
    today = date.today()
    for g in groups:
        # the admin does not pay into the group, so no reminder for the admin
        if g[6] == session["user_id"]:
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
        reminders.append((g[1], g[2], when, due.isoformat()))
    conn.close()

    return render_template("dashboard.html", groups=groups, reminders=reminders)


# this shows the page where an admin creates a group
@app.get("/groups/new")
def new_group_page():
    if "user_id" not in session:
        return redirect("/login")
    # business rule: only an admin can create a group
    if session["role"] != "admin":
        return message("Only an admin can create a group.", "/dashboard", 403)
    return render_template("create_group.html")


# this runs when the admin clicks "Create group"
@app.post("/groups")
def create_group():
    if "user_id" not in session:
        return redirect("/login")
    # I check the role here too, because someone could send the form without using my page
    if session["role"] != "admin":
        return message("Only an admin can create a group.", "/dashboard", 403)

    # I take what the admin typed in the form
    name = request.form["name"].strip()
    frequency = request.form["frequency"]
    start_date = request.form["start_date"]

    # I check the details and give a clear message if something is wrong
    if name == "":
        return message("Group name cannot be empty. Please enter a name.", "/groups/new")
    try:
        amount_due = float(request.form["amount_due"])
    except ValueError:
        return message("Contribution amount must be a number. Please enter an amount.", "/groups/new")
    if amount_due <= 0:
        return message("Contribution amount must be more than 0. Please enter an amount.", "/groups/new")
    if frequency not in FREQUENCIES:
        return message("Please choose how often members pay.", "/groups/new")
    try:
        first_date = date.fromisoformat(start_date)
    except ValueError:
        return message("Please pick the first contribution date.", "/groups/new")
    # new: a date far in the past would make the reliability score slow to work out
    if first_date < date(2020, 1, 1):
        return message("The first contribution date must be in 2020 or later.", "/groups/new")

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
        return message("This group does not exist.", "/dashboard", 404)

    # I check if the logged in user is the admin or a member of this group
    is_admin = group[5] == session["user_id"]
    is_member = conn.execute(
        "SELECT 1 FROM memberships WHERE group_id = ? AND user_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()

    # people who are not in the group cannot see its data
    if not is_admin and not is_member:
        conn.close()
        return message("You cannot open this group.", "/dashboard", 403)

    # I get the members in the order they joined, this order will be used for the payouts
    member_rows = conn.execute(
        """
        SELECT m.join_order, u.full_name, u.email, u.user_id, m.joined_at
        FROM memberships m
        JOIN users u ON u.user_id = m.user_id
        WHERE m.group_id = ?
        ORDER BY m.join_order
        """,
        (group_id,),
    ).fetchall()

    # new: I add the reliability score of each member to the row
    today = date.today()
    members = []
    for m in member_rows:
        score = reliability(conn, group_id, m[3], group[4], group[3], m[4], today)
        members.append((m[0], m[1], m[2], m[3], score))

    # I get the contributions of this group, the newest first
    # I also take the contribution_id, because the Flag button needs it
    contributions = conn.execute(
        """
        SELECT c.contribution_id, c.payment_date, u.full_name, c.amount, c.status
        FROM contributions c
        JOIN users u ON u.user_id = c.user_id
        WHERE c.group_id = ?
        ORDER BY c.payment_date DESC, c.contribution_id DESC
        """,
        (group_id,),
    ).fetchall()

    # whose turn it is, who still has to pay for this round, and the payouts already given
    round_number, next_member, pot = next_turn(conn, group_id)
    waiting = unpaid_members(conn, group_id, round_number)
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

    # the disputes of this group, the newest first
    # date(..., '+3 days') gives the day the admin should resolve it by
    disputes = conn.execute(
        """
        SELECT d.dispute_id, d.contribution_id, c.payment_date, cu.full_name, c.amount,
               ru.full_name, d.reason, d.status, d.resolution_note,
               d.old_amount, d.new_amount, date(d.created_at, '+3 days')
        FROM disputes d
        JOIN contributions c ON c.contribution_id = d.contribution_id
        JOIN users cu ON cu.user_id = c.user_id
        JOIN users ru ON ru.user_id = d.raised_by
        WHERE d.group_id = ?
        ORDER BY d.dispute_id DESC
        """,
        (group_id,),
    ).fetchall()

    # the report of the group, total saved, total paid out and what each member paid (FR 9.1)
    total_in = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM contributions WHERE group_id = ?",
        (group_id,),
    ).fetchone()[0]
    total_out = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM payouts WHERE group_id = ?",
        (group_id,),
    ).fetchone()[0]

    # LEFT JOIN keeps members who did not pay yet, they show with 0
    per_member = conn.execute(
        """
        SELECT u.full_name, COALESCE(SUM(c.amount), 0), COUNT(c.contribution_id)
        FROM memberships m
        JOIN users u ON u.user_id = m.user_id
        LEFT JOIN contributions c ON c.user_id = m.user_id AND c.group_id = m.group_id
        WHERE m.group_id = ?
        GROUP BY m.user_id
        ORDER BY m.join_order
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
        waiting=waiting,
        payouts=payouts,
        disputes=disputes,
        total_in=total_in,
        total_out=total_out,
        per_member=per_member,
        is_admin=is_admin,
        today=today.isoformat(),
    )


# this runs when the admin clicks "Add member"
@app.post("/groups/<int:group_id>/members")
def add_member(group_id):
    if "user_id" not in session:
        return redirect("/login")

    back = "/groups/" + str(group_id)
    conn = sqlite3.connect(DB_NAME)

    # business rule: only the admin of THIS group can add members
    group = conn.execute(
        "SELECT 1 FROM tontine_groups WHERE group_id = ? AND admin_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()
    if group is None:
        conn.close()
        return message("Only the admin of this group can add members.", "/dashboard", 403)

    # I look for a member account with the email the admin typed
    email = request.form["email"].strip().lower()
    user = conn.execute(
        "SELECT user_id FROM users WHERE email = ? AND role = 'member'", (email,)
    ).fetchone()
    if user is None:
        conn.close()
        return message("No member account found with this email. Ask them to register as a Member first.", back, 404)

    # I check that this person is not already in the group
    already = conn.execute(
        "SELECT 1 FROM memberships WHERE group_id = ? AND user_id = ?",
        (group_id, user[0]),
    ).fetchone()
    if already:
        conn.close()
        return message("This person is already in the group.", back, 409)

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
    return redirect(back)


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
        return message("Only the admin of this group can remove members.", "/dashboard", 403)

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

    back = "/groups/" + str(group_id)
    conn = sqlite3.connect(DB_NAME)

    # business rule: only the admin of THIS group can record contributions
    group = conn.execute(
        "SELECT 1 FROM tontine_groups WHERE group_id = ? AND admin_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()
    if group is None:
        conn.close()
        return message("Only the admin of this group can record contributions.", "/dashboard", 403)

    # I take what the admin typed in the form and check it
    payment_date = request.form["payment_date"]
    try:
        member_id = int(request.form["member_id"])
        amount = float(request.form["amount"])
    except ValueError:
        conn.close()
        return message("Please choose a member and enter the amount as a number.", back)
    if amount <= 0:
        conn.close()
        return message("Contribution amount must be more than 0. Please enter an amount.", back)
    try:
        date.fromisoformat(payment_date)
    except ValueError:
        conn.close()
        return message("Please pick the payment date.", back)

    # the person must really be a member of this group
    is_member = conn.execute(
        "SELECT 1 FROM memberships WHERE group_id = ? AND user_id = ?",
        (group_id, member_id),
    ).fetchone()
    if is_member is None:
        conn.close()
        return message("This person is not a member of the group.", back)

    # I save the contribution with the status Recorded
    conn.execute(
        "INSERT INTO contributions (group_id, user_id, amount, payment_date) VALUES (?, ?, ?, ?)",
        (group_id, member_id, amount, payment_date),
    )
    conn.commit()
    conn.close()

    return redirect(back)


# this runs when the admin clicks "Record payout"
@app.post("/groups/<int:group_id>/payouts")
def record_payout(group_id):
    if "user_id" not in session:
        return redirect("/login")

    back = "/groups/" + str(group_id)
    conn = sqlite3.connect(DB_NAME)

    # business rule: only the admin of THIS group can record a payout
    group = conn.execute(
        "SELECT 1 FROM tontine_groups WHERE group_id = ? AND admin_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()
    if group is None:
        conn.close()
        return message("Only the admin of this group can record a payout.", "/dashboard", 403)

    # the app decides who gets the payout, the admin cannot choose (business rule)
    round_number, next_member, pot = next_turn(conn, group_id)
    if next_member is None:
        conn.close()
        return message("Add members to the group first.", back)

    # new: the payout waits until every member has paid for this round
    waiting = unpaid_members(conn, group_id, round_number)
    if len(waiting) > 0:
        conn.close()
        return message("Not everybody has paid for this round yet. Waiting for: " + ", ".join(waiting) + ".", back)
    if pot <= 0:
        conn.close()
        return message("There is no money in the pot yet. Record contributions first.", back)

    # the person who is next receives the whole pot
    conn.execute(
        "INSERT INTO payouts (group_id, user_id, round_number, amount, payout_date) VALUES (?, ?, ?, ?, ?)",
        (group_id, next_member[0], round_number, pot, date.today().isoformat()),
    )
    conn.commit()
    conn.close()

    return redirect(back)


# this runs when a member clicks "Flag" next to a contribution
@app.post("/groups/<int:group_id>/contributions/<int:contribution_id>/flag")
def flag_contribution(group_id, contribution_id):
    if "user_id" not in session:
        return redirect("/login")

    back = "/groups/" + str(group_id)
    conn = sqlite3.connect(DB_NAME)

    # only a member of THIS group can flag a record (the admin resolves disputes, not flags them)
    is_member = conn.execute(
        "SELECT 1 FROM memberships WHERE group_id = ? AND user_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()
    if is_member is None:
        conn.close()
        return message("Only a member of this group can flag a record.", "/dashboard", 403)

    # the contribution must belong to this group
    contribution = conn.execute(
        "SELECT status FROM contributions WHERE contribution_id = ? AND group_id = ?",
        (contribution_id, group_id),
    ).fetchone()
    if contribution is None:
        conn.close()
        return message("This record does not exist.", back, 404)
    if contribution[0] == "Flagged":
        conn.close()
        return message("This record is already flagged and waiting for the admin.", back, 409)

    # the member must say why they think the record is wrong
    reason = request.form["reason"].strip()
    if reason == "":
        conn.close()
        return message("Please write why you think this record is wrong.", back)
    if len(reason) > 300:
        conn.close()
        return message("The reason is too long. Please use 300 characters or less.", back)

    # I save the dispute and I change the status of the contribution to Flagged
    conn.execute(
        "INSERT INTO disputes (group_id, contribution_id, raised_by, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (group_id, contribution_id, session["user_id"], reason, date.today().isoformat()),
    )
    conn.execute(
        "UPDATE contributions SET status = 'Flagged' WHERE contribution_id = ?",
        (contribution_id,),
    )
    conn.commit()
    conn.close()

    return redirect(back)


# this runs when the admin clicks "Resolve" on a dispute
@app.post("/groups/<int:group_id>/disputes/<int:dispute_id>/resolve")
def resolve_dispute(group_id, dispute_id):
    if "user_id" not in session:
        return redirect("/login")

    back = "/groups/" + str(group_id)
    conn = sqlite3.connect(DB_NAME)

    # business rule: only the admin of THIS group can resolve a dispute
    group = conn.execute(
        "SELECT 1 FROM tontine_groups WHERE group_id = ? AND admin_id = ?",
        (group_id, session["user_id"]),
    ).fetchone()
    if group is None:
        conn.close()
        return message("Only the admin of this group can resolve a dispute.", "/dashboard", 403)

    # the dispute must belong to this group and still be open
    dispute = conn.execute(
        "SELECT contribution_id, status FROM disputes WHERE dispute_id = ? AND group_id = ?",
        (dispute_id, group_id),
    ).fetchone()
    if dispute is None:
        conn.close()
        return message("This dispute does not exist.", back, 404)
    if dispute[1] != "Open":
        conn.close()
        return message("This dispute is already resolved.", back, 409)

    # the admin must choose to keep or correct the record, and write a note the member can see
    decision = request.form["decision"]
    note = request.form["note"].strip()
    if decision not in ("keep", "correct"):
        conn.close()
        return message("Please choose to keep or correct the record.", back)
    if note == "":
        conn.close()
        return message("Please write a resolution note, so the member understands the decision.", back)

    # I take the amount now saved in the record, I keep it as the old amount
    old_amount = conn.execute(
        "SELECT amount FROM contributions WHERE contribution_id = ?", (dispute[0],)
    ).fetchone()[0]
    new_amount = None

    if decision == "correct":
        try:
            new_amount = float(request.form["new_amount"])
        except ValueError:
            conn.close()
            return message("To correct the record, please enter the right amount as a number.", back)
        if new_amount <= 0:
            conn.close()
            return message("The right amount must be more than 0.", back)
        # I change the amount in the contribution
        conn.execute(
            "UPDATE contributions SET amount = ? WHERE contribution_id = ?",
            (new_amount, dispute[0]),
        )

    # the contribution goes back to Confirmed, like in my state diagram
    conn.execute(
        "UPDATE contributions SET status = 'Confirmed' WHERE contribution_id = ?",
        (dispute[0],),
    )
    # the dispute is closed, and I keep the old and the new amount as a record of the correction
    conn.execute(
        "UPDATE disputes SET status = 'Resolved', resolution_note = ?, old_amount = ?, new_amount = ? WHERE dispute_id = ?",
        (note, old_amount, new_amount, dispute_id),
    )
    conn.commit()
    conn.close()

    return redirect(back)


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