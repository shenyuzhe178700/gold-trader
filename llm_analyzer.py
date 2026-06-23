# -*- coding: utf-8 -*-
"""
LLM量化分析模块 - DeepSeek大模型驱动
将多维市场数据 + 技术指标输入大模型，输出深度分析报告
"""

import json
import os
import logging
import time
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# DeepSeek API配置
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"  # 或 deepseek-reasoner（推理增强版）

# 缓存LLM分析结果（避免频繁调用）
_llm_cache = {}
_llm_cache_time = {}
_llm_cache_ttl = 120  # 2分钟缓存


def _call_deepseek(prompt, system_prompt=None, temperature=0.3, max_tokens=2000):
    """调用DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        logger.warning("DeepSeek API key not configured")
        return None

    try:
        import urllib.request
        import urllib.error

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            },
        )

        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            logger.info("DeepSeek API call successful (%d tokens)", 
                       result.get("usage", {}).get("total_tokens", 0))
            return content

    except urllib.error.HTTPError as e:
        logger.error("DeepSeek HTTP %d: %s", e.code, e.read().decode("utf-8", errors="replace")[:300])
        return None
    except Exception as e:
        logger.error("DeepSeek call failed: %s", e)
        return None


def build_analysis_prompt(market_snapshot, indicators, rule_signals):
    """
    构建给DeepSeek的结构化分析提示词
    
    将所有量化数据格式化为清晰的结构化prompt，
    让大模型基于完整数据做深度推理
    """
    parts = []
    parts.append("=" * 60)
    parts.append("【任务】你是专业黄金期货短线交易分析师。请基于以下实时量化数据，")
    parts.append("做深度分析并给出1小时内的交易建议。")
    parts.append("=" * 60)
    
    # 1. 核心价格数据
    parts.append("")
    parts.append("## 一、COMEX黄金期货实时行情")
    gold = market_snapshot.get("gold", {}) if market_snapshot else {}
    if gold:
        parts.append(f"- 最新价: ${gold.get('price', 'N/A')}")
        parts.append(f"- 涨跌: {gold.get('change_pct', 0):+.2f}%")
        parts.append(f"- 最高: ${gold.get('high', 'N/A')} 最低: ${gold.get('low', 'N/A')}")
        parts.append(f"- 开盘: ${gold.get('open', 'N/A')} 成交量: {gold.get('volume', 0)}")
    
    # 2. 技术指标
    parts.append("")
    parts.append("## 二、技术指标面板")
    if indicators:
        rsi = indicators.get("rsi", {})
        parts.append(f"- RSI(14): {rsi.get('value', 'N/A')} ({rsi.get('zone', 'N/A')})")
        
        macd = indicators.get("macd", {})
        parts.append(f"- MACD: 快线={macd.get('macd', 'N/A')}, 信号线={macd.get('signal', 'N/A')}, "
                     f"柱={macd.get('histogram', 'N/A')}, 趋势={macd.get('trend', 'N/A')}, "
                     f"方向={macd.get('turning', 'N/A')}")
        
        bb = indicators.get("bollinger", {})
        parts.append(f"- 布林带: 上轨=${bb.get('upper', 'N/A')}, 中轨=${bb.get('middle', 'N/A')}, "
                     f"下轨=${bb.get('lower', 'N/A')}, 价格位置={bb.get('position', 'N/A')}%")
        
        sto = indicators.get("stochastic", {})
        parts.append(f"- 随机KD: K={sto.get('k', 'N/A')}, D={sto.get('d', 'N/A')} "
                     f"({sto.get('zone', 'N/A')})")
        
        parts.append(f"- ATR: {indicators.get('atr', 'N/A')}")
        
        ma = indicators.get("ma", {})
        parts.append(f"- 均线: MA5=${ma.get('ma5', 'N/A')}, MA10=${ma.get('ma10', 'N/A')}, "
                     f"MA20=${ma.get('ma20', 'N/A')}, 排列={ma.get('alignment', 'N/A')}")
        
        parts.append(f"- 10期动量: {indicators.get('momentum', 'N/A')}%")
        parts.append(f"- 量比: {indicators.get('volume_ratio', 'N/A')}")
        
        sr = indicators.get("support_resistance", {})
        parts.append(f"- 支撑位: {sr.get('supports', [])}")
        parts.append(f"- 阻力位: {sr.get('resistances', [])}")
    
    # 3. 关联市场
    parts.append("")
    parts.append("## 三、关联市场数据")
    if market_snapshot:
        for key, name in [("usdjpy", "美元/日元"), ("dxy", "美元指数"), 
                          ("silver", "白银期货"), ("us10y", "美债10Y收益率"),
                          ("vix", "VIX恐慌指数"), ("sp500", "标普500")]:
            item = market_snapshot.get(key, {})
            if item and item.get("price"):
                parts.append(f"- {name}: {item.get('price', 'N/A')} "
                           f"({item.get('change_pct', 0):+.2f}%)")
        
        cf = market_snapshot.get("capital_flow", {})
        if cf:
            parts.append(f"- 资金流向(SPDR GLD): {cf.get('flow', 'N/A')} "
                       f"(多空比={cf.get('ratio', 0):.2f})")
        
        dt = market_snapshot.get("dollar_trend", {})
        if dt:
            parts.append(f"- 美元趋势: {dt.get('trend', 'N/A')} "
                       f"(当前={dt.get('price', 'N/A')}, "
                       f"SMA20={dt.get('sma_20', 'N/A')}, "
                       f"SMA50={dt.get('sma_50', 'N/A')})")
    
    # 4. 规则引擎信号
    parts.append("")
    parts.append("## 四、量化规则引擎信号")
    if rule_signals:
        parts.append(f"- 当前信号: {rule_signals.get('signal', 'N/A')}")
        parts.append(f"- 方向: {rule_signals.get('direction', 'N/A')}")
        parts.append(f"- 置信度: {rule_signals.get('confidence', 'N/A')}%")
        parts.append(f"- 综合得分: {rule_signals.get('score', 'N/A')}")
    
    # 5. 分析要求
    parts.append("")
    parts.append("## 五、请输出JSON格式分析结果（仅JSON，不要其他文字）")
    parts.append("{")
    parts.append('  "direction": "long/short/wait",')
    parts.append('  "confidence": 0-100,')
    parts.append('  "reasoning": "2-3句话的核心理由",')
    parts.append('  "key_factors_bullish": ["利多因素1", "利多因素2"],')
    parts.append('  "key_factors_bearish": ["利空因素1", "利空因素2"],')
    parts.append('  "suggested_entry": "建议入场价格区间或条件",')
    parts.append('  "stop_loss": "建议止损位",')
    parts.append('  "take_profit": "建议止盈位",')
    parts.append('  "risk_level": "low/medium/high",')
    parts.append('  "time_horizon": "30min/60min/2hour",')
    parts.append('  "special_notes": "特别提醒"')
    parts.append("}")

    return "\n".join(parts)


SYSTEM_PROMPT = """你是世界顶级的COMEX黄金期货短线交易分析师，拥有20年实盘经验。
你擅长结合技术指标、跨市场关联、资金流向做1小时内短线判断。
分析原则：
1. 数据驱动，不要主观臆断
2. 多指标共振时置信度高，信号矛盾时降低置信度
3. 注意美元指数与黄金的负相关性
4. RSI>70超买偏向回调做空，RSI<30超卖偏向反弹做多
5. 布林带收窄预示突破，放宽预示趋势延续
6. VIX>25避险利好黄金，VIX<15风险偏好压制黄金
7. 严格输出JSON，不要输出任何其他文字"""


def parse_llm_response(response_text):
    """解析DeepSeek返回的JSON分析结果"""
    if not response_text:
        return None
    
    # 尝试提取JSON
    text = response_text.strip()
    
    # 处理markdown代码块包裹
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    
    # 找最外层大括号
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        text = text[brace_start:brace_end + 1]
    
    try:
        result = json.loads(text)
        # 验证必要字段
        required = ["direction", "confidence", "reasoning"]
        for field in required:
            if field not in result:
                logger.warning("LLM response missing field: %s", field)
                result[field] = "unknown" if field == "direction" else (0 if field == "confidence" else "")
        
        return result
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM JSON: %s", e)
        logger.debug("Raw response: %s", response_text[:500])
        return {
            "direction": "wait",
            "confidence": 0,
            "reasoning": "LLM分析结果解析失败，请查看原始响应",
            "raw_response": response_text[:500],
            "parse_error": True,
        }


def get_llm_analysis(market_snapshot, indicators, rule_signals, force_refresh=False):
    """
    获取LLM增强分析
    
    参数:
        market_snapshot: 市场快照
        indicators: 技术指标
        rule_signals: 规则引擎信号
        force_refresh: 是否强制刷新
    
    返回: LLM分析结果字典
    """
    # 检查缓存
    cache_key = "llm_analysis"
    if not force_refresh:
        if cache_key in _llm_cache:
            elapsed = time.time() - _llm_cache_time.get(cache_key, 0)
            if elapsed < _llm_cache_ttl:
                logger.info("Using cached LLM analysis (%.0fs old)", elapsed)
                return _llm_cache[cache_key]
    
    # 检查API Key
    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY not set, skipping LLM analysis")
        return {
            "direction": "wait",
            "confidence": 0,
            "reasoning": "未配置DeepSeek API Key，无法进行AI分析。请设置环境变量 DEEPSEEK_API_KEY",
            "available": False,
        }
    
    # 构建Prompt
    prompt = build_analysis_prompt(market_snapshot, indicators, rule_signals)
    
    logger.info("Calling DeepSeek API for analysis...")
    t0 = time.time()
    response = _call_deepseek(prompt, SYSTEM_PROMPT, temperature=0.3, max_tokens=2000)
    elapsed = time.time() - t0
    
    if response is None:
        return {
            "direction": "wait",
            "confidence": 0,
            "reasoning": "DeepSeek API调用失败，请检查网络和API Key",
            "available": False,
        }
    
    # 解析
    result = parse_llm_response(response)
    if result:
        result["available"] = True
        result["latency_ms"] = int(elapsed * 1000)
        result["model"] = DEEPSEEK_MODEL
        logger.info("LLM analysis: direction=%s, confidence=%.0f%%, latency=%.1fs",
                   result.get("direction"), result.get("confidence", 0), elapsed)
    
    # 缓存
    _llm_cache[cache_key] = result
    _llm_cache_time[cache_key] = time.time()
    
    return result


def get_combined_signal(market_snapshot, indicators, rule_signals):
    """
    融合规则引擎+LLM分析的最终信号
    
    权重: 规则引擎40% + LLM 60%
    """
    llm = get_llm_analysis(market_snapshot, indicators, rule_signals)
    
    if not llm or not llm.get("available"):
        # LLM不可用时完全依赖规则引擎
        return {
            **rule_signals,
            "llm_analysis": llm,
            "fusion": "rule_only",
        }
    
    # 融合信号
    rule_dir = rule_signals.get("direction", "wait")
    llm_dir = llm.get("direction", "wait")
    rule_conf = rule_signals.get("confidence", 0)
    llm_conf = llm.get("confidence", 0)
    
    # 方向映射到数值
    dir_map = {"long": 1, "short": -1, "wait": 0}
    rule_val = dir_map.get(rule_dir, 0)
    llm_val = dir_map.get(llm_dir, 0)
    
    # 加权得分
    combined_score = rule_val * rule_conf * 0.4 + llm_val * llm_conf * 0.6
    combined_confidence = (rule_conf * 0.4 + llm_conf * 0.6)
    
    # 判断最终方向
    if combined_score > 5:
        final_dir = "long"
    elif combined_score < -5:
        final_dir = "short"
    else:
        final_dir = "wait"
    
    # 最终信号
    signal_map = {
        "long": "buy" if combined_confidence > 50 else "weak_buy",
        "short": "sell" if combined_confidence > 50 else "weak_sell",
        "wait": "neutral",
    }
    
    return {
        "signal": signal_map.get(final_dir, "neutral"),
        "direction": final_dir,
        "confidence": round(combined_confidence, 1),
        "rule_confidence": rule_conf,
        "llm_confidence": llm_conf,
        "rule_direction": rule_dir,
        "llm_direction": llm_dir,
        "llm_analysis": llm,
        "fusion": "rule_and_llm",
        "signals_detail": rule_signals.get("signals_detail", []),
        "summary": rule_signals.get("summary", ""),
    }


def test_with_mock():
    """使用模拟数据测试LLM分析"""
    import sys
    sys.path.insert(0, ".")
    from data_fetcher import get_market_snapshot
    from indicators import calc_short_term_indicators
    from signals import generate_signals
    
    print("=" * 50)
    print("LLM Analysis Test")
    print("=" * 50)
    
    snap = get_market_snapshot()
    gold_df = __import__("data_fetcher").fetch_data("gold", interval="1m", period="1d")
    ind = calc_short_term_indicators(gold_df)
    rule_sig = generate_signals(ind, snap)
    
    print("\nRule signal:", rule_sig["signal"], "| Confidence:", rule_sig["confidence"])
    print("Calling DeepSeek...")
    
    llm = get_llm_analysis(snap, ind, rule_sig)
    if llm:
        print("\n--- LLM Analysis ---")
        print("Direction:", llm.get("direction"))
        print("Confidence:", llm.get("confidence"))
        print("Reasoning:", llm.get("reasoning", "")[:200])
        print("Risk:", llm.get("risk_level"))
        print("Entry:", llm.get("suggested_entry"))
        print("Stop Loss:", llm.get("stop_loss"))
        print("Take Profit:", llm.get("take_profit"))
    
    combined = get_combined_signal(snap, ind, rule_sig)
    print("\n--- Combined Signal ---")
    print("Final:", combined["signal"], "| Dir:", combined["direction"], "| Conf:", combined["confidence"])
    print("Fusion mode:", combined["fusion"])
    
    return combined


if __name__ == "__main__":
    test_with_mock()
