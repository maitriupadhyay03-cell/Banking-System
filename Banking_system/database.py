import os
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'banking.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')


def get_connection():
    """Return a new autocommit-mode connection (caller manages BEGIN/COMMIT)."""
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables/triggers/views and seed the default admin account."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    existing = conn.execute(
        'SELECT id FROM users WHERE email = ?', ('admin@bank.com',)
    ).fetchone()
    if not existing:
        conn.execute(
            'INSERT INTO users (name, email, phone, password_hash, role) VALUES (?, ?, ?, ?, ?)',
            ('Bank Admin', 'admin@bank.com', '555-0000',
             generate_password_hash('admin123'), 'admin')
        )
        conn.commit()
    conn.close()
