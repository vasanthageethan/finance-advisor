"""
SQLite persistence for parsed/categorized transactions, and which Mongo
(GridFS) file ids have already been parsed into them. Replaces the Phase 1
in-memory list so data survives a backend restart. See
docs/design-sqlite-persistence.md and docs/design-mongodb-file-store.md
for the tradeoffs -- this is deliberately not DynamoDB, which is a Phase 5
decision.
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "finance.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    issuer TEXT NOT NULL,
    filename TEXT NOT NULL
);
"""

_connection: sqlite3.Connection | None = None


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
    return _connection


def _conn() -> sqlite3.Connection:
    if _connection is None:
        connect()
    return _connection


def insert_transactions(transactions: list[dict]) -> None:
    conn = _conn()
    conn.executemany(
        """INSERT INTO transactions (date, description, amount, category, category_source, confidence, account)
           VALUES (:date, :description, :amount, :category, :category_source, :confidence, :account)""",
        transactions,
    )
    conn.commit()


def fetch_all_transactions() -> list[sqlite3.Row]:
    conn = _conn()
    return conn.execute("SELECT * FROM transactions ORDER BY date").fetchall()


def count_transactions() -> int:
    conn = _conn()
    return conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()["n"]


def is_file_ingested(mongo_file_id: str) -> bool:
    conn = _conn()
    row = conn.execute("SELECT 1 FROM ingested_files WHERE mongo_file_id = ?", (mongo_file_id,)).fetchone()
    return row is not None


def mark_file_ingested(mongo_file_id: str, issuer: str, filename: str) -> None:
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO ingested_files (mongo_file_id, issuer, filename) VALUES (?, ?, ?)",
        (mongo_file_id, issuer, filename),
    )
    conn.commit()


def clear_all() -> None:
    """Test-only: wipe both tables without closing the connection."""
    conn = _conn()
    conn.execute("DELETE FROM transactions")
    conn.execute("DELETE FROM ingested_files")
    conn.commit()
