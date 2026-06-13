import sqlite3
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from datetime import datetime

DB_PATH = 'market_data.db'


def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql('SELECT timestamp, asset, close, volume FROM prices ORDER BY asset, timestamp', conn)
    conn.close()
    return df


def build_features(df):
    df = df.copy()
    df['lag_close'] = df.groupby('asset')['close'].shift(1)
    df['lag_close_2'] = df.groupby('asset')['close'].shift(2)
    df['momentum'] = df['close'] - df.groupby('asset')['close'].shift(3)
    df['ma_volume'] = (
        df.groupby('asset')['volume']
        .transform(lambda x: x.rolling(5, min_periods=1).mean())
    )
    df = df.dropna()
    return df


def train_and_predict(df):
    results = []

    for asset in df['asset'].unique():
        asset_df = df[df['asset'] == asset].copy()

        if len(asset_df) < 10:
            print(f"  {asset}: not enough rows, skipping")
            continue

        X = asset_df[['lag_close', 'lag_close_2', 'momentum', 'ma_volume']]
        y = asset_df['close']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        model = LinearRegression()
        model.fit(X_train, y_train)

        test_preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, test_preds)
        pct_err = (mae / y_test.mean()) * 100

        print(f"  {asset}: MAE={mae:.4f}  Error={pct_err:.2f}%  (rows={len(asset_df)})")

        all_preds = model.predict(X)
        for i, (idx, actual) in enumerate(zip(X.index, y)):
            results.append({
                'timestamp': asset_df.loc[idx, 'timestamp'],
                'asset': asset,
                'actual_price': round(float(actual), 6),
                'predicted_price': round(float(all_preds[i]), 6),
                'mae': round(float(mae), 6),
                'run_at': str(datetime.now()),
            })

    return results


def save_predictions(results):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS predicted_prices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT,
            asset           TEXT,
            actual_price    REAL,
            predicted_price REAL,
            mae             REAL,
            run_at          TEXT
        )
    ''')
    conn.execute('DELETE FROM predicted_prices')  # clear stale predictions before each run
    conn.executemany(
        '''INSERT INTO predicted_prices
           (timestamp, asset, actual_price, predicted_price, mae, run_at)
           VALUES (:timestamp, :asset, :actual_price, :predicted_price, :mae, :run_at)''',
        results
    )
    conn.commit()
    conn.close()
    print(f"  {len(results)} predictions saved to predicted_prices table")


if __name__ == '__main__':
    print("Loading data...")
    df = load_data()
    print(f"  {len(df)} rows loaded")

    print("Building features...")
    df = build_features(df)

    print("Training models...")
    results = train_and_predict(df)

    print("Saving predictions...")
    save_predictions(results)

    print("Done.")
