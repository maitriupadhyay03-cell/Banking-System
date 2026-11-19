# NexaBank — Banking System

A full-stack banking web app built as a DBMS project. Uses Python (Flask) for the backend, SQLite for the database, and plain HTML/CSS for the frontend.

---

## What it does

There are three types of users:

- **Customer** — can deposit money, transfer between accounts, apply for loans, and view transaction history
- **Teller** — a bank employee who handles in-person cash withdrawals and deposits for customers
- **Admin** — manages everything: approves loans, creates accounts, adds teller staff

---

## Tech Stack

- Python 3 + Flask
- SQLite
- HTML + CSS (dark theme, no frameworks)

---

## Database Features

- **5 tables** — `users`, `accounts`, `transactions`, `loans`, `branches`
- **Trigger** — automatically updates account balance after every transaction insert
- **View** — `account_summary` joins user and account data with transaction counts
- **ACID transactions** — money transfers use explicit `BEGIN` / `COMMIT` / `ROLLBACK`
- **Foreign keys and CHECK constraints**
- **Role-based access** — `role` column on users table (`customer`, `teller`, `admin`)

---

## Running locally

**1. Clone the repo**
```
git clone https://github.com/maitriupadhyay03-cell/Banking-System.git
cd Banking-System/Banking_system
```

**2. Install dependencies**
```
pip install flask werkzeug
```

**3. Run**
```
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

The database (`banking.db`) is created automatically on first run.

---

## Default login

| Role  | Email | Password |
|-------|-------|----------|
| Admin | admin@bank.com | admin123 |

Register a new customer from the login page. Teller accounts are created by the admin.

---

## Project Structure

```
Banking_system/
├── app.py              # all Flask routes and business logic
├── database.py         # DB initialization
├── schema.sql          # tables, trigger, view, seed data
├── static/
│   └── style.css
└── templates/
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── deposit.html
    ├── transfer.html
    ├── history.html
    ├── loans.html
    ├── teller.html
    └── admin.html
```
