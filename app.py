# -*- coding: utf-8 -*-
"""
黄金贵金属短线交易分析工具 - Flask主程序
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
import json
import os
import logging

from data_fetcher import (
    fetch_data, get_market_snapshot,
    SYMBOLS, get_latest_price, check_live_availability
)
from indicators import calc_short_term_indicators
from signals import generate_signals
from llm_analyzer import get_llm_analysis, get_combined_signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = "gold-trader-secret-2026"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

_latest_analysis = None
_update_lock = threading.Lock()
_live_available = False


def run_analysis(use_llm=True, force_live=True):
    """执行完整分析"""
    if force_live:
        import data_fetcher
        data_fetcher._data_source = "unknown"  # reset to try live again
    global _latest_analysis, _live_available
    try:
        snapshot = get_market_snapshot()
        gold_df = fetch_data("gold", interval="1m", period="1d")
        gold_indicators = calc_short_term_indicators(gold_df)
        signals = generate_signals(gold_indicators, snapshot)

        result = {
            "timestamp": snapshot["timestamp"],
            "market": snapshot,
            "indicators": gold_indicators,
            "signals": signals,
            "data_source": snapshot.get("data_source", "unknown"),
        }

        # LLM增强分析
        if use_llm:
            try:
                combined = get_combined_signal(snapshot, gold_indicators, signals)
                result["llm_combined"] = combined
                result["llm_analysis"] = combined.get("llm_analysis")
                result["fusion_mode"] = combined.get("fusion", "rule_only")
            except Exception as e:
                logger.warning("LLM analysis skipped: %s", e)
                result["fusion_mode"] = "rule_only"

        with _update_lock:
            _latest_analysis = result
        return result
    except Exception as e:
        logger.error("Analysis failed: %s", e)
        return {"error": str(e)}


# === Routes ===

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/snapshot")
def api_snapshot():
    return jsonify(get_market_snapshot())


@app.route("/api/analysis")
def api_analysis():
    return jsonify(run_analysis())


@app.route("/api/indicators")
def api_indicators():
    gold_df = fetch_data("gold", interval="1m", period="1d")
    indicators = calc_short_term_indicators(gold_df)
    return jsonify(indicators)


@app.route("/api/signals")
def api_signals():
    snapshot = get_market_snapshot()
    gold_df = fetch_data("gold", interval="1m", period="1d")
    gold_indicators = calc_short_term_indicators(gold_df)
    return jsonify(generate_signals(gold_indicators, snapshot))


@app.route("/api/price/<symbol>")
def api_price(symbol):
    if symbol not in SYMBOLS:
        return jsonify({"error": "Unknown symbol"}), 404
    price = get_latest_price(symbol)
    return jsonify(price)


@app.route("/api/history/<symbol>")
def api_history(symbol):
    if symbol not in SYMBOLS:
        return jsonify({"error": "Unknown symbol"}), 404
    interval = request.args.get("interval", "5m")
    period = request.args.get("period", "1d")
    df = fetch_data(symbol, interval=interval, period=period, force_refresh=True)
    if df is None:
        return jsonify({"error": "Fetch failed"}), 500
    data = []
    for idx, row in df.iterrows():
        data.append({
            "time": str(idx),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        })
    return jsonify({"symbol": SYMBOLS[symbol], "data": data})


@app.route("/api/status")
def api_status():
    return jsonify({"live": _live_available, "data_source": "live" if _live_available else "mock"})


# === WebSocket ===

@socketio.on("connect")
def handle_connect():
    logger.info("Client connected")
    emit("connected", {"status": "ok", "live": _live_available})


@socketio.on("request_analysis")
def handle_analysis_request():
    result = run_analysis()
    emit("analysis_update", result)


@socketio.on("request_price")
def handle_price_request(data):
    symbol = data.get("symbol", "gold")
    price = get_latest_price(symbol)
    emit("price_update", price)


_auto_push_running = False


def auto_push_loop():
    global _auto_push_running
    _auto_push_running = True
    logger.info("Auto-push started")
    while _auto_push_running:
        try:
            result = run_analysis()
            if result and "error" not in result:
                socketio.emit("auto_analysis", result)
        except Exception as e:
            logger.error("Auto-push error: %s", e)
        time.sleep(30)


@socketio.on("start_auto")
def handle_start_auto():
    global _auto_push_running
    if not _auto_push_running:
        thread = threading.Thread(target=auto_push_loop, daemon=True)
        thread.start()
        emit("auto_status", {"running": True})
    else:
        emit("auto_status", {"running": True})


@socketio.on("stop_auto")
def handle_stop_auto():
    global _auto_push_running
    _auto_push_running = False
    emit("auto_status", {"running": False})



@app.route("/api/llm/analysis")
def api_llm_analysis():
    """获取DeepSeek LLM分析"""
    snapshot = get_market_snapshot()
    gold_df = fetch_data("gold", interval="1m", period="1d")
    gold_indicators = calc_short_term_indicators(gold_df)
    rule_signals = generate_signals(gold_indicators, snapshot)
    llm = get_llm_analysis(snapshot, gold_indicators, rule_signals)
    return jsonify(llm)


@app.route("/api/llm/combined")
def api_llm_combined():
    """获取规则+LLM融合信号"""
    snapshot = get_market_snapshot()
    gold_df = fetch_data("gold", interval="1m", period="1d")
    gold_indicators = calc_short_term_indicators(gold_df)
    rule_signals = generate_signals(gold_indicators, snapshot)
    combined = get_combined_signal(snapshot, gold_indicators, rule_signals)
    return jsonify(combined)


@app.route("/api/llm/configure", methods=["POST"])
def api_llm_configure():
    """配置DeepSeek API Key"""
    data = request.get_json()
    api_key = data.get("api_key", "") if data else ""
    if api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key
        import llm_analyzer
        llm_analyzer.DEEPSEEK_API_KEY = api_key
        return jsonify({"status": "ok", "message": "API Key configured"})
    return jsonify({"status": "error", "message": "No API key provided"}), 400


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("  Gold Trader - 黄金短线交易分析工具")
    logger.info("  COMEX Gold Futures + DeepSeek AI")
    logger.info("=" * 50)

    # 检测实时数据
    logger.info("Detecting data source...")
    _live_available = check_live_availability()
    if _live_available:
        logger.info(">>> LIVE DATA mode - Yahoo Finance direct API <<<")
    else:
        logger.warning("Live data unavailable, will retry on each request")

    logger.info("Server: http://0.0.0.0:5000")
    logger.info("Press Ctrl+C to stop")
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
