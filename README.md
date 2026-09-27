# Stock Analysis Bot

A configurable Python stock screener and analyzer. It finds stocks that remain above their 20-day and 200-day simple moving averages (SMA), then ranks candidates using trend, momentum, volatility, volume, and available fundamental data.

> **Important:** This project is for research and education, not financial advice. Market data can be delayed, incomplete, or incorrect. Validate results independently before making investment decisions.

## Features

- Screen a list of ticker symbols or a built-in starter universe.
- Require the latest close to be above both SMA 20 and SMA 200.
- Optionally require the price to have stayed above both averages throughout a configurable lookback window.
- Calculate trend, RSI, MACD, moving-average alignment, volatility, volume ratio, and drawdown.
- Add available Yahoo Finance fundamentals such as market cap, P/E, revenue growth, and profit margin.
- Search/filter results with expressions such as `market_cap > 1000000000 and rsi between 45 and 70`.
- Export results to CSV or JSON.

## Quick start

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt

python stock_bot.py --tickers AAPL MSFT NVDA AMZN --output results.csv
python stock_bot.py --universe tickers.txt --above-days 30 --min-market-cap 1000000000
python stock_bot.py --universe tickers.txt --query "rsi >= 50 and rsi <= 70 and volume_ratio >= 1"
```

For a larger universe, put one ticker per line in `tickers.txt` (blank lines and lines beginning with `#` are ignored). Yahoo Finance is used as the data source through `yfinance`.

## Key options

- `--tickers AAPL MSFT`: analyze symbols supplied on the command line.
- `--universe tickers.txt`: analyze symbols from a file.
- `--period 2y`: historical period; at least 1 year is recommended for SMA 200.
- `--above-days 1`: require every close in the last N sessions to be above SMA 20 and SMA 200.
- `--min-market-cap 1000000000`: exclude smaller companies when market-cap data is available.
- `--query 'rsi >= 50 and pe_ratio < 35'`: apply additional filters.
- `--output results.csv`: write results to CSV; use `.json` for JSON.
- `--workers 4`: download/analyze several symbols concurrently.

## Metrics

The output includes the latest price, SMA 20/200, percentage distances from each SMA, RSI(14), MACD, annualized volatility, relative volume, 52-week drawdown, and available Yahoo Finance fundamentals. The `score` is a transparent heuristic, not a prediction.

## Data and limitations

This implementation deliberately avoids presenting a stock as "safe" or guaranteed to rise. Fundamental fields may be unavailable for some symbols, and technical indicators are calculated from historical prices. Add a licensed market-data provider, caching, retries, and rate-limit handling before using it in production.
