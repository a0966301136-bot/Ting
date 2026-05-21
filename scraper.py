"""
台灣證券交易所 (TWSE) 股票資料爬蟲
資料來源: https://www.twse.com.tw/exchangeReport/STOCK_DAY
"""

import time
import requests
import pandas as pd
from datetime import datetime, timedelta


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.twse.com.tw/",
}

# 常見台股代號對照
STOCK_NAMES = {
    "2330": "台積電",
    "2317": "鴻海",
    "2454": "聯發科",
    "2412": "中華電",
    "2882": "國泰金",
    "2303": "聯電",
    "2881": "富邦金",
    "1301": "台塑",
    "2002": "中鋼",
    "2886": "兆豐金",
}


def fetch_monthly_data(stock_id: str, year: int, month: int) -> pd.DataFrame:
    """爬取單月股票日成交資訊"""
    date_str = f"{year}{month:02d}01"
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {
        "response": "json",
        "date": date_str,
        "stockNo": stock_id,
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [錯誤] {stock_id} {year}/{month:02d}: {e}")
        return pd.DataFrame()

    if data.get("stat") != "OK" or not data.get("data"):
        print(f"  [無資料] {stock_id} {year}/{month:02d}")
        return pd.DataFrame()

    rows = []
    for item in data["data"]:
        try:
            # TWSE 民國年轉西元
            date_parts = item[0].split("/")
            ad_year = int(date_parts[0]) + 1911
            date = f"{ad_year}-{date_parts[1]}-{date_parts[2]}"

            def to_float(s):
                return float(s.replace(",", "").replace("X", "0")) if s.strip() not in ("", "--") else None

            close = to_float(item[6])
            open_ = to_float(item[3])
            high  = to_float(item[4])
            low   = to_float(item[5])
            vol   = int(item[1].replace(",", "")) if item[1].strip() else 0

            # 漲跌幅
            change_raw = item[7].replace(",", "").strip()
            try:
                change_val = float(change_raw.lstrip("X+-"))
                if "-" in change_raw or "X" in change_raw:
                    change_val = -change_val
            except ValueError:
                change_val = 0.0

            change_pct = round(change_val / close * 100, 2) if close else 0.0

            rows.append({
                "date":       date,
                "open":       open_,
                "high":       high,
                "low":        low,
                "close":      close,
                "volume":     vol,
                "change_pct": change_pct,
            })
        except Exception:
            continue

    return pd.DataFrame(rows)


def fetch_stock_history(stock_id: str, months: int = 6) -> pd.DataFrame:
    """爬取最近 N 個月的股票資料"""
    now = datetime.now()
    all_frames = []

    print(f"[爬蟲] 開始抓取 {stock_id} ({STOCK_NAMES.get(stock_id, '')}) 近 {months} 個月資料")

    for i in range(months - 1, -1, -1):
        target = now - timedelta(days=30 * i)
        y, m = target.year, target.month
        print(f"  -> {y}/{m:02d} ...", end=" ")
        df = fetch_monthly_data(stock_id, y, m)
        if not df.empty:
            all_frames.append(df)
            print(f"取得 {len(df)} 筆")
        else:
            print("無資料")
        time.sleep(0.5)  # 避免頻繁請求被封鎖

    if not all_frames:
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    result = result.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return result


def get_stock_name(stock_id: str) -> str:
    return STOCK_NAMES.get(stock_id, stock_id)
