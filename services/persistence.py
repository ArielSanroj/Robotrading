import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "cache" / "trading_history.sqlite"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_type TEXT,
            started_at TEXT,
            total_trades INTEGER,
            money_spent REAL,
            money_earned REAL,
            net_profit REAL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            symbol TEXT,
            action TEXT,
            quantity REAL,
            price REAL,
            value REAL,
            created_at TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
        """
    )
    conn.commit()
    conn.close()


def save_session(session: Dict[str, Any]) -> int:
    conn = _connect()
    cur = conn.cursor()
    total_trades = int(session.get("total_trades", 0))
    money_spent = float(session.get("money_spent", 0.0))
    money_earned = float(session.get("money_earned", 0.0))
    net = money_earned - money_spent
    cur.execute(
        """
        INSERT INTO sessions(session_type, started_at, total_trades, money_spent, money_earned, net_profit)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            session.get("session_type", ""),
            (session.get("session_start_time") or datetime.utcnow()).isoformat(),
            total_trades,
            money_spent,
            money_earned,
            net,
        ),
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def save_trade(session_id: int, symbol: str, action: str, quantity: float, price: float, value: float):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO trades(session_id, symbol, action, quantity, price, value, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, symbol, action, quantity, price, value, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def list_trades(session_id: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    if session_id:
        cur.execute("SELECT id, symbol, action, quantity, price, value, created_at FROM trades WHERE session_id=? ORDER BY id", (session_id,))
    else:
        cur.execute("SELECT id, symbol, action, quantity, price, value, created_at FROM trades ORDER BY id DESC LIMIT 100")
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "symbol": r[1],
            "action": r[2],
            "quantity": r[3],
            "price": r[4],
            "value": r[5],
            "created_at": r[6],
        }
        for r in rows
    ]
