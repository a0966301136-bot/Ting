# 台股爬蟲分析系統

## 快速開始

### 1. 安裝套件
```bash
pip install -r requirements.txt
```

### 2. 抓取資料並分析
```bash
python main.py
# 或指定股票代號
python main.py 2330 2454 2317
```

### 3. 啟動互動儀表板
```bash
streamlit run app.py
```

## 專案結構
```
stock_analysis/
├── scraper.py          # TWSE 網路爬蟲
├── database.py         # SQLite 資料庫管理
├── analyzer.py         # 技術分析 (MA / RSI / 訊號)
├── app.py              # Streamlit 互動儀表板
├── generate_ppt.py     # 自動產生 PPT
├── main.py             # 主程式 (一鍵執行)
└── requirements.txt
```

## 資料來源
- **台灣證券交易所 (TWSE)**：https://www.twse.com.tw/
- 使用官方公開 API 端點，合法且免費

## 功能說明
| 功能 | 說明 |
|------|------|
| 爬蟲 | 抓取近 6 個月每日 OHLCV 資料 |
| 資料庫 | SQLite 儲存，支援增量更新 |
| MA | MA5 / MA20 / MA60 移動平均線 |
| RSI | 14 日相對強弱指標 |
| 訊號 | 黃金交叉/死亡交叉自動標記 |
| 圖表 | 互動式 K 線 + 均線 + 成交量 + RSI |
