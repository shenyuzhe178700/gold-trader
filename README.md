# Gold Trader - AI Gold Short-Term Trading Analysis

COMEX Gold Futures + DeepSeek AI | Real-time | Long/Short Signals | Mobile Ready

## Public Access

**Frontend:** https://shenyuzhe178700.github.io/gold-trader/

## Quick Start

1. Open the frontend URL above
2. Deploy the backend (see below), then enter the backend URL like `https://xxx.onrender.com`
3. Enter your DeepSeek API Key in the AI panel to enable AI analysis

## Backend Deployment (Render - Free)

### One-Click Deploy
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/shenyuzhe178700/gold-trader)

### Manual Deploy
1. Sign up at [Render.com](https://render.com) (free)
2. New + -> Web Service -> Connect GitHub -> Select `shenyuzhe178700/gold-trader`
3. Build: `pip install -r requirements.txt` | Start: `python app.py`
4. Env Var: `DEEPSEEK_API_KEY` = your DeepSeek key
5. Deploy -> Get URL like `https://gold-trader-xxx.onrender.com`

## Data Sources
Yahoo Finance real-time: COMEX Gold, USD/JPY, DXY, Silver, VIX, US10Y, S&P500, SPDR GLD flows

## Disclaimer
For reference only. Not investment advice.
