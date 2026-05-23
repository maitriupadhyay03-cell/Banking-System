CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'customer' CHECK(role IN ('customer', 'admin', 'teller')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_number TEXT UNIQUE NOT NULL,
    account_type TEXT NOT NULL CHECK(account_type IN ('savings', 'current')),
    balance REAL DEFAULT 0.0 CHECK(balance >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('deposit', 'withdrawal', 'transfer_in', 'transfer_out')),
    amount REAL NOT NULL CHECK(amount > 0),
    balance_after REAL NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    interest_rate REAL NOT NULL DEFAULT 8.5,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'paid')),
    due_date DATE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    manager TEXT,
    phone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger: auto-update account balance after each transaction insert
CREATE TRIGGER IF NOT EXISTS update_balance_after_transaction
AFTER INSERT ON transactions
BEGIN
    UPDATE accounts
    SET balance = NEW.balance_after
    WHERE id = NEW.account_id;
END;

-- View: account summary joining users, accounts, and transaction counts
CREATE VIEW IF NOT EXISTS account_summary AS
SELECT
    u.id   AS user_id,
    u.name,
    u.email,
    a.id   AS account_id,
    a.account_number,
    a.account_type,
    a.balance,
    COUNT(t.id) AS transaction_count,
    a.created_at AS account_created
FROM users u
JOIN accounts a ON u.id = a.user_id
LEFT JOIN transactions t ON a.id = t.account_id
GROUP BY a.id;

INSERT OR IGNORE INTO branches (id, name, location, manager, phone) VALUES
(1, 'Main Branch',  'Downtown Financial District', 'Robert Johnson', '555-0101'),
(2, 'North Branch', 'North City Plaza',            'Sarah Williams', '555-0102'),
(3, 'East Branch',  'East Side Mall',              'Michael Chen',   '555-0103');
