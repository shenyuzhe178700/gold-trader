# -*- coding: utf-8 -*-
'''
技术指标计算模块
包含：RSI, MACD, 布林带, 随机指标, 移动均线, ATR, 支撑阻力位等
'''

import numpy as np
import pandas as pd
from scipy import stats

def calc_rsi(df, period=14):
    '''计算RSI'''
    close = df['Close'].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_macd(df, fast=12, slow=26, signal=9):
    '''计算MACD'''
    close = df['Close'].astype(float)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_bollinger_bands(df, period=20, std_dev=2):
    '''计算布林带'''
    close = df['Close'].astype(float)
    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    bandwidth = (upper - lower) / sma * 100
    return upper, sma, lower, bandwidth

def calc_stochastic(df, k_period=14, d_period=3):
    '''计算随机指标KD'''
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    close = df['Close'].astype(float)

    low_min = low.rolling(window=k_period).min()
    high_max = high.rolling(window=k_period).max()

    k = ((close - low_min) / (high_max - low_min).replace(0, np.nan)) * 100
    d = k.rolling(window=d_period).mean()
    return k, d

def calc_atr(df, period=14):
    '''计算平均真实波幅ATR'''
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    close = df['Close'].astype(float)

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr

def calc_moving_averages(df):
    '''计算多周期均线'''
    close = df['Close'].astype(float)
    return {
        'ma5': close.rolling(5).mean(),
        'ma10': close.rolling(10).mean(),
        'ma20': close.rolling(20).mean(),
        'ma60': close.rolling(60).mean(),
        'ma120': close.rolling(min(120, len(df))).mean(),
    }

def calc_volume_analysis(df):
    '''成交量分析'''
    volume = df['Volume'].astype(float)
    close = df['Close'].astype(float)

    vol_sma = volume.rolling(20).mean()
    vol_ratio = volume / vol_sma.replace(0, np.nan)

    # 量价配合分析
    price_up = close.diff() > 0
    volume_up = volume.diff() > 0
    vol_price_confirm = (price_up == volume_up).rolling(10).mean()

    return {
        'vol_ratio': vol_ratio,
        'vol_price_confirm': vol_price_confirm,
        'avg_volume': vol_sma,
    }

def find_support_resistance(df, window=20):
    '''寻找支撑阻力位（基于局部极值）'''
    close = df['Close'].astype(float).values
    high = df['High'].astype(float).values
    low = df['Low'].astype(float).values

    supports = []
    resistances = []

    # 使用滚动窗口找局部极值
    for i in range(window, len(df) - window):
        local_high = high[i]
        local_low = low[i]
        is_resistance = True
        is_support = True

        for j in range(i - window, i + window + 1):
            if j == i:
                continue
            if high[j] >= local_high:
                is_resistance = False
            if low[j] <= local_low:
                is_support = False

        if is_resistance:
            resistances.append(float(close[i]))
        if is_support:
            supports.append(float(close[i]))

    # 聚类相近的水平
    supports = _cluster_levels(supports)
    resistances = _cluster_levels(resistances)

    current_price = float(close[-1])

    # 只保留最近的支撑和阻力
    near_supports = sorted([s for s in supports if s < current_price], reverse=True)[:3]
    near_resistances = sorted([r for r in resistances if r > current_price])[:3]

    return {
        'supports': [round(float(s), 2) for s in near_supports],
        'resistances': [round(float(r), 2) for r in near_resistances],
        'current_price': round(float(current_price), 2),
    }

def _cluster_levels(levels, threshold_pct=0.003):
    '''聚类相近价格水平'''
    if not levels:
        return []
    levels = sorted(set(levels))
    clusters = []
    current_cluster = [levels[0]]

    for level in levels[1:]:
        if level / current_cluster[-1] - 1 < threshold_pct:
            current_cluster.append(level)
        else:
            clusters.append(np.mean(current_cluster))
            current_cluster = [level]
    clusters.append(np.mean(current_cluster))
    return clusters

def calc_momentum(df, period=10):
    '''计算动量指标'''
    close = df['Close'].astype(float)
    momentum = close - close.shift(period)
    momentum_pct = (close / close.shift(period) - 1) * 100
    return momentum, momentum_pct

def calc_short_term_indicators(df):
    '''计算所有短线交易相关指标，返回最新值'''
    if df is None or len(df) < 30:
        return None

    # RSI
    rsi = calc_rsi(df)
    rsi_current = round(float(rsi.iloc[-1]), 2)

    # MACD
    macd_line, signal_line, histogram = calc_macd(df)
    macd_val = round(float(macd_line.iloc[-1]), 4)
    signal_val = round(float(signal_line.iloc[-1]), 4)
    hist_val = round(float(histogram.iloc[-1]), 4)
    hist_prev = round(float(histogram.iloc[-2]), 4) if len(histogram) > 1 else 0

    # 布林带
    bb_upper, bb_mid, bb_lower, bb_width = calc_bollinger_bands(df)
    bb_u = round(float(bb_upper.iloc[-1]), 2)
    bb_m = round(float(bb_mid.iloc[-1]), 2)
    bb_l = round(float(bb_lower.iloc[-1]), 2)
    bb_w = round(float(bb_width.iloc[-1]), 2)

    # 随机指标
    stoch_k, stoch_d = calc_stochastic(df)
    k_val = round(float(stoch_k.iloc[-1]), 2)
    d_val = round(float(stoch_d.iloc[-1]), 2)

    # ATR
    atr = calc_atr(df)
    atr_val = round(float(atr.iloc[-1]), 2)

    # 均线
    mas = calc_moving_averages(df)
    ma5 = round(float(mas['ma5'].iloc[-1]), 2)
    ma10 = round(float(mas['ma10'].iloc[-1]), 2)
    ma20 = round(float(mas['ma20'].iloc[-1]), 2)

    # 动量
    momentum, momentum_pct = calc_momentum(df)
    mom_val = round(float(momentum_pct.iloc[-1]), 2)

    # 成交量
    vol_analysis = calc_volume_analysis(df)
    vol_ratio = round(float(vol_analysis['vol_ratio'].iloc[-1]), 2)

    # 支撑阻力
    sr_levels = find_support_resistance(df)

    # 当前价格
    current = round(float(df['Close'].iloc[-1]), 2)
    prev_close = round(float(df['Close'].iloc[-2]), 2)

    # 布林带位置
    bb_position = (current - bb_l) / (bb_u - bb_l) * 100 if bb_u != bb_l else 50

    return {
        'price': {
            'current': current,
            'prev_close': prev_close,
            'change': round(current - prev_close, 2),
            'change_pct': round((current / prev_close - 1) * 100, 2),
            'high': round(float(df['High'].iloc[-1]), 2),
            'low': round(float(df['Low'].iloc[-1]), 2),
            'volume': int(df['Volume'].iloc[-1]),
        },
        'rsi': {
            'value': rsi_current,
            'zone': 'overbought' if rsi_current > 70 else ('oversold' if rsi_current < 30 else 'neutral'),
        },
        'macd': {
            'macd': macd_val,
            'signal': signal_val,
            'histogram': hist_val,
            'trend': 'bullish' if hist_val > 0 else 'bearish',
            'turning': 'up' if hist_val > hist_prev else 'down',
        },
        'bollinger': {
            'upper': bb_u,
            'middle': bb_m,
            'lower': bb_l,
            'width': bb_w,
            'position': round(bb_position, 1),
        },
        'stochastic': {
            'k': k_val,
            'd': d_val,
            'zone': 'overbought' if k_val > 80 else ('oversold' if k_val < 20 else 'neutral'),
        },
        'atr': atr_val,
        'ma': {
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'alignment': 'bullish' if ma5 > ma10 > ma20 else ('bearish' if ma5 < ma10 < ma20 else 'mixed'),
        },
        'momentum': mom_val,
        'volume_ratio': vol_ratio,
        'support_resistance': sr_levels,
    }
