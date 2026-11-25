# NextPay

**A digital savings tool for tontine groups in Burundi.**

**Try it now:** https://emna6.pythonanywhere.com

## What is NextPay?

In Burundi, many people save in tontines. A tontine is a group of people who each pay the same amount on a regular schedule. In each round, the whole pot goes to one member, until every member has received it once.

Most tontines are run on paper or from memory. This leads to forgotten payments, lost records and arguments about who paid and whose turn it is.

NextPay gives each group one shared and reliable record:

- An admin runs the group and records every payment.
- Every member sees the same history.
- The app works out the payout order by itself.
- Members get a reminder before a payment is due.
- A member can flag a record they think is wrong, and the admin reviews it.
- Each member has a reliability score based on paying on time.

NextPay is made to complement tontines, not replace them. It does not move any money. It only keeps the records.

## Who uses it?

- **Admin:** creates a group, adds and removes members, and records payments and payouts. The admin also resolves disputes.
- **Member:** is added to one or more groups by an admin, sees the shared history, and can flag a record that looks wrong.

## Live version

NextPay is deployed, so you can use it without installing anything:

**https://emna6.pythonanywhere.com**

It runs on PythonAnywhere's free plan, with a secure HTTPS connection. The live app **starts with an empty database**, so create your own accounts to try it. The live site has its own database, separate from the one on your own computer.

### Quick tour: try every feature in about 10 minutes

You need three people at the same time. Use your normal browser window for the admin, and two **private (incognito) windows** for the two members, because each window has its own login.

1. **Create the admin.** Open the live link, click **Create one here**, and register: name `Admin`, email `admin@example.com`, a password of 8 or more characters, role **Admin**. You land on a dashboard that says "You have no groups yet".
2. **Create two members.** In a private window, register `Anna` (`anna@example.com`, role **Member**). In a second private window, register `Bob` (`bob@example.com`, role **Member**). Each dashboard says "You are not in a group yet", because only an admin can add members.
3. **Create a group.** As the admin, click **Create a group**. Use the name `Ubuntu Savers`, amount `10000`, **Weekly**, and the first date **tomorrow**. Click **Create group**.
4. **Add the members.** Open the group. In **Members**, add `anna@example.com`, then `bob@example.com`. They appear as 1 and 2, which is the join order. **Next payout** says Round 1 goes to Anna.
5. **Record the first payment.** In **Contributions**, choose Anna and click **Record contribution**. **Next payout** now says "Waiting for payment from: Bob", and the **Record payout** button is disabled. **Report** shows 10000 saved, 0 paid out and 10000 in the pot.
6. **Record the second payment and the payout.** Record Bob's payment. The button turns on. Click **Record payout** and confirm. Anna receives 20000, both payments change from **Recorded** to **Confirmed**, the pot goes back to 0, and Round 2 is Bob's.
7. **Flag a mistake.** As the admin, record another payment for Bob with a wrong amount, like `8000`. In Bob's window, open the group, write a reason next to that payment, such as `I paid 10000`, and click **Flag**. The payment becomes **Flagged**, and **Disputes** shows it as Open, with a resolve-by date 3 days later.
8. **Resolve the dispute.** As the admin, in **Disputes**, choose **Correct the amount**, type `10000`, write a note, and click **Resolve**. The dispute shows the note and "Corrected from 8000 to 10000 BIF", and the payment is **Confirmed**. Everybody in the group can read this.
9. **See a reminder.** Create a second group with the first date **tomorrow**, add Anna, and record nothing. Log in as Anna: her dashboard shows a reminder that her payment is due tomorrow. When the admin records her payment, the reminder disappears.
10. **See a reliability score.** Create a group with the first date **today**, add Anna, and record her payment with today's date. In **Members**, Anna shows "Paid on time: 100%". Before the first due date, the page shows "No payment due yet".

## Run it on your own computer

### What you need

- **Python 3.9 or newer.** Check with `python --version`. It was tested on Python 3.12 and 3.14.
- **Git.** Check with `git --version`.

### Steps

**1. Download the code**

```
git clone https://github.com/EmnaBarezi/nextpay.git
cd nextpay
```

**2. Create a virtual environment.** This is a private folder for the packages this project needs.

```
python -m venv venv
```

**3. Turn the virtual environment on.**

- On Windows (PowerShell):
  ```
  venv\Scripts\activate
  ```
  If Windows says that running scripts is disabled, run this once and try again:
  ```
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  ```
- On macOS or Linux:
  ```
  source venv/bin/activate
  ```

When it works, `(venv)` appears at the start of the line in your terminal.

**4. Install the packages**

```
python -m pip install -r requirements.txt
```

**5. Start the app**

```
python app.py
```

**6. Open it in your browser**

Go to `http://127.0.0.1:5000`. You should see the NextPay login page. Click **Create one here** to make the first account, then follow the Quick tour above.

### Environment variables

**None are needed.** There is no `.env` file. The only secret, the key that protects login sessions, is created automatically in a file called `.secret_key` the first time the app runs.

### Good to know

- **The database is created automatically.** The first run creates a file called `nextpay.db` next to `app.py`. Both `nextpay.db` and `.secret_key` are listed in `.gitignore`, so they are never uploaded to GitHub.
- **To stop the app,** click in the terminal and press **Ctrl + C**.
- **To start it again later,** turn the virtual environment on (step 3) and run `python app.py`.
- **To start with empty data,** stop the app and delete `nextpay.db`. It is created again, empty, on the next run.
- **If `python` is not found on macOS or Linux,** use `python3` instead.
- **If `pip` is not found,** use `python -m pip`, as in step 4.

## Testing the features that depend on the date

Reminders and the reliability score depend on today's date. To see them, create groups with a first date of tomorrow (reminders) or today (reliability score), as in steps 9 and 10 of the Quick tour. To try other dates when running NextPay on your own computer, change your computer's date and reload the page.

## Features

### Accounts
- A person registers with a name, an email and a password of at least 8 characters, and chooses a role: **admin** or **member**.
- Passwords are never stored as plain text. They are saved as a scrambled version called a hash.
- After registering or logging in, the person lands on their dashboard. Pages that need a login send visitors to the login page.

### Groups and members
- An admin creates a group with a name, the amount each member pays, a schedule (weekly, every 2 weeks or monthly) and the date of the first contribution. The amount is the same for every member and every round.
- The admin adds a member by typing the email they registered with. The person must have registered as a member first. Members cannot join a group on their own.
- Each member gets a **join order** (1, 2, 3 and so on). The join order decides who is paid first.
- The admin can remove a member. One person can belong to several groups, if different admins add them.

### Contributions and the shared history
- Only the admin records a payment: who paid, how much and on which date.
- Every member of the group sees the same history of payments. This is what removes arguments about who paid.
- Each payment has a status: **Recorded** when it is created, **Flagged** when a member disputes it, and **Confirmed** when the round closes (the admin records the payout) or when the admin resolves the dispute.

### The pot and the payout
- **The pot** is the money saved minus the money already paid out. It goes up when members pay, and it goes down when a payout is made.
- **The payout order** follows the join order. The first payout goes to member 1, the second to member 2, and so on. After the last member, a new cycle starts from member 1.
- **The admin cannot choose** who is paid. The app decides, and the admin only confirms the payout.
- **A payout is blocked until every member has paid for that round.** In round 1 every member needs at least 1 recorded payment, in round 2 at least 2, and so on. The page shows who the app is still waiting for, and the **Record payout** button stays disabled until everyone has paid.
- The member who is next receives the whole pot.

### Reminders
- A member sees a reminder on their dashboard from 2 days before a payment is due, until they have paid.
- The due dates come from the group's first date and schedule. For monthly groups, a date that does not exist in a month (like the 31st) moves to the last day of that month.
- Admins do not get reminders, because they do not pay into the group.

### Disputes
- A member who thinks a payment record is wrong can **flag** it. They must write a reason. Only members can flag, not the admin.
- The admin then **keeps** the record or **corrects** the amount, and must write a note. Everybody in the group can read the reason and the note.
- When the admin corrects a record, the app saves both the old and the new amount, so every correction leaves a trace.
- The admin should resolve a dispute within 3 days. The page shows the deadline.

### Reliability score
- Each member has a score from 0 to 100: the payments made on time, divided by the payments due, multiplied by 100.
- A payment is **on time** if it is made after the previous due date and on or before the current due date.
- Only the due dates after the member joined are counted. Before the first due date, the page says "No payment due yet".

### Report
- The group page shows the total saved, the total paid out, the money still in the pot, and how much each member has paid.

## Roles and permissions

When a person registers, they choose a role: **admin** or **member**. Anyone can choose either role.

In NextPay, an **admin is the organiser of a group**, like the person who keeps the notebook in a real tontine. An admin is not an administrator of the whole system. Every admin action is checked on the server against the group that the admin created, so an admin can only act inside their own groups. A person who registers as an admin starts with no groups and cannot open or change anyone else's group.

| Action | Admin of the group | Member of the group | Other people |
|---|---|---|---|
| Create a group | Yes | No | No |
| Add or remove members | Yes | No | No |
| Record a contribution | Yes | No | No |
| Record a payout | Yes | No | No |
| Resolve a dispute | Yes | No | No |
| Flag a contribution | No | Yes | No |
| See the group page, history and report | Yes | Yes | No |
| See payment reminders | No | Yes | No |

## Technology

| Part | What is used | Why |
|---|---|---|
| Language | Python 3 | Simple and readable. |
| Web framework | Flask | A small standard framework: it connects web addresses to Python functions. |
| Database | SQLite, through Python's built-in `sqlite3` module | A relational database stored in one file, with the SQL written by hand. |
| Pages | HTML templates (Jinja, which comes with Flask) | Each page is an HTML file with blanks that Flask fills in with data. |
| Styling | Plain CSS, written by hand | No CSS framework. One stylesheet for the whole app. |
| Passwords | Werkzeug (installed with Flask) | Passwords are saved as hashes, never as plain text. |
| Hosting | PythonAnywhere (free plan) | Runs the live version over HTTPS. |

NextPay uses no external services and no outside APIs. All the data is entered by the admin and the members and saved in its own database.

## Project structure

```
nextpay/
├── app.py              The whole backend: database tables, rules and page addresses (routes)
├── requirements.txt    The Python packages needed to run the app
├── README.md           This file
├── .gitignore          Files that Git must not upload (the database and the secret key)
├── static/
│   └── style.css       All the styles of the app
└── templates/          The HTML pages
    ├── base.html           The top bar and layout shared by every page
    ├── login.html          Log in
    ├── register.html       Create an account
    ├── dashboard.html      The user's groups and reminders
    ├── create_group.html   The form to create a group
    ├── group.html          One group: payout, members, contributions, disputes, report
    └── message.html        The page that shows an error, with a Go back button
```

## How a request works

1. The browser asks for a page, for example `/groups/1`.
2. Flask finds the function in `app.py` for that address. The function checks who is logged in and whether that person is allowed to see the page.
3. The function reads the data it needs from the database with SQL, and hands it to an HTML template.
4. The template turns the data into the page the user sees.
5. When the user submits a form, for example "Record contribution", the data goes to another function. It checks the rules, saves the data and sends the user back to the page.

The rules about who can do what are checked in `app.py` on the server, not only in the pages. Hiding a button is not enough, because someone could send the request without using the page.

## Database

The database is SQLite, in one file called `nextpay.db`. It has six tables. PK means primary key and FK means foreign key.

| Table | Columns | What it stores |
|---|---|---|
| `users` | user_id (PK), full_name, email (unique), password_hash, role | Every account. |
| `tontine_groups` | group_id (PK), name, amount_due, frequency, start_date, admin_id (FK to users) | Each group and the admin who runs it. |
| `memberships` | group_id and user_id (together the PK, both FK), join_order, joined_at, reliability_score | Which member belongs to which group, and in what order they joined. |
| `contributions` | contribution_id (PK), group_id and user_id (FK to memberships), amount, payment_date, status | Every payment. |
| `payouts` | payout_id (PK), group_id (FK), user_id (FK), round_number, amount, payout_date | Every payout. |
| `disputes` | dispute_id (PK), group_id (FK), contribution_id (FK), raised_by (FK to users), reason, status, resolution_note, old_amount, new_amount, created_at | Every flagged record and how the admin resolved it. |

The tables are created automatically the first time the app runs.

## Known limitations

- **Testing:** there are no automated tests in this version. The app was tested by hand, following the Quick tour above.
- **The role belongs to the account, not to the group.** An admin cannot be added as a member of a group, and a member cannot create a group. In a future version, one person could be the admin of one group and a member of another.
- **Foreign keys are declared but not enforced.** SQLite does not enforce them unless it is told to, and switching them on would block removing a member who already has payments.
- **No real money moves.** NextPay only keeps the records. Payments are recorded by the admin.
- **Reminders appear only in the app** (no SMS or email), and only when a member opens their dashboard.
- **A correction made after a payout can make the pot negative.** The report shows the real difference between what was saved and what was paid out.
- **The 3-day deadline for a dispute is shown to the admin but not enforced.**
- **English only.** French and Kirundi are planned for a future version.
- **Reliability scores are calculated when the group page opens.** The `reliability_score` column in `memberships` is not used yet.

## Author

Emna Barezi, African Leadership University. Built for the Introduction to Software Engineering course.