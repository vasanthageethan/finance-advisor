"""
SQLite persistence for customers, parsed/categorized transactions, and
which Mongo (GridFS) file ids have already been parsed into them.
Replaces the Phase 1 in-memory list so data survives a backend restart.
See docs/design-sqlite-persistence.md, docs/design-mongodb-file-store.md,
and docs/design-auth-and-customers.md for the tradeoffs -- this is
deliberately not DynamoDB, which is a Phase 5 decision.
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "finance.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT,
    category_source TEXT,
    confidence REAL,
    account TEXT
);

CREATE TABLE IF NOT EXISTS ingested_files (
    mongo_file_id TEXT PRIMARY KEY,
    customer_id TEXT,
    issuer TEXT NOT NULL,
    filename TEXT NOT NULL
);

-- A historical daily rate never changes after the fact, so entries here
-- never expire -- see docs/design-fx-conversion.md.
CREATE TABLE IF NOT EXISTS fx_rates (
    date TEXT NOT NULL,
    base TEXT NOT NULL,
    target TEXT NOT NULL,
    rate REAL NOT NULL,
    PRIMARY KEY (date, base, target)
);
"""

# Columns added after the tables above already shipped -- SQLite can't add
# a NOT NULL column with no default to a populated table in one step, so
# these are added nullable, then backfilled once a customer exists
# (main.py's startup does the backfill; see migrate_customer_id_column).
_MIGRATIONS = [
    ("transactions", "customer_id", "TEXT"),
    ("ingested_files", "customer_id", "TEXT"),
]

_connection: sqlite3.Connection | None = None


def _run_migrations(conn: sqlite3.Connection) -> None:
    for table, column, col_type in _MIGRATIONS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    conn.commit()


def connect(path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    (Re)connect to the given SQLite file, creating tables if needed. Tests
    pass a throwaway path for full isolation from real data; call this
    again to point the module at a different file (or ":memory:").
    """
    global _connection
    if isinstance(path, Path):
        path.parent.mkdir(parents=True, exist_ok=True)
    _connection = sqlite3.connect(path, check_same_thread=False)
    _connection.row_factory = sqlite3.Row
    _connection.executescript(SCHEMA)
    _run_migrations(_connection)
    return _connection


def _conn() -> sqlite3.Connection:
    if _connection is None:
        connect()
    return _connection


# --- customers ---------------------------------------------------------


def create_customer(customer_id: str, name: str, email: str, created_at: str) -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO customers (customer_id, name, email, created_at) VALUES (?, ?, ?, ?)",
        (customer_id, name, email, created_at),
    )
    conn.commit()


def get_customer_by_email(email: str) -> sqlite3.Row | None:
    conn = _conn()
    return conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()


def get_customer_by_customer_id(customer_id: str) -> sqlite3.Row | None:
    conn = _conn()
    return conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()


def get_any_customer() -> sqlite3.Row | None:
    """This app has exactly one customer today -- used for the startup
    seed check and for backfilling pre-auth data (see
    migrate_customer_id_column)."""
    conn = _conn()
    return conn.execute("SELECT * FROM customers LIMIT 1").fetchone()


def set_customer_password(customer_id: str, password_hash: str) -> None:
    conn = _conn()
    conn.execute("UPDATE customers SET password_hash = ? WHERE customer_id = ?", (password_hash, customer_id))
    conn.commit()


def migrate_customer_id_column(customer_id: str) -> None:
    """Backfill any pre-auth rows (customer_id IS NULL) to the given
    customer. Idempotent -- a no-op once nothing is left unassigned."""
    conn = _conn()
    conn.execute("UPDATE transactions SET customer_id = ? WHERE customer_id IS NULL", (customer_id,))
    conn.execute("UPDATE ingested_files SET customer_id = ? WHERE customer_id IS NULL", (customer_id,))
    conn.commit()


# --- transactions --------------------------------------------------------


def insert_transactions(customer_id: str, transactions: list[dict]) -> None:
    conn = _conn()
    conn.executemany(
        """INSERT INTO transactions (customer_id, date, description, amount, category, category_source, confidence, account)
           VALUES (:customer_id, :date, :description, :amount, :category, :category_source, :confidence, :account)""",
        [{**t, "customer_id": customer_id} for t in transactions],
    )
    conn.commit()


def fetch_all_transactions(customer_id: str) -> list[sqlite3.Row]:
    conn = _conn()
    return conn.execute(
        "SELECT * FROM transactions WHERE customer_id = ? ORDER BY date", (customer_id,)
    ).fetchall()


def count_transactions(customer_id: str) -> int:
    conn = _conn()
    return conn.execute(
        "SELECT COUNT(*) AS n FROM transactions WHERE customer_id = ?", (customer_id,)
    ).fetchone()["n"]


def fetch_transactions_by_source(customer_id: str, category_source: str) -> list[sqlite3.Row]:
    conn = _conn()
    return conn.execute(
        "SELECT * FROM transactions WHERE customer_id = ? AND category_source = ?", (customer_id, category_source)
    ).fetchall()


def update_transaction_category(txn_id: int, category: str, category_source: str, confidence: float) -> None:
    conn = _conn()
    conn.execute(
        "UPDATE transactions SET category = ?, category_source = ?, confidence = ? WHERE id = ?",
        (category, category_source, confidence, txn_id),
    )
    conn.commit()


# --- ingested files --------------------------------------------------------


def is_file_ingested(mongo_file_id: str) -> bool:
    conn = _conn()
    row = conn.execute("SELECT 1 FROM ingested_files WHERE mongo_file_id = ?", (mongo_file_id,)).fetchone()
    return row is not None


def mark_file_ingested(customer_id: str, mongo_file_id: str, issuer: str, filename: str) -> None:
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO ingested_files (mongo_file_id, customer_id, issuer, filename) VALUES (?, ?, ?, ?)",
        (mongo_file_id, customer_id, issuer, filename),
    )
    conn.commit()


def clear_all() -> None:
    """Test-only: wipe every table without closing the connection."""
    conn = _conn()
    conn.execute("DELETE FROM transactions")
    conn.execute("DELETE FROM ingested_files")
    conn.execute("DELETE FROM customers")
    conn.execute("DELETE FROM fx_rates")
    conn.commit()


# --- fx rate cache --------------------------------------------------------


def get_cached_fx_rate(date: str, base: str, target: str) -> float | None:
    conn = _conn()
    row = conn.execute(
        "SELECT rate FROM fx_rates WHERE date = ? AND base = ? AND target = ?", (date, base, target)
    ).fetchone()
    return row["rate"] if row else None


def cache_fx_rate(date: str, base: str, target: str, rate: float) -> None:
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO fx_rates (date, base, target, rate) VALUES (?, ?, ?, ?)", (date, base, target, rate)
    )
    conn.commit()
