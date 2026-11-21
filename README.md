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