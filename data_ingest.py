import yfinance as yf
import sqlite3
from datetime import datetime

DB_PATH = 'market_data.db'
ASSETS = ['BTC-USD', 'ETH-USD', 'NVDA', 'MSFT']


def fetch_and_store():
    conn = sqlite3.connect(DB_PATH)
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

    fetched = 0
    for asset in ASSETS:
        data = yf.download(asset, period='5d', interval='1h', auto_adjust=True, progress=False)
        if data.columns.nlevels > 1:
            data.columns = data.columns.droplevel(1)
        if data.empty:
            print(f"  No data for {asset}")
            continue

        rows = []
        for ts, row in data.iterrows():
            rows.append((
                str(ts),
                asset,
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                float(row['Volume']),
            ))

        conn.executemany(
            'INSERT INTO prices (timestamp, asset, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)',
            rows
        )
        fetched += len(rows)
        print(f"  {asset}: {len(rows)} rows inserted")

    conn.commit()
    conn.close()
    print(f"Done at {datetime.now()} — {fetched} total rows added")


if __name__ == '__main__':
    print(f"Starting ingest at {datetime.now()}")
    fetch_and_store()
