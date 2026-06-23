// === 黄金短线交易分析工具 - 前端仪表盘 ===

const API_BASE = window.location.origin;
let autoRefresh = false;
let autoRefreshTimer = null;
let socket = null;

// === 初始化 ===
document.addEventListener("DOMContentLoaded", () => {
    initSocket();
    bindEvents();
    refreshData();
});

// === WebSocket 连接 ===
function initSocket() {
    socket = io(API_BASE, {
        transports: ["websocket", "polling"],
        reconnection: true,
        reconnectionDelay: 3000,
    });

    socket.on("connect", () => {
        updateStatus("connected", "已连接");
    });

    socket.on("disconnect", () => {
        updateStatus("disconnected", "已断开");
    });

    socket.on("analysis_update", (data) => {
        renderAll(data);
    });

    socket.on("auto_analysis", (data) => {
        renderAll(data);
        flashUpdate();
    });

    socket.on("auto_status", (data) => {
        if (data.running) {
            showToast("自动推送已启动 (每30秒)");
        } else {
            showToast("自动推送已停止");
        }
    });
}

// === 事件绑定 ===
function bindEvents() {
    document.getElementById("btn-refresh").addEventListener("click", () => {
        refreshData();
    });

    document.getElementById("btn-auto").addEventListener("click", () => {
        toggleAuto();
    });

    // LLM config button
    var llmBtn = document.getElementById("btn-config-llm");
    if (llmBtn) {
        llmBtn.addEventListener("click", () => {
            configureLLM();
        });
    }

    // Enter key on API input
    var apiInput = document.getElementById("api-key-input");
    if (apiInput) {
        apiInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") configureLLM();
        });
    }
}

// === 数据刷新 ===
async function refreshData() {
    showLoading();
    try {
        if (socket && socket.connected) {
            socket.emit("request_analysis");
        } else {
            const resp = await fetch(API_BASE + "/api/analysis");
            const data = await resp.json();
            if (data.error) {
                showError(data.error);
                return;
            }
            renderAll(data);
        }
    } catch (e) {
        showError("网络连接失败: " + e.message);
    }
    hideLoading();
}

// === 自动刷新 ===
function toggleAuto() {
    if (socket && socket.connected) {
        if (autoRefresh) {
            socket.emit("stop_auto");
            autoRefresh = false;
            updateAutoBtn(false);
        } else {
            socket.emit("start_auto");
            autoRefresh = true;
            updateAutoBtn(true);
        }
    }
}

function updateAutoBtn(active) {
    const btn = document.getElementById("btn-auto");
    if (active) {
        btn.innerHTML = "⏸ 停止推送";
        btn.className = "btn btn-outline";
    } else {
        btn.innerHTML = "▶ 自动推送";
        btn.className = "btn btn-primary";
    }
}

// === 渲染 ===
function renderAll(data) {
    if (!data) return;
    renderPrice(data.market, data.indicators);
    renderSignal(data.signals);
    renderIndicators(data.indicators);
    renderMarkets(data.market);
    renderSignalDetails(data.signals);
    updateTimestamp(data.timestamp);
}

function renderPrice(market, indicators) {
    if (!market || !market.gold) return;

    const gold = market.gold;
    const el = document.getElementById("price-card");

    if (!gold.price) {
        el.innerHTML = "<div class=\"loading\"><div class=\"spinner\"></div></div>";
        return;
    }

    const changeClass = gold.change_pct >= 0 ? "up" : "down";
    const changeSign = gold.change_pct >= 0 ? "+" : "";
    const price = gold.price.toFixed(2);
    const open = gold.open.toFixed(2);
    const high = gold.high.toFixed(2);
    const low = gold.low.toFixed(2);
    const chg = gold.change.toFixed(2);
    const chgPct = gold.change_pct.toFixed(2);
    const sym = gold.symbol || "GC=F";
    const vol = formatVolume(gold.volume);

    el.innerHTML = [
        "<div class=\"price-main\">",
        "  <div>",
        "    <div class=\"price-label\">🥇 COMEX黄金期货 <span class=\"symbol\">" + sym + "</span></div>",
        "    <div class=\"price-value " + changeClass + "\">$" + price + "</div>",
        "  </div>",
        "  <div class=\"price-change " + changeClass + "\">" + changeSign + chg + " (" + changeSign + chgPct + "%)</div>",
        "</div>",
        "<div class=\"price-details\">",
        "  <span>开盘 <span class=\"val\">" + open + "</span></span>",
        "  <span>最高 <span class=\"val\">" + high + "</span></span>",
        "  <span>最低 <span class=\"val\">" + low + "</span></span>",
        "  <span>量 <span class=\"val\">" + vol + "</span></span>",
        "</div>"
    ].join("\n");
}

function renderSignal(signals) {
    if (!signals) return;

    const el = document.getElementById("signal-card");
    const cls = signals.signal || "neutral";
    const dirMap = {
        "buy": "📈 做多 LONG",
        "sell": "📉 做空 SHORT",
        "weak_buy": "📈 偏多",
        "weak_sell": "📉 偏空",
        "neutral": "⏸ 观望 WAIT",
    };

    const conf = signals.confidence || 0;
    const score = signals.score || 0;
    const absScore = Math.abs(score);
    let barHtml = "";
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

    const el = document.getElementById("indicators-grid");
    if (!el) return;

    var items = [];

    // RSI
    var rsiV = indicators.rsi ? indicators.rsi.value : null;
    var rsiZone = indicators.rsi ? indicators.rsi.zone : null;
    var rsiCls = "neutral-val";
    if (rsiZone === "overbought") rsiCls = "bearish";
    else if (rsiZone === "oversold") rsiCls = "bullish";
    items.push({ label: "RSI(14)", value: rsiV, sub: rsiZone, cls: rsiCls });

    // MACD
    var macdH = indicators.macd ? indicators.macd.histogram : null;
    items.push({ label: "MACD", value: macdH !== null ? macdH.toFixed(4) : null, cls: macdH >= 0 ? "bullish" : "bearish" });

    // Stoch K
    var stochK = indicators.stochastic ? indicators.stochastic.k : null;
    var stochCls = "neutral-val";
    if (stochK > 80) stochCls = "bearish";
    else if (stochK < 20) stochCls = "bullish";
    items.push({ label: "Stoch K", value: stochK, cls: stochCls });

    // Bollinger
    var bbPos = indicators.bollinger ? indicators.bollinger.position : null;
    var bbCls = "neutral-val";
    if (bbPos > 80) bbCls = "bearish";
    else if (bbPos < 20) bbCls = "bullish";
    items.push({ label: "布林位置", value: bbPos !== null ? bbPos + "%" : null, cls: bbCls });

    // ATR
    items.push({ label: "ATR", value: indicators.atr, cls: "neutral-val" });

    // Momentum
    var mom = indicators.momentum;
    items.push({ label: "动量", value: mom !== null ? mom + "%" : null, cls: mom > 0 ? "bullish" : "bearish" });

    // Volume ratio
    var volR = indicators.volume_ratio;
    items.push({ label: "量比", value: volR !== null ? volR.toFixed(1) : null, cls: volR > 1.2 ? "bullish" : "neutral-val" });

    // MA alignment
    var maAlign = indicators.ma ? indicators.ma.alignment : null;
    var maText = maAlign === "bullish" ? "多头" : (maAlign === "bearish" ? "空头" : "交织");
    var maCls = maAlign === "bullish" ? "bullish" : (maAlign === "bearish" ? "bearish" : "neutral-val");
    items.push({ label: "MA排列", value: maText, cls: maCls });

    // Stoch D
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
        if (item.sub) {
            html += "<div class=\"indicator-sub\">" + item.sub + "</div>";
        }
        html += "</div>";
    }

    // 支撑阻力
    var sr = indicators.support_resistance;
    if (sr) {
        var supports = sr.supports || [];
        var resistances = sr.resistances || [];
        html += "<div class=\"indicator-item\" style=\"grid-column: span 2;\">";
        html += "<div class=\"sr-table\">";
        html += "<div class=\"sr-col\"><div class=\"sr-title\">🟢 支撑位</div><div class=\"sr-values support\">" + (supports.length ? supports.join(" / ") : "--") + "</div></div>";
        html += "<div class=\"sr-col\"><div class=\"sr-title\">🔴 阻力位</div><div class=\"sr-values resistance\">" + (resistances.length ? resistances.join(" / ") : "--") + "</div></div>";
        html += "</div></div>";
    }

    el.innerHTML = html;
}

function renderMarkets(market) {
    if (!market) return;
    const el = document.getElementById("markets-list");
    if (!el) return;

    const marketConfigs = [
        { key: "usdjpy", name: "美元/日元", icon: "💱" },
        { key: "dxy", name: "美元指数", icon: "💵" },
        { key: "silver", name: "白银期货", icon: "⚪" },
        { key: "us10y", name: "美债10Y", icon: "📊" },
        { key: "vix", name: "VIX恐慌", icon: "😨" },
        { key: "sp500", name: "标普500", icon: "📈" },
    ];

    var html = "";
    for (var i = 0; i < marketConfigs.length; i++) {
        var m = marketConfigs[i];
        var data = market[m.key];
        if (!data) continue;

        var changeClass = (data.change_pct || 0) >= 0 ? "up-color" : "down-color";
        var changeSign = (data.change_pct || 0) >= 0 ? "+" : "";
        var priceStr = typeof data.price === "number" ? data.price.toFixed(2) : "--";
        var pctStr = (data.change_pct || 0).toFixed(2);

        html += [
            "<div class=\"market-row\">",
            "  <div>",
            "    <div class=\"market-name\">" + m.icon + " " + m.name + "</div>",
            "    <div class=\"market-symbol\">" + (data.symbol || "") + "</div>",
            "  </div>",
            "  <div>",
            "    <div class=\"market-price\">" + priceStr + "</div>",
            "    <div class=\"market-change " + changeClass + "\">" + changeSign + pctStr + "%</div>",
            "  </div>",
            "</div>"
        ].join("\n");
    }

    // 资金流向
    var flow = market.capital_flow;
    if (flow) {
        var flowMap = { bullish: "🟢 流入", bearish: "🔴 流出", neutral: "⚪ 中性" };
        html += [
            "<div class=\"market-row\">",
            "  <div>",
            "    <div class=\"market-name\">💰 资金流向</div>",
            "    <div class=\"market-symbol\">SPDR GLD ETF</div>",
            "  </div>",
            "  <div style=\"text-align:right;\">",
            "    <div class=\"market-price\" style=\"font-size:12px;\">" + (flowMap[flow.flow] || "中性") + "</div>",
            "    <div class=\"market-change\" style=\"font-size:11px;color:var(--text-muted);\">比率 " + (flow.ratio * 100).toFixed(0) + "%</div>",
            "  </div>",
            "</div>"
        ].join("\n");
    }

    el.innerHTML = html;
}

function renderSignalDetails(signals) {
    if (!signals || !signals.signals_detail) return;
    const el = document.getElementById("signals-detail");
    if (!el) return;

    var sorted = signals.signals_detail.slice().sort(function(a, b) {
        var w = { high: 3, medium: 2, low: 1 };
        return (w[b.weight] || 0) - (w[a.weight] || 0);
    });

    var html = "";
    for (var i = 0; i < sorted.length; i++) {
        var s = sorted[i];
        var badgeCls = s.signal === "bullish" ? "bullish" : (s.signal === "bearish" ? "bearish" : "neutral-badge");
        var badgeText = s.signal === "bullish" ? "做多" : (s.signal === "bearish" ? "做空" : "中性");

        html += "<div class=\"signal-item\">";
        html += "<span class=\"signal-badge " + badgeCls + "\">" + badgeText + "</span>";
        html += "<span class=\"signal-source\">" + s.source + "</span>";
        html += "<span class=\"signal-detail\">" + s.detail + "</span>";
        html += "</div>";
    }
    el.innerHTML = html || "<div class=\"empty-state\">暂无信号数据</div>";
}

// === UI辅助 ===
function updateStatus(status, text) {
    const dot = document.querySelector(".status-dot");
    const label = document.querySelector(".status-text");
    if (dot) {
        dot.style.background = status === "connected" ? "var(--green)" : "var(--red)";
    }
    if (label) label.textContent = text;
}

function updateTimestamp(ts) {
    const el = document.getElementById("update-time");
    if (el && ts) {
        el.textContent = "更新: " + ts;
    }
}

function showLoading() {}

function hideLoading() {}

function showError(msg) {
    const el = document.getElementById("price-card");
    if (el) {
        el.innerHTML = "<div class=\"empty-state\"><div class=\"icon\">⚠️</div><div>" + msg + "</div><div style=\"margin-top:8px;font-size:12px;\">请检查网络连接或稍后重试</div></div>";
    }
}

function flashUpdate() {
    const el = document.getElementById("price-card");
    if (el) {
        el.classList.add("flash-update");
        setTimeout(function() { el.classList.remove("flash-update"); }, 600);
    }
}

function showToast(msg) {
    const existing = document.querySelector(".toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
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


// === AI Panel ===
function configureLLM() {
    var input = document.getElementById("api-key-input");
    var apiKey = input ? input.value.trim() : "";
    if (!apiKey) {
        showToast("请输入DeepSeek API Key");
        return;
    }

    fetch(API_BASE + "/api/llm/configure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey }),
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.status === "ok") {
            showToast("AI分析已启用！正在分析...");
            document.getElementById("ai-status").textContent = "分析中...";
            setTimeout(function() { fetchLLMAnalysis(); }, 1000);
        } else {
            showToast("配置失败: " + (data.message || "unknown"));
        }
    })
    .catch(function(e) {
        showToast("请求失败: " + e.message);
    });
}

function fetchLLMAnalysis() {
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

function renderLLMPanel(data) {
    var contentEl = document.getElementById("ai-content");
    var statusEl = document.getElementById("ai-status");
    if (!contentEl) return;

    var llm = data.llm_analysis || {};
    var available = llm.available;
    var fusion = data.fusion || "rule_only";

    if (fusion === "rule_only" && !available) {
        document.getElementById("ai-status").textContent = "规则引擎";
        contentEl.innerHTML = "<div class="empty-state"><div class="icon">🔑</div><div>AI分析未启用</div><div style="font-size:12px;margin-top:4px;">配置DeepSeek API Key以获取AI增强分析</div></div>";
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

    // 融合信号摘要
    html += "<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;">";
    html += "<div>";
    html += "<div style="font-size:20px;font-weight:800;color:" + dirColor + ";">" + (dirMap[data.direction] || "观望") + "</div>";
    html += "<div style="font-size:12px;color:var(--text-muted);">融合置信度: <strong style="color:" + dirColor + ";">" + (data.confidence || 0) + "%</strong></div>";
    html += "</div>";
    html += "<div style="text-align:right;">";
    html += "<div style="font-size:12px;color:var(--text-muted);">AI置信度</div>";
    html += "<div style="font-size:18px;font-weight:700;color:" + dirColor + ";">" + llmConf + "%</div>";
    html += "</div>";
    html += "</div>";

    // AI推理
    html += "<div style="background:rgba(88,166,255,0.06);border-radius:8px;padding:10px;margin:8px 0;">";
    html += "<div style="font-size:12px;color:var(--blue);margin-bottom:4px;">🧠 AI推理</div>";
    html += "<div style="font-size:13px;line-height:1.7;color:var(--text-primary);">" + (llm.reasoning || "分析中...") + "</div>";
    html += "</div>";

    // 关键因素
    var bulls = llm.key_factors_bullish || [];
    var bears = llm.key_factors_bearish || [];
    if (bulls.length || bears.length) {
        html += "<div style="display:flex;gap:8px;margin:6px 0;">";

        html += "<div style="flex:1;background:rgba(63,185,80,0.06);border-radius:8px;padding:8px;">";
        html += "<div style="font-size:11px;color:var(--green);margin-bottom:4px;">🟢 利多因素</div>";
        for (var bi = 0; bi < bulls.length; bi++) {
            html += "<div style="font-size:11px;color:var(--text-secondary);padding:2px 0;">• " + bulls[bi] + "</div>";
        }
        if (!bulls.length) html += "<div style="font-size:11px;color:var(--text-muted);">暂无</div>";
        html += "</div>";

        html += "<div style="flex:1;background:rgba(248,81,73,0.06);border-radius:8px;padding:8px;">";
        html += "<div style="font-size:11px;color:var(--red);margin-bottom:4px;">🔴 利空因素</div>";
        for (var bei = 0; bei < bears.length; bei++) {
            html += "<div style="font-size:11px;color:var(--text-secondary);padding:2px 0;">• " + bears[bei] + "</div>";
        }
        if (!bears.length) html += "<div style="font-size:11px;color:var(--text-muted);">暂无</div>";
        html += "</div>";

        html += "</div>";
    }

    // 交易建议
    html += "<div style="display:flex;gap:8px;margin-top:8px;font-size:11px;">";
    html += "<div style="flex:1;text-align:center;padding:6px;background:rgba(255,255,255,0.03);border-radius:6px;">";
    html += "<div style="color:var(--text-muted);">🎯 入场</div>";
    html += "<div style="color:var(--blue);font-weight:600;">" + (llm.suggested_entry || "--") + "</div></div>";
    html += "<div style="flex:1;text-align:center;padding:6px;background:rgba(255,255,255,0.03);border-radius:6px;">";
    html += "<div style="color:var(--text-muted);">🛑 止损</div>";
    html += "<div style="color:var(--red);font-weight:600;">" + (llm.stop_loss || "--") + "</div></div>";
    html += "<div style="flex:1;text-align:center;padding:6px;background:rgba(255,255,255,0.03);border-radius:6px;">";
    html += "<div style="color:var(--text-muted);">🏁 止盈</div>";
    html += "<div style="color:var(--green);font-weight:600;">" + (llm.take_profit || "--") + "</div></div>";
    html += "</div>";

    // 风险与时效
    html += "<div style="display:flex;justify-content:space-between;margin-top:6px;font-size:11px;color:var(--text-muted);">";
    html += "<span>风险: " + risk + "</span>";
    html += "<span>时效: " + (llm.time_horizon || "--") + "</span>";
    html += "<span>延迟: " + (llm.latency_ms ? (llm.latency_ms / 1000).toFixed(1) + "s" : "--") + "</span>";
    html += "</div>";

    // 特殊提醒
    if (llm.special_notes) {
        html += "<div style="margin-top:6px;padding:6px 8px;background:rgba(210,153,29,0.1);border-radius:6px;font-size:11px;color:var(--orange);">⚠️ " + llm.special_notes + "</div>";
    }

    contentEl.innerHTML = html;
}

// Override renderAll to also handle LLM data
var originalRenderAll = renderAll;
renderAll = function(data) {
    originalRenderAll(data);
    // Also render LLM if available
    if (data.llm_combined) {
        renderLLMPanel(data.llm_combined);
        document.getElementById("ai-status").textContent = "DeepSeek ✓";
    }
};
