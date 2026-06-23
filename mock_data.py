# -*- coding: utf-8 -*-
"""
模拟数据生成器 - 当Yahoo Finance API不可用时使用
基于实际市场的典型价格区间和波动特性生成演示数据
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import pytz

# 基于2025-2026年实际市场范围的参考价格
REFERENCE_PRICES = {
    "gold": 3200.0,      # COMEX黄金期货 (美元/盎司)
    "usdjpy": 145.0,     # 美元/日元
    "dxy": 104.0,        # 美元指数
    "silver": 35.0,      # COMEX白银期货
    "gld": 295.0,        # SPDR黄金ETF
    "us10y": 4.30,       # 美国10年期国债收益率(%)
    "vix": 16.0,         # VIX恐慌指数
    "sp500": 5900.0,     # 标普500
}

# 各品种的日波动率(标准差百分比)
DAILY_VOLATILITY = {
    "gold": 0.012,      # 1.2% daily vol
    "usdjpy": 0.008,    # 0.8%
    "dxy": 0.005,       # 0.5%
    "silver": 0.022,    # 2.2%
    "gld": 0.011,       # 1.1%
    "us10y": 0.015,     # 1.5% (yield changes)
    "vix": 0.15,        # 15%
    "sp500": 0.010,     # 1.0%
}


def generate_mock_data(symbol_key, interval="5m", periods=288):
    """
    生成模拟K线数据
    
    参数:
        symbol_key: 标的名
        interval: 时间周期 (不使用，仅保持接口一致)
        periods: 生成的K线数量 (默认288=1天5分钟线)
    """
    if symbol_key not in REFERENCE_PRICES:
        return None

    base_price = REFERENCE_PRICES[symbol_key]
    daily_vol = DAILY_VOLATILITY[symbol_key]

    # 根据周期数调整波动率
    # 5分钟线: daily_vol / sqrt(288)
    # 1分钟线: daily_vol / sqrt(1440)
    bar_vol = daily_vol / np.sqrt(288)

    # 生成随机价格走势（几何布朗运动 + 均值回归）
    np.random.seed(hash(symbol_key) % 2**31 + int(datetime.now().timestamp() / 300))

    returns = np.random.normal(0, bar_vol, periods)

    # 加入微弱的均值回归
    returns = returns * 0.7 + np.random.normal(0, bar_vol * 0.3, periods)

    # 加入趋势（模拟近期走势）
    trend = np.linspace(0, np.random.uniform(-0.02, 0.02), periods)
    returns = returns + trend / periods

    # 计算价格序列
    prices = base_price * np.exp(np.cumsum(returns))

    # 生成OHLCV
    tz = pytz.timezone("Asia/Shanghai")
    now = datetime.now(tz)
    start = now - timedelta(minutes=5 * periods)

    data = []
    for i in range(periods):
        t = start + timedelta(minutes=5 * i)
        open_p = prices[i]
        intra_range = open_p * bar_vol * np.random.uniform(0.3, 2.0)
        high = open_p + abs(np.random.normal(0, intra_range / 2))
        low = open_p - abs(np.random.normal(0, intra_range / 2))
        close = open_p + np.random.normal(0, intra_range / 4)
        volume = int(np.random.uniform(1000, 50000))

        # 确保high>=all, low<=all
        high = max(high, open_p, close)
        low = min(low, open_p, close)

        data.append({
            "Datetime": t,
            "Open": open_p,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        })

    df = pd.DataFrame(data)
    df.set_index("Datetime", inplace=True)

    # 最后一根K线确保合理
    if len(df) > 1:
        last_close = df["Close"].iloc[-1]
        df.loc[df.index[-1], "Open"] = last_close * np.random.uniform(0.998, 1.002)
        df.loc[df.index[-1], "Close"] = last_close

    return df
