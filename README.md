# NextPay

**A digital savings tool for tontine groups in Burundi.**

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
- **Member:** joins one or more groups, sees the shared history, and can flag a record that looks wrong.

## Project status

NextPay is a working prototype built for a software engineering course at African Leadership University. It is written in Python (Flask) with a SQLite database.

## Features

### Accounts
- A person registers with a name, an email and a password, and chooses a role: **admin** or **member**.
- Passwords are never stored as plain text. They are saved as a scrambled version called a hash.
- After registering or logging in, the person lands on their dashboard. Pages that need a login send visitors to the login page.

### Groups and members
- An admin creates a group with a name, the amount each member pays, a schedule (weekly, every 2 weeks or monthly) and the date of the first contribution.
- The admin adds a member by typing the email they registered with. The person must have registered as a member first.
- Each member gets a **join order** (1, 2, 3 and so on). The join order decides who is paid first.
- The admin can remove a member. One person can belong to several groups.

### Contributions and the shared history
- Only the admin records a payment: who paid, how much and on which date.
- Every member of the group sees the same history of payments. This is what removes arguments about who paid.
- Each payment has a status: **Recorded** when it is created, **Flagged** when a member disputes it, and **Confirmed** after the admin resolves the dispute.

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
- A member who thinks a payment record is wrong can **flag** it. They must write a reason.
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

Two things follow from this design:

- **The admin is trusted inside their own group.** The admin records the payments. To keep this honest, every member can flag a record. The admin must then keep or correct it and write a note that everybody can read, and the old and new amounts are saved.
- **The role belongs to the account, not to the group.** An admin cannot be added as a member of a group, and a member cannot create a group. This is explained in the limitations at the end of this document.