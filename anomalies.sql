-- Hourly price moves of 2% or more, plus what happened the next hour.
-- LAG gets the previous hour's close, LEAD gets the next hour's close.
-- None of the four assets moved 5% in an hour in the collected data,
-- so the threshold is set at 2%.

DROP VIEW IF EXISTS market_anomalies;

CREATE VIEW market_anomalies AS
WITH moves AS (
    SELECT
        timestamp,
        asset,
        close,
        LAG(close)  OVER (PARTITION BY asset ORDER BY timestamp) AS prev_close,
        LEAD(close) OVER (PARTITION BY asset ORDER BY timestamp) AS next_close
    FROM prices
)
SELECT
    timestamp,
    asset,
    ROUND(prev_close, 2) AS prev_close,
    ROUND(close, 2)      AS close,
    ROUND((close - prev_close) / prev_close * 100, 2) AS pct_change,
    ROUND((next_close - close) / close * 100, 2)      AS next_hour_pct_change
FROM moves
WHERE prev_close IS NOT NULL
  AND ABS((close - prev_close) / prev_close) >= 0.02;


-- All flagged moves, biggest first
SELECT * FROM market_anomalies ORDER BY ABS(pct_change) DESC;


-- How often big moves keep going vs. reverse the next hour
SELECT
    asset,
    COUNT(*) AS big_moves,
    SUM(CASE WHEN pct_change * next_hour_pct_change > 0 THEN 1 ELSE 0 END) AS continued,
    SUM(CASE WHEN pct_change * next_hour_pct_change < 0 THEN 1 ELSE 0 END) AS reversed
FROM market_anomalies
WHERE next_hour_pct_change IS NOT NULL
GROUP BY asset;


-- Volatility by asset: average and largest absolute hourly move
WITH moves AS (
    SELECT
        asset,
        (close - LAG(close) OVER (PARTITION BY asset ORDER BY timestamp))
            / LAG(close) OVER (PARTITION BY asset ORDER BY timestamp) * 100 AS pct_change
    FROM prices
)
SELECT
    asset,
    COUNT(pct_change)              AS hours,
    ROUND(AVG(ABS(pct_change)), 3) AS avg_abs_move_pct,
    ROUND(MAX(ABS(pct_change)), 2) AS max_abs_move_pct
FROM moves
GROUP BY asset
ORDER BY avg_abs_move_pct DESC;
