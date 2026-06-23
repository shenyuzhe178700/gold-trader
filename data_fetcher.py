# -*- coding: utf-8 -*-
"""
实时数据采集模块 v3 - 多数据源 + 直连Yahoo原生API
"""

import json
import time
import logging
import threading
import urllib.request
import urllib.error
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SYMBOLS = {
    "gold": "GC=F",
    "usdjpy": "USDJPY=X",
    "dxy": "DX-Y.NYB",
    "gld": "GLD",
    "us10y": "^TNX",
    "silver": "SI=F",
    "vix": "^VIX",
    "sp500": "^GSPC",
}

# 缓存
_cache = {}
_cache_time = {}
_cache_lock = threading.Lock()
CACHE_TTL = {"1m": 30, "5m": 60, "15m": 120, "1h": 300, "1d": 600}

# 数据源追踪
_data_source = "unknown"
_last_request = 0
REQUEST_GAP = 1.5  # 请求间隔(秒)


def _wait_gap():
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < REQUEST_GAP:
        time.sleep(REQUEST_GAP - elapsed)
    _last_request = time.time()


def _fetch_yahoo_direct(symbol_key, interval="5m", period_days=1):
    """
    直接调用Yahoo Finance v8 Chart API
    绕过yfinance库的session管理，避免限流
    """
    yahoo_symbol = SYMBOLS.get(symbol_key)
    if not yahoo_symbol:
        return None

    # 映射interval到Yahoo参数
    interval_map = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "30m": "30m", "1h": "1h", "1d": "1d"
    }
    yf_interval = interval_map.get(interval, "5m")

    # 映射period到range
    if period_days == "1d":
        yf_range = "1d"
    elif period_days == "5d":
        yf_range = "5d"
    elif period_days == "1mo":
        yf_range = "1mo"
    elif period_days == "3mo":
        yf_range = "3mo"
    else:
        yf_range = "1d"

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        f"?range={yf_range}&interval={yf_interval}&includePrePost=false"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    for attempt in range(2):
        try:
            _wait_gap()
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            result = data.get("chart", {}).get("result", [])
            if not result:
                if attempt < 1:
                    time.sleep(2)
                continue

            r = result[0]
            timestamps = r.get("timestamp", [])
            quotes = r.get("indicators", {}).get("quote", [{}])[0]

            if not timestamps or not quotes:
                continue

            opens = quotes.get("open", [])
            highs = quotes.get("high", [])
            lows = quotes.get("low", [])
            closes = quotes.get("close", [])
            volumes = quotes.get("volume", [])

            # 构建DataFrame
            rows = []
            for i, ts in enumerate(timestamps):
                if closes[i] is not None:
                    rows.append({
                        "Datetime": pd.Timestamp(ts, unit="s", tz="UTC"),
                        "Open": opens[i] if opens[i] is not None else closes[i],
                        "High": highs[i] if highs[i] is not None else closes[i],
                        "Low": lows[i] if lows[i] is not None else closes[i],
                        "Close": closes[i],
                        "Volume": int(volumes[i]) if volumes[i] is not None else 0,
                    })

            if not rows:
                continue

            df = pd.DataFrame(rows)
            df.set_index("Datetime", inplace=True)
            df = df.dropna()

            if len(df) > 2:
                logger.info("Yahoo direct: %s -> %d rows", symbol_key, len(df))
                global _data_source
                _data_source = "live"
                return df

        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning("Yahoo 429 rate limit, waiting...")
                time.sleep(5 * (attempt + 1))
            else:
                logger.warning("Yahoo HTTP %d for %s", e.code, symbol_key)
                if attempt < 1:
                    time.sleep(2)
        except Exception as e:
            logger.warning("Yahoo direct error for %s: %s", symbol_key, str(e)[:80])
            if attempt < 1:
                time.sleep(1.5)

    return None


def _fetch_yfinance_fallback(symbol_key, interval="5m", period_days="1d"):
    """yfinance兜底"""
    try:
        import yfinance as yf
        _wait_gap()
        ticker = yf.Ticker(SYMBOLS[symbol_key])
        df = ticker.history(interval=interval, period=period_days)
        if df is not None and not df.empty and len(df) > 3:
            logger.info("yfinance fallback: %s -> %d rows", symbol_key, len(df))
            global _data_source
            _data_source = "live"
            return df.dropna()
    except Exception as e:
        logger.warning("yfinance fallback error: %s", str(e)[:80])
    return None


def fetch_data(symbol_key, interval="1m", period="1d", force_refresh=False):
    """
    获取数据 - 多源策略:
    1. Yahoo直连API
    2. yfinance兜底
    3. 模拟数据(最后手段)
    """
    if symbol_key not in SYMBOLS:
        return None

    cache_key = f"{symbol_key}_{interval}_{period}"
    if not force_refresh:
        with _cache_lock:
            if cache_key in _cache:
                ttl = CACHE_TTL.get(interval, 60)
                if time.time() - _cache_time.get(cache_key, 0) < ttl:
                    return _cache[cache_key]

    df = None

    # 策略1: Yahoo直连
    logger.info("Fetching %s (interval=%s)...", symbol_key, interval)
    df = _fetch_yahoo_direct(symbol_key, interval=interval, period_days=period)

    # 策略2: yfinance兜底
    if df is None:
        df = _fetch_yfinance_fallback(symbol_key, interval=interval, period_days=period)

    # 策略3: 模拟数据
    if df is None:
        from mock_data import generate_mock_data
        periods_map = {"1m": 390, "5m": 288, "15m": 96, "30m": 48, "1h": 24, "1d": 60}
        n = periods_map.get(interval, 288)
        df = generate_mock_data(symbol_key, interval=interval, periods=n)
        logger.info("%s: mock fallback (%d rows)", symbol_key, len(df))

    if df is not None:
        with _cache_lock:
            _cache[cache_key] = df
            _cache_time[cache_key] = time.time()

    return df


def get_latest_price(symbol_key):
    """获取最新价格"""
    df = fetch_data(symbol_key, interval="1m", period="1d")
    if df is not None and len(df) >= 2:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        return {
            "price": round(float(last["Close"]), 2),
            "open": round(float(last["Open"]), 2),
            "high": round(float(last["High"]), 2),
            "low": round(float(last["Low"]), 2),
            "volume": int(last["Volume"]),
            "change": round(float(last["Close"] - prev["Close"]), 2),
            "change_pct": round(float((last["Close"] - prev["Close"]) / prev["Close"] * 100), 2),
            "timestamp": str(df.index[-1]),
            "name": symbol_key, "symbol": SYMBOLS[symbol_key],
        }
    elif df is not None and len(df) == 1:
        last = df.iloc[-1]
        return {
            "price": round(float(last["Close"]), 2),
            "open": round(float(last["Open"]), 2),
            "high": round(float(last["High"]), 2),
            "low": round(float(last["Low"]), 2),
            "volume": int(last["Volume"]),
            "change": 0, "change_pct": 0,
            "timestamp": str(df.index[-1]),
            "name": symbol_key, "symbol": SYMBOLS[symbol_key],
        }
    return None


def get_capital_flow_estimate(gld_df):
    if gld_df is None or gld_df.empty:
        return None
    recent = gld_df.tail(20)
    up_v = recent[recent["Close"] > recent["Open"]]["Volume"].sum()
    down_v = recent[recent["Close"] < recent["Open"]]["Volume"].sum()
    total = up_v + down_v
    if total == 0:
        return {"flow": "neutral", "ratio": 0.5, "net_flow": 0}
    ratio = up_v / total
    flow = "bullish" if ratio > 0.6 else ("bearish" if ratio < 0.4 else "neutral")
    return {"flow": flow, "ratio": round(ratio, 3),
            "net_flow": int(up_v - down_v),
            "up_volume": int(up_v), "down_volume": int(down_v)}


def get_dollar_trend(dxy_df):
    if dxy_df is None or dxy_df.empty:
        return None
    cur = float(dxy_df["Close"].iloc[-1])
    sma20 = float(dxy_df["Close"].tail(20).mean())
    sma50 = float(dxy_df["Close"].tail(min(50, len(dxy_df))).mean())
    trend = "bullish" if cur > sma20 > sma50 else ("bearish" if cur < sma20 < sma50 else "neutral")
    return {"price": round(cur, 2), "sma_20": round(sma20, 2),
            "sma_50": round(sma50, 2), "trend": trend}


def get_market_snapshot():
    """获取市场快照"""
    tz = pytz.timezone("Asia/Shanghai")
    snapshot = {
        "timestamp": datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": _data_source,
    }

    # 核心标的
    for key in ["gold", "usdjpy", "dxy", "silver", "gld"]:
        snapshot[key] = get_latest_price(key)

    # 次要标的
    for key in ["vix", "us10y", "sp500"]:
        snapshot[key] = get_latest_price(key)

    # 资金流
    gld_data = fetch_data("gld", interval="15m", period="5d")
    snapshot["capital_flow"] = get_capital_flow_estimate(gld_data)

    # 美元趋势
    dxy_data = fetch_data("dxy", interval="1d", period="3mo")
    snapshot["dollar_trend"] = get_dollar_trend(dxy_data)

    return snapshot


def check_live_availability():
    """检测Yahoo直连API是否可用"""
    global _data_source
    logger.info("Checking Yahoo direct API...")
    df = _fetch_yahoo_direct("gold", interval="5m", period_days="1d")
    if df is not None and len(df) > 3:
        _data_source = "live"
        logger.info("LIVE DATA available via Yahoo direct API!")
        return True
    logger.info("Yahoo direct API unavailable")
    return False
