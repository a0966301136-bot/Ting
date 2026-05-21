import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "stock_data.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            stock_id   TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            market     TEXT DEFAULT 'TWSE',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id   TEXT NOT NULL,
            date       TEXT NOT NULL,
            open       REAL,
            high       REAL,
            low        REAL,
            close      REAL,
            volume     INTEGER,
            change_pct REAL,
            UNIQUE(stock_id, date),
            FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id TEXT NOT NULL,
            date     TEXT NOT NULL,
            ma5      REAL,
            ma20     REAL,
            ma60     REAL,
            rsi14    REAL,
            signal   TEXT,
            UNIQUE(stock_id, date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_news (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id TEXT NOT NULL,
            date     TEXT NOT NULL,
            title    TEXT NOT NULL,
            url      TEXT,
            source   TEXT DEFAULT '鉅亨網',
            UNIQUE(stock_id, title)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] 資料庫初始化完成")


def upsert_stock(stock_id: str, name: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO stocks (stock_id, name) VALUES (?, ?)",
        (stock_id, name),
    )
    conn.commit()
    conn.close()


def upsert_prices(df: pd.DataFrame, stock_id: str):
    conn = get_connection()
    for _, row in df.iterrows():
        conn.execute(
            """INSERT OR REPLACE INTO daily_prices
               (stock_id, date, open, high, low, close, volume, change_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                stock_id,
                row["date"],
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row["close"],
                row.get("volume"),
                row.get("change_pct"),
            ),
        )
    conn.commit()
    conn.close()


def upsert_analysis(df: pd.DataFrame, stock_id: str):
    conn = get_connection()
    for _, row in df.iterrows():
        conn.execute(
            """INSERT OR REPLACE INTO analysis_results
               (stock_id, date, ma5, ma20, ma60, rsi14, signal)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                stock_id,
                row["date"],
                row.get("ma5"),
                row.get("ma20"),
                row.get("ma60"),
                row.get("rsi14"),
                row.get("signal"),
            ),
        )
    conn.commit()
    conn.close()


def upsert_news(df: pd.DataFrame, stock_id: str):
    conn = get_connection()
    inserted = 0
    for _, row in df.iterrows():
        try:
            conn.execute(
                """INSERT OR IGNORE INTO stock_news
                   (stock_id, date, title, url, source)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    stock_id,
                    row.get("date", ""),
                    row.get("title", ""),
                    row.get("url", ""),
                    row.get("source", "鉅亨網"),
                ),
            )
            inserted += conn.execute("SELECT changes()").fetchone()[0]
        except Exception:
            continue
    conn.commit()
    conn.close()
    print(f"[DB] {stock_id} 新增 {inserted} 則新聞")


def load_prices(stock_id: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM daily_prices WHERE stock_id=? ORDER BY date",
        conn,
        params=(stock_id,),
    )
    conn.close()
    return df


def load_analysis(stock_id: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM analysis_results WHERE stock_id=? ORDER BY date",
        conn,
        params=(stock_id,),
    )
    conn.close()
    return df


def load_news(stock_id: str, days: int = 180) -> pd.DataFrame:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_connection()
    df = pd.read_sql_query(
        """SELECT date, title, url, source
           FROM stock_news
           WHERE stock_id = ? AND date >= ?
           ORDER BY date DESC""",
        conn,
        params=(stock_id, since),
    )
    conn.close()
    return df


def list_stocks() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM stocks ORDER BY stock_id", conn)
    conn.close()
    return df
