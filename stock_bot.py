"""Configurable stock screener focused on price remaining above SMA 20 and SMA 200."""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False).mean()
    losses = -delta.clip(upper=0).ewm(alpha=1 / length, adjust=False).mean()
    rs = gains / losses.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def analyze(ticker: str, period: str, above_days: int) -> dict[str, Any] | None:
    ticker = ticker.strip().upper()
    try:
        prices = yf.download(ticker, period=period, auto_adjust=True, progress=False, threads=False)
        if prices.empty:
            return None
        if isinstance(prices.columns, pd.MultiIndex):
            prices.columns = prices.columns.get_level_values(0)
        required = {"Close", "Volume"}
        if not required.issubset(prices.columns):
            return None
        close = prices["Close"].dropna()
        volume = prices["Volume"].reindex(close.index).fillna(0)
        if len(close) < 210:
            return None
        sma20 = close.rolling(20).mean()
        sma200 = close.rolling(200).mean()
        eligible = (close > sma20) & (close > sma200)
        if not bool(eligible.iloc[-1]) or not bool(eligible.tail(above_days).all()):
            return None

        ema12, ema26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        high_52 = close.tail(252).max()
        avg_volume = volume.tail(50).mean()
        info: dict[str, Any] = {}
        try:
            raw = yf.Ticker(ticker).info
            for key in ("marketCap", "trailingPE", "forwardPE", "profitMargins", "revenueGrowth", "beta", "sector", "longName"):
                info[key] = raw.get(key)
        except Exception:
            pass

        values = {
            "ticker": ticker,
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "price": float(close.iloc[-1]),
            "sma20": float(sma20.iloc[-1]),
            "sma200": float(sma200.iloc[-1]),
            "above_days": int(eligible.tail(above_days).sum()),
            "distance_sma20_pct": float((close.iloc[-1] / sma20.iloc[-1] - 1) * 100),
            "distance_sma200_pct": float((close.iloc[-1] / sma200.iloc[-1] - 1) * 100),
            "rsi": float(rsi(close).iloc[-1]),
            "macd": float(macd.iloc[-1]),
            "macd_signal": float(signal.iloc[-1]),
            "volatility_pct": float(close.pct_change().tail(60).std() * np.sqrt(252) * 100),
            "volume_ratio": float(volume.iloc[-1] / avg_volume) if avg_volume else None,
            "drawdown_52w_pct": float((close.iloc[-1] / high_52 - 1) * 100),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "profit_margin": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "beta": info.get("beta"),
        }
        # A simple, inspectable ranking heuristic; it is not a return forecast.
        values["score"] = round(
            min(values["distance_sma200_pct"], 20) * 1.5
            + min(values["distance_sma20_pct"], 10)
            + (5 if values["macd"] > values["macd_signal"] else 0)
            + (5 if 45 <= values["rsi"] <= 70 else 0)
            + (3 if (values["volume_ratio"] or 0) >= 1 else 0), 2
        )
        return values
    except Exception as exc:
        print(f"Skipping {ticker}: {exc}")
        return None


def query_filter(frame: pd.DataFrame, expression: str) -> pd.DataFrame:
    """Support simple AND filters: field op number, including `between`."""
    if not expression:
        return frame
    result = frame.copy()
    for clause in re.split(r"\s+and\s+", expression, flags=re.I):
        match = re.fullmatch(r"\s*([A-Za-z_][\w]*)\s*(>=|<=|==|!=|>|<|between)\s*(-?[\d.]+)(?:\s+and\s+(-?[\d.]+))?\s*", clause, re.I)
        if not match or match.group(1) not in result.columns:
            raise ValueError(f"Unsupported filter: {clause}")
        field, op, first, second = match.group(1), match.group(2).lower(), float(match.group(3)), match.group(4)
        series = pd.to_numeric(result[field], errors="coerce")
        if op == "between":
            if second is None:
                raise ValueError(f"between requires two numbers: {clause}")
            mask = series.between(first, float(second))
        else:
            mask = {">": series > first, ">=": series >= first, "<": series < first, "<=": series <= first, "==": series == first, "!=": series != first}[op]
        result = result[mask.fillna(False)]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Screen stocks above SMA 20 and SMA 200")
    parser.add_argument("--tickers", nargs="+", help="Ticker symbols")
    parser.add_argument("--universe", default="tickers.txt", help="File containing one ticker per line")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--above-days", type=int, default=1)
    parser.add_argument("--min-market-cap", type=float)
    parser.add_argument("--query", default="")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.tickers:
        symbols = args.tickers
    else:
        symbols = [x.strip() for x in Path(args.universe).read_text().splitlines() if x.strip() and not x.startswith("#")]
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(analyze, symbol, args.period, args.above_days) for symbol in symbols]
        for future in as_completed(futures):
            row = future.result()
            if row:
                rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        print("No symbols matched the SMA requirements.")
        return
    if args.min_market_cap:
        frame = frame[frame.market_cap.fillna(0) >= args.min_market_cap]
    frame = query_filter(frame, args.query).sort_values("score", ascending=False)
    frame.to_csv(args.output, index=False) if args.output and args.output.endswith(".csv") else None
    if args.output and args.output.endswith(".json"):
        Path(args.output).write_text(json.dumps(frame.where(frame.notna(), None).to_dict(orient="records"), indent=2, default=str))
    print(frame.to_string(index=False))
    print(f"\nMatched {len(frame)} of {len(symbols)} symbols.")


if __name__ == "__main__":
    main()
