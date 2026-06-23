# 🥇 Gold Trader - 黄金短线AI交易分析工具

COMEX黄金期货短线交易（1小时内）多维度分析预测工具。接入实时行情 + DeepSeek AI量化分析，输出做多/做空交易信号。

## 🚀 公网部署（2步，免费）

### 第一步：部署后端到 Render（5分钟）

1. Fork 本仓库到你的 GitHub
2. 打开 [Render.com](https://render.com)，注册免费账号
3. 点击 **New +** → **Web Service** → 连接你的 GitHub 仓库
4. 配置：
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Plan**: Free
5. 在 Environment Variables 中添加：
   - `DEEPSEEK_API_KEY` = 你的 DeepSeek API Key
6. 点击 **Deploy Web Service**
7. 等待部署完成，获得后端地址如 `https://gold-trader-api.onrender.com`

### 第二步：部署前端到 GitHub Pages（2分钟）

1. 进入仓库 Settings → Pages
2. Source 选择 **Deploy from a branch**
3. Branch 选择 `main`，文件夹选择 `/frontend`
4. 保存，等待部署完成
5. 获得前端地址如 `https://你的用户名.github.io/仓库名/`

### 使用

打开 GitHub Pages 地址 → 在"服务器连接"输入框填入 Render 后端地址 → 点击连接

**手机同样打开这个URL即可，无需同一WiFi！**

## 📁 项目结构

```
gold_trading_tool/
├── app.py              # Flask后端 + API
├── data_fetcher.py     # Yahoo Finance直连 + 批量采集
├── indicators.py       # RSI/MACD/布林/KD/ATR/支撑阻力
├── signals.py          # 规则引擎 + 多源关联
├── llm_analyzer.py     # DeepSeek AI量化分析
├── mock_data.py        # 模拟数据回退
├── requirements.txt    # Python依赖
├── render.yaml         # Render部署配置
├── Procfile            # 部署入口
├── templates/          # Flask模板(本地用)
├── static/             # 静态资源(本地用)
├── frontend/           # ✨ GitHub Pages前端
│   ├── index.html      # 独立HTML页面
│   ├── css/style.css   # 暗色交易主题
│   └── js/dashboard.js # 前端逻辑(HTTP轮询)
└── README.md
```

## 🔧 本地运行

```bash
pip install -r requirements.txt
$env:DEEPSEEK_API_KEY="sk-xxx"
python app.py
# 打开 http://localhost:5000
```

## 📡 API接口

| 端点 | 说明 |
|------|------|
| GET `/api/snapshot` | 市场快照（8个标的） |
| GET `/api/analysis` | 完整分析（指标+信号） |
| GET `/api/indicators` | 技术指标面板 |
| GET `/api/signals` | 规则引擎信号 |
| GET `/api/llm/analysis` | DeepSeek AI独立分析 |
| GET `/api/llm/combined` | 规则+AI融合信号 |
| POST `/api/llm/configure` | 配置API Key |
| GET `/api/history/<symbol>` | K线历史数据 |

## ⚠️ 免责声明

本工具仅供分析参考，不构成投资建议。交易有风险，入市需谨慎。
