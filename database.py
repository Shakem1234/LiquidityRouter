import os
import sqlite3
from datetime import datetime

# Path to SQLite database file
DB_DIR = os.path.join(os.path.dirname(__file__), 'instance')
DB_PATH = os.path.join(DB_DIR, 'liquidity_router.db')

def create_connection():
    """Create and return a database connection with foreign keys enabled."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def create_tables():
    """Create all required tables for LiquidityRouter application."""
    conn = create_connection()
    cursor = conn.cursor()

    # Table 1: users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            phone TEXT,
            role TEXT NOT NULL,
            approval_status TEXT NOT NULL DEFAULT 'Approved',
            account_status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT
        )
    ''')

    # Table 2: banks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banks (
            bank_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bank_name TEXT NOT NULL,
            country TEXT NOT NULL,
            currency TEXT NOT NULL,
            liquidity REAL NOT NULL DEFAULT 0,
            fx_spread REAL NOT NULL DEFAULT 0,
            latency INTEGER NOT NULL DEFAULT 0,
            transaction_limit REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Active',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Table 3: transactions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            source_country TEXT NOT NULL,
            destination_country TEXT NOT NULL,
            source_currency TEXT NOT NULL,
            destination_currency TEXT NOT NULL,
            selected_bank_id INTEGER,
            fx_rate REAL,
            fx_cost REAL,
            processing_fee REAL,
            total_cost REAL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (selected_bank_id) REFERENCES banks(bank_id)
        )
    ''')

    # Table 4: transaction_routes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transaction_routes (
            route_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            bank_id INTEGER NOT NULL,
            liquidity REAL,
            fx_spread REAL,
            latency INTEGER,
            score REAL,
            selected INTEGER DEFAULT 0,
            reason TEXT,
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
            FOREIGN KEY (bank_id) REFERENCES banks(bank_id)
        )
    ''')

    # Table 5: compliance_rules
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compliance_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            limit_value REAL,
            status TEXT NOT NULL DEFAULT 'Active'
        )
    ''')

    # Table 6: audit_logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER,
            event TEXT NOT NULL,
            old_bank_id INTEGER,
            new_bank_id INTEGER,
            reason TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
        )
    ''')

    conn.commit()
    conn.close()

def create_admin():
    """Create default admin user if not existing."""
    conn = create_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", ('admin@liquidity.com',))
    admin = cursor.fetchone()
    
    if not admin:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO users (name, email, password, phone, role, approval_status, account_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Admin', 'admin@liquidity.com', 'admin123', '+1234567890', 'admin', 'Approved', 'Active', now))
        conn.commit()
    
    conn.close()

def create_demo_banks():
    """Create default demo treasury user, demo bank users, demo banks, and default compliance rules."""
    conn = create_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Demo Treasury User
    cursor.execute("SELECT * FROM users WHERE email = ?", ('treasury@demo.com',))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (name, email, password, phone, role, approval_status, account_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Demo Treasury User', 'treasury@demo.com', 'treasury123', '+919876543210', 'treasury', 'Approved', 'Active', now))

    # 2. Demo Bank Users & Banks
    demo_banks_data = [
        {
            'user_email': 'banka@demo.com',
            'user_name': 'Bank A Representative',
            'password': 'bank123',
            'bank_name': 'Global Bank A',
            'country': 'India',
            'currency': 'INR',
            'liquidity': 2500000,
            'fx_spread': 0.35,
            'latency': 120,
            'transaction_limit': 1000000
        },
        {
            'user_email': 'bankb@demo.com',
            'user_name': 'Bank B Representative',
            'password': 'bank123',
            'bank_name': 'Global Bank B',
            'country': 'India',
            'currency': 'INR',
            'liquidity': 4000000,
            'fx_spread': 0.50,
            'latency': 180,
            'transaction_limit': 2000000
        },
        {
            'user_email': 'bankc@demo.com',
            'user_name': 'Bank C Representative',
            'password': 'bank123',
            'bank_name': 'Global Bank C',
            'country': 'India',
            'currency': 'INR',
            'liquidity': 1500000,
            'fx_spread': 0.30,
            'latency': 300,
            'transaction_limit': 750000
        }
    ]

    for item in demo_banks_data:
        cursor.execute("SELECT * FROM users WHERE email = ?", (item['user_email'],))
        user_row = cursor.fetchone()
        if not user_row:
            cursor.execute('''
                INSERT INTO users (name, email, password, phone, role, approval_status, account_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (item['user_name'], item['user_email'], item['password'], '+919800000000', 'bank', 'Approved', 'Active', now))
            user_id = cursor.lastrowid
        else:
            user_id = user_row['user_id']

        cursor.execute("SELECT * FROM banks WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO banks (user_id, bank_name, country, currency, liquidity, fx_spread, latency, transaction_limit, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, item['bank_name'], item['country'], item['currency'], item['liquidity'], item['fx_spread'], item['latency'], item['transaction_limit'], 'Active'))

    # 3. Default Compliance Rules
    cursor.execute("SELECT COUNT(*) as cnt FROM compliance_rules")
    if cursor.fetchone()['cnt'] == 0:
        rules = [
            ('Maximum Transaction Limit', 'MAX_AMOUNT', 5000000.0, 'Active'),
            ('LRS Single Transfer Limit', 'LRS_LIMIT', 2500000.0, 'Active'),
            ('Restricted Corridor Check', 'RESTRICTED_CORRIDOR', 0.0, 'Active')
        ]
        for r_name, r_type, r_limit, r_status in rules:
            cursor.execute('''
                INSERT INTO compliance_rules (rule_name, rule_type, limit_value, status)
                VALUES (?, ?, ?, ?)
            ''', (r_name, r_type, r_limit, r_status))

    conn.commit()
    conn.close()

# --- USER OPERATIONS ---

def get_user_by_email(email):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(name, email, password, phone, role, approval_status='Approved', account_status='Active'):
    conn = create_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO users (name, email, password, phone, role, approval_status, account_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, email, password, phone, role, approval_status, account_status, now))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id

def get_all_users():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = cursor.fetchall()
    conn.close()
    return users

def activate_user(user_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET account_status = 'Active' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def deactivate_user(user_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET account_status = 'Inactive' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# --- BANK OPERATIONS ---

def get_all_banks():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT b.*, u.name as owner_name, u.email as owner_email, u.approval_status, u.account_status as user_account_status
        FROM banks b
        JOIN users u ON b.user_id = u.user_id
        ORDER BY b.bank_id ASC
    ''')
    banks = cursor.fetchall()
    conn.close()
    return banks

def get_bank_by_id(bank_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT b.*, u.name as owner_name, u.email as owner_email, u.approval_status, u.account_status as user_account_status
        FROM banks b
        JOIN users u ON b.user_id = u.user_id
        WHERE b.bank_id = ?
    ''', (bank_id,))
    bank = cursor.fetchone()
    conn.close()
    return bank

def get_bank_by_user_id(user_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM banks WHERE user_id = ?", (user_id,))
    bank = cursor.fetchone()
    conn.close()
    return bank

def create_bank(user_id, bank_name, country, currency, liquidity=0, fx_spread=0, latency=0, transaction_limit=0, status='Active'):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO banks (user_id, bank_name, country, currency, liquidity, fx_spread, latency, transaction_limit, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, bank_name, country, currency, liquidity, fx_spread, latency, transaction_limit, status))
    bank_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return bank_id

def update_bank(bank_id, liquidity, fx_spread, latency, transaction_limit, status):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE banks 
        SET liquidity = ?, fx_spread = ?, latency = ?, transaction_limit = ?, status = ?
        WHERE bank_id = ?
    ''', (liquidity, fx_spread, latency, transaction_limit, status, bank_id))
    conn.commit()
    conn.close()

def approve_bank(user_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET approval_status = 'Approved' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def reject_bank(user_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET approval_status = 'Rejected' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def activate_bank(bank_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE banks SET status = 'Active' WHERE bank_id = ?", (bank_id,))
    conn.commit()
    conn.close()

def deactivate_bank(bank_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE banks SET status = 'Inactive' WHERE bank_id = ?", (bank_id,))
    conn.commit()
    conn.close()

# --- TRANSACTION OPERATIONS ---

def create_transaction(user_id, amount, source_country, destination_country, source_currency, destination_currency, selected_bank_id=None, fx_rate=None, fx_cost=None, processing_fee=None, total_cost=None, status='Pending'):
    conn = create_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO transactions 
        (user_id, amount, source_country, destination_country, source_currency, destination_currency, selected_bank_id, fx_rate, fx_cost, processing_fee, total_cost, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, source_country, destination_country, source_currency, destination_currency, selected_bank_id, fx_rate, fx_cost, processing_fee, total_cost, status, now))
    tx_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return tx_id

def update_transaction_status(transaction_id, status, selected_bank_id=None, fx_rate=None, fx_cost=None, processing_fee=None, total_cost=None):
    conn = create_connection()
    cursor = conn.cursor()
    if selected_bank_id is not None:
        cursor.execute('''
            UPDATE transactions 
            SET status = ?, selected_bank_id = ?, fx_rate = ?, fx_cost = ?, processing_fee = ?, total_cost = ?
            WHERE transaction_id = ?
        ''', (status, selected_bank_id, fx_rate, fx_cost, processing_fee, total_cost, transaction_id))
    else:
        cursor.execute("UPDATE transactions SET status = ? WHERE transaction_id = ?", (status, transaction_id))
    conn.commit()
    conn.close()

def get_transaction_by_id(transaction_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, u.name as treasury_name, u.email as treasury_email, b.bank_name
        FROM transactions t
        JOIN users u ON t.user_id = u.user_id
        LEFT JOIN banks b ON t.selected_bank_id = b.bank_id
        WHERE t.transaction_id = ?
    ''', (transaction_id,))
    tx = cursor.fetchone()
    conn.close()
    return tx

def get_user_transactions(user_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, b.bank_name
        FROM transactions t
        LEFT JOIN banks b ON t.selected_bank_id = b.bank_id
        WHERE t.user_id = ?
        ORDER BY t.transaction_id DESC
    ''', (user_id,))
    txs = cursor.fetchall()
    conn.close()
    return txs

def get_bank_transactions(bank_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, u.name as treasury_name, u.email as treasury_email
        FROM transactions t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.selected_bank_id = ?
        ORDER BY t.transaction_id DESC
    ''', (bank_id,))
    txs = cursor.fetchall()
    conn.close()
    return txs

def get_all_transactions():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, u.name as treasury_name, b.bank_name
        FROM transactions t
        JOIN users u ON t.user_id = u.user_id
        LEFT JOIN banks b ON t.selected_bank_id = b.bank_id
        ORDER BY t.transaction_id DESC
    ''')
    txs = cursor.fetchall()
    conn.close()
    return txs

# --- ROUTE EVALUATIONS ---

def save_transaction_route(transaction_id, bank_id, liquidity, fx_spread, latency, score, selected, reason):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transaction_routes (transaction_id, bank_id, liquidity, fx_spread, latency, score, selected, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (transaction_id, bank_id, liquidity, fx_spread, latency, score, selected, reason))
    conn.commit()
    conn.close()

def get_transaction_routes(transaction_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT tr.*, b.bank_name, b.country, b.currency
        FROM transaction_routes tr
        JOIN banks b ON tr.bank_id = b.bank_id
        WHERE tr.transaction_id = ?
        ORDER BY tr.score DESC
    ''', (transaction_id,))
    routes = cursor.fetchall()
    conn.close()
    return routes

# --- COMPLIANCE RULES ---

def get_compliance_rules():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM compliance_rules ORDER BY rule_id ASC")
    rules = cursor.fetchall()
    conn.close()
    return rules

def add_compliance_rule(rule_name, rule_type, limit_value, status='Active'):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO compliance_rules (rule_name, rule_type, limit_value, status)
        VALUES (?, ?, ?, ?)
    ''', (rule_name, rule_type, limit_value, status))
    conn.commit()
    conn.close()

def update_compliance_rule(rule_id, rule_name, rule_type, limit_value, status):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE compliance_rules
        SET rule_name = ?, rule_type = ?, limit_value = ?, status = ?
        WHERE rule_id = ?
    ''', (rule_name, rule_type, limit_value, status, rule_id))
    conn.commit()
    conn.close()

def activate_compliance_rule(rule_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE compliance_rules SET status = 'Active' WHERE rule_id = ?", (rule_id,))
    conn.commit()
    conn.close()

def deactivate_compliance_rule(rule_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE compliance_rules SET status = 'Inactive' WHERE rule_id = ?", (rule_id,))
    conn.commit()
    conn.close()

# --- AUDIT LOGS ---

def add_audit_log(transaction_id, event, old_bank_id=None, new_bank_id=None, reason=''):
    conn = create_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO audit_logs (transaction_id, event, old_bank_id, new_bank_id, reason, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (transaction_id, event, old_bank_id, new_bank_id, reason, now))
    conn.commit()
    conn.close()

def get_audit_logs():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT al.*, b1.bank_name as old_bank_name, b2.bank_name as new_bank_name
        FROM audit_logs al
        LEFT JOIN banks b1 ON al.old_bank_id = b1.bank_id
        LEFT JOIN banks b2 ON al.new_bank_id = b2.bank_id
        ORDER BY al.log_id DESC
    ''')
    logs = cursor.fetchall()
    conn.close()
    return logs
