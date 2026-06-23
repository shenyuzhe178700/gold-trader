# -*- coding: utf-8 -*-
'''
交易信号生成引擎
综合多维度数据，生成短线交易信号（做多/做空 + 置信度）
'''

import numpy as np

def generate_signals(gold_indicators, market_snapshot):
    '''
    生成综合交易信号

    信号权重分配：
    - 技术指标信号: 60%
    - 多数据源关联: 40%

    返回: 做多/做空信号 + 置信度(0-100)
    '''
    if gold_indicators is None:
        return {
            'signal': 'neutral',
            'confidence': 0,
            'direction': 'wait',
            'signals_detail': [],
            'summary': '数据不足，无法生成信号',
        }

    signals_detail = []

    # === 1. 技术指标信号 (60%权重) ===
    tech_signals = _analyze_technical(gold_indicators)
    signals_detail.extend(tech_signals)

    tech_bullish = sum(1 for s in tech_signals if s['signal'] == 'bullish')
    tech_bearish = sum(1 for s in tech_signals if s['signal'] == 'bearish')
    tech_total = max(len(tech_signals), 1)
    tech_score = (tech_bullish - tech_bearish) / tech_total * 60

    # === 2. 多数据源关联信号 (40%权重) ===
    multi_signals = _analyze_multi_source(market_snapshot, gold_indicators)
    signals_detail.extend(multi_signals)

    multi_bullish = sum(1 for s in multi_signals if s['signal'] == 'bullish')
    multi_bearish = sum(1 for s in multi_signals if s['signal'] == 'bearish')
    multi_total = max(len(multi_signals), 1)
    multi_score = (multi_bullish - multi_bearish) / multi_total * 40

    # === 3. 综合评分 ===
    total_score = tech_score + multi_score

    # 转换为置信度 (0-100)
    confidence = min(abs(total_score) * 1.2, 95)
    confidence = round(confidence, 1)

    # 判断方向
    if total_score > 15:
        direction = 'long'
        signal = 'buy'
    elif total_score < -15:
        direction = 'short'
        signal = 'sell'
    elif total_score > 5:
        direction = 'long'
        signal = 'weak_buy'
    elif total_score < -5:
        direction = 'short'
        signal = 'weak_sell'
    else:
        direction = 'wait'
        signal = 'neutral'

    # 生成摘要
    summary = _generate_summary(signal, confidence, signals_detail, gold_indicators)

    return {
        'signal': signal,
        'confidence': confidence,
        'direction': direction,
        'score': round(total_score, 1),
        'tech_score': round(tech_score, 1),
        'multi_score': round(multi_score, 1),
        'signals_detail': signals_detail,
        'summary': summary,
    }


def _analyze_technical(ind):
    '''技术指标信号分析'''
    signals = []

    # RSI信号
    rsi = ind['rsi']['value']
    if rsi < 30:
        signals.append({'source': 'RSI', 'signal': 'bullish',
                       'detail': f'RSI={rsi}，超卖区域，反弹概率高', 'weight': 'high'})
    elif rsi > 70:
        signals.append({'source': 'RSI', 'signal': 'bearish',
                       'detail': f'RSI={rsi}，超买区域，回调概率高', 'weight': 'high'})
    elif rsi < 40:
        signals.append({'source': 'RSI', 'signal': 'bullish',
                       'detail': f'RSI={rsi}，偏弱区域，关注反弹', 'weight': 'medium'})
    elif rsi > 60:
        signals.append({'source': 'RSI', 'signal': 'bearish',
                       'detail': f'RSI={rsi}，偏强区域，关注回落', 'weight': 'medium'})
    else:
        signals.append({'source': 'RSI', 'signal': 'neutral',
                       'detail': f'RSI={rsi}，中性区域', 'weight': 'low'})

    # MACD信号
    macd = ind['macd']
    if macd['trend'] == 'bullish' and macd['turning'] == 'up':
        signals.append({'source': 'MACD', 'signal': 'bullish',
                       'detail': 'MACD金叉放量，多头动能增强', 'weight': 'high'})
    elif macd['trend'] == 'bearish' and macd['turning'] == 'down':
        signals.append({'source': 'MACD', 'signal': 'bearish',
                       'detail': 'MACD死叉放量，空头动能增强', 'weight': 'high'})
    elif macd['trend'] == 'bullish':
        signals.append({'source': 'MACD', 'signal': 'bullish',
                       'detail': 'MACD处于零轴上方，多头趋势', 'weight': 'medium'})
    elif macd['trend'] == 'bearish':
        signals.append({'source': 'MACD', 'signal': 'bearish',
                       'detail': 'MACD处于零轴下方，空头趋势', 'weight': 'medium'})

    # 布林带信号
    bb_pos = ind['bollinger']['position']
    if bb_pos > 90:
        signals.append({'source': 'Bollinger', 'signal': 'bearish',
                       'detail': f'价格触及布林上轨(位置{bb_pos}%)，超买', 'weight': 'medium'})
    elif bb_pos < 10:
        signals.append({'source': 'Bollinger', 'signal': 'bullish',
                       'detail': f'价格触及布林下轨(位置{bb_pos}%)，超卖', 'weight': 'medium'})
    else:
        signals.append({'source': 'Bollinger', 'signal': 'neutral',
                       'detail': f'价格在布林带中轨附近(位置{bb_pos}%)', 'weight': 'low'})

    # 随机指标
    sto = ind['stochastic']
    if sto['k'] < 20 and sto['k'] > sto['d']:
        signals.append({'source': 'Stochastic', 'signal': 'bullish',
                       'detail': f'K={sto["k"]}，超卖区金叉', 'weight': 'medium'})
    elif sto['k'] > 80 and sto['k'] < sto['d']:
        signals.append({'source': 'Stochastic', 'signal': 'bearish',
                       'detail': f'K={sto["k"]}，超买区死叉', 'weight': 'medium'})
    elif sto['k'] < 20:
        signals.append({'source': 'Stochastic', 'signal': 'bullish',
                       'detail': f'K={sto["k"]}，超卖区域', 'weight': 'low'})
    elif sto['k'] > 80:
        signals.append({'source': 'Stochastic', 'signal': 'bearish',
                       'detail': f'K={sto["k"]}，超买区域', 'weight': 'low'})

    # 均线排列
    ma = ind['ma']
    if ma['alignment'] == 'bullish':
        signals.append({'source': 'MA排列', 'signal': 'bullish',
                       'detail': 'MA5>MA10>MA20，多头排列', 'weight': 'medium'})
    elif ma['alignment'] == 'bearish':
        signals.append({'source': 'MA排列', 'signal': 'bearish',
                       'detail': 'MA5<MA10<MA20，空头排列', 'weight': 'medium'})
    else:
        signals.append({'source': 'MA排列', 'signal': 'neutral',
                       'detail': '均线交织，方向不明', 'weight': 'low'})

    # 动量
    mom = ind['momentum']
    if mom > 1:
        signals.append({'source': '动量', 'signal': 'bullish',
                       'detail': f'动量={mom}%，上升动能较强', 'weight': 'low'})
    elif mom < -1:
        signals.append({'source': '动量', 'signal': 'bearish',
                       'detail': f'动量={mom}%，下跌动能较强', 'weight': 'low'})

    # 成交量
    vol_ratio = ind['volume_ratio']
    change_pct = ind['price']['change_pct']
    if vol_ratio > 1.5 and change_pct > 0:
        signals.append({'source': '成交量', 'signal': 'bullish',
                       'detail': f'放量上涨(量比{vol_ratio})，多头强势', 'weight': 'medium'})
    elif vol_ratio > 1.5 and change_pct < 0:
        signals.append({'source': '成交量', 'signal': 'bearish',
                       'detail': f'放量下跌(量比{vol_ratio})，空头强势', 'weight': 'medium'})

    return signals


def _analyze_multi_source(snapshot, gold_ind):
    '''多数据源关联分析'''
    signals = []

    if snapshot is None:
        return signals

    gold = snapshot.get('gold', {})
    usdjpy = snapshot.get('usdjpy', {})
    dxy = snapshot.get('dxy', {})
    dollar_trend = snapshot.get('dollar_trend', {})
    capital_flow = snapshot.get('capital_flow', {})
    vix = snapshot.get('vix', {})
    us10y = snapshot.get('us10y', {})

    # === 美元日元与黄金关系 ===
    # 美元日元走高通常美元走强，利空黄金
    if usdjpy and isinstance(usdjpy, dict) and 'change_pct' in usdjpy:
        usdjpy_change = usdjpy.get('change_pct', 0)
        if usdjpy_change > 0.1:
            signals.append({
                'source': 'USD/JPY',
                'signal': 'bearish',
                'detail': f'USD/JPY上涨{usdjpy_change}%，美元走强，利空黄金',
                'weight': 'medium'
            })
        elif usdjpy_change < -0.1:
            signals.append({
                'source': 'USD/JPY',
                'signal': 'bullish',
                'detail': f'USD/JPY下跌{abs(usdjpy_change)}%，美元走弱，利多黄金',
                'weight': 'medium'
            })

    # === 美元指数趋势 ===
    if dollar_trend and isinstance(dollar_trend, dict):
        if dollar_trend.get('trend') == 'bullish':
            signals.append({
                'source': '美元指数',
                'signal': 'bearish',
                'detail': '美元指数处于上升趋势，压制金价',
                'weight': 'high'
            })
        elif dollar_trend.get('trend') == 'bearish':
            signals.append({
                'source': '美元指数',
                'signal': 'bullish',
                'detail': '美元指数处于下降趋势，支撑金价',
                'weight': 'high'
            })

    # === SPDR黄金ETF资金流向 ===
    if capital_flow and isinstance(capital_flow, dict):
        flow = capital_flow.get('flow', 'neutral')
        ratio = capital_flow.get('ratio', 0.5)
        if flow == 'bullish':
            signals.append({
                'source': '资金流向',
                'signal': 'bullish',
                'detail': f'SPDR黄金ETF资金持续流入(比率{ratio})，大资金看多',
                'weight': 'high'
            })
        elif flow == 'bearish':
            signals.append({
                'source': '资金流向',
                'signal': 'bearish',
                'detail': f'SPDR黄金ETF资金持续流出(比率{ratio})，大资金看空',
                'weight': 'high'
            })

    # === VIX恐慌指数 ===
    if vix and isinstance(vix, dict) and 'price' in vix:
        vix_price = vix.get('price', 20)
        if vix_price > 25:
            signals.append({
                'source': 'VIX',
                'signal': 'bullish',
                'detail': f'VIX={vix_price}，恐慌情绪升温，避险利好黄金',
                'weight': 'medium'
            })
        elif vix_price < 15:
            signals.append({
                'source': 'VIX',
                'signal': 'bearish',
                'detail': f'VIX={vix_price}，市场风险偏好高，黄金吸引力下降',
                'weight': 'low'
            })

    # === 美债收益率 ===
    if us10y and isinstance(us10y, dict) and 'change_pct' in us10y:
        y10y_change = us10y.get('change_pct', 0)
        if y10y_change > 1:
            signals.append({
                'source': '美债10Y',
                'signal': 'bearish',
                'detail': f'美债收益率上升{y10y_change}%，持有黄金机会成本增加',
                'weight': 'medium'
            })
        elif y10y_change < -1:
            signals.append({
                'source': '美债10Y',
                'signal': 'bullish',
                'detail': f'美债收益率下降{abs(y10y_change)}%，利好黄金',
                'weight': 'medium'
            })

    # === 金银比 ===
    silver = snapshot.get('silver', {})
    if gold and silver and isinstance(gold, dict) and isinstance(silver, dict):
        gold_price = gold.get('price')
        silver_price = silver.get('price')
        if gold_price and silver_price and silver_price > 0:
            gold_silver_ratio = gold_price / silver_price
            if gold_silver_ratio > 90:
                signals.append({
                    'source': '金银比',
                    'signal': 'bearish',
                    'detail': f'金银比={gold_silver_ratio:.1f}，处于高位，金价可能承压',
                    'weight': 'low'
                })
            elif gold_silver_ratio < 75:
                signals.append({
                    'source': '金银比',
                    'signal': 'bullish',
                    'detail': f'金银比={gold_silver_ratio:.1f}，处于低位，金价有支撑',
                    'weight': 'low'
                })

    return signals


def _generate_summary(signal, confidence, signals_detail, indicators):
    '''生成交易建议摘要'''
    price = indicators['price']
    rsi = indicators['rsi']
    macd = indicators['macd']

    # 关键支撑阻力位
    sr = indicators.get('support_resistance', {})
    supports = sr.get('supports', [])
    resistances = sr.get('resistances', [])

    parts = []

    # 价格概述
    parts.append(f"COMEX黄金现报 ，变动 {price['change_pct']:+.2f}%")

    # 信号概述
    signal_map = {
        'buy': '【做多信号】',
        'sell': '【做空信号】',
        'weak_buy': '【偏多信号】',
        'weak_sell': '【偏空信号】',
        'neutral': '【观望】',
    }
    parts.append(f"信号: {signal_map.get(signal, '观望')}（置信度 {confidence}%）")

    # 关键指标
    parts.append(f"RSI={rsi['value']}({rsi['zone']}), MACD={macd['trend']}")

    # 支撑阻力
    if supports:
        parts.append(f"支撑位: {', '.join([str(s) for s in supports])}")
    if resistances:
        parts.append(f"阻力位: {', '.join([str(r) for r in resistances])}")

    # 关键信号汇总
    key_signals = [s for s in signals_detail if s.get('weight') in ('high', 'medium') and s['signal'] != 'neutral']
    if key_signals:
        key_descriptions = [s['detail'] for s in key_signals[:3]]
        parts.append(' | '.join(key_descriptions))

    return '\n'.join(parts)
