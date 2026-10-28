import os
import sqlite3
from datetime import datetime

import yfinance as yf

# Use the script's own folder so it works when Task Scheduler runs it
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'market_data.db')
ASSETS = ['BTC-USD', 'ETH-USD', 'NVDA', 'MSFT']


def setup_db(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            asset     TEXT,
            open      REAL,
            high      REAL,
            low       REAL,
            close     REAL,
            volume    REAL
        )
    ''')
    # Each run pulls the last 5 days, so the same hour shows up many times.
    # This index makes sure each asset/hour is only stored once.
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_ts_asset ON prices (timestamp, asset)')


def fetch_and_store():
    conn = sqlite3.connect(DB_PATH)
    setup_db(conn)

    added = 0
    for asset in ASSETS:
        data = yf.download(asset, period='5d', interval='1h', auto_adjust=True, progress=False)
        if data.columns.nlevels > 1:
            data.columns = data.columns.droplevel(1)
        if data.empty:
            print(f"  No data for {asset}")
            continue

        rows = [
            (str(ts), asset, float(r['Open']), float(r['High']), float(r['Low']),
             float(r['Close']), float(r['Volume']))
            for ts, r in data.iterrows()
        ]

        before = conn.total_changes
        conn.executemany(
            'INSERT OR IGNORE INTO prices (timestamp, asset, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)',
            rows
        )
        new_rows = conn.total_changes - before
        added += new_rows
        print(f"  {asset}: {new_rows} new rows ({len(rows) - new_rows} already stored)")

    conn.commit()
    total = conn.execute('SELECT COUNT(*) FROM prices').fetchone()[0]
    conn.close()
    print(f"Done at {datetime.now()}: {added} new rows, {total} rows total")


if __name__ == '__main__':
    print(f"Starting ingest at {datetime.now()}")
    fetch_and_store()