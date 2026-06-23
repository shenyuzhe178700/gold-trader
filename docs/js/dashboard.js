// Gold Trader - GitHub Pages Frontend
// 通过HTTP轮询连接远程后端

var API_BASE = "";
var autoRefresh = false;
var autoTimer = null;
var pollingActive = false;
var pollTimer = null;

// === 初始化 ===
document.addEventListener("DOMContentLoaded", function() {
    // 尝试从localStorage恢复服务器地址
    var saved = localStorage.getItem("gold_trader_server");
    if (saved) {
        document.getElementById("server-url").value = saved;
        API_BASE = saved;
        updateServerHint(true);
    }

    // 事件绑定
    document.getElementById("btn-connect").addEventListener("click", connectServer);
    document.getElementById("btn-refresh").addEventListener("click", refreshData);
    document.getElementById("btn-auto").addEventListener("click", toggleAuto);

    var llmBtn = document.getElementById("btn-config-llm");
    if (llmBtn) {
        llmBtn.addEventListener("click", configureLLM);
    }

    var apiInput = document.getElementById("api-key-input");
    if (apiInput) {
        apiInput.addEventListener("keydown", function(e) {
            if (e.key === "Enter") configureLLM();
        });
    }

    // 回车键连接
    document.getElementById("server-url").addEventListener("keydown", function(e) {
        if (e.key === "Enter") connectServer();
    });

    updateStatus("ready", "就绪");
});

// === 服务器连接 ===
function connectServer() {
    var url = document.getElementById("server-url").value.trim();
    if (!url) {
        showToast("请输入后端服务器地址");
        return;
    }

    // 去掉末尾斜杠
    url = url.replace(/\/+$/, "");
    API_BASE = url;
    localStorage.setItem("gold_trader_server", url);

    showToast("正在连接...");
    updateStatus("connecting", "连接中...");

    // 测试连接
    fetch(API_BASE + "/api/status")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.live !== undefined) {
                updateStatus("connected", "已连接 ✓");
                updateServerHint(true);
                showToast("连接成功！开始获取数据...");
                refreshData();
                startPolling();
            } else {
                updateStatus("error", "响应异常");
                showToast("服务器响应异常");
            }
        })
        .catch(function(e) {
            updateStatus("error", "连接失败");
            updateServerHint(false);
            showToast("连接失败，请检查服务器地址");
        });
}

function updateServerHint(ok) {
    var hint = document.getElementById("server-hint");
    if (!hint) return;
    if (ok) {
        hint.innerHTML = "✓ 已连接: " + API_BASE;
        hint.style.color = "var(--green)";
        document.getElementById("config-card").style.display = "none";
    } else {
        hint.innerHTML = "✗ 无法连接，请检查地址";
        hint.style.color = "var(--red)";
    }
}

// === HTTP轮询 ===
function startPolling() {
    if (pollingActive) return;
    pollingActive = true;
    pollLoop();
}

function pollLoop() {
    if (!pollingActive || !API_BASE) return;
    fetch(API_BASE + "/api/analysis")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data && !data.error) {
                renderAll(data);
            }
            if (pollingActive) {
                pollTimer = setTimeout(pollLoop, 30000);
            }
        })
        .catch(function(e) {
            console.error("Poll error:", e);
            if (pollingActive) {
                pollTimer = setTimeout(pollLoop, 30000);
            }
        });
}

function stopPolling() {
    pollingActive = false;
    if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
    }
}

// === 数据刷新 ===
function refreshData() {
    if (!API_BASE) {
        showToast("请先连接服务器");
        return;
    }
    showLoading();
    fetch(API_BASE + "/api/analysis")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.error) {
                showError(data.error);
                return;
            }
            renderAll(data);
        })
        .catch(function(e) {
            showError("网络错误: " + e.message);
        });
    hideLoading();
}

// === 自动刷新 ===
function toggleAuto() {
    if (autoRefresh) {
        stopAuto();
    } else {
        startAuto();
    }
}

function startAuto() {
    if (!API_BASE) {
        showToast("请先连接服务器");
        return;
    }
    autoRefresh = true;
    document.getElementById("btn-auto").innerHTML = "⏸ 停止";
    document.getElementById("btn-auto").className = "btn btn-outline";
    showToast("自动刷新已启动 (30秒)");
    autoTimer = setInterval(refreshData, 30000);
}

function stopAuto() {
    autoRefresh = false;
    document.getElementById("btn-auto").innerHTML = "▶ 自动刷新";
    document.getElementById("btn-auto").className = "btn btn-primary";
    if (autoTimer) {
        clearInterval(autoTimer);
        autoTimer = null;
    }
}

// === AI配置 ===
function configureLLM() {
    if (!API_BASE) {
        showToast("请先连接服务器");
        return;
    }

    var input = document.getElementById("api-key-input");
    var apiKey = input ? input.value.trim() : "";
    if (!apiKey) {
        showToast("请输入DeepSeek API Key");
        return;
    }

    document.getElementById("ai-status").textContent = "配置中...";

    fetch(API_BASE + "/api/llm/configure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey }),
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.status === "ok") {
            showToast("AI已启用！正在分析...");
            document.getElementById("ai-status").textContent = "分析中...";
            // 立即获取AI分析
            fetchLLMAnalysis();
        } else {
            showToast("配置失败: " + (data.message || "unknown"));
        }
    })
    .catch(function(e) {
        showToast("请求失败: " + e.message);
    });
}

function fetchLLMAnalysis() {
    if (!API_BASE) return;
    document.getElementById("ai-status").textContent = "分析中...";
    fetch(API_BASE + "/api/llm/combined")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            renderLLMPanel(data);
        })
        .catch(function(e) {
            document.getElementById("ai-status").textContent = "API错误";
        });
}

// === LLM面板渲染 ===
function renderLLMPanel(data) {
    var contentEl = document.getElementById("ai-content");
    var statusEl = document.getElementById("ai-status");
    if (!contentEl) return;

    var llm = data.llm_analysis || {};
    var available = llm.available;
    var fusion = data.fusion || "rule_only";

    if (fusion === "rule_only" && !available) {
        document.getElementById("ai-status").textContent = "未启用";
        return;
    }

    statusEl.textContent = "DeepSeek ✓";

    var dirMap = { long: "📈 做多 LONG", short: "📉 做空 SHORT", wait: "⏸ 观望" };
    var llmDir = llm.direction || "wait";
    var llmConf = llm.confidence || 0;
    var dirColor = llmDir === "long" ? "var(--green)" : (llmDir === "short" ? "var(--red)" : "var(--text-muted)");

    var riskMap = { low: "🟢 低风险", medium: "🟡 中风险", high: "🔴 高风险" };
    var risk = riskMap[llm.risk_level] || "未知";

    var html = "";

    // 融合信号
    html += "<div style=\"display:flex;align-items:center;justify-content:space-between;padding:8px 0;\">";
    html += "<div>";
    html += "<div style=\"font-size:20px;font-weight:800;color:" + dirColor + ";\">" + (dirMap[data.direction] || "观望") + "</div>";
    html += "<div style=\"font-size:12px;color:var(--text-muted);\">融合置信度 " + (data.confidence || 0) + "% (规则:" + (data.rule_confidence || 0) + "% + AI:" + llmConf + "%)</div>";
    html += "</div>";
    html += "<div style=\"text-align:right;\">";
    html += "<div style=\"font-size:12px;color:var(--text-muted);\">AI置信</div>";
    html += "<div style=\"font-size:18px;font-weight:700;color:" + dirColor + ";\">" + llmConf + "%</div>";
    html += "</div>";
    html += "</div>";

    // AI推理
    html += "<div style=\"background:rgba(88,166,255,0.06);border-radius:8px;padding:10px;margin:8px 0;\">";
    html += "<div style=\"font-size:12px;color:var(--blue);margin-bottom:4px;\">🧠 AI推理</div>";
    html += "<div style=\"font-size:13px;line-height:1.7;color:var(--text-primary);\">" + (llm.reasoning || "分析中...") + "</div>";
    html += "</div>";

    // 多空因素
    var bulls = llm.key_factors_bullish || [];
    var bears = llm.key_factors_bearish || [];
    if (bulls.length || bears.length) {
        html += "<div style=\"display:flex;gap:8px;margin:6px 0;\">";
        html += "<div style=\"flex:1;background:rgba(63,185,80,0.06);border-radius:8px;padding:8px;\">";
        html += "<div style=\"font-size:11px;color:var(--green);margin-bottom:4px;\">🟢 利多</div>";
        for (var i = 0; i < bulls.length; i++) {
            html += "<div style=\"font-size:11px;color:var(--text-secondary);padding:2px 0;\">• " + bulls[i] + "</div>";
        }
        html += "</div><div style=\"flex:1;background:rgba(248,81,73,0.06);border-radius:8px;padding:8px;\">";
        html += "<div style=\"font-size:11px;color:var(--red);margin-bottom:4px;\">🔴 利空</div>";
        for (var j = 0; j < bears.length; j++) {
            html += "<div style=\"font-size:11px;color:var(--text-secondary);padding:2px 0;\">• " + bears[j] + "</div>";
        }
        html += "</div></div>";
    }

    // 交易建议
    html += "<div style=\"display:flex;gap:8px;margin-top:8px;font-size:11px;\">";
    html += "<div style=\"flex:1;text-align:center;padding:6px;background:rgba(255,255,255,0.03);border-radius:6px;\"><div style=\"color:var(--text-muted);\">🎯 入场</div><div style=\"color:var(--blue);font-weight:600;\">" + (llm.suggested_entry || "--") + "</div></div>";
    html += "<div style=\"flex:1;text-align:center;padding:6px;background:rgba(255,255,255,0.03);border-radius:6px;\"><div style=\"color:var(--text-muted);\">🛑 止损</div><div style=\"color:var(--red);font-weight:600;\">" + (llm.stop_loss || "--") + "</div></div>";
    html += "<div style=\"flex:1;text-align:center;padding:6px;background:rgba(255,255,255,0.03);border-radius:6px;\"><div style=\"color:var(--text-muted);\">🏁 止盈</div><div style=\"color:var(--green);font-weight:600;\">" + (llm.take_profit || "--") + "</div></div>";
    html += "</div>";

    html += "<div style=\"display:flex;justify-content:space-between;margin-top:6px;font-size:11px;color:var(--text-muted);\">";
    html += "<span>风险: " + risk + "</span><span>时效: " + (llm.time_horizon || "--") + "</span><span>延迟: " + (llm.latency_ms ? (llm.latency_ms / 1000).toFixed(1) + "s" : "--") + "</span>";
    html += "</div>";

    if (llm.special_notes) {
        html += "<div style=\"margin-top:6px;padding:6px 8px;background:rgba(210,153,29,0.1);border-radius:6px;font-size:11px;color:var(--orange);\">⚠️ " + llm.special_notes + "</div>";
    }

    contentEl.innerHTML = html;
}

// ==================== 渲染函数 ====================

function renderAll(data) {
    if (!data) return;
    renderPrice(data.market, data.indicators);
    renderSignal(data.signals);
    renderIndicators(data.indicators);
    renderMarkets(data.market);
    renderSignalDetails(data.signals);
    updateTimestamp(data.timestamp);

    if (data.llm_combined) {
        renderLLMPanel(data.llm_combined);
        document.getElementById("ai-status").textContent = "DeepSeek ✓";
    }
}

function renderPrice(market, indicators) {
    if (!market || !market.gold) return;
    var gold = market.gold;
    var el = document.getElementById("price-card");
    if (!gold.price) {
        el.innerHTML = "<div class=\"loading\"><div class=\"spinner\"></div></div>";
        return;
    }

    var changeClass = gold.change_pct >= 0 ? "up" : "down";
    var changeSign = gold.change_pct >= 0 ? "+" : "";
    var price = gold.price.toFixed(2);
    var open = gold.open.toFixed(2);
    var high = gold.high.toFixed(2);
    var low = gold.low.toFixed(2);
    var chg = gold.change.toFixed(2);
    var chgPct = gold.change_pct.toFixed(2);
    var sym = gold.symbol || "GC=F";
    var vol = formatVolume(gold.volume);

    el.innerHTML = [
        "<div class=\"price-main\">",
        "  <div>",
        "    <div class=\"price-label\">🥇 COMEX Gold <span class=\"symbol\">" + sym + "</span></div>",
        "    <div class=\"price-value " + changeClass + "\">$" + price + "</div>",
        "  </div>",
        "  <div class=\"price-change " + changeClass + "\">" + changeSign + chg + " (" + changeSign + chgPct + "%)</div>",
        "</div>",
        "<div class=\"price-details\">",
        "  <span>O <span class=\"val\">" + open + "</span></span>",
        "  <span>H <span class=\"val\">" + high + "</span></span>",
        "  <span>L <span class=\"val\">" + low + "</span></span>",
        "  <span>V <span class=\"val\">" + vol + "</span></span>",
        "</div>"
    ].join("\n");
}

function renderSignal(signals) {
    if (!signals) return;
    var el = document.getElementById("signal-card");
    var cls = signals.signal || "neutral";
    var dirMap = {
        "buy": "📈 做多 LONG", "sell": "📉 做空 SHORT",
        "weak_buy": "📈 偏多", "weak_sell": "📉 偏空", "neutral": "⏸ 观望"
    };
    var conf = signals.confidence || 0;
    var score = signals.score || 0;
    var absScore = Math.abs(score);
    var barHtml = "";
    if (score > 0) {
        barHtml = "<div class=\"score-bar\"><div class=\"score-fill-bullish\" style=\"width:" + Math.min(absScore, 100) + "%\"></div></div>";
    } else if (score < 0) {
        barHtml = "<div class=\"score-bar\"><div class=\"score-fill-bearish\" style=\"width:" + Math.min(absScore, 100) + "%\"></div></div>";
    } else {
        barHtml = "<div class=\"score-bar\"><div class=\"score-fill-neutral\" style=\"width:100%\"></div></div>";
    }
    el.className = "signal-card " + cls;
    el.innerHTML = [
        "<div class=\"signal-direction\">" + (dirMap[cls] || "⏸ 观望") + "</div>",
        "<div class=\"signal-confidence\">置信度 <strong>" + conf + "%</strong></div>",
        barHtml,
        "<div class=\"signal-summary\">" + (signals.summary || "") + "</div>"
    ].join("\n");
}

function renderIndicators(indicators) {
    if (!indicators) return;
    var el = document.getElementById("indicators-grid");
    if (!el) return;

    var items = [];

    var rsiV = indicators.rsi ? indicators.rsi.value : null;
    var rsiZone = indicators.rsi ? indicators.rsi.zone : null;
    var rsiCls = "neutral-val";
    if (rsiZone === "overbought") rsiCls = "bearish";
    else if (rsiZone === "oversold") rsiCls = "bullish";
    items.push({ label: "RSI(14)", value: rsiV, sub: rsiZone, cls: rsiCls });

    var macdH = indicators.macd ? indicators.macd.histogram : null;
    items.push({ label: "MACD", value: macdH !== null ? macdH.toFixed(4) : null, cls: macdH >= 0 ? "bullish" : "bearish" });

    var stochK = indicators.stochastic ? indicators.stochastic.k : null;
    var stochCls = "neutral-val";
    if (stochK > 80) stochCls = "bearish";
    else if (stochK < 20) stochCls = "bullish";
    items.push({ label: "Stoch K", value: stochK, cls: stochCls });

    var bbPos = indicators.bollinger ? indicators.bollinger.position : null;
    var bbCls = "neutral-val";
    if (bbPos > 80) bbCls = "bearish";
    else if (bbPos < 20) bbCls = "bullish";
    items.push({ label: "BB位置", value: bbPos !== null ? bbPos + "%" : null, cls: bbCls });

    items.push({ label: "ATR", value: indicators.atr, cls: "neutral-val" });

    var mom = indicators.momentum;
    items.push({ label: "动量", value: mom !== null ? mom + "%" : null, cls: mom > 0 ? "bullish" : "bearish" });

    var volR = indicators.volume_ratio;
    items.push({ label: "量比", value: volR !== null ? volR.toFixed(1) : null, cls: volR > 1.2 ? "bullish" : "neutral-val" });

    var maAlign = indicators.ma ? indicators.ma.alignment : null;
    var maText = maAlign === "bullish" ? "多头" : (maAlign === "bearish" ? "空头" : "交织");
    var maCls = maAlign === "bullish" ? "bullish" : (maAlign === "bearish" ? "bearish" : "neutral-val");
    items.push({ label: "MA排列", value: maText, cls: maCls });

    var stochD = indicators.stochastic ? indicators.stochastic.d : null;
    var stochDCls = "neutral-val";
    if (stochD > 80) stochDCls = "bearish";
    else if (stochD < 20) stochDCls = "bullish";
    items.push({ label: "Stoch D", value: stochD, cls: stochDCls });

    var html = "";
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        html += "<div class=\"indicator-item\">";
        html += "<div class=\"indicator-label\">" + item.label + "</div>";
        html += "<div class=\"indicator-value " + item.cls + "\">" + (item.value !== null ? item.value : "--") + "</div>";
        if (item.sub) html += "<div class=\"indicator-sub\">" + item.sub + "</div>";
        html += "</div>";
    }

    var sr = indicators.support_resistance;
    if (sr) {
        var sups = sr.supports || [];
        var ress = sr.resistances || [];
        html += "<div class=\"indicator-item\" style=\"grid-column: span 2;\">";
        html += "<div class=\"sr-table\">";
        html += "<div class=\"sr-col\"><div class=\"sr-title\">🟢 支撑</div><div class=\"sr-values support\">" + (sups.length ? sups.join(" / ") : "--") + "</div></div>";
        html += "<div class=\"sr-col\"><div class=\"sr-title\">🔴 阻力</div><div class=\"sr-values resistance\">" + (ress.length ? ress.join(" / ") : "--") + "</div></div>";
        html += "</div></div>";
    }
    el.innerHTML = html;
}

function renderMarkets(market) {
    if (!market) return;
    var el = document.getElementById("markets-list");
    if (!el) return;

    var configs = [
        { key: "usdjpy", name: "美元/日元", icon: "💱" },
        { key: "dxy", name: "美元指数", icon: "💵" },
        { key: "silver", name: "白银期货", icon: "⚪" },
        { key: "us10y", name: "美债10Y", icon: "📊" },
        { key: "vix", name: "VIX恐慌", icon: "😨" },
        { key: "sp500", name: "标普500", icon: "📈" },
    ];

    var html = "";
    for (var i = 0; i < configs.length; i++) {
        var m = configs[i];
        var data = market[m.key];
        if (!data) continue;
        var cc = (data.change_pct || 0) >= 0 ? "up-color" : "down-color";
        var cs = (data.change_pct || 0) >= 0 ? "+" : "";
        var ps = typeof data.price === "number" ? data.price.toFixed(2) : "--";
        html += "<div class=\"market-row\">";
        html += "<div><div class=\"market-name\">" + m.icon + " " + m.name + "</div><div class=\"market-symbol\">" + (data.symbol || "") + "</div></div>";
        html += "<div><div class=\"market-price\">" + ps + "</div><div class=\"market-change " + cc + "\">" + cs + (data.change_pct || 0).toFixed(2) + "%</div></div>";
        html += "</div>";
    }

    var flow = market.capital_flow;
    if (flow) {
        var fm = { bullish: "🟢 流入", bearish: "🔴 流出", neutral: "⚪ 中性" };
        html += "<div class=\"market-row\"><div><div class=\"market-name\">💰 资金流向</div><div class=\"market-symbol\">SPDR GLD ETF</div></div>";
        html += "<div style=\"text-align:right;\"><div class=\"market-price\" style=\"font-size:12px;\">" + (fm[flow.flow] || "中性") + "</div>";
        html += "<div class=\"market-change\" style=\"font-size:11px;color:var(--text-muted);\">" + (flow.ratio * 100).toFixed(0) + "%</div></div></div>";
    }
    el.innerHTML = html;
}

function renderSignalDetails(signals) {
    if (!signals || !signals.signals_detail) return;
    var el = document.getElementById("signals-detail");
    if (!el) return;
    var sorted = signals.signals_detail.slice().sort(function(a, b) {
        var w = { high: 3, medium: 2, low: 1 };
        return (w[b.weight] || 0) - (w[a.weight] || 0);
    });
    var html = "";
    for (var i = 0; i < sorted.length; i++) {
        var s = sorted[i];
        var bc = s.signal === "bullish" ? "bullish" : (s.signal === "bearish" ? "bearish" : "neutral-badge");
        var bt = s.signal === "bullish" ? "做多" : (s.signal === "bearish" ? "做空" : "中性");
        html += "<div class=\"signal-item\">";
        html += "<span class=\"signal-badge " + bc + "\">" + bt + "</span>";
        html += "<span class=\"signal-source\">" + s.source + "</span>";
        html += "<span class=\"signal-detail\">" + s.detail + "</span>";
        html += "</div>";
    }
    el.innerHTML = html || "<div class=\"empty-state\">暂无信号数据</div>";
}

// === UI辅助 ===
function updateStatus(status, text) {
    var dot = document.getElementById("status-dot");
    var label = document.getElementById("status-text");
    if (!dot || !label) return;
    if (status === "connected") dot.style.background = "var(--green)";
    else if (status === "error") dot.style.background = "var(--red)";
    else if (status === "connecting") dot.style.background = "var(--orange)";
    else dot.style.background = "var(--text-muted)";
    label.textContent = text;
}

function updateTimestamp(ts) {
    var el = document.getElementById("update-time");
    if (el && ts) el.textContent = "更新: " + ts;
}

function showLoading() {}
function hideLoading() {}

function showError(msg) {
    var el = document.getElementById("price-card");
    if (el) el.innerHTML = "<div class=\"empty-state\"><div class=\"icon\">⚠️</div><div>" + msg + "</div></div>";
}

function showToast(msg) {
    var existing = document.querySelector(".toast");
    if (existing) existing.remove();
    var toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 2500);
}

function formatVolume(v) {
    if (!v) return "0";
    if (v >= 1000000) return (v / 1000000).toFixed(1) + "M";
    if (v >= 1000) return (v / 1000).toFixed(0) + "K";
    return v.toString();
}
