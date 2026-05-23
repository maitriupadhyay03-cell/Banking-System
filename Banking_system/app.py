import os
import random
import string
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, g, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_connection, init_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

init_db()


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = get_connection()
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ── Auth decorators ───────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def teller_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'teller':
            flash('Teller access required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


# ── Utility ───────────────────────────────────────────────────────────────────

def generate_account_number(db):
    while True:
        num = 'ACC' + ''.join(random.choices(string.digits, k=8))
        if not db.execute('SELECT id FROM accounts WHERE account_number = ?', (num,)).fetchone():
            return num


# ── Auth routes ───────────────────────────────────────────────────────────────

def role_home():
    role = session.get('role')
    if role == 'admin':
        return url_for('admin_panel')
    if role == 'teller':
        return url_for('teller_panel')
    return url_for('dashboard')


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(role_home())
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(role_home())
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        account_type = request.form.get('account_type', 'savings')

        errors = []
        if not name or not email or not password:
            errors.append('Name, email, and password are required.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('register.html')

        db = get_db()
        if db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
            flash('An account with this email already exists.', 'danger')
            return render_template('register.html')

        try:
            db.execute('BEGIN')
            result = db.execute(
                'INSERT INTO users (name, email, phone, password_hash) VALUES (?, ?, ?, ?)',
                (name, email, phone, generate_password_hash(password))
            )
            user_id = result.lastrowid
            db.execute(
                'INSERT INTO accounts (user_id, account_number, account_type, balance) VALUES (?, ?, ?, ?)',
                (user_id, generate_account_number(db), account_type, 0.0)
            )
            db.execute('COMMIT')
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception:
            db.execute('ROLLBACK')
            flash('Registration failed. Please try again.', 'danger')

    return render_template('register.html')


@app.route('/logout')
def logout():
    name = session.get('name', '')
    session.clear()
    flash(f'Goodbye, {name}! You have been logged out.', 'info')
    return redirect(url_for('login'))


# ── Customer routes ───────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    accounts = db.execute(
        'SELECT * FROM accounts WHERE user_id = ? ORDER BY created_at',
        (session['user_id'],)
    ).fetchall()
    recent_tx = db.execute(
        '''SELECT t.*, a.account_number
           FROM transactions t
           JOIN accounts a ON t.account_id = a.id
           WHERE a.user_id = ?
           ORDER BY t.created_at DESC LIMIT 10''',
        (session['user_id'],)
    ).fetchall()
    loans = db.execute(
        '''SELECT l.*, a.account_number
           FROM loans l
           JOIN accounts a ON l.account_id = a.id
           WHERE l.user_id = ?
           ORDER BY l.applied_at DESC''',
        (session['user_id'],)
    ).fetchall()
    return render_template('dashboard.html', accounts=accounts, recent_tx=recent_tx, loans=loans)


@app.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    db = get_db()
    accounts = db.execute('SELECT * FROM accounts WHERE user_id = ?', (session['user_id'],)).fetchall()
    if request.method == 'POST':
        account_id = int(request.form.get('account_id', 0))
        try:
            amount = float(request.form.get('amount', 0))
        except ValueError:
            flash('Invalid amount.', 'danger')
            return render_template('deposit.html', accounts=accounts)
        description = request.form.get('description', '').strip() or 'Deposit'

        if amount <= 0:
            flash('Amount must be greater than zero.', 'danger')
            return render_template('deposit.html', accounts=accounts)

        account = db.execute(
            'SELECT * FROM accounts WHERE id = ? AND user_id = ?',
            (account_id, session['user_id'])
        ).fetchone()
        if not account:
            flash('Invalid account.', 'danger')
            return render_template('deposit.html', accounts=accounts)

        balance_after = account['balance'] + amount
        try:
            db.execute('BEGIN')
            db.execute(
                'INSERT INTO transactions (account_id, type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)',
                (account_id, 'deposit', amount, balance_after, description)
            )
            db.execute('COMMIT')
            flash(f'Successfully deposited ₹{amount:,.2f}. New balance: ₹{balance_after:,.2f}', 'success')
            return redirect(url_for('dashboard'))
        except Exception:
            db.execute('ROLLBACK')
            flash('Deposit failed. Please try again.', 'danger')

    return render_template('deposit.html', accounts=accounts)


@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    db = get_db()
    accounts = db.execute('SELECT * FROM accounts WHERE user_id = ?', (session['user_id'],)).fetchall()
    if request.method == 'POST':
        account_id = int(request.form.get('account_id', 0))
        try:
            amount = float(request.form.get('amount', 0))
        except ValueError:
            flash('Invalid amount.', 'danger')
            return render_template('withdraw.html', accounts=accounts)
        description = request.form.get('description', '').strip() or 'Withdrawal'

        if amount <= 0:
            flash('Amount must be greater than zero.', 'danger')
            return render_template('withdraw.html', accounts=accounts)

        account = db.execute(
            'SELECT * FROM accounts WHERE id = ? AND user_id = ?',
            (account_id, session['user_id'])
        ).fetchone()
        if not account:
            flash('Invalid account.', 'danger')
            return render_template('withdraw.html', accounts=accounts)

        if account['balance'] < amount:
            flash(f'Insufficient funds. Available: ₹{account["balance"]:,.2f}', 'danger')
            return render_template('withdraw.html', accounts=accounts)

        balance_after = account['balance'] - amount
        try:
            db.execute('BEGIN')
            db.execute(
                'INSERT INTO transactions (account_id, type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)',
                (account_id, 'withdrawal', amount, balance_after, description)
            )
            db.execute('COMMIT')
            flash(f'Successfully withdrew ₹{amount:,.2f}. New balance: ₹{balance_after:,.2f}', 'success')
            return redirect(url_for('dashboard'))
        except Exception:
            db.execute('ROLLBACK')
            flash('Withdrawal failed. Please try again.', 'danger')

    return render_template('withdraw.html', accounts=accounts)


@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    db = get_db()
    accounts = db.execute('SELECT * FROM accounts WHERE user_id = ?', (session['user_id'],)).fetchall()
    if request.method == 'POST':
        from_id = int(request.form.get('from_account_id', 0))
        to_num = request.form.get('to_account_number', '').strip().upper()
        try:
            amount = float(request.form.get('amount', 0))
        except ValueError:
            flash('Invalid amount.', 'danger')
            return render_template('transfer.html', accounts=accounts)
        description = request.form.get('description', '').strip() or 'Transfer'

        if amount <= 0:
            flash('Amount must be greater than zero.', 'danger')
            return render_template('transfer.html', accounts=accounts)

        from_acc = db.execute(
            'SELECT * FROM accounts WHERE id = ? AND user_id = ?',
            (from_id, session['user_id'])
        ).fetchone()
        if not from_acc:
            flash('Invalid source account.', 'danger')
            return render_template('transfer.html', accounts=accounts)

        to_acc = db.execute(
            'SELECT * FROM accounts WHERE account_number = ?', (to_num,)
        ).fetchone()
        if not to_acc:
            flash('Destination account not found.', 'danger')
            return render_template('transfer.html', accounts=accounts)

        if from_acc['id'] == to_acc['id']:
            flash('Cannot transfer to the same account.', 'danger')
            return render_template('transfer.html', accounts=accounts)

        if from_acc['balance'] < amount:
            flash(f'Insufficient funds. Available: ₹{from_acc["balance"]:,.2f}', 'danger')
            return render_template('transfer.html', accounts=accounts)

        sender_after = from_acc['balance'] - amount
        receiver_after = to_acc['balance'] + amount
        try:
            db.execute('BEGIN')
            db.execute(
                'INSERT INTO transactions (account_id, type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)',
                (from_acc['id'], 'transfer_out', amount, sender_after,
                 f'{description} -> {to_num}')
            )
            db.execute(
                'INSERT INTO transactions (account_id, type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)',
                (to_acc['id'], 'transfer_in', amount, receiver_after,
                 f'{description} <- {from_acc["account_number"]}')
            )
            db.execute('COMMIT')
            flash(f'Successfully transferred ₹{amount:,.2f} to {to_num}.', 'success')
            return redirect(url_for('dashboard'))
        except Exception:
            db.execute('ROLLBACK')
            flash('Transfer failed. Please try again.', 'danger')

    return render_template('transfer.html', accounts=accounts)


@app.route('/history')
@login_required
def history():
    db = get_db()
    accounts = db.execute('SELECT * FROM accounts WHERE user_id = ?', (session['user_id'],)).fetchall()
    account_id = request.args.get('account_id', type=int)

    if account_id:
        owner = db.execute(
            'SELECT id FROM accounts WHERE id = ? AND user_id = ?',
            (account_id, session['user_id'])
        ).fetchone()
        if not owner:
            account_id = None

    if account_id:
        transactions = db.execute(
            '''SELECT t.*, a.account_number
               FROM transactions t JOIN accounts a ON t.account_id = a.id
               WHERE t.account_id = ? ORDER BY t.created_at DESC''',
            (account_id,)
        ).fetchall()
    else:
        ids = [a['id'] for a in accounts]
        if ids:
            placeholders = ','.join('?' * len(ids))
            transactions = db.execute(
                f'''SELECT t.*, a.account_number
                    FROM transactions t JOIN accounts a ON t.account_id = a.id
                    WHERE t.account_id IN ({placeholders})
                    ORDER BY t.created_at DESC''',
                ids
            ).fetchall()
        else:
            transactions = []

    return render_template('history.html', transactions=transactions,
                           accounts=accounts, selected_account_id=account_id)


@app.route('/loans', methods=['GET', 'POST'])
@login_required
def loans():
    db = get_db()
    accounts = db.execute('SELECT * FROM accounts WHERE user_id = ?', (session['user_id'],)).fetchall()
    user_loans = db.execute(
        '''SELECT l.*, a.account_number
           FROM loans l JOIN accounts a ON l.account_id = a.id
           WHERE l.user_id = ? ORDER BY l.applied_at DESC''',
        (session['user_id'],)
    ).fetchall()

    if request.method == 'POST':
        account_id = int(request.form.get('account_id', 0))
        try:
            amount = float(request.form.get('amount', 0))
        except ValueError:
            flash('Invalid amount.', 'danger')
            return render_template('loans.html', accounts=accounts, loans=user_loans)

        if amount < 100 or amount > 100000:
            flash('Loan amount must be between ₹100 and ₹1,00,000.', 'danger')
            return render_template('loans.html', accounts=accounts, loans=user_loans)

        account = db.execute(
            'SELECT * FROM accounts WHERE id = ? AND user_id = ?',
            (account_id, session['user_id'])
        ).fetchone()
        if not account:
            flash('Invalid account.', 'danger')
            return render_template('loans.html', accounts=accounts, loans=user_loans)

        active = db.execute(
            "SELECT id FROM loans WHERE user_id = ? AND status IN ('pending', 'approved')",
            (session['user_id'],)
        ).fetchone()
        if active:
            flash('You already have an active or pending loan application.', 'danger')
            return render_template('loans.html', accounts=accounts, loans=user_loans)

        db.execute(
            'INSERT INTO loans (user_id, account_id, amount, interest_rate) VALUES (?, ?, ?, ?)',
            (session['user_id'], account_id, amount, 8.5)
        )
        flash(f'Loan application for ₹{amount:,.2f} submitted. Awaiting admin approval.', 'success')
        return redirect(url_for('loans'))

    return render_template('loans.html', accounts=accounts, loans=user_loans)


# ── Admin routes ──────────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_panel():
    db = get_db()
    stats = {
        'total_users':        db.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0],
        'total_accounts':     db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
        'total_transactions': db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
        'pending_loans':      db.execute("SELECT COUNT(*) FROM loans WHERE status='pending'").fetchone()[0],
        'total_deposits':     db.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='deposit'").fetchone()[0],
    }
    pending_loans = db.execute(
        '''SELECT l.*, u.name, u.email, a.account_number
           FROM loans l
           JOIN users u ON l.user_id = u.id
           JOIN accounts a ON l.account_id = a.id
           WHERE l.status = 'pending'
           ORDER BY l.applied_at'''
    ).fetchall()
    all_users = db.execute(
        '''SELECT u.*, COUNT(a.id) AS account_count
           FROM users u
           LEFT JOIN accounts a ON u.id = a.user_id
           WHERE u.role = 'customer'
           GROUP BY u.id
           ORDER BY u.created_at DESC'''
    ).fetchall()
    account_summary = db.execute('SELECT * FROM account_summary ORDER BY balance DESC').fetchall()
    branches = db.execute('SELECT * FROM branches ORDER BY id').fetchall()
    return render_template('admin.html', stats=stats, pending_loans=pending_loans,
                           all_users=all_users, account_summary=account_summary,
                           branches=branches)


@app.route('/admin/approve_loan/<int:loan_id>', methods=['POST'])
@admin_required
def approve_loan(loan_id):
    db = get_db()
    loan = db.execute(
        "SELECT l.*, a.balance FROM loans l JOIN accounts a ON l.account_id = a.id WHERE l.id = ? AND l.status = 'pending'",
        (loan_id,)
    ).fetchone()
    if not loan:
        flash('Loan not found or already processed.', 'danger')
        return redirect(url_for('admin_panel'))

    due_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
    balance_after = loan['balance'] + loan['amount']
    try:
        db.execute('BEGIN')
        db.execute("UPDATE loans SET status='approved', due_date=? WHERE id=?", (due_date, loan_id))
        db.execute(
            'INSERT INTO transactions (account_id, type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)',
            (loan['account_id'], 'deposit', loan['amount'], balance_after, f'Loan #{loan_id} disbursed')
        )
        db.execute('COMMIT')
        flash(f'Loan #{loan_id} approved — ₹{loan["amount"]:,.2f} credited to account.', 'success')
    except Exception:
        db.execute('ROLLBACK')
        flash('Failed to approve loan.', 'danger')
    return redirect(url_for('admin_panel'))


@app.route('/admin/reject_loan/<int:loan_id>', methods=['POST'])
@admin_required
def reject_loan(loan_id):
    db = get_db()
    loan = db.execute("SELECT * FROM loans WHERE id=? AND status='pending'", (loan_id,)).fetchone()
    if not loan:
        flash('Loan not found or already processed.', 'danger')
        return redirect(url_for('admin_panel'))
    db.execute("UPDATE loans SET status='rejected' WHERE id=?", (loan_id,))
    flash(f'Loan #{loan_id} rejected.', 'info')
    return redirect(url_for('admin_panel'))


@app.route('/admin/create_account', methods=['POST'])
@admin_required
def create_account():
    db = get_db()
    user_id = int(request.form.get('user_id', 0))
    account_type = request.form.get('account_type', 'savings')
    try:
        initial_balance = float(request.form.get('initial_balance', 0))
    except ValueError:
        initial_balance = 0.0

    user = db.execute("SELECT * FROM users WHERE id=? AND role='customer'", (user_id,)).fetchone()
    if not user:
        flash('Customer not found.', 'danger')
        return redirect(url_for('admin_panel'))

    acc_num = generate_account_number(db)
    try:
        db.execute('BEGIN')
        result = db.execute(
            'INSERT INTO accounts (user_id, account_number, account_type, balance) VALUES (?, ?, ?, ?)',
            (user_id, acc_num, account_type, 0.0)
        )
        account_id = result.lastrowid
        if initial_balance > 0:
            db.execute(
                'INSERT INTO transactions (account_id, type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)',
                (account_id, 'deposit', initial_balance, initial_balance, 'Initial deposit')
            )
        db.execute('COMMIT')
        flash(f'Account {acc_num} created for {user["name"]}.', 'success')
    except Exception:
        db.execute('ROLLBACK')
        flash('Failed to create account.', 'danger')
    return redirect(url_for('admin_panel'))


# ── Teller routes ─────────────────────────────────────────────────────────────

@app.route('/teller')
@teller_required
def teller_panel():
    db = get_db()
    search = request.args.get('account', '').strip().upper()
    account = None
    customer = None
    if search:
        account = db.execute(
            'SELECT * FROM accounts WHERE account_number = ?', (search,)
        ).fetchone()
        if account:
            customer = db.execute(
                'SELECT * FROM users WHERE id = ?', (account['user_id'],)
            ).fetchone()
    recent = db.execute(
        '''SELECT t.*, a.account_number
           FROM transactions t JOIN accounts a ON t.account_id = a.id
           WHERE t.description LIKE ?
           ORDER BY t.created_at DESC LIMIT 20''',
        (f'%teller {session["name"]}%',)
    ).fetchall()
    return render_template('teller.html', search=search, account=account,
                           customer=customer, recent=recent)


@app.route('/teller/process', methods=['POST'])
@teller_required
def teller_process():
    db = get_db()
    account_id = int(request.form.get('account_id', 0))
    tx_type = request.form.get('type')
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('teller_panel'))
    note = request.form.get('description', '').strip()

    if tx_type not in ('deposit', 'withdrawal'):
        flash('Invalid transaction type.', 'danger')
        return redirect(url_for('teller_panel'))
    if amount <= 0:
        flash('Amount must be greater than zero.', 'danger')
        return redirect(url_for('teller_panel'))

    account = db.execute('SELECT * FROM accounts WHERE id = ?', (account_id,)).fetchone()
    if not account:
        flash('Account not found.', 'danger')
        return redirect(url_for('teller_panel'))

    if tx_type == 'withdrawal' and account['balance'] < amount:
        flash(f'Insufficient funds. Available: ₹{account["balance"]:,.2f}', 'danger')
        return redirect(url_for('teller_panel', account=account['account_number']))

    balance_after = (account['balance'] + amount) if tx_type == 'deposit' else (account['balance'] - amount)
    label = 'Cash deposit' if tx_type == 'deposit' else 'Cash withdrawal'
    description = note or f'{label} by teller {session["name"]}'

    try:
        db.execute('BEGIN')
        db.execute(
            'INSERT INTO transactions (account_id, type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)',
            (account_id, tx_type, amount, balance_after, description)
        )
        db.execute('COMMIT')
        flash(f'{label} of ₹{amount:,.2f} processed successfully.', 'success')
    except Exception:
        db.execute('ROLLBACK')
        flash('Transaction failed. Please try again.', 'danger')

    return redirect(url_for('teller_panel', account=account['account_number']))


@app.route('/admin/create_teller', methods=['POST'])
@admin_required
def create_teller():
    db = get_db()
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    if not name or not email or not password:
        flash('All fields are required to create a teller.', 'danger')
        return redirect(url_for('admin_panel'))
    if len(password) < 6:
        flash('Teller password must be at least 6 characters.', 'danger')
        return redirect(url_for('admin_panel'))
    if db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
        flash('That email is already in use.', 'danger')
        return redirect(url_for('admin_panel'))

    try:
        db.execute(
            'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
            (name, email, generate_password_hash(password), 'teller')
        )
        flash(f'Teller account created for {name}. They can now log in.', 'success')
    except Exception:
        flash('Failed to create teller account.', 'danger')
    return redirect(url_for('admin_panel'))


if __name__ == '__main__':
    app.run(debug=True)
