import os
import sqlite3
from datetime import datetime

import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'market_data.db')
EXPORT_PATH = os.path.join(BASE_DIR, 'combined_prices.csv')


def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql('SELECT timestamp, asset, close, volume FROM prices ORDER BY asset, timestamp', conn)
    conn.close()
    return df


def build_features(df):
    # Every feature only uses information available BEFORE the hour being predicted.
    df = df.copy()
    g = df.groupby('asset')
    df['lag_close'] = g['close'].shift(1)
    df['lag_close_2'] = g['close'].shift(2)
    df['momentum'] = df['lag_close'] - g['close'].shift(4)  # change over the previous 3 hours
    df['ma_volume'] = g['volume'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    return df.dropna()


def train_and_evaluate(df):
    features = ['lag_close', 'lag_close_2', 'momentum', 'ma_volume']
    predictions, summary = [], []

    for asset in df['asset'].unique():
        a = df[df['asset'] == asset]
        if len(a) < 20:
            print(f"  {asset}: not enough rows ({len(a)}), skipping")
            continue

        # Time-based split: train on the first 80%, test on the most recent 20%
        split = int(len(a) * 0.8)
        train, test = a.iloc[:split], a.iloc[split:]

        model = LinearRegression().fit(train[features], train['close'])
        test_preds = model.predict(test[features])

        # Baseline: predict that the price stays the same as last hour
        naive_preds = test['lag_close']

        model_err = mean_absolute_error(test['close'], test_preds) / test['close'].mean() * 100
        naive_err = mean_absolute_error(test['close'], naive_preds) / test['close'].mean() * 100
        beats = model_err < naive_err

        print(f"  {asset}: model error {model_err:.3f}% vs. baseline {naive_err:.3f}% "
              f"({'beats' if beats else 'does not beat'} baseline, {len(test)} test hours)")

        summary.append({
            'asset': asset,
            'train_hours': len(train),
            'test_hours': len(test),
            'model_error_pct': round(model_err, 4),
            'baseline_error_pct': round(naive_err, 4),
            'beats_baseline': int(beats),
        })
        for ts, actual, pred, naive in zip(test['timestamp'], test['close'], test_preds, naive_preds):
            predictions.append({
                'timestamp': ts,
                'asset': asset,
                'actual_price': round(float(actual), 4),
                'predicted_price': round(float(pred), 4),
                'baseline_price': round(float(naive), 4),
            })

    return pd.DataFrame(predictions), pd.DataFrame(summary)


def save_results(prices, predictions, summary):
    run_at = str(datetime.now())
    predictions['run_at'] = run_at
    summary['run_at'] = run_at

    conn = sqlite3.connect(DB_PATH)
    predictions.to_sql('predicted_prices', conn, if_exists='replace', index=False)
    summary.to_sql('model_results', conn, if_exists='replace', index=False)
    conn.close()

    # This CSV feeds the Tableau dashboard: every hour's actual price, with the
    # model and baseline predictions filled in for the test period only.
    combined = prices[['timestamp', 'asset', 'close']].rename(columns={'close': 'actual_price'})
    combined = combined.merge(
        predictions[['timestamp', 'asset', 'predicted_price', 'baseline_price']],
        on=['timestamp', 'asset'], how='left'
    )
    combined.to_csv(EXPORT_PATH, index=False)

    print(f"  {len(predictions)} test-period predictions saved")
    print(f"  Model beat the baseline on {int(summary['beats_baseline'].sum())} of {len(summary)} assets")


if __name__ == '__main__':
    print("Loading data...")
    prices = load_data()
    print(f"  {len(prices)} rows loaded")

    print("Building features...")
    df = build_features(prices)

    print("Training and evaluating models...")
    predictions, summary = train_and_evaluate(df)

    print("Saving results...")
    save_results(prices, predictions, summary)

    print("Done.")